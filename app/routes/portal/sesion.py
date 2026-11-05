"""Renovación del access. El refresh solo se envía a esta ruta."""
from flask import Blueprint

from app.controllers.sesion import renovar

sesion_bp = Blueprint("sesion_renovacion", __name__)


@sesion_bp.route("/sesion/renovar", methods=["GET", "POST"])
def renovar_sesion():
    return renovar()
