"""La URL histórica redirige al login institucional único."""
from flask import Blueprint, redirect, url_for

jefatura_auth_bp = Blueprint("jefatura_auth", __name__, url_prefix="/jefatura")


@jefatura_auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return redirect(url_for("personal_auth.ingresar"), code=307)
