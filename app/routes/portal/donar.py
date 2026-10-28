"""
Agendar una donación.

El avance es por pasos y cada paso viaja en la URL
(?fecha=&horario=&tipo=&solicitud=). Así el botón "atrás" del navegador
funciona, el enlace se puede compartir y no hace falta JavaScript para
mantener el estado. Solo la confirmación final es un POST.
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort)
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.portal import (agenda, avisos, elegibilidad,
                                    solicitudes as ctrl_solicitudes)
from app.controllers.sesion import requiere_login, usuario_actual
from app.models import db

donar_bp = Blueprint("donar", __name__, url_prefix="/donar")


@donar_bp.get("/")
@requiere_login
def agendar():
    usuario = usuario_actual()

    # Una sola cita activa por donante: si ya tiene, se la manda a gestionarla.
    vigente = agenda.cita_vigente(usuario)
    if vigente:
        return render_template("portal/donar.html", ya_tiene_cita=vigente)

    # La misma comprobación que hace agenda.crear() antes de grabar. Acá se
    # usa para avisar de entrada, así la persona no completa los tres pasos
    # para que recién al confirmar le digan que no puede.
    estado = elegibilidad.habilitacion(usuario)
    bloqueo = None if estado["apto"] else estado
    solicitud_abierta = agenda._solicitud_abierta(usuario)

    fecha = agenda.parsear_fecha(request.args.get("fecha"))
    dias = agenda.dias(fecha)

    franjas = agenda.franjas_de(fecha) if fecha else []
    sin_horarios = bool(fecha) and not any(f["libres"] > 0 for f in franjas)

    horario = agenda.franja_elegida(fecha, request.args.get("horario", type=int))

    # La solicitud puede venir de la lista ("Donar para esta persona") o de
    # elegir el tipo solidario y después la persona.
    solicitud = None
    id_solicitud = request.args.get("solicitud", type=int)
    if id_solicitud:
        solicitud = ctrl_solicitudes.por_id(id_solicitud)
        if solicitud and solicitud.id_solicitante == usuario.id_usuario:
            # RN03: no se dona a la propia solicitud.
            solicitud = None
            flash("No podés donar para tu propia solicitud.", "error")

    # Entrar desde una solicitud ya define el tipo: elegir a la persona es
    # elegir donación solidaria. Volver a preguntarlo sería pedir dos veces
    # lo mismo, así que ese paso no se muestra.
    desde_solicitud = solicitud is not None

    tipo = agenda.SOLIDARIA if desde_solicitud else request.args.get("tipo")
    if not desde_solicitud and (tipo not in agenda.TIPOS_VALIDOS or not horario):
        tipo = None
    if tipo not in agenda.NECESITA_SOLICITUD:
        solicitud = None

    # La lista para elegir destinatario solo hace falta cuando se llegó por
    # el tipo; viniendo de la solicitud, ya está elegido.
    disponibles = []
    if tipo in agenda.NECESITA_SOLICITUD and not desde_solicitud:
        disponibles = [s for s in ctrl_solicitudes.activas()
                       if s.id_solicitante != usuario.id_usuario]

    puede_confirmar = bool(
        horario and tipo and (tipo not in agenda.NECESITA_SOLICITUD or solicitud))

    return render_template(
        "portal/donar.html",
        bloqueo=bloqueo,
        PERMANENTE=elegibilidad.PERMANENTE,
        DIFERIMIENTO=elegibilidad.DIFERIMIENTO,
        solicitud_abierta=solicitud_abierta,
        dias=dias, fecha=fecha,
        franjas=franjas, sin_horarios=sin_horarios, horario=horario,
        tipos=agenda.TIPOS, tipo=tipo,
        etiqueta=agenda.etiqueta_tipo(tipo) if tipo else None,
        pide_solicitud=tipo in agenda.NECESITA_SOLICITUD and not desde_solicitud,
        desde_solicitud=desde_solicitud,
        solicitudes=disponibles, solicitud=solicitud,
        preseleccion=solicitud.id_solicitud if solicitud else None,
        puede_confirmar=puede_confirmar)


@donar_bp.post("/")
@requiere_login
def confirmar():
    usuario = usuario_actual()

    # Revalidación antes de escribir: la pantalla ya lo impide, pero el POST
    # se puede armar a mano.
    if agenda.cita_vigente(usuario):
        flash("Ya tenés una cita agendada. Gestionala antes de crear otra.", "error")
        return redirect(url_for("mi_cita.ver"))
    if agenda.diferimiento_vigente(usuario):
        flash("No podés agendar una cita en este momento. "
              "Comunicate con el banco de sangre.", "error")
        return redirect(url_for("donar.agendar"))
    if agenda._solicitud_abierta(usuario):
        flash("No podés agendar mientras tengas una solicitud abierta.", "error")
        return redirect(url_for("donar.agendar"))

    fecha = agenda.parsear_fecha(request.form.get("fecha"))
    id_horario = request.form.get("horario", type=int)
    tipo = request.form.get("tipo")
    id_solicitud = request.form.get("solicitud", type=int) or None

    if not fecha or not id_horario or tipo not in agenda.TIPOS_VALIDOS:
        flash("Faltan datos para confirmar la cita. Volvé a elegir fecha y horario.", "error")
        return redirect(url_for("donar.agendar"))

    if tipo in agenda.NECESITA_SOLICITUD:
        solicitud = ctrl_solicitudes.por_id(id_solicitud) if id_solicitud else None
        if solicitud is None:
            flash("Elegí la persona para la que querés donar.", "error")
            return redirect(url_for("donar.agendar", fecha=fecha.isoformat(),
                                    horario=id_horario, tipo=tipo))
    else:
        id_solicitud = None

    try:
        cita = agenda.crear(usuario, fecha, id_horario, tipo, id_solicitud)
    except (agenda.ErrorAgenda, SQLAlchemyError) as e:
        db.session.rollback()
        flash(agenda.mensaje_de_error(e), "error")
        return redirect(url_for("donar.agendar", fecha=fecha.isoformat(),
                                horario=id_horario, tipo=tipo))

    # La confirmación por correo va acá, con la cita ya grabada: adentro de
    # crear() quedaría tomado el bloqueo de la franja mientras se espera al
    # SMTP. Si el correo falla, la cita sigue confirmada y su aviso en el
    # buzón ya está; solo queda registrado en el log.
    avisos.enviar_confirmacion(cita, request.url_root.rstrip("/"))

    return redirect(url_for("donar.confirmada", id_cita=cita.id_cita))


@donar_bp.get("/confirmada/<int:id_cita>")
@requiere_login
def confirmada(id_cita):
    usuario = usuario_actual()
    from app.models import Cita
    cita = Cita.query.filter_by(id_cita=id_cita, id_usuario=usuario.id_usuario).first()
    if cita is None:
        abort(404)
    return render_template("portal/cita_confirmada.html", cita=cita,
                           etiqueta=agenda.etiqueta_tipo(cita.tipo_cita))
