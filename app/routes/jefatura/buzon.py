"""Lectura del buzón. No se responde desde acá."""
from flask import Blueprint

from app.controllers.comun.acceso import pintar, requiere
from app.controllers.jefatura import consejeria

jefatura_buzon_bp = Blueprint("jefatura_buzon", __name__, url_prefix="/jefatura")


@jefatura_buzon_bp.get("/buzon")
@requiere("jef", "jefatura_auth.ingresar")
def lista():
    filas = []
    for mensaje in consejeria.mensajes():
        autor = consejeria.autor_de(mensaje)
        filas.append({
            "fecha": mensaje.fecha,
            "autor": autor.nombre_completo if autor else "—",
            "mensaje": mensaje.mensaje,
        })
    return pintar("jefatura/buzon.html", mensajes=filas)
