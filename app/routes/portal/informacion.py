"""Pantalla pública de información sobre la donación."""
from flask import Blueprint, render_template

from app.controllers.portal import contenido
from app.models import ContenidoPortal

informacion_bp = Blueprint("informacion", __name__)


@informacion_bp.get("/informacion")
def ver():
    publicados = (ContenidoPortal.query
                  .filter_by(vigente=True)
                  .order_by(ContenidoPortal.id_contenido)
                  .all())
    return render_template("portal/informacion.html",
                           faqs=contenido.FAQS,
                           donaciones=contenido.DONACIONES,
                           publicados=publicados)
