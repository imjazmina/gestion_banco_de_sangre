"""
Sesión del usuario y control de acceso.

En la cookie solo va el id_usuario. Los datos se leen de la base en cada
request: si la cuenta se da de baja, la sesión deja de servir de inmediato
en lugar de seguir andando con una copia vieja.

La sesión vence sola por dos motivos, y el control está acá y no en la
pantalla: `usuario_actual()` es por donde pasan todos los decoradores de
acceso, así que un pedido armado a mano se topa con lo mismo que el
navegador.
"""
from datetime import datetime
from functools import wraps

from flask import session, redirect, url_for, flash

from app.models import Usuario

# Minutos sin actividad después de los cuales hay que volver a entrar. El
# portal se usa desde el celular y en lugares compartidos: media hora es
# suficiente para completar un cuestionario sin apuro, y corta el riesgo
# de que alguien encuentre la sesión abierta.
MINUTOS_INACTIVIDAD = 30

# Tope absoluto, se use o no. Evita que una pestaña que se refresca sola
# mantenga la sesión viva para siempre.
HORAS_MAXIMO = 8


def iniciar_sesion(usuario):
    session.clear()
    session["id_usuario"] = usuario.id_usuario
    session["nombre"] = usuario.nombre
    ahora = datetime.now().timestamp()
    session["inicio"] = ahora
    session["visto"] = ahora


def cerrar_sesion():
    session.clear()


def _vencida(ahora):
    """
    ¿Caducó la sesión? Por inactividad o por el tope absoluto.

    Si falta alguna de las dos marcas, la cookie viene de antes de que esto
    existiera: se la trata como vencida en vez de dejarla pasar.
    """
    inicio = session.get("inicio")
    visto = session.get("visto")
    if inicio is None or visto is None:
        return True
    if ahora - visto > MINUTOS_INACTIVIDAD * 60:
        return True
    return ahora - inicio > HORAS_MAXIMO * 3600


def usuario_actual():
    """El Usuario logueado, o None."""
    id_usuario = session.get("id_usuario")
    if not id_usuario:
        return None

    ahora = datetime.now().timestamp()
    if _vencida(ahora):
        cerrar_sesion()
        # Una sola vez: después de limpiar, la condición de arriba corta
        # antes de volver a entrar acá en el mismo pedido.
        flash("Tu sesión se cerró por inactividad. Ingresá de nuevo.", "info")
        return None

    session["visto"] = ahora
    return (Usuario.query
            .filter_by(id_usuario=id_usuario, estado=True, cuenta_suprimida=False)
            .first())


# --------------------------------------------- cuentas en período de gracia
#
# Quien pidió la baja de su cuenta tiene `estado` en falso, así que
# `usuario_actual()` no lo devuelve y no puede entrar a ninguna pantalla del
# portal: eso es justamente lo que se busca. Pero sí tiene que poder volver
# para cancelar el pedido, y para eso hay una marca aparte.
#
# Va en otra clave a propósito. Si se guardara en "id_usuario", cualquier
# descuido en un decorador dejaría entrar a una cuenta dada de baja; con
# una clave distinta, todo lo que hoy exige sesión sigue exigiéndola, y la
# única pantalla que mira esta marca es la de cuenta pendiente.
CLAVE_GRACIA = "gracia_id"


def marcar_en_gracia(usuario):
    """Deja la marca que habilita solo la pantalla de cuenta pendiente."""
    session.clear()
    session[CLAVE_GRACIA] = usuario.id_usuario
    session["visto"] = datetime.now().timestamp()


def usuario_en_gracia():
    """El Usuario con pedido de baja en curso de esta sesión, o None."""
    id_usuario = session.get(CLAVE_GRACIA)
    if not id_usuario:
        return None

    ahora = datetime.now().timestamp()
    visto = session.get("visto")
    if visto is None or ahora - visto > MINUTOS_INACTIVIDAD * 60:
        cerrar_sesion()
        return None
    session["visto"] = ahora

    from app.controllers.portal.supresion import en_gracia

    usuario = Usuario.query.filter_by(id_usuario=id_usuario).first()
    # Si el pedido ya se canceló o ya se ejecutó, la marca no sirve más.
    return usuario if en_gracia(usuario) else None


def requiere_login(vista):
    """Decorador: la vista solo se ve con sesión iniciada."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            flash("Iniciá sesión para continuar.", "info")
            return redirect(url_for("auth.ingresar"))
        return vista(*args, **kwargs)
    return envoltura


def requiere_rol(*codigos):
    """Decorador: además de sesión, exige uno de los roles indicados."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                flash("Iniciá sesión para continuar.", "info")
                return redirect(url_for("auth.ingresar"))
            if not any(usuario.tiene_rol(c) for c in codigos):
                flash("No tenés permiso para acceder a esa sección.", "error")
                return redirect(url_for("main.index"))
            return vista(*args, **kwargs)
        return envoltura
    return decorador
