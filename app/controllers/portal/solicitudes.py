"""
Solicitudes de donantes, vistas desde el portal.

El portal es de solo lectura sobre esta tabla: quien publica y cierra las
solicitudes es el personal, desde el panel de administración. Acá el donante
únicamente las consulta para decidir a quién ayudar.

Nunca se muestra el documento del solicitante: la solicitud se difunde para
conseguir donantes, no para exponer sus datos personales.
"""
from datetime import date

from app.models import Solicitud


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
    """Una solicitud vigente concreta, o None. La usa el agendamiento."""
    return next((s for s in activas() if s.id_solicitud == id_solicitud), None)
