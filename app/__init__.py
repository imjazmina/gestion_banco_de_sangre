import os

from flask import Flask, has_request_context
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import Config
from app.models import db
from app.routes import registrar as registrar_blueprints


def create_app(config_class=Config, inicializar=True):
    app = Flask(
        __name__,
        template_folder="views",
        static_folder="static",
    )
    app.config.from_object(config_class)

    _validar_configuracion(app)

    db.init_app(app)
    registrar_blueprints(app)
    _registrar_errores(app)

    from app.controllers.sesion import usuario_actual

    @app.context_processor
    def inyectar_usuario():
        """
        Deja `usuario` disponible en todas las plantillas.

        La comprobación no sobra: las plantillas de los correos se dibujan
        desde `enviar_avisos.py`, donde no hay ningún pedido en curso y
        `session` no existe. Sin esto, el envío automático se cae con
        "Working outside of request context".
        """
        return {"usuario": usuario_actual() if has_request_context() else None}

    if inicializar:
        with app.app_context():
            _inicializar_base_de_datos(app)
            # El recargador de depuración arranca el proceso dos veces.
            if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
                from app.controllers.comun.simulacion import reponer_laboratorio
                reponer_laboratorio()

    return app


def _validar_configuracion(app):
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta SECRET_KEY en el archivo .env")
    if not app.config.get("DB_NAME"):
        raise RuntimeError("Falta DB_NAME en el archivo .env")


def _registrar_errores(app):
    @app.errorhandler(404)
    def no_encontrado(_error):
        return "Página no encontrada", 404

    @app.errorhandler(500)
    def error_interno(_error):
        return "Error interno del servidor", 500


def _inicializar_base_de_datos(app):
    """Aplica schema.sql si falta la estructura y catalogos.sql en cada arranque.

    catalogos.sql es idempotente (ON CONFLICT / NOT EXISTS): volver a
    levantarlo no duplica roles, donantes ni el resto de la maqueta.
    """
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tablas = connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
            ).scalars().all()
    except OperationalError as exc:
        raise RuntimeError(
            "No se pudo conectar a PostgreSQL "
            f"({app.config['DB_NAME']} en {app.config['DB_HOST']}:{app.config['DB_PORT']}). "
            "Verificá que el servidor esté activo y que la base de datos exista."
        ) from exc

    print("Conexión a PostgreSQL correcta")

    if tablas:
        print("Estructura de la BD ya existe; no se ejecuta schema.sql")
    else:
        _ejecutar_sql(
            app.config["SCHEMA_SQL_PATH"],
            "Ese archivo es la fuente de verdad de la estructura.",
        )
        print("Estructura aplicada desde database/schema.sql")

    _ejecutar_sql(
        app.config["CATALOGOS_SQL_PATH"],
        "Ese archivo carga los catálogos y la maqueta sin duplicar filas.",
    )
    print("Datos aplicados desde database/catalogos.sql")


def _ejecutar_sql(ruta, motivo):
    if not ruta.is_file():
        raise RuntimeError(f"No se encontró {ruta}. {motivo}")

    sql = ruta.read_text(encoding="utf-8")
    raw_connection = db.engine.raw_connection()
    try:
        raw_connection.autocommit = True
        with raw_connection.cursor() as cursor:
            cursor.execute(sql)
    finally:
        raw_connection.close()
