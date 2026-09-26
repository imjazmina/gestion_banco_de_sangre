"""
Descubrimiento automático de blueprints.

Cada módulo dentro de routes/portal/ y routes/admin/ que defina un Blueprint
se registra solo. Nadie tiene que editar este archivo para agregar una
pantalla, y por lo tanto nadie se pisa con la otra en el mismo archivo: cada
pantalla nueva es un archivo nuevo en la carpeta de su módulo.

Para agregar una pantalla:
    1. Crear app/routes/<modulo>/mi_pantalla.py
    2. Definir ahí   mi_bp = Blueprint("mi_pantalla", __name__, url_prefix="/...")
    3. Listo. No se toca ningún archivo compartido.
"""
import importlib
import pkgutil
from pathlib import Path

from flask import Blueprint

# Los módulos del sistema. portal lo desarrolla Johana, admin lo desarrolla
# Jazmín. Cada una trabaja solo dentro de su carpeta.
MODULOS = ("portal", "admin")


def _blueprints_de(paquete):
    """Importa cada archivo del paquete y devuelve los Blueprint que encuentre."""
    encontrados = []
    ruta = Path(__file__).resolve().parent / paquete
    if not ruta.is_dir():
        return encontrados

    for info in pkgutil.iter_modules([str(ruta)]):
        if info.name.startswith("_"):
            continue
        modulo = importlib.import_module(f"app.routes.{paquete}.{info.name}")
        for nombre in dir(modulo):
            objeto = getattr(modulo, nombre)
            if isinstance(objeto, Blueprint):
                encontrados.append(objeto)
    return encontrados


def registrar(app):
    """Registra los blueprints de todos los módulos. La llama create_app()."""
    registrados = []
    for paquete in MODULOS:
        for bp in _blueprints_de(paquete):
            if bp.name in app.blueprints:
                continue
            app.register_blueprint(bp)
            registrados.append(f"{paquete}.{bp.name}")
    return registrados
