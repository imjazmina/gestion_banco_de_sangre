"""
Cuándo sale el correo del cuestionario.

El horario no se guarda en una tabla nueva: se calcula como tres horas antes
de `cita.momento`. Si el proceso se reinicia, al arrancar se vuelven a armar
los temporizadores leyendo las citas activas. Antes de enviar se relee la
cita, así una cancelación o un envío ya registrado no producen otro correo.
"""
import threading
from datetime import datetime, timedelta

from flask import current_app

from app.controllers.portal import avisos, cuestionario
from app.models import Cita, db

HORAS_ANTES = avisos.HORAS_ANTES


def plan(ahora, momento, estado, completo, ya_enviado, horas=HORAS_ANTES):
    """
    Qué hacer con el correo de este turno.

    Devuelve (accion, espera_en_segundos). La espera solo importa si la
    acción es «programado».
    """
    if (estado not in Cita.ACTIVAS or completo or ya_enviado
            or momento is None or momento <= ahora):
        return "omitido", 0
    envio = momento - timedelta(hours=horas)
    if envio <= ahora:
        return "inmediato", 0
    return "programado", (envio - ahora).total_seconds()


class Programador:
    """Temporizadores en memoria, uno por cita, rearmables al arrancar."""

    def __init__(self, fabrica=None):
        self._fabrica = fabrica or threading.Timer
        self._timers = {}
        self._lock = threading.Lock()
        self._app = None

    def enganchar(self, app):
        self._app = app

    def agendar(self, cita, url_base, ahora=None):
        """Envía ahora o deja el temporizador a tres horas del inicio."""
        ahora = ahora or datetime.now()
        accion, espera = self._plan_de(cita, ahora)
        self.cancelar(cita.id_cita)
        if accion == "omitido":
            return "omitido"
        if accion == "inmediato":
            return self._enviar(cita.id_cita, url_base, ahora)
        self._armar(cita.id_cita, espera, url_base)
        return "programado"

    def cancelar(self, id_cita):
        """Anula el temporizador pendiente. No toca la cita."""
        with self._lock:
            timer = self._timers.pop(id_cita, None)
        if timer is not None:
            timer.cancelado = True
            timer.cancel()

    def rearmar(self, ahora=None):
        """Vuelve a dejar los envíos que todavía no salieron."""
        ahora = ahora or datetime.now()
        url_base = current_app.config["URL_BASE"].rstrip("/")
        citas = Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()
        for cita in citas:
            if cita.momento is not None and cita.momento > ahora:
                self.agendar(cita, url_base, ahora)

    def _plan_de(self, cita, ahora):
        return plan(
            ahora, cita.momento, cita.estado,
            cuestionario.completo(cita), avisos.ya_enviado(cita))

    def _armar(self, id_cita, espera, url_base):
        def disparar():
            if getattr(timer, "cancelado", False):
                return
            self._disparar(id_cita, url_base)

        timer = self._fabrica(espera, disparar)
        timer.daemon = True
        timer.cancelado = False
        with self._lock:
            self._timers[id_cita] = timer
        timer.start()

    def _disparar(self, id_cita, url_base):
        with self._lock:
            self._timers.pop(id_cita, None)
        if self._app is None:
            self._enviar(id_cita, url_base)
            return
        with self._app.app_context():
            try:
                self._enviar(id_cita, url_base)
            finally:
                db.session.remove()

    def _enviar(self, id_cita, url_base, ahora=None):
        ahora = ahora or datetime.now()
        cita = db.session.get(Cita, id_cita)
        if cita is None:
            return "omitido"
        accion, _espera = self._plan_de(cita, ahora)
        if accion == "omitido":
            return "omitido"
        if accion == "programado":
            return "programado"
        enviado, _detalle = avisos.enviar_cuestionario(cita, url_base)
        return "enviado" if enviado else "fallo"


programador = Programador()
