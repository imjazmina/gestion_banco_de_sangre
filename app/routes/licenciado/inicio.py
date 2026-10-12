"""Inicio de la jornada de enfermería."""
from datetime import datetime

from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun.informes import vista_previa
from app.controllers.licenciado import jornada
from app.controllers.licenciado.jornada import ErrorJornada
from app.controllers.portal.agenda import diferimiento_vigente

licenciado_inicio_bp = Blueprint("licenciado_inicio", __name__, url_prefix="/licenciado")

COLORES = {
    "Completada": "#059669",
    "Confirmada": "#2563EB",
    "Pendiente": "#2563EB",
    "Ausente": "#D97706",
    "No apto": "#B91C1C",
}


def _contexto(encontrado=None, diferimiento=None):
    citas = jornada.citas_del_dia()
    orden = ["Completada", "Confirmada", "Pendiente", "Ausente", "No apto"]
    ahora = datetime.now().strftime("%H:%M")
    activas = [c for c in citas
               if c.estado in ("Pendiente", "Confirmada")
               and c.horario.hora_inicio.strftime("%H:%M") >= ahora]
    if not activas:
        activas = [c for c in citas if c.estado in ("Pendiente", "Confirmada")]
    return dict(
        resumen=jornada.resumen_estados(citas, orden, COLORES),
        proxima=jornada.fila(activas[0]) if activas else None,
        siguientes=[jornada.fila(c) for c in activas[1:4]],
        previa=vista_previa(),
        encontrado=encontrado,
        diferimiento=diferimiento,
        restriccion=jornada.restriccion_de(diferimiento),
    )


@licenciado_inicio_bp.get("/")
@requiere("lic", "licenciado_auth.ingresar")
def inicio():
    return pintar("licenciado/inicio.html", **_contexto())


@licenciado_inicio_bp.post("/espontaneo")
@requiere("lic", "licenciado_auth.ingresar")
def espontaneo():
    personal = operador_actual()["usuario"]
    documento = request.form.get("documento", "")
    donante = jornada.buscar_donante(documento)
    if donante is None:
        flash("No se encontró ese documento. "
              "No se da de alta una cuenta desde este panel.", "error")
        return redirect(url_for("licenciado_inicio.inicio"))
    if request.form.get("abrir") == "1":
        try:
            cita = jornada.abrir_espontanea(donante, personal)
        except ErrorJornada as exc:
            flash(str(exc), "error")
            return redirect(url_for("licenciado_inicio.inicio"))
        return redirect(url_for("licenciado_ficha.ver",
                                donor_id=donante.id_usuario, cita=cita.id_cita))
    return pintar("licenciado/inicio.html",
                  **_contexto(donante, diferimiento_vigente(donante)))
