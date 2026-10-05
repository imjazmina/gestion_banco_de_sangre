"""
Simulación del laboratorio y de las solicitudes publicadas.

Los resultados son sintéticos (RN13). No hay rol de laboratorio ni pantalla
para publicarlos a mano. Publicar una solicitud tampoco tiene pantalla de
solicitante: si no hay ninguna vigente, esta función inserta unas pocas.
"""
import random
from datetime import date, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Asignacion, Auditoria, Cita, CitacionConsejeria, CompatibilidadAboRh,
    Diferimiento, HorarioDisponible, Notificacion, RegistroDiferimiento,
    ResultadoLaboratorio, Rol, Solicitud, TipoSangre, TransicionEstado,
    Unidad, Usuario, UsuarioRol, db,
)

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


def _transicion(unidad, personal, destino, motivo=None):
    db.session.add(TransicionEstado(
        id_unidad=unidad.id_unidad,
        id_personal=personal.id_usuario,
        estado_origen=unidad.estado,
        estado_destino=destino,
        motivo=motivo,
        fecha=datetime.now(),
    ))
    unidad.estado = destino
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


def simular_resultado(unidad, personal):
    """Escribe un resultado al azar y mueve la unidad. No es un análisis real."""
    if unidad.estado != Unidad.EN_LABORATORIO:
        raise ErrorSimulacion("Solo se simula el resultado de una unidad en laboratorio.")
    if ResultadoLaboratorio.query.filter_by(id_unidad=unidad.id_unidad).first():
        raise ErrorSimulacion("Esa unidad ya tiene un resultado simulado.")

    tipo = random.choice(TipoSangre.query.all())
    if tipo is None:
        raise ErrorSimulacion("Falta el catálogo de grupos sanguíneos.")
    reactivo = random.choice((True, False))
    if reactivo:
        _reactivo(unidad, personal, tipo)
    else:
        _no_reactivo(unidad, personal, tipo)
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ErrorSimulacion(str(getattr(exc, "orig", exc)).splitlines()[0])


def _no_reactivo(unidad, personal, tipo):
    db.session.add(ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.NO_REACTIVO,
        fecha=datetime.now(),
    ))
    _transicion(unidad, personal, Unidad.EN_STOCK)
    unidad.id_tipo_sangre = tipo.id_tipo_sangre
    donante = db.session.get(Usuario, unidad.id_donante)
    if donante is not None:
        donante.id_tipo_sangre = tipo.id_tipo_sangre
    _intentar_asignar(unidad, personal, tipo)


def _reactivo(unidad, personal, tipo):
    causa = Diferimiento.query.filter_by(nombre="Serología reactiva").first()
    if causa is None:
        raise ErrorSimulacion("Falta la causa «Serología reactiva» en el catálogo.")
    jefatura = _jefatura()
    if jefatura is None:
        raise ErrorSimulacion("No hay una cuenta de jefatura para firmar la citación.")
    franja = HorarioDisponible.query.filter_by(disponible=True).first()
    if franja is None:
        raise ErrorSimulacion("No hay franjas horarias para citar a consejería.")

    registro = RegistroDiferimiento(
        id_donante=unidad.id_donante,
        id_diferimiento=causa.id_diferimiento,
        id_personal=None,
        origen=RegistroDiferimiento.LABORATORIO,
        institucion_diagnostico=INSTITUCION_LOCAL,
        fecha_inicio=date.today(),
    )
    db.session.add(registro)
    db.session.flush()

    resultado = ResultadoLaboratorio(
        id_unidad=unidad.id_unidad,
        id_diferimiento=causa.id_diferimiento,
        id_registro_diferimiento=registro.id_registro,
        id_tipo_sangre=tipo.id_tipo_sangre,
        resultado=ResultadoLaboratorio.REACTIVO,
        fecha=datetime.now(),
    )
    db.session.add(resultado)
    db.session.flush()
    unidad.id_tipo_sangre = tipo.id_tipo_sangre
    _transicion(unidad, personal, Unidad.DESCARTADA,
                motivo="Resultado simulado reactivo.")

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


def _intentar_asignar(unidad, personal, tipo):
    """Asigna a una solicitud compatible con cupo, si hay alguna."""
    solicitudes = (Solicitud.query
                   .filter(Solicitud.estado == Solicitud.PUBLICADA,
                           Solicitud.consentimiento_publicacion.is_(True),
                           Solicitud.unidades_asignadas < Solicitud.unidades_requeridas)
                   .all())
    for solicitud in solicitudes:
        par = (CompatibilidadAboRh.query
               .filter_by(id_tipo_donante=tipo.id_tipo_sangre,
                          id_tipo_receptor=solicitud.id_tipo_sangre)
               .first())
        if par is None:
            continue
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
        return


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
    """Pasa a Vencida solo si `fecha_vencimiento` ya está cargada y superada."""
    hoy = date.today()
    unidades = (Unidad.query
                .filter(Unidad.fecha_vencimiento.isnot(None),
                        Unidad.fecha_vencimiento < hoy,
                        Unidad.estado.in_((Unidad.EN_STOCK, Unidad.ASIGNADA)))
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
