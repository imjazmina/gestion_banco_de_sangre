"""Rutas de registro, inicio, cierre de sesión y recuperación de contraseña."""
from flask import (Blueprint, current_app, render_template, request, redirect,
                   url_for, flash)

from app import correo
from app.controllers.portal import autenticacion, inicio, recuperacion
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
    """
    Acceso al portal.

    Tiene dos presentaciones del mismo formulario. La normal es la del menú.
    La otra, ?donar=1, es la que abre el botón "Quiero donar": suma al
    costado las razones para donar y los requisitos, porque quien llega por
    ahí todavía no decidió, no viene a entrar a su cuenta.
    """
    if usuario_actual():
        return redirect(url_for("main.index"))

    promocional = request.args.get("donar") == "1"
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

    if promocional:
        return render_template(
            "portal/auth/quiero_donar.html", correo=correo,
            solicitudes_activas=inicio.solicitudes_activas())
    return render_template("portal/auth/ingresar.html", correo=correo)


@auth_bp.get("/salir")
def salir():
    cerrar_sesion()
    return redirect(url_for("main.index"))


# ------------------------------------------------- recuperar contraseña
def _entregar_enlace(direccion, nombre, enlace):
    """
    Manda el enlace por correo. Devuelve True si salió de verdad.

    Si el envío falla no se corta la respuesta ni se le avisa a la persona:
    un error acá contaría que la cuenta existe, que es justo lo que este
    formulario no debe revelar. El problema queda en el log del servidor,
    que es donde se lo puede ver sin filtrarlo a nadie.
    """
    cuerpo = render_template("correos/recuperar.html", nombre=nombre,
                             enlace=enlace, horas=recuperacion.HORAS_VIGENCIA)
    try:
        return correo.enviar(direccion, "Restablecé tu contraseña", cuerpo)
    except correo.ErrorCorreo:
        return False


@auth_bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if usuario_actual():
        return redirect(url_for("perfil.ver"))

    direccion = ""
    if request.method == "POST":
        direccion = request.form.get("correo", "").strip()
        pedido = recuperacion.solicitar(direccion)

        enlace = enviado = None
        if pedido:
            token, usuario = pedido
            enlace = url_for("auth.restablecer", token=token, _external=True)
            enviado = _entregar_enlace(direccion, usuario.nombre, enlace)

        # La misma pantalla exista o no la cuenta: si fueran distintas,
        # este formulario diría qué correos están registrados.
        return render_template(
            "portal/auth/recuperar_enviado.html",
            correo=direccion,
            horas=recuperacion.HORAS_VIGENCIA,
            # El enlace en pantalla es solo para desarrollo, y únicamente
            # cuando no hay correo configurado: si el correo salió de
            # verdad, mostrarlo acá sería una puerta de atrás.
            enlace=enlace if (current_app.debug and enviado is False) else None)

    return render_template("portal/auth/recuperar.html", correo=direccion)


@auth_bp.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer(token):
    if recuperacion.pedido_vigente(token) is None:
        return render_template("portal/auth/enlace_vencido.html"), 410

    if request.method == "POST":
        try:
            recuperacion.restablecer(token,
                                     request.form.get("contrasena", ""),
                                     request.form.get("repetir", ""))
        except recuperacion.ErrorRecuperacion as e:
            for mensaje in e.args[0]:
                flash(mensaje, "error")
            return render_template("portal/auth/restablecer.html", token=token)

        flash("Tu contraseña fue actualizada. Ya podés entrar con la nueva.", "ok")
        return redirect(url_for("auth.ingresar"))

    return render_template("portal/auth/restablecer.html", token=token)
