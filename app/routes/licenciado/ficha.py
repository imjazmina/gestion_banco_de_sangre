"""Ficha interna del donante."""
from flask import Blueprint, flash, redirect, request, url_for

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
    # `cita` dice desde qué turno se abrió la ficha; `de` desde qué pantalla.
    cita_actual = None
    id_cita = request.args.get("cita", type=int)
    if id_cita is not None:
        cita_actual = jornada.cita_por_id(id_cita)
        if cita_actual is not None and cita_actual.id_usuario != donor_id:
            cita_actual = None
    volver = request.args.get("de", "agendamientos")
    if volver == "inicio":
        volver_url, volver_texto = url_for("licenciado_inicio.inicio"), "Inicio"
    else:
        volver_url, volver_texto = url_for("licenciado_agendamientos.lista"), "Agendamientos"
    return pintar("licenciado/ficha.html", cita_actual=cita_actual,
                  volver_url=volver_url, volver_texto=volver_texto, **datos)
