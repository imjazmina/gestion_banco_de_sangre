"""La URL histórica redirige al login institucional único."""
from flask import Blueprint, redirect, url_for

licenciado_auth_bp = Blueprint("licenciado_auth", __name__, url_prefix="/licenciado")


@licenciado_auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return redirect(url_for("personal_auth.ingresar"), code=307)
