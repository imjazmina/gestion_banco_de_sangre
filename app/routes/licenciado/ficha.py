"""Ficha interna del donante."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun.derivacion import ErrorDerivacion, pendientes, registrar
from app.controllers.licenciado import jornada
from app.models import RegistroDiferimiento, db

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
                  volver_url=volver_url, volver_texto=volver_texto,
                  derivables=_derivables(donor_id), **datos)


def _derivables(donor_id):
    registros = (RegistroDiferimiento.query
                 .filter_by(id_donante=donor_id)
                 .order_by(RegistroDiferimiento.id_registro)
                 .all())
    return pendientes(registros)


@licenciado_ficha_bp.post("/ficha/<int:donor_id>/derivar")
@requiere("lic", "licenciado_auth.ingresar")
def derivar(donor_id):
    registro = db.session.get(RegistroDiferimiento, request.form.get("id_registro", type=int))
    if registro is None or registro.id_donante != donor_id:
        flash("Ese diferimiento no es de este donante.", "error")
        return redirect(url_for("licenciado_ficha.ver", donor_id=donor_id))
    try:
        registrar(registro, operador_actual()["usuario"],
                  request.form.get("establecimiento"),
                  request.form.get("motivo"))
        flash("Derivación registrada.", "ok")
    except ErrorDerivacion as exc:
        flash(str(exc), "error")
    return redirect(url_for("licenciado_ficha.ver", donor_id=donor_id))
