"""Extracción de compatibilidad: misma extracción, otro tipo de cita."""
from flask import Blueprint, redirect, url_for

from app.controllers.comun.acceso import requiere
from app.controllers.licenciado import jornada

licenciado_compatibilidad_bp = Blueprint(
    "licenciado_compatibilidad", __name__, url_prefix="/licenciado")


@licenciado_compatibilidad_bp.route(
    "/atencion/<int:cita_id>/compatibilidad", methods=["GET", "POST"])
@requiere("lic", "licenciado_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None or cita.tipo_cita != jornada.Cita.COMPATIBILIDAD:
        return redirect(url_for("licenciado_extraccion.ver", cita_id=cita_id))
    return redirect(url_for("licenciado_extraccion.ver", cita_id=cita_id), code=307)
