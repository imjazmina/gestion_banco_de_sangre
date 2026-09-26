"""Gestión de la cita vigente: consultar, reprogramar y cancelar."""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.portal import agenda
from app.controllers.sesion import requiere_login, usuario_actual
from app.models import db

mi_cita_bp = Blueprint("mi_cita", __name__, url_prefix="/mi-cita")


@mi_cita_bp.get("/")
@requiere_login
def ver():
    usuario = usuario_actual()
    return render_template(
        "portal/mi_cita.html",
        cita=agenda.cita_vigente(usuario),
        historial=agenda.historial(usuario),
        etiqueta_tipo=agenda.etiqueta_tipo,
        confirmar=request.args.get("confirmar"))


@mi_cita_bp.get("/reprogramar")
@requiere_login
def reprogramar():
    usuario = usuario_actual()
    cita = agenda.cita_vigente(usuario)
    if cita is None:
        flash("No tenés una cita vigente para reprogramar.", "error")
        return redirect(url_for("mi_cita.ver"))

    fecha = agenda.parsear_fecha(request.args.get("fecha"))
    dias = agenda.calendario(fecha)
    franjas = agenda.franjas_de(fecha) if fecha else []
    sin_horarios = bool(fecha) and not any(f["libres"] > 0 for f in franjas)
    horario = agenda.franja_elegida(fecha, request.args.get("horario", type=int))

    return render_template("portal/reprogramar.html",
                           cita=cita, dias=dias, fecha=fecha,
                           franjas=franjas, sin_horarios=sin_horarios,
                           horario=horario,
                           etiqueta_tipo=agenda.etiqueta_tipo)


@mi_cita_bp.post("/reprogramar")
@requiere_login
def reprogramar_confirmar():
    usuario = usuario_actual()
    cita = agenda.cita_vigente(usuario)
    if cita is None:
        flash("No tenés una cita vigente para reprogramar.", "error")
        return redirect(url_for("mi_cita.ver"))

    fecha = agenda.parsear_fecha(request.form.get("fecha"))
    id_horario = request.form.get("horario", type=int)
    if not fecha or not id_horario:
        flash("Elegí una nueva fecha y horario.", "error")
        return redirect(url_for("mi_cita.reprogramar"))

    try:
        agenda.reprogramar(cita, fecha, id_horario)
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(agenda.mensaje_de_error(e), "error")
        return redirect(url_for("mi_cita.reprogramar", fecha=fecha.isoformat()))

    flash("Tu cita fue reprogramada.", "ok")
    return redirect(url_for("mi_cita.ver"))


@mi_cita_bp.post("/cancelar")
@requiere_login
def cancelar():
    usuario = usuario_actual()
    cita = agenda.cita_vigente(usuario)
    if cita is None:
        flash("No tenés una cita vigente para cancelar.", "error")
        return redirect(url_for("mi_cita.ver"))

    try:
        agenda.cancelar(cita)
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(agenda.mensaje_de_error(e), "error")
        return redirect(url_for("mi_cita.ver"))

    flash("Tu cita fue cancelada. Podés agendar una nueva cuando quieras.", "ok")
    return redirect(url_for("mi_cita.ver"))
