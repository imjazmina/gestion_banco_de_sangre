"""
Prueba la configuración de correo del .env y dice exactamente qué falla.

    python probar_correo.py                    manda una prueba a SMTP_USUARIO
    python probar_correo.py otra@correo.com    manda la prueba a esa dirección

Existe porque "no me anda el correo" puede ser cinco cosas distintas y el
error que devuelve Python no se entiende. Este script va paso por paso
—conectar, cifrar, autenticar, enviar— y cuando algo se corta dice qué
revisar en lugar de tirar una traza.
"""
import smtplib
import socket
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import Config                          # noqa: E402


def tapado(clave):
    """Muestra la contraseña sin mostrarla: sirve para ver si quedó vacía."""
    if not clave:
        return "(vacía)"
    return f"{clave[:2]}{'·' * (len(clave) - 4)}{clave[-2:]}  ({len(clave)} caracteres)"


def paso(texto):
    print(f"  {texto} ... ", end="", flush=True)


def main():
    cfg = Config
    destino = sys.argv[1] if len(sys.argv) > 1 else cfg.SMTP_USUARIO

    print("\nConfiguración leída del .env")
    print(f"  SMTP_HOST       {cfg.SMTP_HOST or '(vacío)'}")
    print(f"  SMTP_PUERTO     {cfg.SMTP_PUERTO}")
    print(f"  SMTP_USUARIO    {cfg.SMTP_USUARIO or '(vacío)'}")
    print(f"  SMTP_CONTRASENA {tapado(cfg.SMTP_CONTRASENA)}")
    print(f"  SMTP_TLS        {'sí' if cfg.SMTP_TLS else 'no'}")
    print(f"  CORREO_DESDE    {cfg.CORREO_DESDE or '(vacío, se usa SMTP_USUARIO)'}")
    print()

    if not cfg.SMTP_HOST:
        print("SMTP_HOST está vacío.")
        print()
        print("No es un error: así configurado, el portal funciona igual y")
        print("escribe los correos en la consola en lugar de enviarlos.")
        print("Si querés que salgan de verdad, completá los datos en el .env")
        print("(mirá .env.ejemplo, que tiene las instrucciones).")
        return 0

    if not destino:
        print("No sé a quién mandar la prueba.")
        print("Pasá una dirección:  python probar_correo.py tucorreo@gmail.com")
        return 1

    # Sin usuario no hay login, y el servidor recién se queja al final,
    # cuando ya no se entiende qué pasó: contesta "Authentication Required"
    # sobre el remitente, que no es donde está el problema.
    if not cfg.SMTP_USUARIO and cfg.SMTP_HOST not in ("localhost", "127.0.0.1"):
        print("SMTP_USUARIO está vacío.")
        print()
        print("Cargaste el servidor pero no la cuenta, así que no hay con qué")
        print("entrar. Abrí el .env y completá estas tres líneas:")
        print()
        print("  SMTP_USUARIO=tucuenta@gmail.com")
        print("  SMTP_CONTRASENA=las16letrasdelacontraseñadeaplicacion")
        print("  CORREO_DESDE=tucuenta@gmail.com")
        print()
        print("Para abrirlo:  code .env")
        return 1

    # ----------------------------------------------------------- Gmail
    if "gmail" in cfg.SMTP_HOST and cfg.SMTP_CONTRASENA:
        limpia = cfg.SMTP_CONTRASENA.replace(" ", "")
        if len(limpia) != 16:
            print("AVISO: con Gmail, SMTP_CONTRASENA tiene que ser una")
            print(f"contraseña de aplicación de 16 letras. La tuya tiene {len(limpia)}.")
            print("Si pusiste la contraseña con la que entrás a Gmail, no sirve:")
            print("Google la rechaza siempre.\n")
        elif " " in cfg.SMTP_CONTRASENA:
            print("AVISO: la contraseña tiene espacios. Google la muestra en")
            print("grupos de cuatro, pero hay que pegarla sin espacios.\n")

    puerto = int(cfg.SMTP_PUERTO or 587)
    contexto = ssl.create_default_context()

    try:
        paso(f"conectando a {cfg.SMTP_HOST}:{puerto}")
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(cfg.SMTP_HOST, puerto,
                                        context=contexto, timeout=20)
        else:
            servidor = smtplib.SMTP(cfg.SMTP_HOST, puerto, timeout=20)
        print("ok")
    except socket.gaierror:
        print("FALLÓ")
        print(f"\nNo existe el servidor «{cfg.SMTP_HOST}».")
        print("Revisá SMTP_HOST. Para Gmail es exactamente:  smtp.gmail.com")
        return 1
    except (socket.timeout, TimeoutError):
        print("FALLÓ")
        print("\nEl servidor no contestó a tiempo.")
        print("Suele ser el antivirus o el firewall bloqueando el puerto")
        print(f"{puerto}. Probá desactivarlo un momento, o usá el otro puerto")
        print(f"({'587' if puerto == 465 else '465'}) en SMTP_PUERTO.")
        return 1
    except ConnectionRefusedError:
        print("FALLÓ")
        print(f"\nEl servidor rechazó la conexión en el puerto {puerto}.")
        print("Probá con SMTP_PUERTO=587 (o 465 si ya estabas en 587).")
        return 1
    except Exception as e:
        print("FALLÓ")
        print(f"\n{type(e).__name__}: {e}")
        return 1

    try:
        with servidor:
            servidor.ehlo()

            if puerto != 465 and cfg.SMTP_TLS:
                try:
                    paso("activando el cifrado (STARTTLS)")
                    servidor.starttls(context=contexto)
                    servidor.ehlo()
                    print("ok")
                except smtplib.SMTPNotSupportedError:
                    print("FALLÓ")
                    print("\nEste servidor no acepta STARTTLS en este puerto.")
                    print("Probá con SMTP_PUERTO=465, que cifra desde el principio.")
                    return 1

            if cfg.SMTP_USUARIO:
                try:
                    paso(f"entrando como {cfg.SMTP_USUARIO}")
                    servidor.login(cfg.SMTP_USUARIO, cfg.SMTP_CONTRASENA)
                    print("ok")
                except smtplib.SMTPAuthenticationError as e:
                    print("FALLÓ")
                    print(f"\nEl servidor rechazó el usuario o la contraseña.")
                    print(f"Dijo: {e.smtp_code} {e.smtp_error.decode(errors='replace')[:140]}")
                    print()
                    if "gmail" in cfg.SMTP_HOST:
                        print("Con Gmail esto casi siempre es una de tres:")
                        print("  1. Pusiste tu contraseña de Gmail en lugar de una")
                        print("     contraseña de aplicación. No sirve, Google la rechaza.")
                        print("  2. La contraseña de aplicación quedó con espacios.")
                        print("     Google la muestra en 4 grupos; se pega sin espacios.")
                        print("  3. SMTP_USUARIO no es la misma cuenta con la que")
                        print("     generaste la contraseña de aplicación.")
                    return 1

            paso(f"enviando la prueba a {destino}")
            remitente = cfg.CORREO_DESDE or cfg.SMTP_USUARIO
            mensaje = (
                f"From: {cfg.CORREO_NOMBRE} <{remitente}>\r\n"
                f"To: {destino}\r\n"
                f"Subject: Prueba del portal de donantes\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                "Si estás leyendo esto, el envío de correo del portal de\r\n"
                "donantes del Banco de Sangre HRL quedó funcionando.\r\n"
            )
            servidor.sendmail(remitente, [destino], mensaje.encode("utf-8"))
            print("ok")

    except smtplib.SMTPRecipientsRefused:
        print("FALLÓ")
        print(f"\nEl servidor no aceptó la dirección «{destino}».")
        print("Revisá que esté bien escrita.")
        return 1
    except smtplib.SMTPSenderRefused as e:
        print("FALLÓ")
        dijo = e.smtp_error.decode(errors="replace")
        # El rechazo del remitente y la falta de autenticación llegan por el
        # mismo camino. Si se los confunde, uno se pone a revisar
        # CORREO_DESDE cuando el problema era que nunca hubo login.
        if "auth" in dijo.lower():
            print("\nEl servidor pide autenticarse y no encontró con qué.")
            print("Revisá que SMTP_USUARIO y SMTP_CONTRASENA estén cargados")
            print("en el .env. Para abrirlo:  code .env")
        else:
            print(f"\nEl servidor no aceptó el remitente «{cfg.CORREO_DESDE}».")
            print("Con casi todos los proveedores, CORREO_DESDE tiene que ser")
            print("la misma dirección de SMTP_USUARIO.")
        print(f"\nDijo: {dijo[:160]}")
        return 1
    except Exception as e:
        print("FALLÓ")
        print(f"\n{type(e).__name__}: {e}")
        return 1

    print()
    print("=" * 62)
    print(f"LISTO. Revisá la bandeja de {destino}.")
    print("Si no llegó en un minuto, mirá la carpeta de spam.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
