"""
Perfil del donante: consulta y actualización de sus propios datos.

Lo que el donante puede cambiar es su contacto. El documento no, porque es
lo que lo identifica en el banco de sangre; el grupo sanguíneo tampoco,
porque lo determina el laboratorio a partir de una extracción, no una
declaración del donante.
"""
import base64
import calendar
import hashlib
import re
import secrets
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.controllers.portal.agenda import diferimiento_vigente
from app.controllers.portal.autenticacion import (
    correo_es_institucional, hashear, verificar)
from app.controllers.portal.recuperacion import validar_contrasena
from app.models import (
    db, Usuario, Correo, Auditoria, Cita, Solicitud, HistorialSolicitud,
    Notificacion, Extraccion, Unidad, Asignacion,
    MuestraCompatibilidad, ResultadoCompatibilidad,
)

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Intervalo mínimo entre donaciones de sangre total. Es el mismo criterio que
# se le anuncia al visitante en el home, así que si cambia uno tiene que
# cambiar el otro.
INTERVALO_MESES = {"Masculino": 3, "Femenino": 4}
INTERVALO_POR_DEFECTO = 4  # el más conservador, si el género no estuviera cargado


class ErrorPerfil(Exception):
    """Los datos no pasan las validaciones. El mensaje se le muestra al usuario."""


class ErrorSupresion(Exception):
    """Hay citas, extracciones o solicitudes abiertas. No se tocó ningún registro."""

    def __init__(self, operaciones):
        self.operaciones = operaciones


def _direccion(texto):
    return (texto or "").strip().lower()


def _error_direccion(direccion):
    if not _CORREO.match(direccion or ""):
        return "Ingresá un correo electrónico válido."
    if len(direccion) > 120:
        return "El correo es demasiado largo."
    return None


def _correo_propio(usuario, id_correo):
    return next((c for c in usuario.correos if c.id_correo == id_correo), None)


def _direccion_ocupada(direccion, id_correo=None):
    """uq_correo_direccion es única en toda la tabla, no por usuario."""
    consulta = Correo.query.filter(func.lower(Correo.direccion) == direccion)
    if id_correo is not None:
        consulta = consulta.filter(Correo.id_correo != id_correo)
    return consulta.first() is not None


def agregar_correo(usuario, direccion):
    """Agrega un correo secundario. El de alta sigue siendo el principal."""
    direccion = _direccion(direccion)
    error = _error_direccion(direccion)
    if error:
        raise ErrorPerfil([error])
    if _direccion_ocupada(direccion) or correo_es_institucional(direccion):
        raise ErrorPerfil(["Ese correo ya está registrado."])

    try:
        fila = Correo(
            id_usuario=usuario.id_usuario,
            direccion=direccion,
            es_principal=not usuario.correos,
        )
        db.session.add(fila)
        db.session.flush()
        Auditoria.registrar(usuario.id_usuario, "CORREO",
                            fila.id_correo, Auditoria.ALTA)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorPerfil(["Ese correo ya está registrado."])
    except Exception:
        db.session.rollback()
        raise


def editar_correo(usuario, id_correo, direccion):
    """Cambia la dirección. Si es la principal, el login pasa a usar la nueva."""
    fila = _correo_propio(usuario, id_correo)
    if fila is None:
        raise ErrorPerfil(["No encontramos ese correo."])

    direccion = _direccion(direccion)
    error = _error_direccion(direccion)
    if error:
        raise ErrorPerfil([error])
    if direccion == fila.direccion:
        return
    if _direccion_ocupada(direccion, fila.id_correo) or correo_es_institucional(direccion):
        raise ErrorPerfil(["Ese correo ya está registrado."])

    try:
        fila.direccion = direccion
        Auditoria.registrar(usuario.id_usuario, "CORREO",
                            fila.id_correo, Auditoria.MODIFICACION)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorPerfil(["Ese correo ya está registrado."])
    except Exception:
        db.session.rollback()
        raise


