"""Ficha interna del donante."""
from flask import Blueprint, flash, redirect, url_for

from app.controllers.comun.acceso import pintar, requiere
from app.controllers.licenciado import jornada

licenciado_ficha_bp = Blueprint("licenciado_ficha", __name__, url_prefix="/licenciado")


@licenciado_ficha_bp.get("/ficha/<int:donor_id>")
@requiere("lic", "licenciado_auth.ingresar")
def ver(donor_id):
    datos = jornada.ficha(donor_id)
    if datos is None:
        flash("No existe ese donante.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    return pintar("licenciado/ficha.html", **datos)
