"""Atención de la extracción de muestra para compatibilidad."""
import re

from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun.simulacion import agendar_compatibilidad
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada
from app.models import ResultadoCompatibilidad

licenciado_muestra_bp = Blueprint(
    "licenciado_muestra", __name__, url_prefix="/licenciado")

BRAZOS = ("Derecho", "Izquierdo")
PUNCIONES = ("Punción única", "Varias")
REACCIONES = ("Normal", "Lipotimia", "Otras")
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _opcion(formulario, nombre, validos, etiqueta):
    valor = (formulario.get(nombre) or "").strip()
    if valor not in validos:
        raise ErrorJornada(f"Falta {etiqueta}.")
    return valor


def _hora(formulario, nombre, etiqueta):
    valor = (formulario.get(nombre) or "").strip()
    if not _HORA.fullmatch(valor):
        raise ErrorJornada(f"Falta {etiqueta}.")
    return valor


def _observacion(formulario):
    brazo = _opcion(formulario, "brazo", BRAZOS, "el brazo")
    puncion = _opcion(formulario, "puncion", PUNCIONES, "la punción")
    reaccion = _opcion(formulario, "reaccion", REACCIONES, "la reacción")
    inicio = _hora(formulario, "hora_inicio", "la hora de inicio")
    fin = _hora(formulario, "hora_fin", "la hora de finalización")
    if fin < inicio:
        raise ErrorJornada("La hora de finalización es anterior al inicio.")
    return " · ".join((
        f"Brazo: {brazo}",
        f"Punción: {puncion}",
        f"Reacción: {reaccion}",
        f"Inicio: {inicio}",
        f"Fin: {fin}",
        "Muestra: venosa para compatibilidad",
    ))


def _filas(texto):
    campos = {}
    for parte in (texto or "").split(" · "):
        if ": " in parte:
            clave, valor = parte.split(": ", 1)
            campos[clave] = valor
    return [
        ("Brazo", campos.get("Brazo")),
        ("Punción", campos.get("Punción")),
        ("Reacción post-extracción", campos.get("Reacción")),
        ("Hora de inicio", campos.get("Inicio")),
        ("Hora de finalización", campos.get("Fin")),
    ]


@licenciado_muestra_bp.route(
    "/atencion/<int:cita_id>/muestra", methods=["GET", "POST"])
@requiere("lic", "licenciado_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None or cita.tipo_cita != jornada.Cita.MUESTRA:
        flash("No existe esa extracción de muestra.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    personal = operador_actual()["usuario"]
    if request.method == "POST":
        try:
            muestra = jornada.registrar_muestra(
                cita, personal, _observacion(request.form))
            agendar_compatibilidad(muestra.id_muestra)
        except ErrorJornada as exc:
            flash(str(exc), "error")
        return redirect(url_for("licenciado_muestra.ver", cita_id=cita_id))

    extraccion = jornada.extraccion_de(cita)
    muestra = jornada.muestra_de(cita)
    resultado = None
    if muestra is not None:
        resultado = (ResultadoCompatibilidad.query
                     .filter_by(id_muestra=muestra.id_muestra)
                     .first())
    return pintar(
        "licenciado/muestra.html",
        cita=cita,
        apto=jornada.mediciones_aptas(cita),
        extraccion=extraccion,
        muestra=muestra,
        resultado=resultado,
        filas=_filas(extraccion.observacion) if extraccion else [],
        brazos=BRAZOS,
        punciones=PUNCIONES,
        reacciones=REACCIONES,
    )
