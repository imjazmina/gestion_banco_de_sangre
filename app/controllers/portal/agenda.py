"""
Agenda de donación: disponibilidad, reglas y alta de la cita.

El esquema no guarda el día de la cita: guarda la franja del catálogo
(`horario_disponible`) y cuándo se reservó. El día se calcula —la próxima
vez que esa franja ocurre— en app/calendario.py.

De ahí salen dos cosas que este módulo hace y conviene entender:

  * La agenda ofrece 7 días. Cada franja del catálogo ocurre una vez por
    semana; a partir del octavo día se repetiría y dos lunes distintos
    apuntarían a la misma franja.
  * Las reglas (una cita activa por donante, cupo de la franja, diferimiento
    vigente) las hace cumplir este código, no la base. El alta toma un
    bloqueo sobre la fila de la franja para contar y grabar sin que dos
    reservas simultáneas pasen el cupo.
"""
from datetime import date, datetime

from sqlalchemy import func, text

from app import calendario
from app.models import (db, Cita, HorarioDisponible, Notificacion,
                        RegistroDiferimiento, Usuario)

# Documento del usuario de servicio «Personal de turno». `cita.id_personal`
# es NOT NULL y al reservar todavía no se sabe quién va a atender, así que
# queda este y el panel lo reemplaza por la persona real en el mostrador.
DOCUMENTO_PERSONAL_DE_TURNO = "00000000"

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

DOW_CORTO = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


class ErrorAgenda(Exception):
    """La reserva no se puede hacer. El mensaje se le muestra al donante."""


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


def _citas_de(usuario, activas):
    """
    Las citas del donante, ya ordenadas por su día.

    El orden se hace acá y no en la consulta porque la fecha no es una
    columna: se calcula a partir de la franja. Son las citas de una sola
    persona, así que traerlas y ordenarlas en Python no cuesta nada.
    """
    consulta = Cita.query.filter(Cita.id_usuario == usuario.id_usuario)
    consulta = (consulta.filter(Cita.estado.in_(Cita.ACTIVAS)) if activas
                else consulta.filter(db.not_(Cita.estado.in_(Cita.ACTIVAS))))
    citas = [c for c in consulta.all() if c.fecha_cita is not None]
    return sorted(citas, key=lambda c: c.momento, reverse=not activas)


def cita_vigente(usuario):
    """
    La cita Pendiente o Confirmada de hoy en adelante.

    Se compara por día y no por hora a propósito: una cita de las 07:00 que
    a las 11 todavía está Confirmada es una cita que el personal no cerró,
    no una cita vencida. Sacarla de la pantalla dejaría al donante sin
    dónde ver su turno ni responder el cuestionario, y le permitiría sacar
    otro turno encima del que ya tiene.
    """
    hoy = date.today()
    return next((c for c in _citas_de(usuario, activas=True)
                 if c.fecha_cita >= hoy), None)


def historial(usuario):
    """Las citas ya cerradas, de la más reciente a la más vieja."""
    return _citas_de(usuario, activas=False)


# ------------------------------------------------------------------ agenda
def parsear_fecha(texto):
    """'2026-09-28' -> date, o None si no sirve o cae fuera de la agenda."""
    if not texto:
        return None
    try:
        d = date.fromisoformat(texto)
    except (ValueError, TypeError):
        return None
    return d if d in calendario.dias_de_agenda() else None


def _ocupados_por_franja():
    """Cuántas citas activas tiene cada franja, en una sola consulta."""
    return dict(
        db.session.query(Cita.id_horario, func.count(Cita.id_cita))
        .filter(Cita.estado.in_(Cita.ACTIVAS))
        .group_by(Cita.id_horario).all())


def _franjas_habilitadas():
    return (HorarioDisponible.query
            .filter_by(disponible=True)
            .order_by(HorarioDisponible.hora_inicio)
            .all())


def _disponibilidad(ahora=None):
    """
    Los lugares libres de cada franja, ubicados en el día que les toca.

    Devuelve {fecha: [franja, ...]}. Una franja cuya hora ya pasó hoy cae
    en la semana que viene, o sea fuera de los siete días, y no aparece.
    """
    ahora = ahora or datetime.now()
    ocupados = _ocupados_por_franja()
    dias = set(calendario.dias_de_agenda(ahora))

    por_fecha = {}
    for h in _franjas_habilitadas():
        fecha = calendario.proxima_fecha(h.dia_semana, h.hora_inicio, ahora)
        if fecha is None or fecha not in dias:
            continue
        por_fecha.setdefault(fecha, []).append({
            "id_horario": h.id_horario,
            "hora_inicio": h.hora_inicio,
            "hora_fin": h.hora_fin,
            "cupo": h.cupo_atencion,
            "libres": max(h.cupo_atencion - ocupados.get(h.id_horario, 0), 0),
        })

    for franjas in por_fecha.values():
        franjas.sort(key=lambda f: f["hora_inicio"])
    return por_fecha


def dias(seleccionada=None, ahora=None):
    """La tira de días, con cuántos lugares libres tiene cada uno."""
    ahora = ahora or datetime.now()
    disponible = _disponibilidad(ahora)
    resultado = []
    for fecha in calendario.dias_de_agenda(ahora):
        libres = sum(f["libres"] for f in disponible.get(fecha, []))
        resultado.append({
            "fecha": fecha,
            "iso": fecha.isoformat(),
            "dow": DOW_CORTO[fecha.weekday()],
            "dia": fecha.day,
            "etiqueta": calendario.etiqueta(fecha, ahora.date()),
            "libres": libres,
            "cerrado": libres == 0,
            "seleccionado": fecha == seleccionada,
        })
    return resultado


