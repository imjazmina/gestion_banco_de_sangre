"""
Agenda de donación: disponibilidad, reglas y alta de la cita.

Las reglas duras las hace cumplir la base (migración 002): una sola cita
activa, cupo por franja y fecha, nada de agendar con un diferimiento
vigente, ni sobre una fecha pasada, ni en un día que no coincide con la
franja. Acá se consulta y se arma la pantalla; si algo se escapa, el INSERT
falla igual y el mensaje del trigger se muestra al donante.
"""
from datetime import date, timedelta

from sqlalchemy import func, text

from app.models import db, Cita, HorarioDisponible, RegistroDiferimiento, Notificacion

# Cuántos días hacia adelante se ofrecen.
DIAS_AGENDA = 21

# El día de la semana como lo guarda horario_disponible, indexado por
# weekday() de Python (lunes = 0).
DIA_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
DOW_CORTO = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

# Los tipos que el donante puede elegir. 'Extraccion de compatibilidad' queda
# afuera a propósito: la indica el personal, no se pide desde el portal.
TIPOS = [
    ("Donacion altruista", "Altruista",
     "Donás sin destinatario específico, para la reserva general del banco.",
     False),
    ("Reposicion", "Reposición",
     "Donás para reponer unidades que usó un familiar o conocido.",
     False),
    ("Donacion solidaria", "Solidaria",
     "Donás para una persona concreta de la lista de solicitudes.",
     True),
]
TIPOS_VALIDOS = {clave for clave, _, _, _ in TIPOS}
NECESITA_SOLICITUD = {clave for clave, _, _, necesita in TIPOS if necesita}
ETIQUETA = {clave: etiqueta for clave, etiqueta, _, _ in TIPOS}


def etiqueta_tipo(clave):
    return ETIQUETA.get(clave, clave)


# ------------------------------------------------------------------ estado
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


def cita_vigente(usuario):
    """La cita Pendiente o Confirmada que no pasó todavía."""
    return (Cita.query
            .filter(Cita.id_usuario == usuario.id_usuario,
                    Cita.estado.in_(Cita.ACTIVAS),
                    Cita.fecha_cita >= date.today())
            .order_by(Cita.fecha_cita.asc())
            .first())


def historial(usuario):
    return (Cita.query
            .filter(Cita.id_usuario == usuario.id_usuario,
                    db.not_(Cita.estado.in_(Cita.ACTIVAS)))
            .order_by(Cita.fecha_cita.desc())
            .all())


# ------------------------------------------------------------------ agenda
def _rango():
    """Desde mañana: una cita para hoy no le sirve a nadie que la agende hoy."""
    desde = date.today() + timedelta(days=1)
    return desde, desde + timedelta(days=DIAS_AGENDA - 1)


def parsear_fecha(texto):
    """'2026-09-28' -> date, o None si no sirve o cae fuera del rango."""
    if not texto:
        return None
    try:
        d = date.fromisoformat(texto)
    except (ValueError, TypeError):
        return None
    desde, hasta = _rango()
    return d if desde <= d <= hasta else None


def _libres_por_fecha():
    """
    Cuántos lugares quedan cada día del rango.

    Se resuelve en una sola consulta: pedirlo día por día serían 21 viajes a
    la base para pintar una tira de fechas.
    """
    desde, hasta = _rango()
    filas = db.session.execute(text("""
        SELECT d.fecha::date AS fecha,
               COALESCE(SUM(GREATEST(h.cupo_atencion - COALESCE(o.ocupados, 0), 0)), 0) AS libres
          FROM generate_series(:desde, :hasta, interval '1 day') AS d(fecha)
          LEFT JOIN horario_disponible h
                 ON h.disponible
                AND h.dia_semana = CASE EXTRACT(DOW FROM d.fecha)
                      WHEN 1 THEN 'Lunes'   WHEN 2 THEN 'Martes'
                      WHEN 3 THEN 'Miercoles' WHEN 4 THEN 'Jueves'
                      WHEN 5 THEN 'Viernes' WHEN 6 THEN 'Sabado'
                      ELSE 'Domingo' END
          LEFT JOIN (
               SELECT fecha_cita, id_horario, count(*) AS ocupados
                 FROM cita
                WHERE estado IN ('Pendiente','Confirmada')
                GROUP BY fecha_cita, id_horario
          ) o ON o.id_horario = h.id_horario AND o.fecha_cita = d.fecha::date
         GROUP BY d.fecha
         ORDER BY d.fecha
    """), {"desde": desde, "hasta": hasta}).all()
    return {f.fecha: f.libres for f in filas}


