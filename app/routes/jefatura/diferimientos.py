"""Lista de citaciones a consejería."""
from flask import Blueprint

from app.controllers.comun.acceso import pintar, requiere
from app.controllers.jefatura import consejeria
from app.models import Usuario, db

jefatura_diferimientos_bp = Blueprint(
    "jefatura_diferimientos", __name__, url_prefix="/jefatura")


@jefatura_diferimientos_bp.get("/diferimientos")
@requiere("jef", "jefatura_auth.ingresar")
def lista():
    filas = []
    for citacion in consejeria.citaciones():
        donante = db.session.get(Usuario, citacion.id_donante)
        filas.append({
            "id": citacion.id_citacion,
            "hora": citacion.horario.hora_inicio.strftime("%H:%M") if citacion.horario else "—",
            "donante": donante.nombre_completo if donante else "—",
            "ci": donante.documento if donante else "",
            "estado": citacion.estado,
        })
    return pintar(
        "jefatura/diferimientos.html",
        citas=filas,
        total=len(filas),
        pendientes=sum(1 for c in filas if c["estado"] == "Pendiente"),
        realizadas=sum(1 for c in filas if c["estado"] == "Realizada"),
        ausentes=sum(1 for c in filas if c["estado"] == "Ausente"),
    )
