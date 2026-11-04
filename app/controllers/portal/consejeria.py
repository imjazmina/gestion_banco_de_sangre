"""
Agenda de consejería del donante.

El laboratorio avisa y no crea la cita. La fila nace cuando el donante
reserva. Si cancela, la misma fila vuelve a Pendiente al reservar de nuevo:
hay una sola citación por resultado. No hay cuestionario.

Jefatura no reserva, no reprograma y no cancela. El día de atención la
confirma el donante. Desde ese día, jefatura marca ausente o realizada.

El historial solo guarda el cambio de estado. Una reprogramación no lo
cambia: queda en auditoría como MODIFICACION. No hay columna de motivo.
"""
from datetime import date, datetime, time, timedelta

from app import calendario
from app.controllers.portal.agenda import (
    DOW_CORTO, ErrorAgenda, personal_de_turno, parsear_fecha,
)
from app.models import (
    Auditoria, Cita, CitacionConsejeria, Diferimiento, Extraccion,
    HorarioDisponible, MuestraCompatibilidad, Notificacion,
    ResultadoCompatibilidad, ResultadoLaboratorio, Rol, Unidad, db,
)


class Caso:
    """Un resultado que habilita consejería, de unidad o de muestra."""

    def __init__(self, resultado, citacion, muestra=False):
        self.resultado = resultado
        self.citacion = citacion
        self.muestra = muestra

    @property
    def id_agenda(self):
        if self.muestra:
            return self.resultado.id_resultado_compatibilidad
        return self.resultado.id_resultado


class ErrorConsejeria(Exception):
    """La reserva de consejería no se puede guardar."""


def _exigir_donante(usuario):
    if usuario.tiene_rol(Rol.JEFATURA):
        raise ErrorConsejeria(
            "Jefatura no agenda, reprograma ni cancela citas de consejería.")


def casos(usuario):
    """Resultados que abren consejería: serología reactiva o PAI positivo."""
    laboratorio = (
        db.session.query(ResultadoLaboratorio, CitacionConsejeria)
        .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
        .outerjoin(
            CitacionConsejeria,
            CitacionConsejeria.id_resultado == ResultadoLaboratorio.id_resultado)
        .filter(Unidad.id_donante == usuario.id_usuario,
                ResultadoLaboratorio.resultado == ResultadoLaboratorio.REACTIVO)
        .order_by(ResultadoLaboratorio.fecha.desc())
        .all()
    )
    muestras = (
        db.session.query(ResultadoCompatibilidad, CitacionConsejeria)
        .join(MuestraCompatibilidad,
              MuestraCompatibilidad.id_muestra == ResultadoCompatibilidad.id_muestra)
        .join(Extraccion,
              Extraccion.id_extraccion == MuestraCompatibilidad.id_extraccion)
        .join(Cita, Cita.id_cita == Extraccion.id_cita)
        .join(Diferimiento,
              Diferimiento.id_diferimiento == ResultadoCompatibilidad.id_diferimiento)
        .outerjoin(
            CitacionConsejeria,
            CitacionConsejeria.id_resultado_compatibilidad
            == ResultadoCompatibilidad.id_resultado_compatibilidad)
        .filter(Cita.id_usuario == usuario.id_usuario,
                Diferimiento.nombre == ResultadoCompatibilidad.PAI_POSITIVO)
        .order_by(ResultadoCompatibilidad.fecha.desc())
        .all()
    )
    pares = [Caso(resultado, citacion) for resultado, citacion in laboratorio]
    pares.extend(Caso(resultado, citacion, muestra=True)
                 for resultado, citacion in muestras)
    return pares


def caso_de(usuario, id_resultado, muestra=False):
    for caso in casos(usuario):
        if caso.muestra == muestra and caso.id_agenda == id_resultado:
            return caso.resultado, caso.citacion
    return None, None


def citacion_de(usuario, id_citacion):
    citacion = db.session.get(CitacionConsejeria, id_citacion)
    if citacion is None or citacion.id_donante != usuario.id_usuario:
        return None
    return citacion