def franjas_de(fecha, ahora=None):
    """Las franjas de ese día, con su cupo y cuántos lugares quedan."""
    return _disponibilidad(ahora).get(fecha, [])


def franja_elegida(fecha, id_horario, ahora=None):
    """La franja pedida, solo si existe ese día y todavía tiene lugar."""
    if not fecha or not id_horario:
        return None
    return next((f for f in franjas_de(fecha, ahora)
                 if f["id_horario"] == id_horario and f["libres"] > 0), None)


def personal_de_turno():
    """
    El usuario de servicio que queda como responsable al reservar.

    Lo carga database/catalogos.sql. Si no está, se avisa en lugar de
    inventar un responsable: `cita.id_personal` no admite nulos y poner a
    cualquiera sería atribuirle a una persona un trabajo que no hizo.
    """
    usuario = Usuario.query.filter_by(
        documento=DOCUMENTO_PERSONAL_DE_TURNO).first()
    if usuario is None:
        raise ErrorAgenda(
            "Falta el usuario «Personal de turno» en la base. "
            "Ejecutá: python database/cargar_catalogos.py")
    return usuario


# --------------------------------------------------------------- escritura
def crear(usuario, fecha, id_horario, tipo, id_solicitud=None):
    """
    Registra la cita y su notificación, en una sola transacción.

    El cupo se vuelve a contar acá adentro, después de bloquear la fila de
    la franja. Sin ese bloqueo, dos personas que reservan en el mismo
    segundo cuentan las dos "hay lugar" y entran las dos; con él, la
    segunda espera a que la primera termine y ve el cupo ya consumido.
    """
    if diferimiento_vigente(usuario):
        raise ErrorAgenda("No podés agendar mientras tengas una condición "
                          "registrada por el personal de salud.")
    if cita_vigente(usuario):
        raise ErrorAgenda("Ya tenés una cita agendada. "
                          "Gestionala antes de crear otra.")

    responsable = personal_de_turno()

    try:
        franja = _bloquear_franja(id_horario, fecha)
        cita = Cita(tipo_cita=tipo,
                    id_usuario=usuario.id_usuario,
                    id_solicitud=id_solicitud,
                    id_personal=responsable.id_usuario,
                    id_horario=id_horario,
                    fecha_hora_creacion=datetime.now(),
                    estado=Cita.CONFIRMADA)
        db.session.add(cita)
        db.session.flush()

        db.session.add(Notificacion(
            id_usuario=usuario.id_usuario,
            id_cita=cita.id_cita,
            id_solicitud=id_solicitud,
            tipo=Notificacion.CONFIRMACION_CITA,
            mensaje=f"Tu cita de donación quedó confirmada para el "
                    f"{fecha.strftime('%d/%m/%Y')} a las "
                    f"{franja.hora_inicio.strftime('%H:%M')}."))
        db.session.commit()
        return cita
    except ErrorAgenda:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


def _bloquear_franja(id_horario, fecha):
    """
    Toma la franja para escribir y comprueba que todavía tenga lugar.

    El SELECT ... FOR UPDATE retiene la fila hasta el commit: es lo que
    convierte "contar y después grabar" en una sola operación indivisible.
    """
    franja = (db.session.query(HorarioDisponible)
              .filter_by(id_horario=id_horario)
              .with_for_update()
              .first())
    if franja is None or not franja.disponible:
        raise ErrorAgenda("Esa franja horaria no está habilitada.")

    if calendario.proxima_fecha(franja.dia_semana, franja.hora_inicio) != fecha:
        raise ErrorAgenda("Esa franja no corresponde al día que elegiste.")

    ocupados = (db.session.query(func.count(Cita.id_cita))
                .filter(Cita.id_horario == id_horario,
                        Cita.estado.in_(Cita.ACTIVAS))
                .scalar())
    if ocupados >= franja.cupo_atencion:
        raise ErrorAgenda("Ese horario se acaba de llenar. Elegí otro.")
    return franja


def reprogramar(cita, fecha, id_horario):
    """
    Mueve la cita a otra franja.

    `fecha_hora_creacion` se actualiza porque es lo que ancla el cálculo del
    día: es la fecha de alta de esta reserva, no de la primera que hubo.
    """
    try:
        franja = _bloquear_franja(id_horario, fecha)
        cita.id_horario = id_horario
        cita.fecha_hora_creacion = datetime.now()
        db.session.add(Notificacion(
            id_usuario=cita.id_usuario,
            id_cita=cita.id_cita,
            tipo=Notificacion.CONFIRMACION_CITA,
            mensaje=f"Reprogramaste tu cita para el {fecha.strftime('%d/%m/%Y')} "
                    f"a las {franja.hora_inicio.strftime('%H:%M')}."))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def cancelar(cita):
    cita.estado = Cita.CANCELADA
    db.session.commit()


def mensaje_de_error(excepcion):
    """El texto que se le muestra al donante cuando la reserva no sale."""
    if isinstance(excepcion, ErrorAgenda):
        return str(excepcion)

    texto = str(getattr(excepcion, "orig", excepcion))
    primera = texto.strip().splitlines()[0] if texto.strip() else ""
    for prefijo in ("ERROR:", "error:"):
        if primera.startswith(prefijo):
            primera = primera[len(prefijo):]
    primera = primera.strip()

    if "duplicate key" in texto.lower():
        return "Ya existe un registro con esos datos."
    return primera or "No se pudo registrar la cita."
