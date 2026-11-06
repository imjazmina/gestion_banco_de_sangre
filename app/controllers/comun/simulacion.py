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
    Asignacion, Auditoria, Cita, CompatibilidadAboRh,
    Diferimiento, Extraccion, HistorialSolicitud, MuestraCompatibilidad,
    Notificacion, RegistroDiferimiento, ResultadoCompatibilidad,
    ResultadoLaboratorio, Solicitud, TipoSangre,
    TransicionEstado, Unidad, Usuario, db,
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
# Cubre AUDITORIA.id_usuario y TRANSICION_ESTADO.id_personal en procesos
# automáticos. Sin rol ni clave: no entra al portal ni al panel.
DOCUMENTO_SISTEMA = "00000002"
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
    (Unidad.ASIGNADA, Unidad.UTILIZADA),
    (Unidad.ASIGNADA, Unidad.EN_STOCK),
    (Unidad.ASIGNADA, Unidad.VENCIDA),
}


def usuario_sistema():
    """Usuario de servicio que firma vencimientos. No tiene rol ni clave."""
    usuario = Usuario.query.filter_by(documento=DOCUMENTO_SISTEMA).first()
    if usuario is not None:
        return usuario
    usuario = Usuario(
        documento=DOCUMENTO_SISTEMA,
        nombre="Sistema",
        apellido=None,
        fecha_nacimiento=date(2000, 1, 1),
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
    for fila in (MuestraCompatibilidad.query.all()):
        if ResultadoCompatibilidad.query.filter_by(id_muestra=fila.id_muestra).first() is None:
            agendar_compatibilidad(fila.id_muestra)


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

    db.session.execute(
        text("SELECT pg_advisory_xact_lock(CAST(:clase AS integer), CAST(:donante AS integer))"),
        {"clase": 2, "donante": unidad.id_donante},
    )
    tipo = _tipo_de_laboratorio(unidad)
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


def _no_reactivo(unidad, personal, tipo):
    resultado = ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.NO_REACTIVO,
        fecha=datetime.now(),
    )
    db.session.add(resultado)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "RESULTADO_LABORATORIO",
                        resultado.id_resultado, Auditoria.ALTA)
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

    resultado = ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.REACTIVO,
        fecha=datetime.now(),
    )
    db.session.add(resultado)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "RESULTADO_LABORATORIO",
                        resultado.id_resultado, Auditoria.ALTA)
    registros = []
    for causa in elegidas:
        registro = RegistroDiferimiento(
            id_donante=unidad.id_donante,
            id_diferimiento=causa.id_diferimiento,
            id_cita=extraccion.id_cita,
            id_personal=None,
            origen=RegistroDiferimiento.LABORATORIO,
            institucion_diagnostico=INSTITUCION_LOCAL,
            fecha_inicio=date.today(),
            id_resultado=resultado.id_resultado,
        )
        db.session.add(registro)
        registros.append(registro)
    db.session.flush()
    for registro in registros:
        db.session.refresh(registro)
        if registro.fecha_fin is not None:
            raise ErrorSimulacion(
                "Un diferimiento permanente de laboratorio no admite fecha de fin.")
        Auditoria.registrar(personal.id_usuario, "REGISTRO_DIFERIMIENTO",
                            registro.id_registro, Auditoria.ALTA)
    _copiar_tipificacion(unidad, tipo)
    _transicion(
        unidad, personal, Unidad.DESCARTADA,
        motivo="Resultado reactivo: " + ", ".join(causa.nombre for causa in elegidas) + ".",
    )

    db.session.add(Notificacion(
        id_usuario=unidad.id_donante,
        tipo=Notificacion.CITACION_GENERICA,
        mensaje=("El banco de sangre te pide agendar una consejería presencial. "
                 "Entrá a Consejería en el portal y elegí día y horario. "
                 "El motivo se conversa en el servicio."),
    ))


def _cita_de_la_unidad(unidad):
    extraccion = db.session.get(Extraccion, unidad.id_extraccion)
    if extraccion is None:
        return None
    return db.session.get(Cita, extraccion.id_cita)


