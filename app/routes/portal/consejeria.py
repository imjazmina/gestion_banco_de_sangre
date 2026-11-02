"""El donante consulta el cupo, agenda, reprograma y cancela su consejería."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.portal import consejeria
from app.controllers.sesion import requiere_login, usuario_actual
from app.models import db

consejeria_bp = Blueprint("consejeria", __name__, url_prefix="/consejeria")


def _pantalla(usuario, id_resultado=None, id_citacion=None, muestra=False):
    fecha = consejeria.parsear_fecha(request.args.get("fecha"))
    excepto = id_citacion
    dias = consejeria.dias(fecha, excepto_id=excepto)
    franjas = consejeria.franjas_de(fecha, excepto) if fecha else []
    sin_horarios = bool(fecha) and not any(f["libres"] > 0 for f in franjas)
    horario = consejeria.franja_elegida(
        fecha, request.args.get("horario", type=int), excepto)
    return render_template(
        "portal/consejeria.html",
        pares=consejeria.casos(usuario),
        id_resultado=id_resultado,
        id_citacion=id_citacion,
        muestra=muestra,
        dias=dias,
        fecha=fecha,
        franjas=franjas,
        sin_horarios=sin_horarios,
        horario=horario,
        hoy=date.today(),
    )


@consejeria_bp.get("/")
@requiere_login
def ver():
    return _pantalla(usuario_actual())


@consejeria_bp.get("/agendar/<int:id_resultado>")
@requiere_login
def agendar(id_resultado):
    usuario = usuario_actual()
    resultado, citacion = consejeria.caso_de(usuario, id_resultado, muestra=False)
    if resultado is None:
        flash("No tenés esa consejería.", "error")
        return redirect(url_for("consejeria.ver"))
    if citacion is not None and citacion.estado not in (
            None, citacion.CANCELADA):
        if citacion.estado in citacion.ABIERTAS:
            flash("Esa consejería ya tiene una cita.", "error")
        else:
            flash("Esa consejería ya fue cerrada.", "error")
        return redirect(url_for("consejeria.ver"))
    return _pantalla(usuario, id_resultado=id_resultado)


@consejeria_bp.post("/agendar/<int:id_resultado>")
@requiere_login
def agendar_confirmar(id_resultado):
    usuario = usuario_actual()
    fecha = consejeria.parsear_fecha(request.form.get("fecha"))
    id_horario = request.form.get("horario", type=int)
    if not fecha or not id_horario:
        flash("Elegí una fecha y un horario.", "error")
        return redirect(url_for("consejeria.agendar", id_resultado=id_resultado))
    try:
        consejeria.agendar(usuario, id_resultado, fecha, id_horario, muestra=False)
    except (consejeria.ErrorConsejeria, consejeria.ErrorAgenda, SQLAlchemyError) as exc:
        db.session.rollback()
        flash(consejeria.mensaje_de_error(exc), "error")
        return redirect(url_for("consejeria.agendar", id_resultado=id_resultado,
                                fecha=fecha.isoformat()))
    flash("Tu consejería quedó agendada.", "ok")
    return redirect(url_for("consejeria.ver"))


@consejeria_bp.get("/agendar/muestra/<int:id_resultado>")
@requiere_login
def agendar_muestra(id_resultado):
    usuario = usuario_actual()
    resultado, citacion = consejeria.caso_de(usuario, id_resultado, muestra=True)
    if resultado is None:
        flash("No tenés esa consejería.", "error")
        return redirect(url_for("consejeria.ver"))
    if citacion is not None and citacion.estado not in (None, citacion.CANCELADA):
        flash("Esa consejería ya tiene una cita." if citacion.estado in citacion.ABIERTAS
              else "Esa consejería ya fue cerrada.", "error")
        return redirect(url_for("consejeria.ver"))
    return _pantalla(usuario, id_resultado=id_resultado, muestra=True)


@consejeria_bp.post("/agendar/muestra/<int:id_resultado>")
@requiere_login
def agendar_muestra_confirmar(id_resultado):
    usuario = usuario_actual()
    fecha = consejeria.parsear_fecha(request.form.get("fecha"))
    id_horario = request.form.get("horario", type=int)
    if not fecha or not id_horario:
        flash("Elegí una fecha y un horario.", "error")
        return redirect(url_for("consejeria.agendar_muestra", id_resultado=id_resultado))
    try:
        consejeria.agendar(usuario, id_resultado, fecha, id_horario, muestra=True)
    except (consejeria.ErrorConsejeria, consejeria.ErrorAgenda, SQLAlchemyError) as exc:
        db.session.rollback()
        flash(consejeria.mensaje_de_error(exc), "error")
        return redirect(url_for("consejeria.agendar_muestra", id_resultado=id_resultado,
                                fecha=fecha.isoformat()))
    flash("Tu consejería quedó agendada.", "ok")
    return redirect(url_for("consejeria.ver"))


@consejeria_bp.get("/reprogramar/<int:id_citacion>")
@requiere_login
def reprogramar(id_citacion):
    usuario = usuario_actual()
    citacion = consejeria.citacion_de(usuario, id_citacion)
    if citacion is None or citacion.estado != citacion.PENDIENTE:
        flash("Esa consejería no se puede reprogramar.", "error")
        return redirect(url_for("consejeria.ver"))
    return _pantalla(usuario, id_citacion=id_citacion)


@consejeria_bp.post("/reprogramar/<int:id_citacion>")
@requiere_login
def reprogramar_confirmar(id_citacion):
    usuario = usuario_actual()
    citacion = consejeria.citacion_de(usuario, id_citacion)
    if citacion is None:
        flash("No encontramos esa consejería.", "error")
        return redirect(url_for("consejeria.ver"))
    fecha = consejeria.parsear_fecha(request.form.get("fecha"))
    id_horario = request.form.get("horario", type=int)
    if not fecha or not id_horario:
        flash("Elegí una fecha y un horario.", "error")
        return redirect(url_for("consejeria.reprogramar", id_citacion=id_citacion))
    try:
        consejeria.reprogramar(citacion, usuario, fecha, id_horario)
    except (consejeria.ErrorConsejeria, consejeria.ErrorAgenda, SQLAlchemyError) as exc:
        db.session.rollback()
        flash(consejeria.mensaje_de_error(exc), "error")
        return redirect(url_for("consejeria.reprogramar", id_citacion=id_citacion,
                                fecha=fecha.isoformat()))
    flash("Tu consejería fue reprogramada.", "ok")
    return redirect(url_for("consejeria.ver"))


@consejeria_bp.post("/confirmar/<int:id_citacion>")
@requiere_login
def confirmar(id_citacion):
    usuario = usuario_actual()
    citacion = consejeria.citacion_de(usuario, id_citacion)
    if citacion is None:
        flash("No encontramos esa consejería.", "error")
        return redirect(url_for("consejeria.ver"))
    try:
        consejeria.confirmar(citacion, usuario)
    except (consejeria.ErrorConsejeria, consejeria.ErrorAgenda, SQLAlchemyError) as exc:
        db.session.rollback()
        flash(consejeria.mensaje_de_error(exc), "error")
        return redirect(url_for("consejeria.ver"))
    flash("Confirmaste tu consejería.", "ok")
    return redirect(url_for("consejeria.ver"))


@consejeria_bp.post("/cancelar/<int:id_citacion>")
@requiere_login
def cancelar(id_citacion):
    usuario = usuario_actual()
    citacion = consejeria.citacion_de(usuario, id_citacion)
    if citacion is None:
        flash("No encontramos esa consejería.", "error")
        return redirect(url_for("consejeria.ver"))
    try:
        consejeria.cancelar(citacion, usuario)
    except (consejeria.ErrorConsejeria, consejeria.ErrorAgenda, SQLAlchemyError) as exc:
        db.session.rollback()
        flash(consejeria.mensaje_de_error(exc), "error")
        return redirect(url_for("consejeria.ver"))
    flash("Tu consejería fue cancelada. Podés volver a agendarla.", "ok")
    return redirect(url_for("consejeria.ver"))
