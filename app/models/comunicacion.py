"""Notificaciones al usuario, buzón de mensajes y bitácora de auditoría."""
from datetime import datetime

from app.models import db


class Notificacion(db.Model):
    """
    Aviso dirigido a un usuario.

    El schema no tiene columna "leido", así que por ahora no hay forma de
    marcar una notificación como vista: se listan todas.
    """
    __tablename__ = "notificacion"

    id_notificacion = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_cita = db.Column(db.Integer, db.ForeignKey("cita.id_cita"))
    id_citacion = db.Column(
        db.Integer, db.ForeignKey("citacion_consejeria.id_citacion"))
    id_solicitud = db.Column(db.Integer, db.ForeignKey("solicitud.id_solicitud"))
    tipo = db.Column(db.String(40), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    fecha_envio = db.Column(db.DateTime, nullable=False, default=datetime.now)

    CONFIRMACION_CITA = "CONFIRMACION_CITA"
    # El portal lo usa para el correo con el cuestionario previo: que
    # exista sobre una cita significa que ya se le envió, y así no se
    # manda dos veces.
    RECORDATORIO_CITA = "RECORDATORIO_CITA"
    HABILITACION = "HABILITACION"
    AGRADECIMIENTO = "AGRADECIMIENTO"
    ASIGNACION_DONANTE = "ASIGNACION_DONANTE"
    ASIGNACION_SOLICITANTE = "ASIGNACION_SOLICITANTE"
    META_COMPLETA = "META_COMPLETA"
    CITACION_GENERICA = "CITACION_GENERICA"


class Buzon(db.Model):
    """
    Mensaje al equipo del banco de sangre.

    id_usuario es NOT NULL en el schema, así que el mensaje queda asociado a
    quien lo escribe: no se puede enviar de forma anónima ni sin sesión.
    """
    __tablename__ = "buzon"

    id_mensaje = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)


class Auditoria(db.Model):
    """
    Bitácora de acciones sensibles.

    No se elimina: el trigger trg_auditoria_no_borrar rechaza el DELETE.
    """
    __tablename__ = "auditoria"

    id_auditoria = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    entidad = db.Column(db.String(40), nullable=False)
    id_entidad = db.Column(db.Integer, nullable=False)
    accion = db.Column(db.String(30), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    ALTA = "ALTA"
    MODIFICACION = "MODIFICACION"
    BAJA = "BAJA"
    LOGIN = "LOGIN"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    SUPRESION_CUENTA = "SUPRESION_CUENTA"

    @classmethod
    def registrar(cls, id_usuario, entidad, id_entidad, accion):
        """Atajo para dejar el rastro sin repetir el mismo bloque en cada vista."""
        db.session.add(cls(id_usuario=id_usuario, entidad=entidad,
                           id_entidad=id_entidad, accion=accion))