def _tipo_de_laboratorio(unidad):
    """
    Reutiliza la primera tipificación del donante.

    Si todavía no tiene, y la cita es para una solicitud, el sorteo elige
    un grupo que pueda donarle a ese receptor. Así la unidad queda asociada
    cuando el resultado no es reactivo y hay cupo. Sin solicitud, cualquier
    grupo del catálogo.
    """
    tipo = Usuario.tipo_confirmado(unidad.id_donante)
    if tipo is not None:
        return tipo
    tipos = TipoSangre.query.order_by(TipoSangre.id_tipo_sangre).all()
    if not tipos:
        db.session.rollback()
        raise ErrorSimulacion("Falta el catálogo de grupos sanguíneos.")
    cita = _cita_de_la_unidad(unidad)
    solicitud = None
    if cita is not None and cita.id_solicitud is not None:
        solicitud = db.session.get(Solicitud, cita.id_solicitud)
    if solicitud is not None:
        admitidos = {
            fila.id_tipo_donante
            for fila in CompatibilidadAboRh.query.filter_by(
                id_tipo_receptor=solicitud.id_tipo_sangre).all()
        }
        compatibles = [t for t in tipos if t.id_tipo_sangre in admitidos]
        if compatibles:
            return random.choice(compatibles)
    return random.choice(tipos)


def _cupo_libre(solicitud):
    ocupadas = (Asignacion.query
                .filter_by(id_solicitud=solicitud.id_solicitud)
                .count())
    return ocupadas < solicitud.unidades_requeridas


def _asignar_solicitud_de_la_cita(unidad, personal, tipo):
    """Asigna solo si la cita de la extracción sigue dirigida a una solicitud."""
    cita = _cita_de_la_unidad(unidad)
    if cita is None or cita.id_solicitud is None:
        return
    solicitud = db.session.get(Solicitud, cita.id_solicitud)
    if solicitud is None:
        return
    if solicitud.estado not in Solicitud.ABIERTAS:
        _soltar_vinculo(cita, personal)
        return
    if solicitud.id_tipo_sangre is None:
        return
    compatible = (CompatibilidadAboRh.query
                  .filter_by(id_tipo_donante=tipo.id_tipo_sangre,
                             id_tipo_receptor=solicitud.id_tipo_sangre)
                  .first())
    if compatible is None or not _cupo_libre(solicitud):
        _soltar_vinculo(cita, personal)
        return
    asignacion = Asignacion(
        id_unidad=unidad.id_unidad,
        id_solicitud=solicitud.id_solicitud,
        fecha=datetime.now(),
    )
    db.session.add(asignacion)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "ASIGNACION",
                        asignacion.id_asignacion, Auditoria.ALTA)
    unidad.id_solicitud = solicitud.id_solicitud
    _transicion(unidad, personal, Unidad.ASIGNADA)
    solicitud.unidades_asignadas = (Asignacion.query
                                    .filter_by(id_solicitud=solicitud.id_solicitud)
                                    .count())
    if solicitud.unidades_asignadas >= solicitud.unidades_requeridas:
        _consumir_asignadas(solicitud, personal)
    db.session.add(Notificacion(
        id_usuario=solicitud.id_solicitante,
        id_solicitud=solicitud.id_solicitud,
        tipo=Notificacion.ASIGNACION_SOLICITANTE,
        mensaje="Se asignó una unidad a tu solicitud.",
    ))
    if solicitud.unidades_asignadas >= solicitud.unidades_requeridas:
        _cambiar_estado(solicitud, Solicitud.CERRADA, personal)
        _soltar_citas(solicitud, personal)
        db.session.add(Notificacion(
            id_usuario=solicitud.id_solicitante,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.META_COMPLETA,
            mensaje="La cantidad publicada de tu solicitud ya se completó.",
        ))


def _consumir_asignadas(solicitud, personal):
    """Al completarse la solicitud, cada unidad asignada pasa a Utilizada."""
    unidades = (Unidad.query
                .filter_by(id_solicitud=solicitud.id_solicitud,
                           estado=Unidad.ASIGNADA)
                .all())
    for unidad in unidades:
        _transicion(unidad, personal, Unidad.UTILIZADA)


