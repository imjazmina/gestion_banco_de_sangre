"""Cierra la sesión del personal."""
from flask import Blueprint, redirect, url_for

from app.controllers.comun.acceso import cerrar_panel

licenciado_salir_bp = Blueprint("licenciado_salir", __name__, url_prefix="/licenciado")


@licenciado_salir_bp.get("/salir")
def salir():
    cerrar_panel()
    return redirect(url_for("licenciado_auth.ingresar"))
