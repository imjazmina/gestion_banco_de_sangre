from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import Config
from app.models import db
from app.routes import main_bp


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="views",
        static_folder="static",
    )
    app.config.from_object(config_class)

    _validar_configuracion(app)

    db.init_app(app)
    app.register_blueprint(main_bp)
    _registrar_errores(app)

    with app.app_context():
        _inicializar_base_de_datos(app)

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
    """Conecta a PostgreSQL y aplica schema.sql solo si aún no hay tablas."""
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
        return

    schema_path = app.config["SCHEMA_SQL_PATH"]
    if not schema_path.is_file():
        raise RuntimeError(
            f"No se encontró {schema_path}. "
            "Ese archivo es la fuente de verdad de la estructura."
        )

    sql = schema_path.read_text(encoding="utf-8")
    raw_connection = db.engine.raw_connection()
    try:
        raw_connection.autocommit = True
        with raw_connection.cursor() as cursor:
            cursor.execute(sql)
    finally:
        raw_connection.close()

    print("Estructura aplicada desde database/schema.sql")
