"""
Pasa a Ausente lo que sigue abierto una hora después del horario.

Cita: solo desde Confirmada, que es el único paso que admite el modelo.
La espontánea no entra: la persona ya está en la sala. Si hay medición,
cuestionario de sala o extracción, la atención empezó y la cita sigue.

Consejería: Pendiente o Confirmada, con fecha y hora cargadas. Realizada
es la atención. Sin horario no hay plazo que correr.

Lo firma el usuario Sistema. El historial lo agrega el flush.
"""
import threading
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Auditoria, Cita, CitacionConsejeria, Cuestionario, Extraccion, Medicion, db,
)

ESPERA = timedelta(hours=1)
_INTERVALO = 60
_lock = threading.Lock()
_enganchado = False


def plazo_cumplido(momento, ahora, espera=ESPERA):
    """True cuando ya pasó la espera desde el inicio del turno."""
    return momento is not None and momento + espera <= ahora


def marcar(ahora=None):
    """Cierra las que vencieron. Devuelve cuántas pasaron a Ausente."""
    from app.controllers.comun.simulacion import usuario_sistema
    from app.controllers.licenciado.jornada import es_espontanea

    ahora = ahora or datetime.now()
    sistema = usuario_sistema()
    n = 0

    citas = Cita.query.filter_by(estado=Cita.CONFIRMADA).all()
    candidatas = [
        cita for cita in citas
        if plazo_cumplido(cita.momento, ahora) and not es_espontanea(cita)
    ]
    atendidas = _con_atencion([cita.id_cita for cita in candidatas])
    for cita in candidatas:
        if cita.id_cita in atendidas:
            continue
        cita.id_personal = sistema.id_usuario
        cita.estado = Cita.AUSENTE
        Auditoria.registrar(
            sistema.id_usuario, "CITA", cita.id_cita, Auditoria.CAMBIO_ESTADO)
        n += 1

    citaciones = CitacionConsejeria.query.filter(
        CitacionConsejeria.estado.in_(CitacionConsejeria.ABIERTAS)).all()
    for citacion in citaciones:
        if not plazo_cumplido(citacion.fecha_hora, ahora):
            continue
        citacion.id_personal = sistema.id_usuario
        citacion.estado = CitacionConsejeria.AUSENTE
        Auditoria.registrar(
            sistema.id_usuario, "CITACION_CONSEJERIA", citacion.id_citacion,
            Auditoria.CAMBIO_ESTADO)
        n += 1

    if n:
        db.session.commit()
    return n


def _con_atencion(ids):
    """Citas en las que el personal ya empezó la atención."""
    if not ids:
        return set()
    vistos = set()
    consultas = (
        db.session.query(Medicion.id_cita).filter(Medicion.id_cita.in_(ids)),
        db.session.query(Extraccion.id_cita).filter(Extraccion.id_cita.in_(ids)),
        db.session.query(Cuestionario.id_cita).filter(
            Cuestionario.id_cita.in_(ids),
            Cuestionario.id_personal.isnot(None)),
    )
    for consulta in consultas:
        vistos.update(fila[0] for fila in consulta)
    return vistos


def enganchar(app):
    """Revisa cada minuto en el proceso que atiende pedidos."""
    global _enganchado
    with _lock:
        if _enganchado:
            return
        _enganchado = True

    def ciclo():
        with app.app_context():
            try:
                marcar()
            except SQLAlchemyError:
                db.session.rollback()
            finally:
                db.session.remove()
        timer = threading.Timer(_INTERVALO, ciclo)
        timer.daemon = True
        timer.start()

    timer = threading.Timer(_INTERVALO, ciclo)
    timer.daemon = True
    timer.start()
