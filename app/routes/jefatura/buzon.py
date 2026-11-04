"""Lectura del buzón. No se responde desde acá.

Enfermería entra desde el mismo botón del navbar. La ruta sigue bajo
/jefatura porque ahí vive la pantalla.
"""
from flask import Blueprint, redirect, url_for

from app.controllers.comun.acceso import operador_actual, pintar
from app.controllers.jefatura import consejeria
from app.models import Rol

jefatura_buzon_bp = Blueprint("jefatura_buzon", __name__, url_prefix="/jefatura")


@jefatura_buzon_bp.get("/buzon")
def lista():
    operador = operador_actual()
    if operador is None or operador["rol"] not in (Rol.JEFATURA, Rol.ENFERMERIA):
        return redirect(url_for("licenciado_auth.ingresar"))
    filas = []
    for mensaje in consejeria.mensajes():
        autor = consejeria.autor_de(mensaje)
        filas.append({
            "fecha": mensaje.fecha,
            "autor": autor.nombre_completo if autor else "—",
            "tipo": mensaje.tipo or "—",
            "mensaje": mensaje.mensaje,
        })
    return pintar("jefatura/buzon.html", mensajes=filas)