def _liberar_unidades(solicitud, personal):
    """Asignada vuelve a En stock y deja de ocupar la solicitud vencida."""
    unidades = (Unidad.query
                .filter_by(id_solicitud=solicitud.id_solicitud,
                           estado=Unidad.ASIGNADA)
                .all())
    for unidad in unidades:
        _transicion(unidad, personal, Unidad.EN_STOCK,
                    motivo="La solicitud venció y la unidad vuelve al stock.")
        unidad.id_solicitud = None
        asignacion = Asignacion.query.filter_by(id_unidad=unidad.id_unidad).first()
        if asignacion is not None:
            Auditoria.registrar(personal.id_usuario, "ASIGNACION",
                                asignacion.id_asignacion, Auditoria.BAJA)
            db.session.delete(asignacion)
    db.session.flush()
    solicitud.unidades_asignadas = (Asignacion.query
                                    .filter_by(id_solicitud=solicitud.id_solicitud)
                                    .count())


def fecha_de_publicacion(solicitud):
    """Día en que quedó Publicada. Si nació así, vale fecha_creacion."""
    fila = (HistorialSolicitud.query
            .filter_by(id_solicitud=solicitud.id_solicitud,
                       estado_nuevo=Solicitud.PUBLICADA)
            .order_by(HistorialSolicitud.fecha_hora)
            .first())
    if fila is not None:
        return fila.fecha_hora.date()
    return solicitud.fecha_creacion.date()


def vencer_publicadas(hoy=None):
    """
    A los 7 días de publicada, si sigue Publicada: pasa a Vencida,
    libera sus unidades asignadas y avisa al solicitante. Una sola vez.
    Lo firma Sistema, no un operador.
    """
    from app.controllers.comun.estados import solicitud_vencida

    sistema = usuario_sistema()
    hoy = hoy or date.today()
    vencidas = 0
    for solicitud in Solicitud.query.filter_by(estado=Solicitud.PUBLICADA).all():
        if not solicitud_vencida(fecha_de_publicacion(solicitud), hoy):
            continue
        _liberar_unidades(solicitud, sistema)
        _cambiar_estado(solicitud, Solicitud.VENCIDA, sistema)
        db.session.add(Notificacion(
            id_usuario=solicitud.id_solicitante,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.SOLICITUD_VENCIDA,
            mensaje="Tu solicitud venció a los 7 días de publicada y no se completó.",
        ))
        vencidas += 1
    return vencidas


def _soltar_vinculo(cita, personal):
    cita.id_solicitud = None
    if cita.tipo_cita == Cita.SOLIDARIA:
        cita.tipo_cita = Cita.ALTRUISTA
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.MODIFICACION)


def _cambiar_estado(solicitud, destino, personal):
    anterior = solicitud.estado
    if anterior == destino:
        return
    solicitud.estado = destino
    db.session.add(HistorialSolicitud(
        id_solicitud=solicitud.id_solicitud,
        estado_anterior=anterior,
        estado_nuevo=destino,
        fecha_hora=datetime.now(),
    ))
    Auditoria.registrar(personal.id_usuario, "SOLICITUD",
                        solicitud.id_solicitud, Auditoria.CAMBIO_ESTADO)


def _soltar_citas(solicitud, personal):
    """RN08: las citas dirigidas activas dejan de apuntar a la solicitud."""
    citas = (Cita.query
             .filter(Cita.id_solicitud == solicitud.id_solicitud,
                     Cita.estado.in_(Cita.ACTIVAS))
             .all())
    for cita in citas:
        cita.id_solicitud = None
        if cita.tipo_cita == Cita.SOLIDARIA:
            cita.tipo_cita = Cita.ALTRUISTA
        Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                            Auditoria.MODIFICACION)


