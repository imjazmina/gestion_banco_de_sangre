"""
Buzón de sugerencias, comentarios y reclamos.

Exige sesión iniciada porque buzon.id_usuario es NOT NULL en el esquema: el
mensaje queda asociado a quien lo escribe. El prototipo lo planteaba anónimo;
eso requiere hacer la columna nullable, y es uno de los puntos a decidir con
el módulo de administración (ver EQUIPO.md).
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)

from app.controllers.sesion import requiere_login, usuario_actual
from app.models import db, Buzon

buzon_bp = Blueprint("buzon", __name__, url_prefix="/buzon")

TIPOS = [
    ("Sugerencia", "lightbulb", "Propuesta de mejora para el servicio o para el portal.",
     "#E6F4F3", "var(--teal-ink)"),
    ("Comentario", "messageCircle", "Compartí tu experiencia de donación.",
     "#EAF1FE", "var(--info)"),
    ("Reclamo", "flag", "Reportá un problema o inconveniente.",
     "#FDECEC", "var(--danger)"),
]
CLAVES = {clave for clave, _, _, _, _ in TIPOS}

LARGO_MINIMO = 10
LARGO_MAXIMO = 2000


@buzon_bp.get("/")
@requiere_login
def formulario():
    tipo = request.args.get("tipo")
    return render_template("portal/buzon.html",
                           tipos=TIPOS,
                           tipo=tipo if tipo in CLAVES else None,
                           enviado=False)


@buzon_bp.post("/")
@requiere_login
def enviar():
    usuario = usuario_actual()
    tipo = request.form.get("tipo")
    mensaje = (request.form.get("mensaje") or "").strip()

    if tipo not in CLAVES:
        flash("Elegí el tipo de mensaje.", "error")
        return redirect(url_for("buzon.formulario"))
    if len(mensaje) < LARGO_MINIMO:
        flash(f"Contanos un poco más: el mensaje necesita al menos {LARGO_MINIMO} caracteres.", "error")
        return redirect(url_for("buzon.formulario", tipo=tipo))
    if len(mensaje) > LARGO_MAXIMO:
        flash(f"El mensaje es demasiado largo (máximo {LARGO_MAXIMO} caracteres).", "error")
        return redirect(url_for("buzon.formulario", tipo=tipo))

    # La tabla no tiene columna "tipo", así que el tipo va al principio del
    # texto. Es la forma de conservarlo sin cambiar el esquema, que es
    # compartido con el módulo de administración.
    try:
        db.session.add(Buzon(id_usuario=usuario.id_usuario,
                             mensaje=f"[{tipo}] {mensaje}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return render_template("portal/buzon.html", tipos=TIPOS, tipo=tipo, enviado=True)
