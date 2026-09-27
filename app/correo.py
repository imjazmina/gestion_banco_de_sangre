"""
Envío de correo.

Habla SMTP común, así que sirve con cualquier proveedor: Gmail, Brevo,
Mailtrap, el que sea. Lo único que cambia son los datos del .env; el código
no se toca.

Si no hay SMTP_HOST configurado, no falla: escribe el correo en la consola.
Eso permite trabajar sin conexión y, sobre todo, que nadie se quede sin
poder levantar el proyecto por no tener credenciales.

    from app.correo import enviar
    enviar("persona@correo.com", "Asunto", "<p>Hola</p>", texto="Hola")
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app


class ErrorCorreo(Exception):
    """No se pudo entregar el correo al servidor SMTP."""


def configurado():
    """¿Hay un servidor de correo cargado en el .env?"""
    return bool(current_app.config.get("SMTP_HOST"))


def enviar(destinatario, asunto, html, texto=None):
    """
    Entrega un correo. Devuelve True si salió por SMTP, False si fue a consola.

    Lanza ErrorCorreo si hay SMTP configurado pero falla. Quien llama decide
    qué hacer: en la recuperación de contraseña, por ejemplo, el fallo no se
    le muestra a la persona, para no delatar si la cuenta existe.
    """
    cfg = current_app.config
    remitente = cfg.get("CORREO_DESDE") or cfg.get("SMTP_USUARIO") or "no-reply@localhost"

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((cfg.get("CORREO_NOMBRE", "Banco de sangre HRL"),
                                  remitente))
    mensaje["To"] = destinatario
    # Los clientes que no muestran HTML leen esta parte. No es un adorno:
    # sin ella, varios filtros marcan el mensaje como spam.
    mensaje.set_content(texto or _a_texto(html))
    mensaje.add_alternative(html, subtype="html")

    if not configurado():
        _a_consola(destinatario, asunto, mensaje.get_body(("plain",)).get_content())
        return False

    try:
        _entregar(cfg, mensaje)
    except Exception as e:
        current_app.logger.error("No se pudo enviar el correo a %s: %s",
                                 destinatario, e)
        raise ErrorCorreo(str(e)) from e

    current_app.logger.info("Correo enviado a %s: %s", destinatario, asunto)
    return True


def _entregar(cfg, mensaje):
    host = cfg["SMTP_HOST"]
    puerto = int(cfg.get("SMTP_PUERTO") or 587)
    usuario = cfg.get("SMTP_USUARIO")
    clave = cfg.get("SMTP_CONTRASENA")
    contexto = ssl.create_default_context()

    # El puerto 465 habla cifrado desde el saludo; el 587 arranca en claro y
    # sube a cifrado con STARTTLS. Son dos formas distintas de conectarse,
    # no una opción: elegir mal da un error que no dice nada útil.
    if puerto == 465:
        with smtplib.SMTP_SSL(host, puerto, context=contexto, timeout=20) as s:
            if usuario:
                s.login(usuario, clave)
            s.send_message(mensaje)
    else:
        with smtplib.SMTP(host, puerto, timeout=20) as s:
            s.ehlo()
            if cfg.get("SMTP_TLS", True):
                s.starttls(context=contexto)
                s.ehlo()
            if usuario:
                s.login(usuario, clave)
            s.send_message(mensaje)


def _a_consola(destinatario, asunto, texto):
    print("\n" + "=" * 66)
    print("CORREO SIN ENVIAR (no hay SMTP configurado en el .env)")
    print(f"Para:   {destinatario}")
    print(f"Asunto: {asunto}")
    print("-" * 66)
    print(texto.strip())
    print("=" * 66 + "\n")


def _a_texto(html):
    """Versión en texto plano, por si quien llama no la escribió."""
    import re
    texto = re.sub(r"<br\s*/?>", "\n", html)
    texto = re.sub(r"</(p|div|h1|h2|h3|tr)>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\n{3,}", "\n\n", texto).strip()
