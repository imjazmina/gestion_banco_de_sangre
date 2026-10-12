"""Agenda del día, leída de `cita`."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada

licenciado_agendamientos_bp = Blueprint(
    "licenciado_agendamientos", __name__, url_prefix="/licenciado")


TIPOS_AGENDAMIENTO = ["Donación", "Extracción de compatibilidad"]
ESTADOS = ["Pendiente", "Confirmada", "Completada", "Ausente", "No apto"]


@licenciado_agendamientos_bp.get("/agendamientos")
@requiere("lic", "licenciado_auth.ingresar")
def lista():
    citas = jornada.pendientes_primero(
        [jornada.fila(c) for c in jornada.citas_del_dia()])
    filtro_tipo = request.args.get("tipo", "")
    filtro_estado = request.args.get("estado", "")
    visibles = [
        c for c in citas
        if (not filtro_tipo or c["tipoAgendamiento"] == filtro_tipo)
        and (not filtro_estado or c["estado"] == filtro_estado)
    ]
    return pintar(
        "licenciado/agendamientos.html",
        citas=visibles,
        tipos=TIPOS_AGENDAMIENTO,
        estados=ESTADOS,
        filtro_tipo=filtro_tipo,
        filtro_estado=filtro_estado,
        total=len(citas),
        pendientes=sum(1 for c in citas if c["estado"] in ("Pendiente", "Confirmada")),
        completadas=sum(1 for c in citas if c["estado"] == "Completada"),
        ausentes=sum(1 for c in citas if c["estado"] == "Ausente"),
        no_aptos=sum(1 for c in citas if c["estado"] == "No apto"),
    )


@licenciado_agendamientos_bp.post("/agendamientos/<int:cita_id>/ausente")
@requiere("lic", "licenciado_auth.ingresar")
def ausente(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    try:
        jornada.marcar_ausente(cita, operador_actual()["usuario"])
    except ErrorJornada as exc:
        flash(str(exc), "error")
    return redirect(url_for("licenciado_agendamientos.lista"))
