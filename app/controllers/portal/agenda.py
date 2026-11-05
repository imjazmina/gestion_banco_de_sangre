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
from app.models import (db, Auditoria, Cita, HorarioDisponible, MuestraCompatibilidad,
                        Notificacion, RegistroDiferimiento, Solicitud)

# Usuario de servicio del mostrador en la maqueta. No firma vencimientos:
# esos los graba Sistema (documento 00000002).
DOCUMENTO_PERSONAL_DE_TURNO = "00000000"

# Los tipos que el donante puede elegir. La extracción de muestra queda
# afuera a propósito: la indica el personal, no se pide desde el portal.
TIPOS = [
    ("Donacion altruista", "Altruista",
     "Donás sin destinatario específico, para la reserva general del banco.",
     False),
    ("Donacion solidaria", "Solidaria",
     "Donás para una persona concreta de la lista de solicitudes.",
     True),
]
TIPOS_VALIDOS = {clave for clave, _, _, _ in TIPOS}
NECESITA_SOLICITUD = {clave for clave, _, _, necesita in TIPOS if necesita}
ETIQUETA = {clave: etiqueta for clave, etiqueta, _, _ in TIPOS}
TIPO_MUESTRA = Cita.MUESTRA
ETIQUETA[TIPO_MUESTRA] = "Extracción de muestra para compatibilidad"

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


def solicitud_abierta(usuario):
    """RN23: Creada o Publicada impide agendar una donación."""
    return (Solicitud.query
            .filter(Solicitud.id_solicitante == usuario.id_usuario,
                    Solicitud.estado.in_(Solicitud.ABIERTAS))
            .order_by(Solicitud.fecha_creacion.desc())
            .first())


def solicitud_creada(usuario):
    """Solo una solicitud Creada habilita la extracción de muestra."""
    return (Solicitud.query
            .filter_by(id_solicitante=usuario.id_usuario,
                       estado=Solicitud.CREADA)
            .order_by(Solicitud.fecha_creacion.desc())
            .first())


def tiene_muestra(solicitud):
    if solicitud is None:
        return False
    return (MuestraCompatibilidad.query
            .filter_by(id_solicitud=solicitud.id_solicitud)
            .first() is not None)


# --------------------------------------------------------------- escritura
def crear(usuario, fecha, id_horario, tipo, id_solicitud=None,
         consentimiento_publicacion=None):
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

    if tipo == TIPO_MUESTRA:
        solicitud = solicitud_creada(usuario)
        if solicitud is None:
            raise ErrorAgenda(
                "Solo podés agendar la extracción de muestra "
                "con una solicitud creada.")
        if tiene_muestra(solicitud):
            raise ErrorAgenda(
                "Esta solicitud ya tiene una extracción de muestra.")
        if consentimiento_publicacion is None:
            raise ErrorAgenda(
                "Indicá si autorizás publicar la solicitud.")
        solicitud.consentimiento_publicacion = bool(consentimiento_publicacion)
        Auditoria.registrar(usuario.id_usuario, "SOLICITUD",
                            solicitud.id_solicitud, Auditoria.MODIFICACION)
        # La cita no apunta a la solicitud propia: lo impide RN03.
        # El vínculo queda en muestra_compatibilidad.
        id_solicitud = None
    elif solicitud_abierta(usuario):
        raise ErrorAgenda("No podés agendar mientras tengas una solicitud abierta.")
    elif tipo not in TIPOS_VALIDOS:
        raise ErrorAgenda("Ese tipo de cita no está disponible.")

    try:
        franja = _bloquear_franja(id_horario, fecha)
        cita = Cita(tipo_cita=tipo,
                    id_usuario=usuario.id_usuario,
                    id_solicitud=id_solicitud,
                    id_horario=id_horario,
                    fecha_hora_creacion=datetime.now(),
                    estado=Cita.PENDIENTE)
        db.session.add(cita)
        db.session.flush()
        Auditoria.registrar(usuario.id_usuario, "CITA", cita.id_cita,
                            Auditoria.ALTA)

        if tipo == TIPO_MUESTRA:
            texto = "Tu extracción de muestra"
        else:
            texto = "Tu cita de donación"
        db.session.add(Notificacion(
            id_usuario=usuario.id_usuario,
            id_cita=cita.id_cita,
            id_solicitud=id_solicitud,
            tipo=Notificacion.CONFIRMACION_CITA,
            mensaje=f"{texto} quedó {cita.estado} para el "
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
    Con el cuestionario ya enviado la cita quedó confirmada y no se mueve.
    """
    from app.controllers.portal.cuestionario import completo
    if completo(cita):
        raise ErrorAgenda(
            "No podés reprogramar porque el cuestionario ya fue enviado.")
    try:
        franja = _bloquear_franja(id_horario, fecha)
        cita.id_horario = id_horario
        cita.fecha_hora_creacion = datetime.now()
        db.session.add(Notificacion(
            id_usuario=cita.id_usuario,
            id_cita=cita.id_cita,
            tipo=Notificacion.CONFIRMACION_CITA,
            mensaje=f"Reprogramaste tu cita para el {fecha.strftime('%d/%m/%Y')} "
                    f"a las {franja.hora_inicio.strftime('%H:%M')}. "
                    f"El estado sigue siendo {cita.estado}."))
        Auditoria.registrar(cita.id_usuario, "CITA", cita.id_cita,
                            Auditoria.MODIFICACION)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def cancelar(cita):
    if cita.estado != Cita.PENDIENTE:
        raise ErrorAgenda("Solo podés cancelar una cita pendiente.")
    cita.estado = Cita.CANCELADA
    Auditoria.registrar(cita.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
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
