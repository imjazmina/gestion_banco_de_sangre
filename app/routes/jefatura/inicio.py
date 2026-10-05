"""Inicio de jefatura: citaciones del día de consejería."""
from flask import Blueprint

from app.controllers.comun.acceso import pintar, requiere
from app.controllers.comun.informes import vista_previa
from app.controllers.jefatura import consejeria
from app.models import Usuario, db

jefatura_inicio_bp = Blueprint("jefatura_inicio", __name__, url_prefix="/jefatura")

COLORES = {
    "Pendiente": "#2563EB",
    "Realizada": "#059669",
    "Ausente": "#D97706",
}


@jefatura_inicio_bp.get("/")
@requiere("jef", "jefatura_auth.ingresar")
def inicio():
    filas = consejeria.citaciones()
    orden = ["Pendiente", "Realizada", "Ausente"]
    total = len(filas) or 1
    resumen = []
    for estado in orden:
        n = sum(1 for c in filas if c.estado == estado)
        resumen.append({"estado": estado, "n": n, "pct": round(100 * n / total, 1),
                        "color": COLORES[estado]})
    pendiente = next((c for c in filas if c.estado == "Pendiente"), None)
    previa = vista_previa()
    return pintar(
        "jefatura/inicio.html",
        resumen=resumen,
        proxima=_fila(pendiente) if pendiente else None,
        siguientes=[_fila(c) for c in filas if c.estado == "Pendiente"][1:4],
        previa=previa,
    )


def _fila(citacion):
    donante = db.session.get(Usuario, citacion.id_donante)
    return {
        "id": citacion.id_citacion,
        "hora": citacion.horario.hora_inicio.strftime("%H:%M") if citacion.horario else "—",
        "donante": donante.nombre_completo if donante else "—",
        "ci": donante.documento if donante else "",
        "estado": citacion.estado,
    }
