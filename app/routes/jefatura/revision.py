"""Cierra una citación el día de atención y muestra su historial."""
from datetime import date

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
            consejeria.marcar(citacion, request.form.get("estado"), personal)
            flash("Citación actualizada.", "ok")
        except ErrorConsejeria as exc:
            flash(str(exc), "error")
        return redirect(url_for("jefatura_revision.ver", cita_id=cita_id))

    donante = db.session.get(Usuario, citacion.id_donante)
    dia = citacion.fecha_hora.date() if citacion.fecha_hora else None
    hoy = date.today()
    estados, acciones = consejeria.evolucion(citacion)
    responsables = {
        accion.id_usuario: db.session.get(Usuario, accion.id_usuario)
        for accion in acciones
    }
    return pintar(
        "jefatura/revision.html",
        citacion=citacion,
        donante=donante,
        registros=consejeria.registros_de(citacion),
        puede_cerrar=(
            citacion.estado in ("Pendiente", "Confirmada")
            and dia is not None and dia <= hoy),
        estados=estados,
        acciones=acciones,
        responsables=responsables,
    )
