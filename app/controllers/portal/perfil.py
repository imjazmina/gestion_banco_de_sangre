"""
Perfil del donante: consulta y actualización de sus propios datos.

Lo que el donante puede cambiar es su contacto. El documento no, porque es
lo que lo identifica en el banco de sangre; el grupo sanguíneo tampoco,
porque lo determina el laboratorio a partir de una extracción, no una
declaración del donante.
"""
import re

from sqlalchemy import func

from app.models import db, Usuario, Correo, Telefono, Auditoria

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorPerfil(Exception):
    """Los datos no pasan las validaciones. El mensaje se le muestra al usuario."""


def validar(nombre, apellido, correo):
    errores = []
    if not nombre:
        errores.append("Ingresá tu nombre.")
    elif len(nombre) > 80:
        errores.append("El nombre es demasiado largo.")
    if not apellido:
        errores.append("Ingresá tu apellido.")
    elif len(apellido) > 80:
        errores.append("El apellido es demasiado largo.")
    if not _CORREO.match(correo or ""):
        errores.append("Ingresá un correo electrónico válido.")
    elif len(correo) > 120:
        errores.append("El correo es demasiado largo.")
    return errores


def actualizar(usuario, datos):
    """
    Guarda nombre, apellido, correo y teléfono principal en una transacción.

    Lanza ErrorPerfil si el correo ya pertenece a otra cuenta.
    """
    nombre = (datos.get("nombre") or "").strip()
    apellido = (datos.get("apellido") or "").strip()
    correo = (datos.get("correo") or "").strip().lower()
    telefono = (datos.get("telefono") or "").strip()

    errores = validar(nombre, apellido, correo)
    if errores:
        raise ErrorPerfil(errores)

    # uq_correo_direccion es único en toda la tabla, no por usuario: el correo
    # de otra cuenta no se puede reutilizar. Se comprueba acá para dar un
    # mensaje claro en lugar de dejar que explote la restricción.
    ocupado = (Correo.query
               .filter(func.lower(Correo.direccion) == correo,
                       Correo.id_usuario != usuario.id_usuario)
               .first())
    if ocupado:
        raise ErrorPerfil(["Ese correo ya está registrado en otra cuenta."])

    try:
        usuario.nombre = nombre
        usuario.apellido = apellido

        principal = usuario.correo_principal
        if principal:
            principal.direccion = correo
        else:
            db.session.add(Correo(id_usuario=usuario.id_usuario,
                                  direccion=correo, es_principal=True))

        actual = usuario.telefono_principal
        if telefono:
            if actual:
                actual.numero = telefono
            else:
                db.session.add(Telefono(id_usuario=usuario.id_usuario,
                                        numero=telefono, es_principal=True))
        elif actual:
            # Sin número, la fila no tiene sentido: numero es NOT NULL.
            db.session.delete(actual)

        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.MODIFICACION)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def suprimir_cuenta(usuario):
    """
    Supresión de cuenta (Ley N.º 1682/01).

    No se borra la fila: se anula el acceso y se conserva el rastro clínico,
    que el banco de sangre está obligado a guardar. El CHECK
    ck_usuario_supresion exige que la contraseña quede nula.
    """
    try:
        usuario.cuenta_suprimida = True
        usuario.estado = False
        usuario.contrasena = None

        for correo in usuario.correos:
            db.session.delete(correo)
        for telefono in usuario.telefonos:
            db.session.delete(telefono)

        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.SUPRESION_CUENTA)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def resumen(usuario):
    """Datos que muestra la pantalla de perfil."""
    return {
        "usuario": usuario,
        "correo": usuario.correo_principal.direccion if usuario.correo_principal else "",
        "telefono": usuario.telefono_principal.numero if usuario.telefono_principal else "",
        "grupo": usuario.tipo_sangre.etiqueta if usuario.tipo_sangre else None,
        "roles": [r.nombre for r in usuario.roles],
    }
