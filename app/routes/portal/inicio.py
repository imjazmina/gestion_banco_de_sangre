"""Pantalla de entrada del portal."""
from flask import Blueprint, render_template

from app.controllers.portal import contenido, inicio as ctrl
from app.controllers.sesion import usuario_actual

inicio_bp = Blueprint("main", __name__)


@inicio_bp.get("/")
def index():
    usuario = usuario_actual()

    if usuario is None:
        return render_template(
            "portal/home.html",
            usuario=None,
            abierto=contenido.abierto_ahora(),
            faqs=contenido.FAQS[:5],
            solicitudes_activas=ctrl.solicitudes_activas())

    return render_template("portal/inicio.html",
                           usuario=usuario, **ctrl.panel(usuario))
