"""Signos vitales. `apto` lo calcula el trigger de la base."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.licenciado import criterios, jornada
from app.controllers.licenciado.jornada import ErrorJornada

licenciado_evaluacion_bp = Blueprint(
    "licenciado_evaluacion", __name__, url_prefix="/licenciado")


def _siguiente(cita):
    destino = ("licenciado_muestra.ver"
               if cita.tipo_cita == jornada.Cita.MUESTRA
               else "licenciado_extraccion.ver")
    return redirect(url_for(destino, cita_id=cita.id_cita))


@licenciado_evaluacion_bp.route("/atencion/<int:cita_id>/evaluacion", methods=["GET", "POST"])
@requiere("lic", "personal_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    personal = operador_actual()["usuario"]
    valores = {m.tipo.codigo: float(m.valor) for m in jornada.mediciones_de(cita)}
    if request.method == "POST":
        try:
            pares = jornada.valores_del_formulario(request.form)
            valores = {t.codigo: v for t, v in pares}
            todos_aptos = all(
                jornada.fuera_de_rango(t, v) is None for t, v in pares)
            diferir = request.form.get("accion") == "diferir"
            # Fuera de rango sin confirmar: no guardar; el form sigue editable.
            if not diferir and not todos_aptos:
                return _pintar(cita, valores)
            jornada.guardar_mediciones(cita, personal, request.form)
            if todos_aptos:
                return _siguiente(cita)
            jornada.diferir_por_mediciones(cita, personal)
            flash("Evaluación física no superada. Se registró el "
                  "diferimiento y la cita quedó como no apta.", "ok")
            return redirect(url_for("licenciado_ficha.ver",
                                    donor_id=cita.id_usuario, cita=cita.id_cita))
        except ErrorJornada as exc:
            flash(str(exc), "error")
            return redirect(url_for("licenciado_evaluacion.ver", cita_id=cita_id))
    mediciones = jornada.mediciones_de(cita)
    if mediciones and jornada.mediciones_aptas(cita):
        return _siguiente(cita)
    return _pintar(cita, valores)


def _pintar(cita, valores):
    mediciones = jornada.mediciones_de(cita)
    catalogo = {c.nombre: c for c in jornada.causas_de_medicion_posibles()}
    fuera = [{
        "medicion": m,
        "umbral": jornada.fuera_de_rango(m.tipo, float(m.valor)),
        "causa": catalogo.get(nombre),
    } for m, nombre in jornada.mediciones_fuera_de_rango(cita)]
    return pintar(
        "licenciado/evaluacion.html",
        cita=cita,
        tipos=jornada.tipos_medicion(),
        mediciones=mediciones,
        fuera=fuera,
        valores=valores,
        causas_rango=criterios.MEDICION,
        catalogo=catalogo,
    )
