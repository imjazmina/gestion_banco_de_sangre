"""
¿Esta persona puede donar hoy? (RF09, RF16)

Hay una sola respuesta a esa pregunta y vive acá. Antes la regla estaba en
perfil.py, que solo la usaba para mostrar una fecha orientativa, mientras
que la agenda dejaba reservar igual: el portal anunciaba «tu próxima
donación habilitada es el 15 de marzo» y aceptaba una cita para mañana.

Este módulo no importa de agenda.py ni de perfil.py, justamente para que
los dos puedan importar de él. `diferimiento_vigente` se movió para acá y
agenda.py lo vuelve a exportar, así el panel de enfermería sigue
importándolo de donde siempre.

Dos reglas, y una manda sobre la otra:

  * El diferimiento lo decide el personal de salud. Mientras esté vigente
    no se dona, hayan pasado los meses que hayan pasado.
  * El intervalo mínimo desde la última donación efectiva, que depende del
    sexo (protocolo PNS). Se cuenta desde la fecha de la extracción, que es
    cuándo la persona efectivamente donó.

Lo que se calcula acá es orientativo para el donante y bloqueante para la
reserva, pero no es una autorización: la aptitud la determina el personal
el día de la cita, con el cuestionario y las mediciones.
"""
import calendar
from datetime import date

from app.models import Cita, Extraccion, RegistroDiferimiento, db

# Intervalo mínimo entre donaciones de sangre total, en meses. Es el mismo
# criterio que se le anuncia al visitante en el home: si cambia uno, tiene
# que cambiar el otro.
INTERVALO_MESES = {"Masculino": 3, "Femenino": 4}

# El más conservador, por si el género no estuviera cargado.
INTERVALO_POR_DEFECTO = 4

# Motivos que devuelve habilitacion(), para que quien la llame no tenga que
# comparar contra textos sueltos.
SIN_DONACIONES = "sin_donaciones"
INTERVALO = "intervalo"
DIFERIMIENTO = "diferimiento"
PERMANENTE = "permanente"


def diferimiento_vigente(usuario):
    """
    El diferimiento activo del donante, o None.

    Nunca se muestra la causa clínica en el portal: solo que hay una
    condición registrada y, si corresponde, hasta cuándo.
    """
    return (RegistroDiferimiento.query
            .filter(RegistroDiferimiento.id_donante == usuario.id_usuario,
                    (RegistroDiferimiento.fecha_fin.is_(None)) |
                    (RegistroDiferimiento.fecha_fin > date.today()))
            .order_by(RegistroDiferimiento.fecha_inicio.desc())
            .first())


def fechas_de_donacion(usuario):
    """
    Las fechas en que esta persona donó, de la más reciente a la más vieja.

    La fecha sale de `extraccion.fecha`, que es cuándo se le extrajo sangre
    de verdad. La de la cita no sirve para esto: `Cita.fecha_cita` no es una
    columna sino una cuenta a partir de la franja horaria y de cuándo se
    reservó, o sea qué día *caía* ese turno. Si la persona vino otro día, o
    si el turno se reprogramó, el intervalo se contaría desde una fecha que
    nunca pasó.

    Toda cita completada tiene su extracción: `registrar_extraccion()` es el
    único lugar del sistema que escribe el estado Completada, y lo hace en
    la misma transacción que crea la extracción. Aun así el LEFT JOIN deja
    el respaldo por la cita, para un dato viejo o cargado a mano en la base:
    sin él, una cita completada sin extracción desaparecería de la cuenta y
    el intervalo se reiniciaría solo.

    Las extracciones de compatibilidad cuentan como donación, porque lo son:
    van por la misma extracción que cualquier otra y generan una unidad de
    sangre total. Al donante le corresponde el mismo descanso.
    """
    filas = (db.session.query(Cita, Extraccion.fecha)
             .outerjoin(Extraccion, Extraccion.id_cita == Cita.id_cita)
             .filter(Cita.id_usuario == usuario.id_usuario,
                     Cita.estado == Cita.COMPLETADA)
             .all())

    fechas = []
    for cita, fecha_extraccion in filas:
        if fecha_extraccion is not None:
            fechas.append(fecha_extraccion.date())
        elif cita.fecha_cita is not None:
            fechas.append(cita.fecha_cita)
    return sorted(fechas, reverse=True)


def ultima_donacion(usuario):
    """
    La fecha de la última donación efectiva, o None.

    Devuelve una fecha, no la cita: lo que importa de acá en adelante es
    cuándo se extrajo, y la cita ya no es de donde sale ese dato.
    """
    fechas = fechas_de_donacion(usuario)
    return fechas[0] if fechas else None


def sumar_meses(fecha, meses):
    """
    Suma meses de calendario, no días.

    El intervalo entre donaciones se cuenta en meses («3 meses»), no en 90
    días, y los meses no miden lo mismo. Si el día no existe en el mes
    destino —un 31 de enero más un mes— se recorta al último día de ese mes.
    """
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def intervalo_de(usuario):
    """Cuántos meses le corresponden a esta persona entre donaciones."""
    return INTERVALO_MESES.get(usuario.genero, INTERVALO_POR_DEFECTO)


def habilitacion(usuario, hoy=None):
    """
    Desde cuándo puede volver a donar esta persona.

    Devuelve un diccionario con:
        apto   : si hoy no hay nada que lo impida
        fecha  : desde cuándo, o None si no se puede estimar
        dias   : cuántos faltan, o None
        motivo : SIN_DONACIONES | INTERVALO | DIFERIMIENTO | PERMANENTE
    """
    hoy = hoy or date.today()

    # El diferimiento manda sobre el intervalo: aunque hayan pasado los
    # meses, con un diferimiento vigente no se puede donar.
    diferimiento = diferimiento_vigente(usuario)
    if diferimiento:
        if diferimiento.fecha_fin is None:
            return {"apto": False, "fecha": None, "dias": None,
                    "motivo": PERMANENTE}
        return {"apto": False,
                "fecha": diferimiento.fecha_fin,
                "dias": (diferimiento.fecha_fin - hoy).days,
                "motivo": DIFERIMIENTO}

    ultima = ultima_donacion(usuario)
    if ultima is None:
        return {"apto": True, "fecha": None, "dias": None,
                "motivo": SIN_DONACIONES}

    fecha = sumar_meses(ultima, intervalo_de(usuario))
    return {"apto": fecha <= hoy,
            "fecha": fecha,
            "dias": max((fecha - hoy).days, 0),
            "motivo": INTERVALO}


def motivo_del_impedimento(estado):
    """
    Qué se le dice a la persona cuando no puede agendar.

    El diferimiento se informa de forma genérica, sin la causa clínica
    (RF09): que exista una condición registrada ya es un dato de salud, y
    el portal no es el lugar donde se entera del cuál. Para eso está la
    consejería.

    El intervalo sí se explica con su fecha: no es información clínica, es
    el calendario, y saberlo le evita volver a intentar todos los días.
    """
    if estado["apto"]:
        return ""

    if estado["motivo"] == PERMANENTE:
        return ("No podés agendar en este momento. Hay una condición "
                "registrada por el personal de salud. Acercate al banco de "
                "sangre para que te orienten.")

    if estado["motivo"] == DIFERIMIENTO:
        return (f"No podés agendar hasta el "
                f"{estado['fecha'].strftime('%d/%m/%Y')}. Hay una condición "
                f"registrada por el personal de salud.")

    return (f"Todavía no pasó el tiempo mínimo entre donaciones. "
            f"Vas a poder agendar desde el "
            f"{estado['fecha'].strftime('%d/%m/%Y')}.")
