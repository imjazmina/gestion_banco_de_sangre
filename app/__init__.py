import locale
import os
from urllib.parse import quote_plus

from flask import Flask, has_request_context
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

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

    from app.controllers.sesion import aplicar_cookies_de_sesion, usuario_actual

    app.after_request(aplicar_cookies_de_sesion)

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
                from app.controllers.comun.simulacion import (
                    aplicar_vencimientos, reponer_laboratorio)
                reponer_laboratorio()
                aplicar_vencimientos()
                _arrancar_programador(app)

    return app


def _arrancar_programador(app):
    """Arma los envíos del cuestionario solo en el proceso que atiende.

    El recargador de depuración arranca dos procesos. El padre no atiende
    pedidos: si el temporizador quedara ahí, desaparece al recargar.
    """
    if os.environ.get("FLASK_RUN_FROM_CLI") != "true":
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    from app.controllers.portal.programacion import programador
    programador.enganchar(app)
    with app.app_context():
        programador.rearmar()


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
        tablas = _listar_tablas()
    except (OperationalError, UnicodeDecodeError) as exc:
        # En Windows el aviso «no existe la base de datos» llega en la página
        # del sistema (el « es 0xAB). psycopg2 lo lee como UTF-8 y esconde
        # el error real. Si la base no está, se crea y se sigue.
        if not _base_inexistente(_mensaje_de_conexion(exc)):
            raise RuntimeError(
                "No se pudo conectar a PostgreSQL "
                f"({app.config['DB_NAME']} en {app.config['DB_HOST']}:{app.config['DB_PORT']}). "
                "Verificá que el servidor esté activo."
            ) from exc
        _crear_base_de_datos(app)
        tablas = _listar_tablas()

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


def _listar_tablas():
    with db.engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        return connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )
        ).scalars().all()


def _mensaje_de_conexion(exc):
    """Recupera el texto de PostgreSQL cuando psycopg2 no puede decodificarlo."""
    vistos = set()
    actual = exc
    while actual is not None and id(actual) not in vistos:
        vistos.add(id(actual))
        if isinstance(actual, UnicodeDecodeError) and isinstance(actual.object, (bytes, bytearray)):
            encoding = locale.getpreferredencoding(False) or "cp1252"
            return actual.object.decode(encoding, errors="replace")
        actual = actual.__cause__ or actual.__context__
    return str(exc)


def _base_inexistente(mensaje):
    texto = mensaje.lower()
    return "no existe la base de datos" in texto or (
        "database" in texto and "does not exist" in texto
    )


def _crear_base_de_datos(app):
    nombre = app.config["DB_NAME"]
    if not nombre.replace("_", "").isalnum():
        raise RuntimeError(f"DB_NAME no es un identificador válido: {nombre}")

    usuario = quote_plus(app.config["DB_USER"])
    clave = quote_plus(app.config["DB_PASSWORD"] or "")
    url = (
        "postgresql+psycopg2://"
        f"{usuario}:{clave}@{app.config['DB_HOST']}:{app.config['DB_PORT']}/postgres"
    )
    # CREATE DATABASE no puede ir dentro de una transacción.
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{nombre}"'))
    except ProgrammingError as exc:
        if "ya existe" not in str(exc).lower() and "already exists" not in str(exc).lower():
            raise
    finally:
        admin.dispose()

    db.engine.dispose()
    print(f"Base de datos {nombre} creada")


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
