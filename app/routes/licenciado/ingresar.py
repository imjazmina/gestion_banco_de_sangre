"""Acceso de enfermería. La contraseña se verifica contra la base."""
from flask import Blueprint

from app.controllers.comun.acceso import vista_ingreso

licenciado_auth_bp = Blueprint("licenciado_auth", __name__, url_prefix="/licenciado")


@licenciado_auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return vista_ingreso()
