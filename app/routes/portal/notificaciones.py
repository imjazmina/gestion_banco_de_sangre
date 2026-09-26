"""
Notificaciones del donante.

El esquema no tiene columna "leido", así que no se puede marcar una como
vista: se listan todas, de la más reciente a la más vieja. Agregar esa
columna es uno de los puntos a decidir con el módulo de administración
(ver EQUIPO.md).
"""
from flask import Blueprint, render_template

from app.controllers.sesion import requiere_login, usuario_actual
from app.models import Notificacion

notificaciones_bp = Blueprint("notificaciones", __name__)

# Ícono, fondo y color por tipo. Los tipos son los del CHECK ck_notificacion_tipo.
ESTILOS = {
    "CONFIRMACION_CITA":      ("calendar",  "#E6F4F3", "#0F766E"),
    "RECORDATORIO_CITA":      ("clock",     "#FEF3E2", "#D97706"),
    "HABILITACION":           ("check",     "#E7F6EF", "#059669"),
    "AGRADECIMIENTO":         ("award",     "#FFF7F7", "#C81E1E"),
    "ASIGNACION_DONANTE":     ("users",     "#EAF1FE", "#2563EB"),
    "ASIGNACION_SOLICITANTE": ("users",     "#EAF1FE", "#2563EB"),
    "META_COMPLETA":          ("activity",  "#E6F4F3", "#0F766E"),
    "CITACION_GENERICA":      ("megaphone", "#F3F4F6", "#6B7280"),
}

TITULOS = {
    "CONFIRMACION_CITA":      "Cita confirmada",
    "RECORDATORIO_CITA":      "Recordatorio de cita",
    "HABILITACION":           "Ya podés volver a donar",
    "AGRADECIMIENTO":         "Gracias por donar",
    "ASIGNACION_DONANTE":     "Tu donación fue asignada",
    "ASIGNACION_SOLICITANTE": "Un donante se sumó a tu solicitud",
    "META_COMPLETA":          "Solicitud completa",
    "CITACION_GENERICA":      "Mensaje del banco de sangre",
}


@notificaciones_bp.get("/notificaciones")
@requiere_login
def listar():
    usuario = usuario_actual()
    avisos = (Notificacion.query
              .filter_by(id_usuario=usuario.id_usuario)
              .order_by(Notificacion.fecha_envio.desc())
              .all())
    return render_template("portal/notificaciones.html",
                           avisos=avisos, estilos=ESTILOS, titulos=TITULOS)
