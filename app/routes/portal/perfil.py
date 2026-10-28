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


def _volver_con_error(error):
    for mensaje in error.args[0]:
        flash(mensaje, "error")
    return redirect(url_for("perfil.ver"))


@perfil_bp.post("/correos")
@requiere_login
def agregar_correo():
    try:
        ctrl.agregar_correo(usuario_actual(), request.form.get("direccion"))
    except ctrl.ErrorPerfil as e:
        return _volver_con_error(e)
    flash("Correo agregado.", "ok")
    return redirect(url_for("perfil.ver"))


@perfil_bp.post("/correos/<int:id_correo>")
@requiere_login
def editar_correo(id_correo):
    try:
        ctrl.editar_correo(usuario_actual(), id_correo, request.form.get("direccion"))
    except ctrl.ErrorPerfil as e:
        return _volver_con_error(e)
    flash("Correo actualizado.", "ok")
    return redirect(url_for("perfil.ver"))


@perfil_bp.post("/correos/<int:id_correo>/principal")
@requiere_login
def principal_correo(id_correo):
    try:
        ctrl.hacer_principal(usuario_actual(), id_correo)
    except ctrl.ErrorPerfil as e:
        return _volver_con_error(e)
    flash("Ese correo quedó como principal. Vas a entrar con él.", "ok")
    return redirect(url_for("perfil.ver"))


@perfil_bp.post("/correos/<int:id_correo>/eliminar")
@requiere_login
def eliminar_correo(id_correo):
    try:
        ctrl.eliminar_correo(usuario_actual(), id_correo)
    except ctrl.ErrorPerfil as e:
        return _volver_con_error(e)
    flash("Correo eliminado.", "ok")
    return redirect(url_for("perfil.ver"))


@perfil_bp.get("/suprimir")
@requiere_login
def confirmar_supresion():
    usuario = usuario_actual()
    operaciones = ctrl.operaciones_abiertas(usuario)
    bloqueada = request.args.get("bloqueada") == "1"
    return render_template(
        "portal/perfil/suprimir.html",
        operaciones=operaciones,
        mostrar_modal=bloqueada and ctrl.hay_operaciones_abiertas(operaciones),
    )


@perfil_bp.post("/suprimir")
@requiere_login
def suprimir():
    try:
        ctrl.suprimir_cuenta(usuario_actual())
    except ctrl.ErrorSupresion:
        return redirect(url_for("perfil.confirmar_supresion", bloqueada=1))
    cerrar_sesion()
    flash("Tu cuenta fue suprimida. Gracias por haber formado parte del portal.", "ok")
    return redirect(url_for("main.index"))