def solicitudes_publicadas():
    hoy = date.today()
    return (Solicitud.query
            .filter(Solicitud.estado == Solicitud.PUBLICADA,
                    Solicitud.consentimiento_publicacion.is_(True),
                    (Solicitud.fecha_limite.is_(None)) | (Solicitud.fecha_limite >= hoy))
            .order_by(Solicitud.fecha_creacion.desc())
            .all())


def candidatos_de(solicitud):
    """Donantes cuyo grupo ABO/Rh puede servir a ese receptor. Es preselección."""
    ids = [fila.id_tipo_donante for fila in CompatibilidadAboRh.query.filter_by(
        id_tipo_receptor=solicitud.id_tipo_sangre).all()]
    if not ids:
        return []
    primera = (
        db.session.query(Unidad.id_donante.label("id_donante"),
                         ResultadoLaboratorio.id_tipo_sangre.label("id_tipo_sangre"))
        .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
        .distinct(Unidad.id_donante)
        .order_by(Unidad.id_donante,
                  ResultadoLaboratorio.fecha.asc(),
                  ResultadoLaboratorio.id_resultado.asc())
        .subquery()
    )
    return (Usuario.query
            .join(primera, primera.c.id_donante == Usuario.id_usuario)
            .filter(primera.c.id_tipo_sangre.in_(ids),
                    Usuario.estado.is_(True),
                    Usuario.cuenta_suprimida.is_(False),
                    Usuario.id_usuario != solicitud.id_solicitante)
            .order_by(Usuario.apellido)
            .all())


def _avisar_compatibles(solicitud):
    """Aviso de preselección. No afirma compatibilidad definitiva ni nombra al paciente."""
    if solicitud.id_tipo_sangre is None:
        return
    texto = (
        "Hay una solicitud de donación que podría coincidir con tu grupo. "
        "Es una preselección por ABO y Rh: la compatibilidad definitiva "
        "la confirma el personal de salud."
    )
    ahora = datetime.now()
    for donante in candidatos_de(solicitud):
        db.session.add(Notificacion(
            id_usuario=donante.id_usuario,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.PRESELECCION_COMPATIBLE,
            mensaje=texto,
            fecha_envio=ahora,
        ))


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


def agendar_compatibilidad(id_muestra):
    """Encola la tipificación y el PAI de una muestra, sin crear unidades."""
    app = current_app._get_current_object()
    clave = ("muestra", id_muestra)
    with _en_curso_lock:
        if clave in _en_curso:
            return
        _en_curso.add(clave)
    threading.Thread(
        target=_tarea_compatibilidad,
        args=(app, id_muestra),
        name=f"compatibilidad-{id_muestra}",
        daemon=True,
    ).start()


def _tarea_compatibilidad(app, id_muestra):
    try:
        time.sleep(DEMORA_LABORATORIO_SEGUNDOS)
        with app.app_context():
            simular_compatibilidad(id_muestra)
    except Exception:
        logger.exception("No se pudo simular la muestra %s", id_muestra)
        db.session.rollback()
    finally:
        with _en_curso_lock:
            _en_curso.discard(("muestra", id_muestra))


