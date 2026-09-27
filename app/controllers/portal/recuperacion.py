"""
Recuperación de contraseña.

Cómo funciona: se genera un token al azar, se le manda a la persona dentro
de un enlace y en la base queda guardada solo su huella SHA-256. Quien lea
la tabla no puede armar el enlace, igual que pasa con las contraseñas.

Tres reglas que no son adorno:

  - La pantalla responde lo mismo exista o no el correo. Si respondiera
    distinto, cualquiera podría averiguar qué correos están registrados
    probando uno por uno, que es justo lo que evita el login.
  - El enlace vence y sirve una sola vez.
  - Al pedir uno nuevo, los anteriores dejan de servir. Si no, un enlace
    viejo reenviado por error seguiría abriendo la cuenta.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func

from app.controllers.portal.autenticacion import (
    LARGO_MINIMO_CONTRASENA, hashear)
from app.models import db, Auditoria, Correo, RecuperacionContrasena, Usuario

HORAS_VIGENCIA = 2


class ErrorRecuperacion(Exception):
    """El enlace no sirve o la contraseña nueva no pasa las validaciones."""


def _huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    Registra el pedido y devuelve (token, usuario), o None si no hay a quién
    mandarlo.

    Quien llama NO debe usar ese None para cambiar lo que ve la persona: la
    pantalla dice lo mismo en los dos casos. Sirve solo para saber si hay
    que enviar algo.
    """
    usuario = _usuario_por_correo(correo)
    if usuario is None:
        return None

    ahora = datetime.now()

    # Los pedidos abiertos anteriores se dan por usados: queda uno solo vivo.
    (RecuperacionContrasena.query
     .filter(RecuperacionContrasena.id_usuario == usuario.id_usuario,
             RecuperacionContrasena.fecha_uso.is_(None))
     .update({"fecha_uso": ahora}, synchronize_session=False))

    token = secrets.token_urlsafe(32)
    db.session.add(RecuperacionContrasena(
        id_usuario=usuario.id_usuario,
        token_hash=_huella(token),
        fecha_creacion=ahora,
        fecha_expiracion=ahora + timedelta(hours=HORAS_VIGENCIA),
    ))
    db.session.commit()
    return token, usuario


def pedido_vigente(token):
    """El pedido sin usar y sin vencer que corresponde al token, o None."""
    if not token:
        return None
    return (RecuperacionContrasena.query
            .filter(RecuperacionContrasena.token_hash == _huella(token),
                    RecuperacionContrasena.fecha_uso.is_(None),
                    RecuperacionContrasena.fecha_expiracion > datetime.now())
            .first())


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
    Cambia la contraseña y quema el enlace, todo en una transacción.

    Lanza ErrorRecuperacion con la lista de mensajes si algo no cierra.
    """
    pedido = pedido_vigente(token)
    if pedido is None:
        raise ErrorRecuperacion(
            ["El enlace no sirve o ya venció. Pedí uno nuevo."])

    errores = validar_contrasena(contrasena, repetida)
    if errores:
        raise ErrorRecuperacion(errores)

    try:
        usuario = pedido.usuario
        usuario.contrasena = hashear(contrasena)
        pedido.fecha_uso = datetime.now()
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.MODIFICACION)
        db.session.commit()
        return usuario
    except Exception:
        db.session.rollback()
        raise