def calendario(seleccionada=None):
    """La tira de días, con cuántos lugares libres tiene cada uno."""
    libres = _libres_por_fecha()
    desde, _ = _rango()
    return [{
        "fecha": desde + timedelta(days=i),
        "iso": (desde + timedelta(days=i)).isoformat(),
        "dow": DOW_CORTO[(desde + timedelta(days=i)).weekday()],
        "dia": (desde + timedelta(days=i)).day,
        "libres": libres.get(desde + timedelta(days=i), 0),
        "cerrado": libres.get(desde + timedelta(days=i), 0) == 0,
        "seleccionado": (desde + timedelta(days=i)) == seleccionada,
    } for i in range(DIAS_AGENDA)]


def franjas_de(fecha):
    """Las franjas de un día, con su cupo y cuántos lugares quedan."""
    ocupados = dict(
        db.session.query(Cita.id_horario, func.count(Cita.id_cita))
        .filter(Cita.fecha_cita == fecha, Cita.estado.in_(Cita.ACTIVAS))
        .group_by(Cita.id_horario).all())

    franjas = (HorarioDisponible.query
               .filter_by(dia_semana=DIA_SEMANA[fecha.weekday()], disponible=True)
               .order_by(HorarioDisponible.hora_inicio)
               .all())

    return [{
        "id_horario": h.id_horario,
        "hora_inicio": h.hora_inicio,
        "hora_fin": h.hora_fin,
        "cupo": h.cupo_atencion,
        "libres": max(h.cupo_atencion - ocupados.get(h.id_horario, 0), 0),
    } for h in franjas]


def franja_elegida(fecha, id_horario):
    """La franja pedida, solo si existe ese día y todavía tiene lugar."""
    if not fecha or not id_horario:
        return None
    return next((f for f in franjas_de(fecha)
                 if f["id_horario"] == id_horario and f["libres"] > 0), None)


# --------------------------------------------------------------- escritura
def crear(usuario, fecha, id_horario, tipo, id_solicitud=None):
    """
    Registra la cita y su notificación, en una sola transacción.

    No se asigna personal: eso lo hace el banco al organizar el día
    (id_personal quedó nullable en la migración 002).
    """
    cita = Cita(tipo_cita=tipo,
                id_usuario=usuario.id_usuario,
                id_solicitud=id_solicitud,
                id_horario=id_horario,
                fecha_cita=fecha,
                estado=Cita.CONFIRMADA)
    db.session.add(cita)
    db.session.flush()

    db.session.add(Notificacion(
        id_usuario=usuario.id_usuario,
        id_cita=cita.id_cita,
        id_solicitud=id_solicitud,
        tipo=Notificacion.CONFIRMACION_CITA,
        mensaje=f"Tu cita de donación quedó confirmada para el "
                f"{fecha.strftime('%d/%m/%Y')}."))
    db.session.commit()
    return cita


def reprogramar(cita, fecha, id_horario):
    cita.fecha_cita = fecha
    cita.id_horario = id_horario
    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.CONFIRMACION_CITA,
        mensaje=f"Reprogramaste tu cita para el {fecha.strftime('%d/%m/%Y')}."))
    db.session.commit()


def cancelar(cita):
    cita.estado = Cita.CANCELADA
    db.session.commit()


def mensaje_de_error(excepcion):
    """
    Saca el texto del RAISE EXCEPTION de PostgreSQL.

    Los triggers ya devuelven el mensaje redactado en castellano, así que se
    puede mostrar tal cual en lugar de un error genérico.
    """
    texto = str(getattr(excepcion, "orig", excepcion))
    primera = texto.strip().splitlines()[0] if texto.strip() else ""
    for prefijo in ("ERROR:", "error:"):
        if primera.startswith(prefijo):
            primera = primera[len(prefijo):]
    primera = primera.strip()

    if "uq_cita_activa_por_donante" in texto:
        return "Ya tenés una cita agendada. Gestionala antes de crear otra."
    if "duplicate key" in texto.lower():
        return "Ya existe un registro con esos datos."
    return primera or "No se pudo registrar la cita."
