"""Citaciones a consejería: cierre del día y consulta del historial."""
from datetime import date

from app.models import (
    Auditoria, Buzon, CitacionConsejeria, HistorialCitaConsejeria,
    RegistroDiferimiento, Usuario, db,
)


class ErrorConsejeria(Exception):
    """La acción no se puede guardar."""


def citaciones():
    filas = CitacionConsejeria.query.order_by(CitacionConsejeria.id_citacion.desc()).all()
    return filas


def citacion_por_id(id_citacion):
    return db.session.get(CitacionConsejeria, id_citacion)


def marcar(citacion, estado, personal):
    """Desde el día de atención marca ausente o completada. No confirma ni cancela."""
    if estado not in (
            CitacionConsejeria.AUSENTE, CitacionConsejeria.COMPLETADA):
        raise ErrorConsejeria(
            "La confirmación la hace el donante. Jefatura marca ausente o completada.")
    if citacion.estado not in CitacionConsejeria.ABIERTAS:
        raise ErrorConsejeria("Esa citación ya fue cerrada.")
    if citacion.estado == estado:
        raise ErrorConsejeria("La citación ya está en ese estado.")
    if citacion.fecha_hora is None or citacion.fecha_hora.date() > date.today():
        raise ErrorConsejeria("Ese estado se registra el día de atención, no antes.")
    citacion.estado = estado
    citacion.id_personal = personal.id_usuario
    Auditoria.registrar(personal.id_usuario, "CITACION_CONSEJERIA",
                        citacion.id_citacion, Auditoria.CAMBIO_ESTADO)
    db.session.commit()


def evolucion(citacion):
    """Estados inmutables y auditoría. La reprogramación solo está en auditoría."""
    estados = (HistorialCitaConsejeria.query
               .filter_by(id_cita_consejeria=citacion.id_citacion)
               .order_by(HistorialCitaConsejeria.fecha_hora,
                         HistorialCitaConsejeria.id_historial_cita_consejeria)
               .all())
    acciones = (Auditoria.query
                .filter_by(entidad="CITACION_CONSEJERIA",
                           id_entidad=citacion.id_citacion)
                .order_by(Auditoria.fecha, Auditoria.id_auditoria)
                .all())
    return estados, acciones


def registros_de(citacion):
    """Diferimientos de laboratorio asociados a ese resultado. Puede haber varios."""
    if citacion.id_resultado is not None:
        return (RegistroDiferimiento.query
                .filter_by(id_resultado=citacion.id_resultado)
                .order_by(RegistroDiferimiento.id_registro)
                .all())
    if citacion.id_resultado_compatibilidad is not None:
        return (RegistroDiferimiento.query
                .filter_by(id_resultado_compatibilidad=citacion.id_resultado_compatibilidad)
                .order_by(RegistroDiferimiento.id_registro)
                .all())
    return []


def mensajes():
    return (Buzon.query
            .order_by(Buzon.fecha.desc())
            .all())


def autor_de(mensaje):
    return db.session.get(Usuario, mensaje.id_usuario)
