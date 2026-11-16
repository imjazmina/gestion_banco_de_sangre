"""Citaciones a consejería: cierre del día y consulta del historial."""
from datetime import date

from app.controllers.comun.estados import CITACION_CERRADA, id_al_cerrar
from app.models import (
    Auditoria, Buzon, CitacionConsejeria, DetalleDiferimiento, Extraccion,
    HistorialCitaConsejeria, MuestraCompatibilidad, RegistroDiferimiento,
    ResultadoCompatibilidad, Usuario, db,
)


class ErrorConsejeria(Exception):
    """La acción no se puede guardar."""


def citaciones():
    filas = CitacionConsejeria.query.order_by(CitacionConsejeria.id_citacion.desc()).all()
    return filas


def citacion_por_id(id_citacion):
    return db.session.get(CitacionConsejeria, id_citacion)


def marcar(citacion, estado, personal, observaciones=None):
    """Desde el día de atención marca ausente o realizada. No confirma ni cancela.

    `observaciones` es opcional: lo que el personal anote queda en la citación.
    """
    if estado not in (
            CitacionConsejeria.AUSENTE, CitacionConsejeria.REALIZADA):
        raise ErrorConsejeria(
            "La confirmación la hace el donante. Jefatura marca ausente o realizada.")
    if citacion.estado not in CitacionConsejeria.ABIERTAS:
        raise ErrorConsejeria("Esa citación ya fue cerrada.")
    if citacion.estado == estado:
        raise ErrorConsejeria("La citación ya está en ese estado.")
    if citacion.fecha_hora is None or citacion.fecha_hora.date() > date.today():
        raise ErrorConsejeria("Ese estado se registra el día de atención, no antes.")
    citacion.id_personal = id_al_cerrar(
        estado, personal, CITACION_CERRADA, ErrorConsejeria)
    citacion.estado = estado
    if observaciones is not None:
        citacion.observaciones = observaciones.strip() or None
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
        return (DetalleDiferimiento.query
                .filter_by(id_resultado=citacion.id_resultado)
                .order_by(DetalleDiferimiento.id_detalle)
                .all())
    if citacion.id_resultado_compatibilidad is not None:
        # La muestra no enlaza el detalle: se llega por la cita de la extracción.
        resultado = db.session.get(
            ResultadoCompatibilidad, citacion.id_resultado_compatibilidad)
        if resultado is None or resultado.id_diferimiento is None:
            return []
        muestra = db.session.get(MuestraCompatibilidad, resultado.id_muestra)
        if muestra is None:
            return []
        extraccion = db.session.get(Extraccion, muestra.id_extraccion)
        if extraccion is None:
            return []
        return (DetalleDiferimiento.query
                .join(RegistroDiferimiento)
                .filter(RegistroDiferimiento.id_cita == extraccion.id_cita,
                        RegistroDiferimiento.origen == RegistroDiferimiento.LABORATORIO,
                        DetalleDiferimiento.id_diferimiento == resultado.id_diferimiento)
                .order_by(DetalleDiferimiento.id_detalle)
                .all())
    return []


def mensajes():
    return (Buzon.query
            .order_by(Buzon.fecha.desc())
            .all())


def autor_de(mensaje):
    return db.session.get(Usuario, mensaje.id_usuario)
