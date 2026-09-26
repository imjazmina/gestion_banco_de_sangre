"""
Datos de la pantalla de entrada.

Hay dos pantallas distintas detrás de la misma URL: el visitante ve el home
público y el donante logueado ve su panel. Se separan acá y no en la
plantilla para que cada consulta se haga solo cuando hace falta.
"""
from datetime import date

from app.models import db, Cita, Solicitud, Notificacion

MESES = {1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun',
         7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic'}


def solicitudes_activas():
    """Cuántas personas están esperando un donante ahora mismo."""
    return Solicitud.query.filter(
        Solicitud.estado == Solicitud.PUBLICADA,
        Solicitud.consentimiento_publicacion.is_(True),
        (Solicitud.fecha_limite.is_(None)) | (Solicitud.fecha_limite >= date.today()),
    ).count()


def proxima_cita(usuario):
    """
    La cita vigente del donante.

    Una cita cuya fecha ya pasó no es "próxima" aunque siga en Pendiente: el
    estado lo cierra el personal cuando el donante se presenta o falta, y
    hasta entonces quedaría colgada en la pantalla como si fuera futura.
    """
    return (Cita.query
            .filter(Cita.id_usuario == usuario.id_usuario,
                    Cita.estado.in_(Cita.ACTIVAS),
                    Cita.fecha_cita >= date.today())
            .order_by(Cita.fecha_cita.asc())
            .first())


def historial(usuario, limite=3):
    """Citas ya cerradas: completadas, canceladas, ausentes o no aptas."""
    return (Cita.query
            .filter(Cita.id_usuario == usuario.id_usuario,
                    db.not_(Cita.estado.in_(Cita.ACTIVAS)))
            .order_by(Cita.fecha_cita.desc())
            .limit(limite)
            .all())


def notificaciones(usuario, limite=3):
    return (Notificacion.query
            .filter_by(id_usuario=usuario.id_usuario)
            .order_by(Notificacion.fecha_envio.desc())
            .limit(limite)
            .all())


def panel(usuario):
    """Todo lo que muestra la pantalla del donante, en una sola llamada."""
    return {
        "cita": proxima_cita(usuario),
        "historial": historial(usuario),
        "avisos": notificaciones(usuario),
        "meses": MESES,
    }
