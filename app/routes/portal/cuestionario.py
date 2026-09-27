"""Rutas del cuestionario previo a la donación."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from app.controllers.portal import cuestionario as ctrl
from app.controllers.sesion import requiere_login, usuario_actual

cuestionario_bp = Blueprint("cuestionario", __name__, url_prefix="/cuestionario")


@cuestionario_bp.get("/<int:id_cita>")
@requiere_login
def responder(id_cita):
    usuario = usuario_actual()
    cita = ctrl.cita_del_donante(id_cita, usuario)
    if cita is None:
        flash("No encontramos esa cita entre las tuyas.", "error")
        return redirect(url_for("mi_cita.ver"))

    # Sin ?seccion= se entra por donde quedó: así el enlace del correo lleva
    # directo al punto exacto, tanto la primera vez como al retomarlo.
    pedida = request.args.get("seccion")
    if pedida not in ctrl.SECCIONES:
        pendiente = ctrl.seccion_pendiente(cita)
        if pendiente is None:
            return render_template("portal/cuestionario/listo.html",
                                   cita=cita, **_resumen(cita))
        return redirect(url_for("cuestionario.responder", id_cita=id_cita,
                                seccion=pendiente))

    return render_template("portal/cuestionario/responder.html",
                           **_paso(cita, pedida))


@cuestionario_bp.post("/<int:id_cita>")
@requiere_login
def guardar(id_cita):
    usuario = usuario_actual()
    cita = ctrl.cita_del_donante(id_cita, usuario)
    if cita is None:
        flash("No encontramos esa cita entre las tuyas.", "error")
        return redirect(url_for("mi_cita.ver"))

    seccion = request.form.get("seccion")
    if seccion not in ctrl.SECCIONES:
        return redirect(url_for("cuestionario.responder", id_cita=id_cita))

    errores = ctrl.guardar_seccion(cita, usuario, seccion, request.form)
    if errores:
        for e in errores[:4]:
            flash(e, "error")
        if len(errores) > 4:
            flash(f"…y {len(errores) - 4} más.", "error")
        return render_template("portal/cuestionario/responder.html",
                               **_paso(cita, seccion, request.form))

    siguiente = ctrl.seccion_pendiente(cita)
    if siguiente is None:
        flash("Cuestionario enviado. Gracias.", "ok")
        return redirect(url_for("cuestionario.responder", id_cita=id_cita))
    return redirect(url_for("cuestionario.responder", id_cita=id_cita,
                            seccion=siguiente))


@cuestionario_bp.get("/<int:id_cita>/respuestas")
@requiere_login
def ver(id_cita):
    """Lo que la persona respondió, para que lo pueda repasar."""
    usuario = usuario_actual()
    cita = ctrl.cita_del_donante(id_cita, usuario)
    if cita is None:
        flash("No encontramos esa cita entre las tuyas.", "error")
        return redirect(url_for("mi_cita.ver"))
    return render_template("portal/cuestionario/listo.html",
                           cita=cita, **_resumen(cita))


# ------------------------------------------------------------- auxiliares
def _paso(cita, seccion, formulario=None):
    indice = ctrl.SECCIONES.index(seccion)
    respondidas, total = ctrl.avance(cita)
    return {
        "cita": cita,
        "seccion": seccion,
        "SECCIONES": ctrl.SECCIONES,
        "paso": indice + 1,
        "pasos": len(ctrl.SECCIONES),
        "preguntas": ctrl.preguntas(seccion),
        "guardadas": ctrl.respuestas(cita),
        "formulario": formulario,
        "respondidas": respondidas,
        "total": total,
    }


def _resumen(cita):
    filas, atencion = ctrl.resumen(cita)
    return {"filas": filas, "atencion": atencion,
            "SECCIONES_LISTA": ctrl.SECCIONES}
