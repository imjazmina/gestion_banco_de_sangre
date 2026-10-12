"""Acceso de jefatura. La contraseña se verifica contra la base."""
from flask import Blueprint

from app.controllers.comun.acceso import vista_ingreso

jefatura_auth_bp = Blueprint("jefatura_auth", __name__, url_prefix="/jefatura")


@jefatura_auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return vista_ingreso()
