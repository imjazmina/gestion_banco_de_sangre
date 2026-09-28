"""
Recuperación de contraseña, sin guardar nada.

El enlace no se apoya en ninguna tabla: lleva un token firmado con la
SECRET_KEY del proyecto. Quien recibe el enlace no puede fabricar otro
—no tiene la clave— y el servidor no necesita recordar cuáles entregó.

Cómo se consiguen las tres garantías que hacen falta:

  * **Vence.** La firma lleva la hora en que se emitió y se rechaza pasadas
    HORAS_VIGENCIA.
  * **Sirve una sola vez.** La firma se calcula con el hash actual de la
    contraseña metido en la sal. Al cambiarla, el hash cambia, y todas las
    firmas hechas con el anterior dejan de validar. No hace falta marcar
    nada como usado: el propio cambio lo invalida.
  * **No delata cuentas.** La pantalla responde lo mismo exista o no el
    correo. Si respondiera distinto, cualquiera podría averiguar qué correos
    están registrados probando uno por uno, que es justo lo que evita el
    login.

Lo que se pierde frente a guardar los tokens en una tabla: pedir un enlace
nuevo no apaga el anterior. Los dos valen hasta que uno se use o venzan.
Queda anotado porque es una diferencia real, no un detalle.
"""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func

from app.controllers.portal.autenticacion import (
    LARGO_MINIMO_CONTRASENA, hashear)
from app.models import db, Auditoria, Correo, Usuario

HORAS_VIGENCIA = 2
_PROPOSITO = "recuperar-contrasena"


class ErrorRecuperacion(Exception):
    """El enlace no sirve o la contraseña nueva no pasa las validaciones."""


def _firmador(usuario):
    """
    El firmador de este usuario, atado a su contraseña actual.

    El hash va en la sal, no en el contenido del token: así no viaja en el
    enlace y aun así cualquier firma hecha con el hash viejo deja de
    validar apenas la contraseña cambia.
    """
    return URLSafeTimedSerializer(
        secret_key=current_app.config["SECRET_KEY"],
        salt=f"{_PROPOSITO}:{usuario.contrasena or ''}")


def _usuario_por_correo(correo):
    correo = (correo or "").strip().lower()
    if not correo:
        return None
    usuario = (Usuario.query
               .join(Correo, Correo.id_usuario == Usuario.id_usuario)
               .filter(func.lower(Correo.direccion) == correo,
                       Correo.es_principal.is_(True))
               .first())
    if usuario is None or not usuario.estado or usuario.cuenta_suprimida:
        return None
    return usuario


def solicitar(correo):
    """
    Devuelve (token, usuario) para armar el enlace, o None si no hay a quién
    mandárselo.

    Quien llama NO debe usar ese None para cambiar lo que ve la persona: la
    pantalla dice lo mismo en los dos casos. Sirve solo para saber si hay
    que enviar algo.
    """
    usuario = _usuario_por_correo(correo)
    if usuario is None:
        return None
    if not usuario.contrasena:
        # Cuenta sin contraseña: no hay nada que restablecer y además la
        # sal quedaría vacía, que es una firma más débil.
        return None
    return _firmador(usuario).dumps(usuario.id_usuario), usuario


def usuario_del_token(token):
    """
    El usuario al que corresponde el enlace, o None si no sirve.

    El token no se puede abrir sin saber de quién es, porque la sal depende
    de su contraseña. Se lee primero el identificador sin comprobar la
    firma, se busca al usuario, y recién ahí se valida de verdad. Leer sin
    validar no autoriza nada: si la firma no cierra, la función devuelve
    None igual.
    """
    if not token:
        return None
    try:
        sin_verificar = URLSafeTimedSerializer(
            current_app.config["SECRET_KEY"]).loads_unsafe(token)[1]
    except Exception:
        return None
    if not isinstance(sin_verificar, int):
        return None

    usuario = Usuario.query.filter_by(id_usuario=sin_verificar,
                                      estado=True,
                                      cuenta_suprimida=False).first()
    if usuario is None or not usuario.contrasena:
        return None

    try:
        confirmado = _firmador(usuario).loads(
            token, max_age=HORAS_VIGENCIA * 3600)
    except (BadSignature, SignatureExpired):
        return None
    return usuario if confirmado == usuario.id_usuario else None


def validar_contrasena(contrasena, repetida):
    errores = []
    if len(contrasena or "") < LARGO_MINIMO_CONTRASENA:
        errores.append(
            f"La contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres.")
    if contrasena != repetida:
        errores.append("Las dos contraseñas no coinciden.")
    return errores


def restablecer(token, contrasena, repetida):
    """
    Cambia la contraseña. Al cambiarla, el enlace deja de valer solo.

    Lanza ErrorRecuperacion con la lista de mensajes si algo no cierra.
    """
    usuario = usuario_del_token(token)
    if usuario is None:
        raise ErrorRecuperacion(
            ["El enlace no sirve o ya venció. Pedí uno nuevo."])

    errores = validar_contrasena(contrasena, repetida)
    if errores:
        raise ErrorRecuperacion(errores)

    try:
        usuario.contrasena = hashear(contrasena)
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.MODIFICACION)
        db.session.commit()
        return usuario
    except Exception:
        db.session.rollback()
        raise
