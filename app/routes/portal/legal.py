"""
Política de privacidad y términos de uso.

Son públicas a propósito: el formulario de registro exige aceptarlas, y nadie
puede aceptar algo que no puede leer antes de tener cuenta.
"""
from flask import Blueprint, render_template

from app.controllers.portal import contenido

legal_bp = Blueprint("legal", __name__)


@legal_bp.get("/privacidad")
def privacidad():
    return render_template(
        "portal/legal.html",
        titulo="Política de privacidad y seguridad del sistema",
        secciones=contenido.PRIVACIDAD
    )


@legal_bp.get("/terminos")
def terminos():
    return render_template(
        "portal/legal.html",
        titulo="Términos y condiciones de uso",
        secciones=contenido.TERMINOS
    )


@legal_bp.get("/declaracion-donante")
def declaracion_donante():
    return render_template(
        "portal/legal.html",
        titulo="Declaración y consentimiento del donante",
        secciones=contenido.DECLARACION_DONANTE
    )
