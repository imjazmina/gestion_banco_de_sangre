"""
Simulación del laboratorio y de las solicitudes publicadas.

Los resultados son sintéticos (RN13). No hay rol de laboratorio ni pantalla
para publicarlos a mano. Al cerrar la extracción, el resultado se calcula
en otro hilo: la pantalla sigue en `En laboratorio` y no espera.

Publicar una solicitud tampoco tiene pantalla de solicitante: si no hay
ninguna vigente, esta función inserta unas pocas.
"""
import logging
import random
import threading
import time
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Asignacion, Auditoria, Cita, CitacionConsejeria, CompatibilidadAboRh,
    Diferimiento, Extraccion, HorarioDisponible, Notificacion,
    RegistroDiferimiento, ResultadoLaboratorio, Rol, Solicitud, TipoSangre,
    TransicionEstado, Unidad, Usuario, UsuarioRol, db,
)

logger = logging.getLogger(__name__)

# Prototipo: no es un tiempo de laboratorio. Alcanza para que la pantalla
# de la extracción se dibuje con la unidad todavía en laboratorio.
DEMORA_LABORATORIO_SEGUNDOS = 8
PROBABILIDAD_REACTIVO = 0.2
# Una grafía por marcador. Las duplicadas sin espacio no se sortean.
CAUSAS_SEROLOGIA = (
    "VIH 1/2",
    "HBsAg (Hepatitis B)",
    "Anti-HCV (Hepatitis C)",
    "VDRL (Sífilis)",
    "Chagas (T. cruzi)",
    "HTLV I/II",
    "Anti-HBc (Hepatitis B)",
    "CMV",
)

_en_curso = set()
_en_curso_lock = threading.Lock()

INSTITUCION_LOCAL = "Hospital Regional de Luque"
DOCUMENTO_SOLICITANTE = "00000001"
MEDICOS = (
    "Dra. Liz Montiel",
    "Dr. Ramón Espínola",
    "Dra. Patricia Acuña",
    "Dr. Carlos Mendoza",
)


class ErrorSimulacion(Exception):
    """La simulación no pudo escribir. El mensaje se muestra al personal."""


# Alta queda en Registrada al crear la unidad. Desde ahí la simulación
# solo escribe este orden. No reescribe unidades que ya siguieron otro.
_FLUJO = {
    (Unidad.REGISTRADA, Unidad.EN_LABORATORIO),
    (Unidad.EN_LABORATORIO, Unidad.EN_STOCK),
    (Unidad.EN_LABORATORIO, Unidad.DESCARTADA),
    (Unidad.EN_STOCK, Unidad.ASIGNADA),
    (Unidad.EN_STOCK, Unidad.VENCIDA),
}


def _transicion(unidad, personal, destino, motivo=None):
    if (unidad.estado, destino) not in _FLUJO:
        raise ErrorSimulacion(
            "Transicion fuera del flujo: %s a %s" % (unidad.estado, destino))
    db.session.add(TransicionEstado(
        id_unidad=unidad.id_unidad,
        id_personal=personal.id_usuario,
        estado_origen=unidad.estado,
        estado_destino=destino,
        motivo=motivo,
        fecha=datetime.now(),
    ))
    unidad.estado = destino
    # El trigger lee el estado vigente al insertar la fila siguiente.
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "UNIDAD", unidad.id_unidad,
                        Auditoria.CAMBIO_ESTADO)


def _jefatura():
    return (Usuario.query
            .join(UsuarioRol, UsuarioRol.id_usuario == Usuario.id_usuario)
            .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
            .filter(Rol.codigo == Rol.JEFATURA,
                    Usuario.estado.is_(True),
                    Usuario.contrasena.isnot(None))
            .first())


def agendar_resultado(id_unidad):
    """Encola la simulación sin frenar el pedido que guardó la extracción."""
    app = current_app._get_current_object()
    with _en_curso_lock:
        if id_unidad in _en_curso:
            return
        _en_curso.add(id_unidad)
    threading.Thread(
        target=_tarea_laboratorio,
        args=(app, id_unidad),
        name=f"laboratorio-{id_unidad}",
        daemon=True,
    ).start()


def reponer_laboratorio():
    """Retoma unidades que siguen en laboratorio si el proceso se reinició."""
    identificadores = [
        fila.id_unidad
        for fila in (Unidad.query
                     .filter(Unidad.estado == Unidad.EN_LABORATORIO)
                     .all())
        if ResultadoLaboratorio.query.filter_by(id_unidad=fila.id_unidad).first() is None
    ]
    for id_unidad in identificadores:
        agendar_resultado(id_unidad)


def _tarea_laboratorio(app, id_unidad):
    try:
        time.sleep(DEMORA_LABORATORIO_SEGUNDOS)
        with app.app_context():
            simular_resultado(id_unidad)
    except Exception:
        logger.exception("No se pudo simular el laboratorio de la unidad %s", id_unidad)
        db.session.rollback()
    finally:
        with _en_curso_lock:
            _en_curso.discard(id_unidad)


