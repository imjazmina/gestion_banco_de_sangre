"""
Solicitudes de donantes, vistas desde el portal.

El portal es de solo lectura sobre esta tabla: quien publica y cierra las
solicitudes es el personal, desde el panel de administración. Acá el donante
únicamente las consulta para decidir a quién ayudar.

Nunca se muestra el documento del solicitante: la solicitud se difunde para
conseguir donantes, no para exponer sus datos personales.
"""
from datetime import date, datetime

from app.models import Notificacion, Solicitud, Usuario, db


def activas():
    """
    Solicitudes publicadas que siguen vigentes.

    Las vencidas quedan afuera aunque su estado todavía diga 'Publicada': el
    estado lo cierra un proceso del panel, pero la fecha límite ya pasó y no
    tiene sentido pedir donantes para eso.
    """
    hoy = date.today()
    return (Solicitud.query
            .filter(Solicitud.estado == Solicitud.PUBLICADA,
                    Solicitud.consentimiento_publicacion.is_(True),
                    (Solicitud.fecha_limite.is_(None)) | (Solicitud.fecha_limite >= hoy),
                    Solicitud.unidades_asignadas < Solicitud.unidades_requeridas)
            .order_by(Solicitud.fecha_limite.asc().nullslast(),
                      Solicitud.fecha_creacion.desc())
            .all())


def por_id(id_solicitud):
    """Una solicitud publicada concreta, o None. La usa el agendamiento."""
    return next((s for s in activas() if s.id_solicitud == id_solicitud), None)


def por_cedula(documento, id_usuario):
    """Solicitud privada del paciente, para vincular una donación."""
    documento = (documento or "").strip()
    if not documento:
        return None
    return (Solicitud.query
            .join(Usuario, Usuario.id_usuario == Solicitud.id_solicitante)
            .filter(Usuario.documento == documento,
                    Solicitud.estado == Solicitud.CREADA,
                    Solicitud.consentimiento_publicacion.is_(False),
                    Solicitud.id_solicitante != id_usuario,
                    Solicitud.unidades_asignadas < Solicitud.unidades_requeridas)
            .order_by(Solicitud.fecha_creacion.desc())
            .first())


def vinculable(id_solicitud, usuario):
    """Pública por id, o privada si el id es de una solicitud Creada."""
    if not id_solicitud:
        return None
    publica = por_id(id_solicitud)
    if publica is not None and publica.id_solicitante != usuario.id_usuario:
        return publica
    privada = db.session.get(Solicitud, id_solicitud)
    if (privada is not None
            and privada.estado == Solicitud.CREADA
            and not privada.consentimiento_publicacion
            and privada.id_solicitante != usuario.id_usuario
            and privada.unidades_asignadas < privada.unidades_requeridas):
        return privada
    return None


def avisar_abierta(usuario):
    """Una notificación por solicitud abierta. No se repite en cada ingreso."""
    abiertas = (Solicitud.query
                .filter(Solicitud.id_solicitante == usuario.id_usuario,
                        Solicitud.estado.in_(Solicitud.ABIERTAS))
                .all())
    nuevas = False
    for solicitud in abiertas:
        ya = (Notificacion.query
              .filter_by(id_usuario=usuario.id_usuario,
                         id_solicitud=solicitud.id_solicitud,
                         tipo=Notificacion.SOLICITUD_ABIERTA)
              .first())
        if ya is not None:
            continue
        db.session.add(Notificacion(
            id_usuario=usuario.id_usuario,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.SOLICITUD_ABIERTA,
            mensaje="Solicitud abierta",
            fecha_envio=datetime.now(),
        ))
        nuevas = True
    if nuevas:
        db.session.commit()
