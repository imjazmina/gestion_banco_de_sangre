"""Pantalla pública de información sobre la donación."""
from flask import Blueprint, render_template

from app.controllers.portal import contenido

informacion_bp = Blueprint("informacion", __name__)


@informacion_bp.get("/informacion")
def ver():
    return render_template("portal/informacion.html",
                           faqs=contenido.FAQS,
                           donaciones=contenido.DONACIONES)