def hacer_principal(usuario, id_correo):
    """
    Deja un solo principal.

    Primero se apaga el anterior y se hace flush: el índice parcial
    uq_correo_principal no admite dos filas con es_principal a la vez.
    """
    fila = _correo_propio(usuario, id_correo)
    if fila is None:
        raise ErrorPerfil(["No encontramos ese correo."])
    if fila.es_principal:
        return

    try:
        for otro in usuario.correos:
            if otro.es_principal:
                otro.es_principal = False
        db.session.flush()
        fila.es_principal = True
        Auditoria.registrar(usuario.id_usuario, "CORREO",
                            fila.id_correo, Auditoria.MODIFICACION)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorPerfil(["No se pudo cambiar el correo principal. Intentá de nuevo."])
    except Exception:
        db.session.rollback()
        raise


def cambiar_contrasena(usuario, actual, nueva, repetida):
    """Reemplaza el hash. La actual se verifica; la nueva usa las mismas reglas que el alta."""
    if not verificar(actual or "", usuario.contrasena):
        raise ErrorPerfil(["La contraseña actual no es correcta."])

    errores = validar_contrasena(nueva, repetida)
    if errores:
        raise ErrorPerfil(errores)

    try:
        usuario.contrasena = hashear(nueva)
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.MODIFICACION)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def eliminar_correo(usuario, id_correo):
    fila = _correo_propio(usuario, id_correo)
    if fila is None:
        raise ErrorPerfil(["No encontramos ese correo."])
    if len(usuario.correos) <= 1:
        raise ErrorPerfil(["Tenés que conservar al menos un correo."])
    if fila.es_principal:
        raise ErrorPerfil(["Elegí otro correo como principal antes de eliminar este."])

    try:
        Auditoria.registrar(usuario.id_usuario, "CORREO",
                            fila.id_correo, Auditoria.BAJA)
        db.session.delete(fila)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# 16 bytes de sal + digest SHA-256 (32). En base64 ocupan 64 caracteres,
# el largo de usuario.documento.
_SALT_BYTES = 16
_DIGEST_BYTES = 32


