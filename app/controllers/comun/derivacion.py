"""Derivación a otro establecimiento. La registra el licenciado."""
from datetime import date

from app.controllers.comun.simulacion import INSTITUCION_LOCAL
from app.models import Auditoria, Derivacion, db


class ErrorDerivacion(Exception):
    """La derivación no se puede guardar."""


def puede_derivar(registro):
    if registro is None:
        return False
    return registro.institucion_diagnostico.strip().lower() != INSTITUCION_LOCAL.lower()


def pendientes(registros):
    """Registros de otro establecimiento que todavía no tienen derivación."""
    salida = []
    for registro in registros:
        if not puede_derivar(registro):
            continue
        ya = Derivacion.query.filter_by(
            id_registro_diferimiento=registro.id_registro).first()
        if ya is None:
            salida.append(registro)
    return salida


def registrar(registro, personal, establecimiento, motivo):
    if not puede_derivar(registro):
        raise ErrorDerivacion(
            "La derivación solo se registra si el diagnóstico no es de este banco.")
    if Derivacion.query.filter_by(
            id_registro_diferimiento=registro.id_registro).first():
        raise ErrorDerivacion("Ese diferimiento ya tiene una derivación.")
    establecimiento = (establecimiento or "").strip()
    if not establecimiento:
        raise ErrorDerivacion("Indicá el establecimiento de destino.")
    fila = Derivacion(
        id_registro_diferimiento=registro.id_registro,
        id_personal=personal.id_usuario,
        establecimiento_destino=establecimiento,
        fecha=date.today(),
        motivo_interno=(motivo or "").strip() or None,
    )
    db.session.add(fila)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "DERIVACION",
                        fila.id_derivacion, Auditoria.ALTA)
    db.session.commit()
    return fila
