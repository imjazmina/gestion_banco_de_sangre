"""Rutas del perfil del donante."""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)

from app.controllers.portal import perfil as ctrl
from app.controllers.portal import avisos, supresion
from app.controllers.sesion import (requiere_login, usuario_actual,
                                    cerrar_sesion, marcar_en_gracia)

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
    return render_template("portal/perfil/suprimir.html",
                           dias_de_gracia=supresion.DIAS_DE_GRACIA)


@perfil_bp.post("/suprimir")
@requiere_login
def suprimir():
    """
    Pide la baja. No borra nada todavía: arranca el plazo de gracia.

    Se cierra la sesión porque la cuenta queda sin acceso, pero se deja la
    marca de gracia para que la pantalla siguiente pueda mostrar hasta
    cuándo hay tiempo de arrepentirse sin pedir la contraseña de nuevo.
    """
    usuario = usuario_actual()
    try:
        supresion.solicitar(usuario)
    except supresion.ErrorSupresion as e:
        flash(str(e), "error")
        return redirect(url_for("perfil.ver"))

    # El correo se manda después de grabar y su resultado no cambia lo que
    # ve la persona: si el envío falla, el pedido igual quedó registrado y
    # la pantalla siguiente le dice lo mismo que diría el correo.
    avisos.avisar_supresion_solicitada(
        usuario, url_for("auth.ingresar", _external=True))

    cerrar_sesion()
    marcar_en_gracia(usuario)
    return redirect(url_for("auth.cuenta_pendiente"))