def simular_compatibilidad(id_muestra):
    """
    Tipifica la muestra y registra el PAI.

    Si el paciente ya tiene tipificación, se reutiliza y no se pisa.
    El PAI positivo difiere y abre consejería. No cambia el consentimiento
    ni descarta unidades. Publica solo con consentimiento y resultado.
    """
    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:clave)"),
        {"clave": 1_000_000 + id_muestra},
    )
    muestra = db.session.get(MuestraCompatibilidad, id_muestra)
    if muestra is None:
        db.session.rollback()
        return
    if ResultadoCompatibilidad.query.filter_by(id_muestra=muestra.id_muestra).first():
        db.session.rollback()
        return

    extraccion = db.session.get(Extraccion, muestra.id_extraccion)
    cita = db.session.get(Cita, extraccion.id_cita) if extraccion else None
    personal = db.session.get(Usuario, extraccion.id_personal) if extraccion else None
    solicitud = db.session.get(Solicitud, muestra.id_solicitud)
    if cita is None or personal is None or solicitud is None:
        db.session.rollback()
        raise ErrorSimulacion("La muestra no tiene extracción, personal o solicitud.")

    db.session.execute(
        text("SELECT pg_advisory_xact_lock(CAST(:clase AS integer), CAST(:donante AS integer))"),
        {"clase": 2, "donante": cita.id_usuario},
    )
    tipo = Usuario.tipo_confirmado(cita.id_usuario)
    if tipo is None:
        tipos = TipoSangre.query.order_by(TipoSangre.id_tipo_sangre).all()
        if not tipos:
            db.session.rollback()
            raise ErrorSimulacion("Falta el catálogo de grupos sanguíneos.")
        tipo = random.choice(tipos)

    positivo = random.random() < PROBABILIDAD_REACTIVO
    nombre = (ResultadoCompatibilidad.PAI_POSITIVO if positivo
              else ResultadoCompatibilidad.PAI_NEGATIVO)
    causa = Diferimiento.query.filter_by(nombre=nombre).first()
    if causa is None:
        db.session.rollback()
        raise ErrorSimulacion("Falta el PAI en el catálogo de diferimientos.")

    resultado = ResultadoCompatibilidad(
        id_muestra=muestra.id_muestra,
        id_tipo_sangre=tipo.id_tipo_sangre,
        id_diferimiento=causa.id_diferimiento,
        fecha=datetime.now(),
    )
    db.session.add(resultado)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "RESULTADO_COMPATIBILIDAD",
                        resultado.id_resultado_compatibilidad, Auditoria.ALTA)

    if solicitud.id_tipo_sangre is None:
        solicitud.id_tipo_sangre = tipo.id_tipo_sangre
    if (solicitud.consentimiento_publicacion
            and solicitud.estado == Solicitud.CREADA):
        _cambiar_estado(solicitud, Solicitud.PUBLICADA, personal)
    if solicitud.estado == Solicitud.PUBLICADA:
        _avisar_compatibles(solicitud)

    if positivo:
        registro = RegistroDiferimiento(
            id_donante=cita.id_usuario,
            id_diferimiento=causa.id_diferimiento,
            id_cita=cita.id_cita,
            id_personal=None,
            origen=RegistroDiferimiento.LABORATORIO,
            institucion_diagnostico=INSTITUCION_LOCAL,
            fecha_inicio=date.today(),
            id_resultado_compatibilidad=resultado.id_resultado_compatibilidad,
        )
        db.session.add(registro)
        db.session.flush()
        db.session.refresh(registro)
        if registro.fecha_fin is not None:
            raise ErrorSimulacion(
                "Un diferimiento permanente de laboratorio no admite fecha de fin.")
        Auditoria.registrar(personal.id_usuario, "REGISTRO_DIFERIMIENTO",
                            registro.id_registro, Auditoria.ALTA)
        db.session.add(Notificacion(
            id_usuario=cita.id_usuario,
            tipo=Notificacion.CITACION_GENERICA,
            mensaje=("El banco de sangre te pide agendar una consejería presencial. "
                     "Entrá a Consejería en el portal y elegí día y horario. "
                     "El motivo se conversa en el servicio."),
        ))
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0]) from exc


def marcar_vencidas():
    """Pasa a Vencida una unidad cuya fecha ya se superó. Sale del stock."""
    sistema = usuario_sistema()
    hoy = date.today()
    unidades = (Unidad.query
                .filter(Unidad.fecha_vencimiento.isnot(None),
                        Unidad.fecha_vencimiento < hoy,
                        Unidad.estado.in_((Unidad.EN_STOCK, Unidad.ASIGNADA)))
                .all())
    for unidad in unidades:
        _transicion(unidad, sistema, Unidad.VENCIDA,
                    motivo="Fecha de vencimiento ya cargada, superada.")
    return len(unidades)


def aplicar_vencimientos(hoy=None):
    """Cierra solicitudes y unidades vencidas. Las firma Sistema."""
    try:
        n_sol = vencer_publicadas(hoy)
        n_uni = marcar_vencidas()
        db.session.commit()
        return n_sol, n_uni
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0]) from exc
