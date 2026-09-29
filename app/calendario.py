"""
De qué día es una cita.

El esquema guarda la franja (`horario_disponible`: «Lunes, 07:00 a 07:30») y
cuándo se hizo la reserva (`cita.fecha_hora_creacion`). No guarda el día de
la cita, y eso es a propósito: la franja es un catálogo de los horarios que
atiende el banco, y la cita se toma para **la próxima vez que esa franja
ocurre**.

Entonces el día no se guarda, se calcula: es la primera vez que cae ese día
de la semana a partir del momento de la reserva. Reservar un martes una
franja de «Lunes 07:00» significa el lunes siguiente.

Dos consecuencias de este modelo, que conviene tener presentes:

  * La agenda alcanza 7 días. Más allá de eso, dos lunes distintos
    apuntarían a la misma franja y no habría cómo distinguirlos.
  * Reprogramar mueve la fecha de la reserva, porque es lo que ancla el
    cálculo. Por eso `fecha_hora_creacion` se actualiza al reprogramar: es
    la fecha de alta de *esa* reserva, no de la primera que hubo.

Este módulo no importa modelos a propósito: recibe los datos sueltos, así
lo puede usar tanto el modelo como los controladores sin importarse en
círculo.
"""
from datetime import date, datetime, timedelta

# Los nombres tal como están cargados en horario_disponible.dia_semana.
# Sin tildes, que es como los escribe el catálogo.
DIA_A_INDICE = {
    "Lunes": 0, "Martes": 1, "Miercoles": 2, "Jueves": 3,
    "Viernes": 4, "Sabado": 5, "Domingo": 6,
}

INDICE_A_DIA = {v: k for k, v in DIA_A_INDICE.items()}

# Para mostrar en pantalla.
DIA_LARGO = {
    "Lunes": "Lunes", "Martes": "Martes", "Miercoles": "Miércoles",
    "Jueves": "Jueves", "Viernes": "Viernes", "Sabado": "Sábado",
    "Domingo": "Domingo",
}

MES_CORTO = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
             7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}


def proxima_fecha(dia_semana, hora_inicio, desde=None):
    """
    El próximo día concreto en que ocurre esa franja.

    `desde` es el momento desde el cual se mira, normalmente la reserva.
    Si la franja es hoy pero su hora ya pasó, se va a la semana que viene:
    no se puede reservar un turno que ya empezó.

    Devuelve None si el día de la semana no se reconoce, en lugar de
    inventar una fecha.
    """
    indice = DIA_A_INDICE.get(dia_semana)
    if indice is None:
        return None

    desde = desde or datetime.now()
    if isinstance(desde, datetime):
        dia_base, hora_base = desde.date(), desde.time()
    else:
        dia_base, hora_base = desde, None

    faltan = (indice - dia_base.weekday()) % 7
    if faltan == 0 and hora_base is not None and hora_inicio <= hora_base:
        faltan = 7
    return dia_base + timedelta(days=faltan)


def momento(fecha, hora_inicio):
    """Fecha y hora juntas, para comparar contra `ahora`."""
    return datetime.combine(fecha, hora_inicio)


def dias_de_agenda(desde=None):
    """
    Los 7 días que puede ofrecer la agenda, de hoy en adelante.

    Siete y no más: cada franja del catálogo ocurre una vez por semana, así
    que a partir del octavo día se repetirían y no habría forma de saber a
    cuál de los dos lunes se refiere una cita.
    """
    desde = desde or datetime.now()
    base = desde.date() if isinstance(desde, datetime) else desde
    return [base + timedelta(days=i) for i in range(7)]


def etiqueta(fecha, hoy=None):
    """«Hoy», «Mañana» o «Lunes 6», para los chips del calendario."""
    hoy = hoy or date.today()
    if fecha == hoy:
        return "Hoy"
    if fecha == hoy + timedelta(days=1):
        return "Mañana"
    return f"{DIA_LARGO[INDICE_A_DIA[fecha.weekday()]]} {fecha.day}"
