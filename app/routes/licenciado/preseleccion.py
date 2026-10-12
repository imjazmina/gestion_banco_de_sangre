"""Preselección ABO/Rh. Lista candidatos. No envía un aviso nuevo."""
from flask import Blueprint

from app.controllers.comun.acceso import pintar, requiere
from app.controllers.comun.simulacion import candidatos_de, solicitudes_publicadas

licenciado_preseleccion_bp = Blueprint(
    "licenciado_preseleccion", __name__, url_prefix="/licenciado")


@licenciado_preseleccion_bp.get("/preseleccion")
@requiere("lic", "licenciado_auth.ingresar")
def ver():
    solicitudes = solicitudes_publicadas()
    grupos = [(s, candidatos_de(s)) for s in solicitudes]
    return pintar("licenciado/preseleccion.html", grupos=grupos)
