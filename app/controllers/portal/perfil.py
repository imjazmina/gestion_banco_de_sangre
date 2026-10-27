"""
Perfil del donante: consulta y actualización de sus propios datos.

Lo que el donante puede cambiar es su contacto. El documento no, porque es
lo que lo identifica en el banco de sangre; el grupo sanguíneo tampoco,
porque lo determina el laboratorio a partir de una extracción, no una
declaración del donante.
"""
import calendar
import hashlib
import re
from datetime import date

from sqlalchemy import func

from app.controllers.portal.agenda import diferimiento_vigente
from app.models import (
    db, Usuario, Correo, Telefono, Auditoria, Cita, Solicitud,
    Notificacion, Extraccion, Unidad,
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


def validar(nombre, apellido, correo):
    errores = []
    if not nombre:
        errores.append("Ingresá tu nombre.")
    elif len(nombre) > 80:
        errores.append("El nombre es demasiado largo.")
    if not apellido:
        errores.append("Ingresá tu apellido.")
    elif len(apellido) > 80:
        errores.append("El apellido es demasiado largo.")
    if not _CORREO.match(correo or ""):
        errores.append("Ingresá un correo electrónico válido.")
    elif len(correo) > 120:
        errores.append("El correo es demasiado largo.")
    return errores


def actualizar(usuario, datos):
    """
    Guarda nombre, apellido, correo y teléfono principal en una transacción.

    Lanza ErrorPerfil si el correo ya pertenece a otra cuenta.
    """
    nombre = (datos.get("nombre") or "").strip()
    apellido = (datos.get("apellido") or "").strip()
    correo = (datos.get("correo") or "").strip().lower()
    telefono = (datos.get("telefono") or "").strip()

    errores = validar(nombre, apellido, correo)
    if errores:
        raise ErrorPerfil(errores)

    # uq_correo_direccion es único en toda la tabla, no por usuario: el correo
    # de otra cuenta no se puede reutilizar. Se comprueba acá para dar un
    # mensaje claro en lugar de dejar que explote la restricción.
    ocupado = (Correo.query
               .filter(func.lower(Correo.direccion) == correo,
                       Correo.id_usuario != usuario.id_usuario)
               .first())
    if ocupado:
        raise ErrorPerfil(["Ese correo ya está registrado en otra cuenta."])

    try:
        usuario.nombre = nombre
        usuario.apellido = apellido

        principal = usuario.correo_principal
        if principal:
            principal.direccion = correo
        else:
            db.session.add(Correo(id_usuario=usuario.id_usuario,
                                  direccion=correo, es_principal=True))

        actual = usuario.telefono_principal
        if telefono:
            if actual:
                actual.numero = telefono
            else:
                db.session.add(Telefono(id_usuario=usuario.id_usuario,
                                        numero=telefono, es_principal=True))
        elif actual:
            # Sin número, la fila no tiene sentido: numero es NOT NULL.
            db.session.delete(actual)

        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.MODIFICACION)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _documento_pseudonimo(id_usuario, documento):
    """
    Hash del documento. Incluye el id para que una segunda cuenta, creada
    con la misma cédula y suprimida después, no choque con la clave única.
    """
    materia = f"{id_usuario}:{documento}".encode("utf-8")
    return hashlib.sha256(materia).hexdigest()


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
                   .filter_by(id_solicitante=usuario.id_usuario,
                              estado=Solicitud.PUBLICADA)
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
        for telefono in list(usuario.telefonos):
            db.session.delete(telefono)

        usuario.documento = _documento_pseudonimo(
            usuario.id_usuario, usuario.documento)
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


def resumen(usuario):
    """Datos que muestra la pantalla de perfil."""
    ultima = ultima_donacion(usuario)
    return {
        "usuario": usuario,
        "correo": usuario.correo_principal.direccion if usuario.correo_principal else "",
        "telefono": usuario.telefono_principal.numero if usuario.telefono_principal else "",
        "grupo": usuario.tipo_sangre.etiqueta if usuario.tipo_sangre else None,
        "roles": [r.nombre for r in usuario.roles],
        "ultima_donacion": ultima,
        "donaciones": total_donaciones(usuario),
        "habilitacion": habilitacion(usuario),
        "historial": historial_citas(usuario),
        "intervalo": INTERVALO_MESES.get(usuario.genero, INTERVALO_POR_DEFECTO),
    }
