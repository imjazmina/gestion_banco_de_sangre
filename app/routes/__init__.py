from flask import Blueprint

from app.controllers import mostrar_estado

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return mostrar_estado()
