"""Cierra una citación y, si corresponde, registra la derivación."""
from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.jefatura import consejeria
from app.controllers.jefatura.consejeria import ErrorConsejeria
from app.models import Usuario, db

jefatura_revision_bp = Blueprint("jefatura_revision", __name__, url_prefix="/jefatura")


@jefatura_revision_bp.route("/diferimientos/<int:cita_id>", methods=["GET", "POST"])
@requiere("jef", "jefatura_auth.ingresar")
def ver(cita_id):
    citacion = consejeria.citacion_por_id(cita_id)
    if citacion is None:
        flash("No existe esa citación.", "error")
        return redirect(url_for("jefatura_diferimientos.lista"))
    personal = operador_actual()["usuario"]
    if request.method == "POST":
        try:
            if request.form.get("accion") == "derivar":
                registro = consejeria.registro_para_derivar(
                    consejeria.registros_de(citacion))
                consejeria.derivar(
                    registro, personal,
                    request.form.get("establecimiento"),
                    request.form.get("motivo"),
                )
                flash("Derivación registrada.", "ok")
            else:
                consejeria.marcar(citacion, request.form.get("estado"), personal)
                flash("Citación actualizada.", "ok")
        except ErrorConsejeria as exc:
            flash(str(exc), "error")
        return redirect(url_for("jefatura_revision.ver", cita_id=cita_id))

    donante = db.session.get(Usuario, citacion.id_donante)
    registros = consejeria.registros_de(citacion)
    externo = consejeria.registro_para_derivar(registros)
    return pintar(
        "jefatura/revision.html",
        citacion=citacion,
        donante=donante,
        registros=registros,
        puede_derivar=externo is not None,
    )
