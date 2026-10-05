"""Extracción y alta de la unidad."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun.simulacion import ErrorSimulacion, simular_resultado
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada

licenciado_extraccion_bp = Blueprint(
    "licenciado_extraccion", __name__, url_prefix="/licenciado")


@licenciado_extraccion_bp.route("/atencion/<int:cita_id>/extraccion", methods=["GET", "POST"])
@requiere("lic", "licenciado_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    personal = operador_actual()["usuario"]
    if request.method == "POST":
        accion = request.form.get("accion")
        try:
            if accion == "simular":
                unidad = jornada.unidad_de(cita)
                if unidad is None:
                    raise ErrorJornada("Todavía no hay una unidad para simular.")
                simular_resultado(unidad, personal)
                flash("Resultado de laboratorio simulado. No es un análisis real.", "ok")
            else:
                jornada.registrar_extraccion(
                    cita, personal, request.form.get("observacion"))
                flash("Extracción registrada. La unidad quedó en laboratorio.", "ok")
        except (ErrorJornada, ErrorSimulacion) as exc:
            flash(str(exc), "error")
        return redirect(url_for("licenciado_extraccion.ver", cita_id=cita_id))
    return pintar(
        "licenciado/extraccion.html",
        cita=cita,
        apto=jornada.mediciones_aptas(cita),
        extraccion=jornada.extraccion_de(cita),
        unidad=jornada.unidad_de(cita),
    )