def simular_resultado(id_unidad):
    """Escribe un resultado y mueve la unidad. No es un análisis real.

    Si otro hilo ya lo hizo, termina sin insertar. No toca
    `fecha_vencimiento`: esa fecha no se calcula acá.
    """
    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:clave)"),
        {"clave": id_unidad},
    )
    unidad = db.session.get(Unidad, id_unidad)
    if unidad is None or unidad.estado != Unidad.EN_LABORATORIO:
        db.session.rollback()
        return
    if ResultadoLaboratorio.query.filter_by(id_unidad=unidad.id_unidad).first():
        db.session.rollback()
        return

    extraccion = db.session.get(Extraccion, unidad.id_extraccion)
    personal = db.session.get(Usuario, extraccion.id_personal) if extraccion else None
    if personal is None:
        db.session.rollback()
        raise ErrorSimulacion("La extracción no tiene personal para firmar la transición.")

    tipos = TipoSangre.query.all()
    if not tipos:
        db.session.rollback()
        raise ErrorSimulacion("Falta el catálogo de grupos sanguíneos.")
    tipo = random.choice(tipos)
    if random.random() < PROBABILIDAD_REACTIVO:
        _reactivo(unidad, personal, extraccion, tipo)
    else:
        _no_reactivo(unidad, personal, tipo)
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0]) from exc


def _copiar_tipificacion(unidad, tipo):
    unidad.id_tipo_sangre = tipo.id_tipo_sangre
    donante = db.session.get(Usuario, unidad.id_donante)
    if donante is not None:
        donante.id_tipo_sangre = tipo.id_tipo_sangre


def _no_reactivo(unidad, personal, tipo):
    db.session.add(ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.NO_REACTIVO,
        fecha=datetime.now(),
    ))
    db.session.flush()
    _transicion(unidad, personal, Unidad.EN_STOCK)
    _copiar_tipificacion(unidad, tipo)
    _asignar_solicitud_de_la_cita(unidad, personal, tipo)


def _causas_serologicas():
    filas = (Diferimiento.query
             .filter(Diferimiento.nombre.in_(CAUSAS_SEROLOGIA),
                     Diferimiento.tipo == "Permanente")
             .all())
    if not filas:
        raise ErrorSimulacion("Faltan causas serológicas permanentes en el catálogo.")
    return filas


def _reactivo(unidad, personal, extraccion, tipo):
    causas = _causas_serologicas()
    cantidad = random.randint(1, min(3, len(causas)))
    elegidas = random.sample(causas, cantidad)
    jefatura = _jefatura()
    if jefatura is None:
        raise ErrorSimulacion("No hay una cuenta de jefatura para firmar la citación.")
    franja = HorarioDisponible.query.filter_by(disponible=True).first()
    if franja is None:
        raise ErrorSimulacion("No hay franjas horarias para citar a consejería.")

    resultado = ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.REACTIVO,
        fecha=datetime.now(),
    )
    db.session.add(resultado)
    db.session.flush()
    for causa in elegidas:
        db.session.add(RegistroDiferimiento(
            id_donante=unidad.id_donante,
            id_diferimiento=causa.id_diferimiento,
            id_cita=extraccion.id_cita,
            id_personal=None,
            origen=RegistroDiferimiento.LABORATORIO,
            institucion_diagnostico=INSTITUCION_LOCAL,
            fecha_inicio=date.today(),
            id_resultado=resultado.id_resultado,
        ))
    db.session.flush()
    _copiar_tipificacion(unidad, tipo)
    _transicion(
        unidad, personal, Unidad.DESCARTADA,
        motivo="Resultado reactivo: " + ", ".join(causa.nombre for causa in elegidas) + ".",
    )

    citacion = CitacionConsejeria(
        id_donante=unidad.id_donante,
        id_personal=jefatura.id_usuario,
        id_horario=franja.id_horario,
        id_resultado=resultado.id_resultado,
        estado="Pendiente",
    )
    db.session.add(citacion)
    db.session.flush()
    db.session.add(Notificacion(
        id_usuario=unidad.id_donante,
        id_citacion=citacion.id_citacion,
        tipo=Notificacion.CITACION_GENERICA,
        mensaje=("El banco de sangre te cita a una consejería presencial. "
                 "Acercate al servicio para coordinar el horario."),
    ))


