"""
Historial de estado de cita y de citación, en el mismo flush que el cambio.

Cubre altas y actualizaciones que pasan por la sesión. Si el estado no
cambia, no se agrega fila. En el alta, estado_anterior queda nulo.
"""
from datetime import datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, configure_mappers

_registrado = False


def activar(cita_cls, historial_cita_cls, relacion_cita,
            citacion_cls, historial_citacion_cls, relacion_citacion):
    """Engancha el volcado una sola vez y pide el valor previo del estado."""
    global _registrado
    if _registrado:
        return
    _registrado = True

    configure_mappers()
    for modelo in (cita_cls, citacion_cls):
        modelo.estado.impl.active_history = True

    pares = (
        (cita_cls, historial_cita_cls, relacion_cita),
        (citacion_cls, historial_citacion_cls, relacion_citacion),
    )

    def antes_del_flush(session, flush_context, instances):
        if session.info.get("_registrando_historial"):
            return
        session.info["_registrando_historial"] = True
        try:
            for modelo, historial_cls, relacion in pares:
                _volcar(session, modelo, historial_cls, relacion)
        finally:
            session.info["_registrando_historial"] = False

    event.listen(Session, "before_flush", antes_del_flush)


def _volcar(session, modelo, historial_cls, relacion):
    for obj in list(session.new):
        if not isinstance(obj, modelo) or obj in session.deleted:
            continue
        estado = _estado_a_guardar(obj)
        if not estado:
            continue
        _agregar(session, historial_cls, relacion, obj, None, estado)

    for obj in list(session.dirty):
        if not isinstance(obj, modelo) or obj in session.new or obj in session.deleted:
            continue
        cambio = _cambio_de_estado(obj)
        if cambio is None:
            continue
        anterior, nuevo = cambio
        _agregar(session, historial_cls, relacion, obj, anterior, nuevo)


def _estado_a_guardar(obj):
    if obj.estado:
        return obj.estado
    columna = obj.__class__.__table__.c.estado
    if columna.default is None:
        return None
    valor = columna.default.arg
    if callable(valor):
        valor = valor(None)
    if valor:
        obj.estado = valor
    return valor


def _cambio_de_estado(obj):
    historia = inspect(obj).attrs.estado.history
    if not historia.has_changes():
        return None
    nuevo = historia.added[0] if historia.added else obj.estado
    if not nuevo:
        return None
    if historia.deleted:
        anterior = historia.deleted[0]
    else:
        anterior = inspect(obj).committed_state.get("estado")
    if anterior == nuevo:
        return None
    return anterior, nuevo


def _agregar(session, historial_cls, relacion, obj, anterior, nuevo):
    fila = historial_cls(
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        fecha_hora=datetime.now(),
    )
    setattr(fila, relacion, obj)
    session.add(fila)
