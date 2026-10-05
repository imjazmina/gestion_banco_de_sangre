"""Citaciones a consejería y derivación a otro establecimiento."""
from datetime import date

from app.controllers.comun.simulacion import INSTITUCION_LOCAL
from app.models import (
    Auditoria, Buzon, CitacionConsejeria, Derivacion, RegistroDiferimiento,
    Usuario, db,
)


class ErrorConsejeria(Exception):
    """La acción no se puede guardar."""


def citaciones():
    filas = CitacionConsejeria.query.order_by(CitacionConsejeria.id_citacion.desc()).all()
    return filas


def citacion_por_id(id_citacion):
    return db.session.get(CitacionConsejeria, id_citacion)


def marcar(citacion, estado, personal):
    if estado not in ("Realizada", "Ausente"):
        raise ErrorConsejeria("Ese estado no está en el catálogo de la citación.")
    if citacion.estado != "Pendiente":
        raise ErrorConsejeria("Esa citación ya fue cerrada.")
    citacion.estado = estado
    citacion.id_personal = personal.id_usuario
    Auditoria.registrar(personal.id_usuario, "CITACION_CONSEJERIA",
                        citacion.id_citacion, Auditoria.CAMBIO_ESTADO)
    db.session.commit()


def registro_de(citacion):
    from app.models import ResultadoLaboratorio
    resultado = db.session.get(ResultadoLaboratorio, citacion.id_resultado)
    if resultado is None or resultado.id_registro_diferimiento is None:
        return None
    return db.session.get(RegistroDiferimiento, resultado.id_registro_diferimiento)


def puede_derivar(registro):
    if registro is None:
        return False
    return registro.institucion_diagnostico.strip().lower() != INSTITUCION_LOCAL.lower()


def derivar(registro, personal, establecimiento, motivo):
    if not puede_derivar(registro):
        raise ErrorConsejeria(
            "La derivación solo se registra si el diagnóstico no es de este banco.")
    if Derivacion.query.filter_by(id_registro_diferimiento=registro.id_registro).first():
        raise ErrorConsejeria("Ese diferimiento ya tiene una derivación.")
    establecimiento = (establecimiento or "").strip()
    if not establecimiento:
        raise ErrorConsejeria("Indicá el establecimiento de destino.")
    db.session.add(Derivacion(
        id_registro_diferimiento=registro.id_registro,
        id_personal=personal.id_usuario,
        establecimiento_destino=establecimiento,
        fecha=date.today(),
        motivo_interno=(motivo or "").strip() or None,
    ))
    db.session.commit()


def mensajes():
    return (Buzon.query
            .order_by(Buzon.fecha.desc())
            .all())


def autor_de(mensaje):
    return db.session.get(Usuario, mensaje.id_usuario)
