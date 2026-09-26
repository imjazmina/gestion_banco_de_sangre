"""
Registro y verificación de credenciales.

Las contraseñas se guardan hasheadas con bcrypt. Nunca en texto plano, ni en
la base ni en los logs: si alguien accede a la base, no obtiene contraseñas.
"""
import re
from datetime import date, datetime

import bcrypt
from sqlalchemy import func

from app.models import db, Usuario, Rol, UsuarioRol, Correo, Telefono, Auditoria

EDAD_MINIMA = 18
EDAD_MAXIMA = 65
LARGO_MINIMO_CONTRASENA = 8

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorRegistro(Exception):
    """Los datos no pasan las validaciones. El mensaje se le muestra al usuario."""


# ------------------------------------------------------------ contraseñas
def hashear(contrasena):
    return bcrypt.hashpw(contrasena.encode("utf-8"),
                         bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar(contrasena, hash_guardado):
    if not hash_guardado:
        return False
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"),
                              hash_guardado.encode("utf-8"))
    except ValueError:
        # Hash ilegible (cargado a mano o truncado). Es un login fallido,
        # no un error del servidor: si se deja escapar, la pantalla de
        # acceso devuelve un 500 en lugar de "datos incorrectos".
        return False


# ------------------------------------------------------------ validación
def calcular_edad(fecha_nacimiento, hoy=None):
    hoy = hoy or date.today()
    años = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        años -= 1
    return años


def validar_registro(datos, contrasena, acepta_privacidad):
    """
    Devuelve la lista de errores. Vacía significa que los datos sirven.

    Esto corre en el servidor aunque el HTML ya valide: el formulario del
    navegador se puede saltear, este control no.
    """
    errores = []

    documento = (datos.get("documento") or "").strip()
    if not documento.isdigit():
        errores.append("El número de documento debe contener solo dígitos.")
    elif not 5 <= len(documento) <= 20:
        errores.append("El número de documento no tiene un largo válido.")

    if not (datos.get("nombre") or "").strip():
        errores.append("Ingresá tu nombre.")
    if not (datos.get("apellido") or "").strip():
        errores.append("Ingresá tu apellido.")

    nacimiento = datos.get("fecha_nacimiento")
    if not nacimiento:
        errores.append("Indicá tu fecha de nacimiento.")
    else:
        try:
            nacimiento = (nacimiento if isinstance(nacimiento, date)
                          else date.fromisoformat(nacimiento))
        except ValueError:
            errores.append("La fecha de nacimiento no es válida.")
        else:
            edad = calcular_edad(nacimiento)
            if edad < EDAD_MINIMA:
                errores.append(f"Para donar hay que tener {EDAD_MINIMA} años o más.")
            elif edad > EDAD_MAXIMA:
                errores.append(
                    f"El registro en línea es para personas de hasta {EDAD_MAXIMA} años. "
                    "Comunicate con el banco de sangre.")

    if datos.get("genero") not in ("Masculino", "Femenino"):
        errores.append("Seleccioná el género.")

    correo = (datos.get("correo") or "").strip().lower()
    if not _CORREO.match(correo):
        errores.append("Ingresá un correo electrónico válido.")

    if len(contrasena or "") < LARGO_MINIMO_CONTRASENA:
        errores.append(
            f"La contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres.")

    if not acepta_privacidad:
        errores.append("Tenés que aceptar la política de privacidad para continuar.")

    return errores


# --------------------------------------------------------------- registro
def registrar_donante(datos, contrasena):
    """
    Da de alta al donante con su rol y sus contactos, en una sola transacción:
    si algo falla, no queda un usuario a medio crear.

    Devuelve el Usuario. Lanza ErrorRegistro si el documento o el correo ya existen.
    """
    documento = datos["documento"].strip()
    correo = datos["correo"].strip().lower()

    if Usuario.query.filter_by(documento=documento).first():
        raise ErrorRegistro("Ya existe una cuenta con ese número de documento.")
    if Correo.query.filter(func.lower(Correo.direccion) == correo).first():
        raise ErrorRegistro("Ese correo ya está registrado.")

    rol_donante = Rol.query.filter_by(codigo=Rol.DONANTE).first()
    if rol_donante is None:
        raise ErrorRegistro(
            "El catálogo de roles está vacío. Ejecutá database/catalogos.sql.")

    nacimiento = datos["fecha_nacimiento"]
    if not isinstance(nacimiento, date):
        nacimiento = date.fromisoformat(nacimiento)

    try:
        usuario = Usuario(
            documento=documento,
            nombre=datos["nombre"].strip(),
            apellido=datos["apellido"].strip(),
            fecha_nacimiento=nacimiento,
            genero=datos["genero"],
            contrasena=hashear(contrasena),
            consentimiento_privacidad=True,
            estado=True,
            cuenta_suprimida=False,
            fecha_alta=datetime.now(),
        )
        db.session.add(usuario)
        # flush, no commit: necesitamos el id_usuario para las filas que
        # dependen de él, pero la transacción sigue abierta.
        db.session.flush()

        db.session.add(UsuarioRol(id_usuario=usuario.id_usuario,
                                  id_rol=rol_donante.id_rol))
        db.session.add(Correo(id_usuario=usuario.id_usuario,
                              direccion=correo, es_principal=True))

        telefono = (datos.get("telefono") or "").strip()
        if telefono:
            db.session.add(Telefono(id_usuario=usuario.id_usuario,
                                    numero=telefono, es_principal=True))

        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.ALTA)
        db.session.commit()
        return usuario
    except Exception:
        db.session.rollback()
        raise


# ----------------------------------------------------------------- acceso
def autenticar(correo, contrasena):
    """
    Devuelve el Usuario si las credenciales sirven, o None.

    Se busca por el correo principal. Una cuenta suprimida o dada de baja no
    entra aunque la contraseña sea correcta.
    """
    correo = (correo or "").strip().lower()
    if not correo or not contrasena:
        return None

    usuario = (Usuario.query
               .join(Correo, Correo.id_usuario == Usuario.id_usuario)
               .filter(func.lower(Correo.direccion) == correo,
                       Correo.es_principal.is_(True))
               .first())

    if usuario is None or not usuario.estado or usuario.cuenta_suprimida:
        return None
    if not verificar(contrasena, usuario.contrasena):
        return None

    Auditoria.registrar(usuario.id_usuario, "USUARIO",
                        usuario.id_usuario, Auditoria.LOGIN)
    db.session.commit()
    return usuario
