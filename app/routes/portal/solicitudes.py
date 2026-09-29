"""
Listado de personas que necesitan donantes.

Solo lectura: publicar y cerrar solicitudes es del panel de administración.
"""
from flask import Blueprint, render_template

from app.controllers.portal import solicitudes as ctrl
from app.controllers.sesion import requiere_login, usuario_actual

solicitudes_bp = Blueprint("solicitudes", __name__, url_prefix="/solicitudes")


@solicitudes_bp.get("/")
@requiere_login
def listar():
    usuario = usuario_actual()
    return render_template("portal/solicitudes/lista.html",
                           solicitudes=ctrl.activas(),
                           id_actual=usuario.id_usuario)
