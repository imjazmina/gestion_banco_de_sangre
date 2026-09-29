"""
Sesión del usuario y control de acceso.

En la cookie solo va el id_usuario. Los datos se leen de la base en cada
request: si la cuenta se da de baja, la sesión deja de servir de inmediato
en lugar de seguir andando con una copia vieja.
"""
from functools import wraps

from flask import session, redirect, url_for, flash

from app.models import Usuario


def iniciar_sesion(usuario):
    session.clear()
    session["id_usuario"] = usuario.id_usuario
    session["nombre"] = usuario.nombre


def cerrar_sesion():
    session.clear()


def usuario_actual():
    """El Usuario logueado, o None."""
    id_usuario = session.get("id_usuario")
    if not id_usuario:
        return None
    return (Usuario.query
            .filter_by(id_usuario=id_usuario, estado=True, cuenta_suprimida=False)
            .first())


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
