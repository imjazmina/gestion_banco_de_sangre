"""Login único del personal institucional (jefatura y licenciado).

La URL no pertenece a un rol: tras validar el correo institucional,
el rol de la cuenta elige el inicio. Las pantallas de cada módulo
siguen bajo /jefatura y /licenciado.
"""
from flask import Blueprint

from app.controllers.comun.acceso import vista_ingreso

personal_auth_bp = Blueprint("personal_auth", __name__, url_prefix="/personal")


@personal_auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return vista_ingreso()
