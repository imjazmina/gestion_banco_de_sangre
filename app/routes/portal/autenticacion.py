"""Rutas de registro, inicio y cierre de sesión."""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)

from app.controllers.portal import autenticacion
from app.controllers.sesion import (iniciar_sesion, cerrar_sesion,
                                    usuario_actual)

auth_bp = Blueprint("auth", __name__)

CAMPOS = ("documento", "nombre", "apellido", "fecha_nacimiento",
          "genero", "correo", "telefono")


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if usuario_actual():
        return redirect(url_for("main.index"))

    datos = {}
    if request.method == "POST":
        datos = {campo: request.form.get(campo, "").strip() for campo in CAMPOS}
        contrasena = request.form.get("contrasena", "")
        acepta = request.form.get("acepta") == "on"

        errores = autenticacion.validar_registro(datos, contrasena, acepta)
        if errores:
            for e in errores:
                flash(e, "error")
        else:
            try:
                usuario = autenticacion.registrar_donante(datos, contrasena)
            except autenticacion.ErrorRegistro as e:
                flash(str(e), "error")
            else:
                iniciar_sesion(usuario)
                flash("Tu cuenta fue creada correctamente.", "ok")
                return redirect(url_for("main.index"))

    # Se devuelven los datos para no obligar a reescribir todo el formulario
    # cuando falla una sola validación. La contraseña no vuelve nunca.
    return render_template("portal/auth/registro.html", datos=datos)


@auth_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    if usuario_actual():
        return redirect(url_for("main.index"))

    correo = ""
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        usuario = autenticacion.autenticar(correo, request.form.get("contrasena", ""))
        if usuario:
            iniciar_sesion(usuario)
            return redirect(url_for("main.index"))

        # Un solo mensaje para "el correo no existe" y "la contraseña está
        # mal". Si fueran distintos, cualquiera podría averiguar qué correos
        # están registrados probando uno por uno.
        flash("Correo o contraseña incorrectos.", "error")

    return render_template("portal/auth/ingresar.html", correo=correo)


@auth_bp.get("/salir")
def salir():
    cerrar_sesion()
    return redirect(url_for("main.index"))