def _ocupados(fechas, excepto_id=None):
    if not fechas:
        return {}
    desde = datetime.combine(min(fechas), time.min)
    hasta = datetime.combine(max(fechas) + timedelta(days=1), time.min)
    consulta = (db.session.query(CitacionConsejeria)
                .filter(CitacionConsejeria.estado.in_(CitacionConsejeria.ABIERTAS),
                        CitacionConsejeria.fecha_hora >= desde,
                        CitacionConsejeria.fecha_hora < hasta))
    if excepto_id is not None:
        consulta = consulta.filter(CitacionConsejeria.id_citacion != excepto_id)
    cuenta = {}
    for citacion in consulta.all():
        clave = (citacion.fecha_hora.date(), citacion.id_horario)
        cuenta[clave] = cuenta.get(clave, 0) + 1
    return cuenta


def _disponibilidad(excepto_id=None, ahora=None):
    ahora = ahora or datetime.now()
    dias = list(calendario.dias_de_agenda(ahora))
    ocupados = _ocupados(dias, excepto_id)
    por_fecha = {}
    for franja in (HorarioDisponible.query
                   .filter_by(disponible=True)
                   .order_by(HorarioDisponible.hora_inicio)
                   .all()):
        fecha = calendario.proxima_fecha(franja.dia_semana, franja.hora_inicio, ahora)
        if fecha is None or fecha not in dias:
            continue
        libres = franja.cupo_consejeria - ocupados.get((fecha, franja.id_horario), 0)
        por_fecha.setdefault(fecha, []).append({
            "id_horario": franja.id_horario,
            "hora_inicio": franja.hora_inicio,
            "hora_fin": franja.hora_fin,
            "cupo": franja.cupo_consejeria,
            "libres": max(libres, 0),
        })
    for franjas in por_fecha.values():
        franjas.sort(key=lambda f: f["hora_inicio"])
    return por_fecha


def dias(seleccionada=None, excepto_id=None, ahora=None):
    ahora = ahora or datetime.now()
    disponible = _disponibilidad(excepto_id, ahora)
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


def franjas_de(fecha, excepto_id=None, ahora=None):
    if fecha is None:
        return []
    return _disponibilidad(excepto_id, ahora).get(fecha, [])


def franja_elegida(fecha, id_horario, excepto_id=None, ahora=None):
    if not fecha or not id_horario:
        return None
    return next((f for f in franjas_de(fecha, excepto_id, ahora)
                 if f["id_horario"] == id_horario and f["libres"] > 0), None)


def _bloquear(id_horario, fecha, excepto_id=None):
    franja = (db.session.query(HorarioDisponible)
              .filter_by(id_horario=id_horario)
              .with_for_update()
              .first())
    if franja is None or not franja.disponible:
        raise ErrorConsejeria("Esa franja horaria no está habilitada.")
    if calendario.proxima_fecha(franja.dia_semana, franja.hora_inicio) != fecha:
        raise ErrorConsejeria("Esa franja no corresponde al día que elegiste.")
    ocupados = _ocupados([fecha], excepto_id).get((fecha, id_horario), 0)
    if ocupados >= franja.cupo_consejeria:
        raise ErrorConsejeria("Ese horario se acaba de llenar. Elegí otro.")
    return franja


def _aviso(usuario, citacion, texto):
    db.session.add(Notificacion(
        id_usuario=usuario.id_usuario,
        id_citacion=citacion.id_citacion,
        tipo=Notificacion.CONFIRMACION_CITA,
        mensaje=texto,
    ))


def _momento(fecha, franja):
    return datetime.combine(fecha, franja.hora_inicio)


