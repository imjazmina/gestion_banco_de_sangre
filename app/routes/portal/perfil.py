"""Rutas del perfil del donante."""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)

from app.controllers.portal import perfil as ctrl
from app.controllers.sesion import requiere_login, usuario_actual, cerrar_sesion

perfil_bp = Blueprint("perfil", __name__, url_prefix="/perfil")


@perfil_bp.get("/")
@requiere_login
def ver():
    return render_template("portal/perfil/ver.html",
                           **ctrl.resumen(usuario_actual()),
                           editando=request.args.get("editar") == "1")


@perfil_bp.post("/")
@requiere_login
def guardar():
    usuario = usuario_actual()
    try:
        ctrl.actualizar(usuario, request.form)
    except ctrl.ErrorPerfil as e:
        for mensaje in e.args[0]:
            flash(mensaje, "error")
        return redirect(url_for("perfil.ver", editar=1))

    flash("Tus datos fueron actualizados.", "ok")
    return redirect(url_for("perfil.ver"))


@perfil_bp.get("/suprimir")
@requiere_login
def confirmar_supresion():
    return render_template("portal/perfil/suprimir.html")


@perfil_bp.post("/suprimir")
@requiere_login
def suprimir():
    ctrl.suprimir_cuenta(usuario_actual())
    cerrar_sesion()
    flash("Tu cuenta fue suprimida. Gracias por haber formado parte del portal.", "ok")
    return redirect(url_for("main.index"))
