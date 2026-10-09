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
        flash(ctrl.motivo_no_habilitado(
            ctrl.cita_para_avisar(id_cita, usuario)), "info")
        return redirect(url_for("mi_cita.ver"))

    if ctrl.completo(cita):
        return render_template("portal/cuestionario/listo.html",
                               cita=cita, **_resumen(cita))

    return render_template("portal/cuestionario/responder.html",
                           **_paso(cita))


@cuestionario_bp.post("/<int:id_cita>")
@requiere_login
def guardar(id_cita):
    usuario = usuario_actual()
    cita = ctrl.cita_del_donante(id_cita, usuario)
    if cita is None:
        flash(ctrl.motivo_no_habilitado(
            ctrl.cita_para_avisar(id_cita, usuario)), "info")
        return redirect(url_for("mi_cita.ver"))

    try:
        ctrl.enviar(cita, usuario, request.form)
    except ctrl.ErrorCuestionario as exc:
        flash(str(exc), "error")
        return render_template(
            "portal/cuestionario/responder.html",
            **_paso(cita, request.form, paso=len(ctrl.SECCIONES)))

    flash("Cuestionario enviado. Tu cita quedó confirmada.", "ok")
    return redirect(url_for("cuestionario.responder", id_cita=id_cita))


@cuestionario_bp.get("/<int:id_cita>/respuestas")
@requiere_login
def ver(id_cita):
    """Lo que la persona respondió, para que lo pueda repasar."""
    usuario = usuario_actual()
    cita = ctrl.cita_del_donante(id_cita, usuario)
    if cita is None:
        flash(ctrl.motivo_no_habilitado(
            ctrl.cita_para_avisar(id_cita, usuario)), "info")
        return redirect(url_for("mi_cita.ver"))
    return render_template("portal/cuestionario/listo.html",
                           cita=cita, **_resumen(cita))


# ------------------------------------------------------------- auxiliares
def _paso(cita, formulario=None, paso=1):
    items = ctrl.preguntas()
    return {
        "cita": cita,
        "SECCIONES": ctrl.SECCIONES,
        "paso": paso,
        "pasos": len(ctrl.SECCIONES),
        "preguntas": items,
        "formulario": formulario,
        "total": len(items),
    }


def _resumen(cita):
    filas, atencion = ctrl.resumen(cita)
    return {"filas": filas, "atencion": atencion}
