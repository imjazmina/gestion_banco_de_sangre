"""Signos vitales. `apto` lo calcula el trigger de la base."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada
from app.models import RegistroDiferimiento

licenciado_evaluacion_bp = Blueprint(
    "licenciado_evaluacion", __name__, url_prefix="/licenciado")


@licenciado_evaluacion_bp.route("/atencion/<int:cita_id>/evaluacion", methods=["GET", "POST"])
@requiere("lic", "licenciado_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    personal = operador_actual()["usuario"]
    if request.method == "POST":
        try:
            if request.form.get("accion") == "diferir":
                jornada.registrar_diferimiento(
                    cita, personal,
                    request.form.get("id_diferimiento", type=int),
                    RegistroDiferimiento.MEDICION,
                    request.form.get("institucion"),
                )
                flash("Diferimiento registrado. La cita quedó como no apta.", "ok")
                return redirect(url_for("licenciado_ficha.ver",
                                        donor_id=cita.id_usuario, cita=cita.id_cita))
            jornada.guardar_mediciones(cita, personal, request.form)
            flash("Signos registrados. La aptitud de cada medición la calculó el sistema.", "ok")
        except ErrorJornada as exc:
            flash(str(exc), "error")
        return redirect(url_for("licenciado_evaluacion.ver", cita_id=cita_id))
    return pintar(
        "licenciado/evaluacion.html",
        cita=cita,
        tipos=jornada.tipos_medicion(),
        mediciones=jornada.mediciones_de(cita),
        apto=jornada.mediciones_aptas(cita),
        sugeridas=jornada.causas_sugeridas(cita),
        causas=jornada.catalogo_diferimientos(),
        institucion=jornada.INSTITUCION_LOCAL,
    )