def _documento_pseudonimo(documento):
    """
    SHA-256 del documento con sal aleatoria.

    La sal se guarda delante del hash. No entra el id ni ningún otro dato.
    Cada supresión sale distinta, así la clave única no choca si la misma
    cédula vuelve a registrarse.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.sha256(salt + documento.encode("utf-8")).digest()
    return base64.b64encode(salt + digest).decode("ascii")


def verificar_documento(documento, almacenado):
    """True si el documento es el que originó el hash guardado con su sal."""
    if not documento or not almacenado:
        return False
    try:
        crudo = base64.b64decode(almacenado, validate=True)
    except (ValueError, TypeError):
        return False
    if len(crudo) != _SALT_BYTES + _DIGEST_BYTES:
        return False
    salt, digest = crudo[:_SALT_BYTES], crudo[_SALT_BYTES:]
    calculado = hashlib.sha256(salt + documento.encode("utf-8")).digest()
    return secrets.compare_digest(calculado, digest)


def operaciones_abiertas(usuario):
    """
    Citas sin atender, extracciones sin tipificar y solicitudes publicadas.

    La tipificación la carga el laboratorio al salir de «En laboratorio».
    «Registrada» es el instante previo y también queda pendiente.
    """
    citas = (Cita.query
             .filter(Cita.id_usuario == usuario.id_usuario,
                     Cita.estado.in_(Cita.ACTIVAS))
             .all())
    extracciones = (db.session.query(Extraccion, Unidad)
                    .join(Unidad, Unidad.id_extraccion == Extraccion.id_extraccion)
                    .filter(Unidad.id_donante == usuario.id_usuario,
                            Unidad.estado.in_((Unidad.REGISTRADA,
                                               Unidad.EN_LABORATORIO)))
                    .all())
    solicitudes = (Solicitud.query
                   .filter(Solicitud.id_solicitante == usuario.id_usuario,
                           Solicitud.estado.in_(Solicitud.ABIERTAS))
                   .all())
    return {"citas": citas, "extracciones": extracciones,
            "solicitudes": solicitudes}


def hay_operaciones_abiertas(operaciones):
    return bool(operaciones["citas"] or operaciones["extracciones"]
                or operaciones["solicitudes"])


def _quitar_avisos_operativos(usuario):
    """Conserva la citación genérica del resultado reactivo."""
    (Notificacion.query
     .filter(Notificacion.id_usuario == usuario.id_usuario,
             Notificacion.tipo != Notificacion.CITACION_GENERICA)
     .delete(synchronize_session=False))


def suprimir_cuenta(usuario):
    """
    Supresión de cuenta (Ley N.º 1682/01).

    Si hay una cita activa, una extracción sin tipificar o una solicitud
    publicada, no cambia nada. Si no las hay, la fila y el id_usuario quedan:
    de ellos cuelgan extracción, unidad, diferimiento y la citación por
    resultado reactivo. Se borran contacto,
    nombre y credencial. El documento pasa a hash. Fecha de nacimiento,
    género y tipo de sangre se mantienen para las métricas y el rastro
    clínico. El CHECK ck_usuario_supresion exige contraseña nula.
    """
    if usuario.cuenta_suprimida:
        return
    abiertas = operaciones_abiertas(usuario)
    if hay_operaciones_abiertas(abiertas):
        raise ErrorSupresion(abiertas)
    try:
        _quitar_avisos_operativos(usuario)

        for correo in list(usuario.correos):
            db.session.delete(correo)

        usuario.documento = _documento_pseudonimo(usuario.documento)
        usuario.nombre = None
        usuario.apellido = None
        usuario.contrasena = None
        usuario.estado = False
        usuario.cuenta_suprimida = True

        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.SUPRESION_CUENTA)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _sumar_meses(fecha, meses):
    """
    Suma meses de calendario, no días.

    El intervalo entre donaciones se cuenta en meses ("3 meses"), no en 90
    días, y los meses no miden lo mismo. Si el día no existe en el mes destino
    —un 31 de enero más un mes— se recorta al último día de ese mes.
    """
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _completadas(usuario):
    """
    Las citas que terminaron en donación efectiva, de la más reciente a la
    más vieja.

    Se mira el estado de la cita y no la tabla extraccion porque es el estado
    lo que el personal cierra siempre; la extracción la carga después el
    laboratorio y podría no estar todavía.

    El orden se hace en Python: la fecha de la cita se calcula a partir de
    la franja, así que no es una columna por la que se pueda ordenar en SQL.
    """
    citas = (Cita.query
             .filter(Cita.id_usuario == usuario.id_usuario,
                     Cita.estado == Cita.COMPLETADA)
             .all())
    citas = [c for c in citas if c.fecha_cita is not None]
    return sorted(citas, key=lambda c: c.momento, reverse=True)


def ultima_donacion(usuario):
    """La última cita que terminó en donación efectiva, o None."""
    completadas = _completadas(usuario)
    return completadas[0] if completadas else None


def total_donaciones(usuario):
    return (Cita.query
            .filter(Cita.id_usuario == usuario.id_usuario,
                    Cita.estado == Cita.COMPLETADA)
            .count())


def habilitacion(usuario):
    """
    Fecha estimada en la que el donante podría volver a donar (RF30).

    Es orientativa, no una autorización: la aptitud la decide el personal de
    salud el día de la cita con el cuestionario y las mediciones. Acá se
    calcula solo con lo que el portal puede saber —el intervalo mínimo desde
    la última donación y si hay un diferimiento vigente—, y la plantilla lo
    dice con esas palabras para que nadie lea la fecha como un permiso.

    Devuelve un diccionario con:
        apto   : si hoy no hay nada que lo impida
        fecha  : desde cuándo, o None si no se puede estimar
        dias   : cuántos faltan, o None
        motivo : 'sin_donaciones' | 'intervalo' | 'diferimiento' | 'permanente'
    """
    hoy = date.today()

    # El diferimiento manda sobre el intervalo: aunque hayan pasado los meses,
    # con un diferimiento vigente no se puede donar.
    diferimiento = diferimiento_vigente(usuario)
    if diferimiento:
        if diferimiento.fecha_fin is None:
            return {"apto": False, "fecha": None, "dias": None,
                    "motivo": "permanente"}
        return {"apto": False,
                "fecha": diferimiento.fecha_fin,
                "dias": (diferimiento.fecha_fin - hoy).days,
                "motivo": "diferimiento"}

    ultima = ultima_donacion(usuario)
    if ultima is None:
        return {"apto": True, "fecha": None, "dias": None,
                "motivo": "sin_donaciones"}

    meses = INTERVALO_MESES.get(usuario.genero, INTERVALO_POR_DEFECTO)
    fecha = _sumar_meses(ultima.fecha_cita, meses)
    return {"apto": fecha <= hoy,
            "fecha": fecha,
            "dias": max((fecha - hoy).days, 0),
            "motivo": "intervalo"}


def historial_citas(usuario, limite=10):
    """Todas las citas del donante, la más reciente primero."""
    citas = Cita.query.filter(Cita.id_usuario == usuario.id_usuario).all()
    citas = [c for c in citas if c.fecha_cita is not None]
    citas.sort(key=lambda c: (c.momento, c.fecha_hora_creacion), reverse=True)
    return citas[:limite]


def solicitud_con_resultado(usuario):
    """
    La solicitud propia del donante cuyo resultado de laboratorio de
    compatibilidad ya se registró, o None.

    El resultado cuelga de la muestra (muestra_compatibilidad → solicitud).
    Sin ese resultado la tarjeta del perfil no se muestra. Si hubiera más de
    una, se toma la más reciente.
    """
    return (Solicitud.query
            .join(MuestraCompatibilidad,
                  MuestraCompatibilidad.id_solicitud == Solicitud.id_solicitud)
            .join(ResultadoCompatibilidad,
                  ResultadoCompatibilidad.id_muestra
                  == MuestraCompatibilidad.id_muestra)
            .filter(Solicitud.id_solicitante == usuario.id_usuario)
            .order_by(Solicitud.fecha_creacion.desc())
            .first())


def donaciones_recibidas(solicitud):
    """Unidades efectivamente asignadas a la solicitud. Es el historial de
    donaciones recibidas; la revocación no lo toca."""
    if solicitud is None:
        return 0
    return (Asignacion.query
            .filter_by(id_solicitud=solicitud.id_solicitud)
            .count())


def puede_revocar(solicitud):
    """Hay consentimiento vigente que revocar: solo mientras sigue abierta."""
    return (solicitud is not None
            and solicitud.consentimiento_publicacion
            and solicitud.estado in Solicitud.ABIERTAS)


def revocar_consentimiento(usuario):
    """
    Revoca el consentimiento de publicación de la solicitud propia.

    No borra la solicitud ni toca las donaciones ya recibidas: solo retira el
    permiso de publicación. La solicitud pasa a «Revocada» —el estado que
    exige ck_solicitud_publicacion al quedar sin consentimiento— y el cambio
    queda en el historial inmutable. No se puede volver a publicar desde acá.
    """
    solicitud = solicitud_con_resultado(usuario)
    if solicitud is None:
        raise ErrorPerfil(["No encontramos una solicitud para revocar."])
    if solicitud.estado == Solicitud.REVOCADA:
        return
    if not puede_revocar(solicitud):
        raise ErrorPerfil(["Esta solicitud ya no admite revocación."])

    try:
        anterior = solicitud.estado
        solicitud.consentimiento_publicacion = False
        solicitud.estado = Solicitud.REVOCADA
        db.session.add(HistorialSolicitud(
            id_solicitud=solicitud.id_solicitud,
            estado_anterior=anterior,
            estado_nuevo=Solicitud.REVOCADA,
            fecha_hora=datetime.now(),
        ))
        Auditoria.registrar(usuario.id_usuario, "SOLICITUD",
                            solicitud.id_solicitud, Auditoria.CAMBIO_ESTADO)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def resumen(usuario):
    """Datos que muestra la pantalla de perfil."""
    ultima = ultima_donacion(usuario)
    solicitud = solicitud_con_resultado(usuario)
    return {
        "usuario": usuario,
        "correos": sorted(usuario.correos,
                          key=lambda c: (not c.es_principal, c.direccion)),
        "grupo": usuario.tipo_sangre.etiqueta if usuario.tipo_sangre else None,
        "roles": [r.nombre for r in usuario.roles],
        "ultima_donacion": ultima,
        "donaciones": total_donaciones(usuario),
        "habilitacion": habilitacion(usuario),
        "historial": historial_citas(usuario),
        "intervalo": INTERVALO_MESES.get(usuario.genero, INTERVALO_POR_DEFECTO),
        "solicitud": solicitud,
        "donaciones_recibidas": donaciones_recibidas(solicitud),
        "puede_revocar": puede_revocar(solicitud),
        "solicitud_revocada": solicitud is not None
                              and solicitud.estado == Solicitud.REVOCADA,
    }