def _asignar_solicitud_de_la_cita(unidad, personal, tipo):
    """Asigna solo si la cita de la extracción sigue dirigida a una solicitud."""
    extraccion = db.session.get(Extraccion, unidad.id_extraccion)
    if extraccion is None:
        return
    cita = db.session.get(Cita, extraccion.id_cita)
    if cita is None or cita.id_solicitud is None:
        return
    solicitud = db.session.get(Solicitud, cita.id_solicitud)
    if solicitud is None:
        return
    compatible = (CompatibilidadAboRh.query
                  .filter_by(id_tipo_donante=tipo.id_tipo_sangre,
                             id_tipo_receptor=solicitud.id_tipo_sangre)
                  .first())
    abierta = (solicitud.estado == Solicitud.PUBLICADA
               and solicitud.consentimiento_publicacion
               and solicitud.unidades_asignadas < solicitud.unidades_requeridas)
    if compatible is None or not abierta:
        cita.id_solicitud = None
        if cita.tipo_cita == Cita.SOLIDARIA:
            cita.tipo_cita = Cita.ALTRUISTA
        return
    db.session.add(Asignacion(
        id_unidad=unidad.id_unidad,
        id_solicitud=solicitud.id_solicitud,
        fecha=datetime.now(),
    ))
    unidad.id_solicitud = solicitud.id_solicitud
    _transicion(unidad, personal, Unidad.ASIGNADA)
    solicitud.unidades_asignadas += 1
    db.session.add(Notificacion(
        id_usuario=solicitud.id_solicitante,
        id_solicitud=solicitud.id_solicitud,
        tipo=Notificacion.ASIGNACION_SOLICITANTE,
        mensaje="Se asignó una unidad a tu solicitud.",
    ))
    if solicitud.unidades_asignadas >= solicitud.unidades_requeridas:
        solicitud.estado = Solicitud.COMPLETA
        _soltar_citas(solicitud)
        db.session.add(Notificacion(
            id_usuario=solicitud.id_solicitante,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.META_COMPLETA,
            mensaje="La cantidad publicada de tu solicitud ya se completó.",
        ))


def _soltar_citas(solicitud):
    """RN08: las citas dirigidas activas dejan de apuntar a la solicitud."""
    citas = (Cita.query
             .filter(Cita.id_solicitud == solicitud.id_solicitud,
                     Cita.estado.in_(Cita.ACTIVAS))
             .all())
    for cita in citas:
        cita.id_solicitud = None
        if cita.tipo_cita == Cita.SOLIDARIA:
            cita.tipo_cita = Cita.ALTRUISTA


def solicitudes_publicadas():
    hoy = date.today()
    return (Solicitud.query
            .filter(Solicitud.estado == Solicitud.PUBLICADA,
                    Solicitud.consentimiento_publicacion.is_(True),
                    (Solicitud.fecha_limite.is_(None)) | (Solicitud.fecha_limite >= hoy))
            .order_by(Solicitud.fecha_creacion.desc())
            .all())


def candidatos_de(solicitud):
    """Donantes cuyo grupo puede notificar a ese receptor. Sin aviso nuevo."""
    ids = [fila.id_tipo_donante for fila in CompatibilidadAboRh.query.filter_by(
        id_tipo_receptor=solicitud.id_tipo_sangre).all()]
    if not ids:
        return []
    return (Usuario.query
            .filter(Usuario.id_tipo_sangre.in_(ids),
                    Usuario.estado.is_(True),
                    Usuario.cuenta_suprimida.is_(False),
                    Usuario.id_usuario != solicitud.id_solicitante)
            .order_by(Usuario.apellido)
            .all())


def _solicitante_de_servicio():
    """Cuenta sin contraseña que figura como solicitante de las filas simuladas."""
    usuario = Usuario.query.filter_by(documento=DOCUMENTO_SOLICITANTE).first()
    if usuario is not None:
        return usuario
    usuario = Usuario(
        documento=DOCUMENTO_SOLICITANTE,
        nombre="Solicitud",
        apellido="simulada",
        fecha_nacimiento=date(1990, 1, 1),
        genero="Femenino",
        contrasena=None,
        consentimiento_privacidad=True,
        estado=True,
        cuenta_suprimida=False,
        fecha_alta=datetime.now(),
    )
    db.session.add(usuario)
    db.session.flush()
    return usuario


def asegurar_publicadas():
    """Inserta solicitudes al azar solo si no queda ninguna vigente."""
    if solicitudes_publicadas():
        return
    solicitante = _solicitante_de_servicio()
    cita_activa = (Cita.query
                   .filter(Cita.id_usuario == solicitante.id_usuario,
                           Cita.estado.in_(Cita.ACTIVAS))
                   .first())
    if cita_activa is not None:
        return
    tipos = TipoSangre.query.all()
    if not tipos:
        return
    for _ in range(3):
        db.session.add(Solicitud(
            id_solicitante=solicitante.id_usuario,
            medico_tratante=random.choice(MEDICOS),
            id_tipo_sangre=random.choice(tipos).id_tipo_sangre,
            unidades_requeridas=random.randint(1, 3),
            unidades_asignadas=0,
            consentimiento_publicacion=True,
            fecha_limite=date.today() + timedelta(days=14),
            estado=Solicitud.PUBLICADA,
            fecha_creacion=datetime.now(),
        ))
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0])


def marcar_vencidas(personal):
    """Pasa a Vencida una unidad en stock cuya fecha cargada ya se superó."""
    hoy = date.today()
    unidades = (Unidad.query
                .filter(Unidad.fecha_vencimiento.isnot(None),
                        Unidad.fecha_vencimiento < hoy,
                        Unidad.estado == Unidad.EN_STOCK)
                .all())
    for unidad in unidades:
        _transicion(unidad, personal, Unidad.VENCIDA,
                    motivo="Fecha de vencimiento ya cargada, superada.")
    if unidades:
        try:
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0])
    return len(unidades)
