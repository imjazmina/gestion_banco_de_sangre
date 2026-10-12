"""Cierra la sesión del personal."""
from flask import Blueprint, redirect, url_for

from app.controllers.comun.acceso import cerrar_panel

jefatura_salir_bp = Blueprint("jefatura_salir", __name__, url_prefix="/jefatura")


@jefatura_salir_bp.get("/salir")
def salir():
    cerrar_panel()
    return redirect(url_for("jefatura_auth.ingresar"))
