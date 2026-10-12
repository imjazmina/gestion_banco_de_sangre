"""Informes simulados de enfermería."""
from flask import Blueprint, Response, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun import informes
from app.controllers.comun.simulacion import marcar_vencidas

licenciado_informes_bp = Blueprint(
    "licenciado_informes", __name__, url_prefix="/licenciado")


def _vista():
    desde, hasta, error = informes.leer_periodo(
        request.args.get("desde"), request.args.get("hasta"))
    return informes.presentacion(desde, hasta, error, con_hemovigilancia=True)


def _tab(datos):
    pedido = request.args.get("tab") or "donaciones"
    ids = [p["id"] for p in datos["pestanas"]]
    return pedido if pedido in ids else "donaciones"


@licenciado_informes_bp.get("/informes")
@requiere("lic", "licenciado_auth.ingresar")
def ver():
    datos = _vista()
    return pintar(
        "comun/informes.html",
        datos=datos,
        tab=_tab(datos),
        volver_url="licenciado_inicio.inicio",
        volver="Inicio",
        exportar_url="licenciado_informes.exportar",
    )


@licenciado_informes_bp.get("/informes/exportar")
@requiere("lic", "licenciado_auth.ingresar")
def exportar():
    datos = _vista()
    tab = _tab(datos)
    nombre = f"{tab}_{datos['desde'].isoformat()}_{datos['hasta'].isoformat()}.csv"
    return Response(
        informes.csv_maqueta(datos, tab),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@licenciado_informes_bp.post("/informes/vencer")
@requiere("lic", "licenciado_auth.ingresar")
def vencer():
    n = marcar_vencidas(operador_actual()["usuario"])
    flash(f"Unidades pasadas a vencidas: {n}. No se calculó una vida útil.", "ok")
    return redirect(url_for("licenciado_informes.ver"))
