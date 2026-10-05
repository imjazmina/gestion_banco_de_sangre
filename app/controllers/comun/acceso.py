"""Sesión del personal de salud.

Usa la misma cookie que el portal (`id_usuario` en sesion.py). El correo
de ingreso es `perfil_personal.correo_institucional` y la contraseña es el
hash de `usuario`. No hay usuarios de demostración en este archivo.
"""
from functools import wraps

from flask import redirect, render_template, request, url_for
from sqlalchemy import func

from app.controllers.portal.autenticacion import verificar
from app.controllers.sesion import cerrar_sesion, iniciar_sesion, usuario_actual
from app.models import Auditoria, PerfilPersonal, Rol, db


PANELES = {
    Rol.ENFERMERIA: {
        "rol": Rol.ENFERMERIA,
        "titulo": "Lic. Enfermería · HRL",
        "inicio": "licenciado_inicio.inicio",
        "ingresar": "licenciado_auth.ingresar",
        "salir": "licenciado_salir.salir",
    },
    Rol.JEFATURA: {
        "rol": Rol.JEFATURA,
        "titulo": "Jefatura · Banco de Sangre HRL",
        "inicio": "jefatura_inicio.inicio",
        "ingresar": "jefatura_auth.ingresar",
        "salir": "jefatura_salir.salir",
    },
}


def _codigo_panel(usuario):
    """Jefatura gana si la persona tiene los dos roles."""
    if usuario.tiene_rol(Rol.JEFATURA):
        return Rol.JEFATURA
    if usuario.tiene_rol(Rol.ENFERMERIA):
        return Rol.ENFERMERIA
    return None


def operador_actual():
    """Dict para la plantilla, o None si no hay personal con sesión válida."""
    usuario = usuario_actual()
    if usuario is None:
        return None
    codigo = _codigo_panel(usuario)
    if codigo is None:
        return None
    perfil = PerfilPersonal.query.filter_by(id_usuario=usuario.id_usuario).first()
    if perfil is None:
        return None
    meta = PANELES[codigo]
    return {
        "usuario": usuario,
        "id_usuario": usuario.id_usuario,
        "email": perfil.correo_institucional,
        "nombre": usuario.nombre_completo,
        "iniciales": (usuario.nombre[:1] + usuario.apellido[:1]).upper(),
        **meta,
    }


def intentar_ingreso(email, contrasena):
    """Devuelve (operador, error). El operador queda con la sesión iniciada."""
    email = (email or "").strip().lower()
    if not email or not contrasena:
        return None, "Ingrese correo y contraseña institucional."

    perfil = (PerfilPersonal.query
              .filter(func.lower(PerfilPersonal.correo_institucional) == email)
              .first())
    if perfil is None:
        return None, "Correo o contraseña incorrectos."

    usuario = perfil.usuario
    if (usuario is None or not usuario.estado or usuario.cuenta_suprimida
            or not verificar(contrasena, usuario.contrasena)):
        return None, "Correo o contraseña incorrectos."
    if _codigo_panel(usuario) is None:
        return None, "Este acceso es solo para enfermería o jefatura."

    Auditoria.registrar(usuario.id_usuario, "USUARIO",
                        usuario.id_usuario, Auditoria.LOGIN)
    db.session.commit()
    iniciar_sesion(usuario)
    return operador_actual(), None


def cerrar_panel():
    cerrar_sesion()


_ALIAS_ROL = {"lic": Rol.ENFERMERIA, "jef": Rol.JEFATURA}


def requiere(rol, ingresar_endpoint):
    """Deja pasar solo el rol del módulo. El otro vuelve a su inicio."""
    codigo = _ALIAS_ROL.get(rol, rol)

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            operador = operador_actual()
            if operador is None:
                return redirect(url_for(ingresar_endpoint))
            if operador["rol"] != codigo:
                return redirect(url_for(operador["inicio"]))
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def vista_ingreso():
    """Login compartido. El rol de la cuenta decide el inicio, no la URL."""
    if request.method == "POST":
        email = request.form.get("email", "")
        meta, error = intentar_ingreso(email, request.form.get("contrasena", ""))
        if meta:
            return redirect(url_for(meta["inicio"]))
        return pintar(
            "comun/auth/ingresar.html",
            error=error, email=email, operador=None,
        )
    operador = operador_actual()
    if operador:
        return redirect(url_for(operador["inicio"]))
    return pintar("comun/auth/ingresar.html", error=None, email="", operador=None)


def pintar(plantilla, **contexto):
    contexto.setdefault("operador", operador_actual())
    return render_template(plantilla, **contexto)
