"""Derivación a otro establecimiento. La registra el licenciado."""
from datetime import date

from app.controllers.comun.simulacion import INSTITUCION_LOCAL
from app.models import Auditoria, Derivacion, db


class ErrorDerivacion(Exception):
    """La derivación no se puede guardar."""


def es_externo(registro):
    if registro is None:
        return False
    return registro.institucion_diagnostico.strip().lower() != INSTITUCION_LOCAL.lower()


def esta_vigente(registro, hoy=None):
    """Permanente, o temporal cuyo fin todavía no llegó."""
    if registro is None:
        return False
    hoy = hoy or date.today()
    return registro.fecha_fin is None or registro.fecha_fin > hoy


def puede_derivar(registro):
    return es_externo(registro) and esta_vigente(registro)


def externo_vigente(id_donante):
    """Hay un diferimiento de otro establecimiento que hoy sigue activo."""
    from app.controllers.portal.agenda import diferimientos_vigentes
    from app.models import Usuario

    usuario = db.session.get(Usuario, id_donante)
    if usuario is None:
        return False
    return any(es_externo(registro) for registro in diferimientos_vigentes(usuario))


def pendientes(registros):
    """Diferimientos vigentes de otro establecimiento, sin derivación."""
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
    if not es_externo(registro):
        raise ErrorDerivacion(
            "La derivación solo se registra si el diagnóstico no es de este banco.")
    if not esta_vigente(registro):
        raise ErrorDerivacion(
            "Ese diferimiento de otro establecimiento ya no está vigente.")
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