def agendar(usuario, id_resultado, fecha, id_horario, muestra=False):
    """Crea la citación o reabre la cancelada del mismo resultado."""
    _exigir_donante(usuario)
    resultado, citacion = caso_de(usuario, id_resultado, muestra)
    if resultado is None:
        raise ErrorConsejeria("No tenés una consejería pendiente de agendar.")
    if citacion is not None and citacion.estado in CitacionConsejeria.ABIERTAS:
        raise ErrorConsejeria("Esa consejería ya tiene una cita. Gestionala desde esta pantalla.")
    if citacion is not None and citacion.estado != CitacionConsejeria.CANCELADA:
        raise ErrorConsejeria("Esa consejería ya fue cerrada.")

    try:
        responsable = personal_de_turno()
        franja = _bloquear(id_horario, fecha)
        momento = _momento(fecha, franja)
        if citacion is None:
            citacion = CitacionConsejeria(
                id_donante=usuario.id_usuario,
                id_personal=responsable.id_usuario,
                id_horario=id_horario,
                id_resultado=None if muestra else resultado.id_resultado,
                id_resultado_compatibilidad=(
                    resultado.id_resultado_compatibilidad if muestra else None),
                fecha_hora=momento,
                estado=CitacionConsejeria.PENDIENTE,
            )
            db.session.add(citacion)
            db.session.flush()
            Auditoria.registrar(usuario.id_usuario, "CITACION_CONSEJERIA",
                                citacion.id_citacion, Auditoria.ALTA)
        else:
            citacion.estado = CitacionConsejeria.PENDIENTE
            citacion.id_horario = id_horario
            citacion.fecha_hora = momento
            citacion.id_personal = responsable.id_usuario
            db.session.flush()
            Auditoria.registrar(usuario.id_usuario, "CITACION_CONSEJERIA",
                                citacion.id_citacion, Auditoria.CAMBIO_ESTADO)
        _aviso(usuario, citacion,
               "Tu consejería quedó agendada para el "
               f"{fecha.strftime('%d/%m/%Y')} a las "
               f"{franja.hora_inicio.strftime('%H:%M')}. "
               "El motivo se conversa en el banco, no por este medio.")
        db.session.commit()
        return citacion
    except (ErrorConsejeria, ErrorAgenda):
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


def reprogramar(citacion, usuario, fecha, id_horario):
    _exigir_donante(usuario)
    if citacion.id_donante != usuario.id_usuario:
        raise ErrorConsejeria("Esa consejería no es tuya.")
    if citacion.estado != CitacionConsejeria.PENDIENTE:
        raise ErrorConsejeria("Solo podés reprogramar una consejería pendiente.")
    try:
        franja = _bloquear(id_horario, fecha, excepto_id=citacion.id_citacion)
        citacion.id_horario = id_horario
        citacion.fecha_hora = _momento(fecha, franja)
        try:
            citacion.id_personal = personal_de_turno().id_usuario
        except ErrorAgenda as exc:
            raise ErrorConsejeria(str(exc)) from exc
        Auditoria.registrar(usuario.id_usuario, "CITACION_CONSEJERIA",
                            citacion.id_citacion, Auditoria.MODIFICACION)
        _aviso(usuario, citacion,
               "Reprogramaste tu consejería para el "
               f"{fecha.strftime('%d/%m/%Y')} a las "
               f"{franja.hora_inicio.strftime('%H:%M')}.")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def confirmar(citacion, usuario):
    """El donante confirma solo el día de la atención. No cambia al personal."""
    _exigir_donante(usuario)
    if citacion.id_donante != usuario.id_usuario:
        raise ErrorConsejeria("Esa consejería no es tuya.")
    if citacion.estado != CitacionConsejeria.PENDIENTE:
        raise ErrorConsejeria("Solo podés confirmar una consejería pendiente.")
    if citacion.fecha_hora is None or citacion.fecha_hora.date() != date.today():
        raise ErrorConsejeria("La consejería se confirma el día de atención.")
    citacion.estado = CitacionConsejeria.CONFIRMADA
    Auditoria.registrar(usuario.id_usuario, "CITACION_CONSEJERIA",
                        citacion.id_citacion, Auditoria.CAMBIO_ESTADO)
    db.session.commit()


def cancelar(citacion, usuario):
    _exigir_donante(usuario)
    if citacion.id_donante != usuario.id_usuario:
        raise ErrorConsejeria("Esa consejería no es tuya.")
    if citacion.estado != CitacionConsejeria.PENDIENTE:
        raise ErrorConsejeria("Solo podés cancelar una consejería pendiente.")
    citacion.estado = CitacionConsejeria.CANCELADA
    Auditoria.registrar(usuario.id_usuario, "CITACION_CONSEJERIA",
                        citacion.id_citacion, Auditoria.CAMBIO_ESTADO)
    db.session.commit()


def mensaje_de_error(excepcion):
    if isinstance(excepcion, (ErrorConsejeria, ErrorAgenda)):
        return str(excepcion)
    return "No pudimos guardar la consejería. Intentá de nuevo."
