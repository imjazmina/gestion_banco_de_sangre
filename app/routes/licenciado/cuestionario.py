"""Parte B del cuestionario, en sala."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada
from app.models import RegistroDiferimiento

licenciado_cuestionario_bp = Blueprint(
    "licenciado_cuestionario", __name__, url_prefix="/licenciado")


def _cita_o_volver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
    return cita


@licenciado_cuestionario_bp.get("/atencion/<int:cita_id>/cuestionario")
@requiere("lic", "licenciado_auth.ingresar")
def ver(cita_id):
    cita = _cita_o_volver(cita_id)
    if cita is None:
        return redirect(url_for("licenciado_agendamientos.lista"))
    return pintar(
        "licenciado/cuestionario.html",
        cita=cita,
        preguntas=jornada.preguntas_parte_b(),
        respuestas=jornada.respuestas_de(cita),
        causas=jornada.catalogo_diferimientos(),
        institucion=jornada.INSTITUCION_LOCAL,
    )


@licenciado_cuestionario_bp.post("/atencion/<int:cita_id>/cuestionario")
@requiere("lic", "licenciado_auth.ingresar")
def guardar(cita_id):
    cita = _cita_o_volver(cita_id)
    if cita is None:
        return redirect(url_for("licenciado_agendamientos.lista"))
    personal = operador_actual()["usuario"]
    try:
        if request.form.get("accion") == "diferir":
            jornada.registrar_diferimiento(
                cita, personal,
                request.form.get("id_diferimiento", type=int),
                RegistroDiferimiento.CUESTIONARIO_PERSONAL,
                request.form.get("institucion"),
            )
            flash("La cita quedó como no apta y el diferimiento fue registrado.", "ok")
            return redirect(url_for("licenciado_ficha.ver",
                                    donor_id=cita.id_usuario, cita=cita.id_cita))
        jornada.guardar_parte_b(cita, personal, request.form)
    except ErrorJornada as exc:
        flash(str(exc), "error")
        return redirect(url_for("licenciado_cuestionario.ver", cita_id=cita_id))
    flash("Parte B guardada.", "ok")
    return redirect(url_for("licenciado_evaluacion.ver", cita_id=cita_id))
