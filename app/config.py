import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = (
        "postgresql+psycopg2://"
        f"{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SCHEMA_SQL_PATH = BASE_DIR / "database" / "schema.sql"

    # ------------------------------------------------------------ correo
    # Si SMTP_HOST está vacío, la aplicación igual funciona: los correos se
    # escriben en la consola en lugar de enviarse. Así nadie se queda sin
    # poder levantar el proyecto por no tener credenciales.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PUERTO = os.getenv("SMTP_PUERTO", "587")
    SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
    SMTP_CONTRASENA = os.getenv("SMTP_CONTRASENA", "")
    SMTP_TLS = os.getenv("SMTP_TLS", "1") != "0"
    CORREO_DESDE = os.getenv("CORREO_DESDE", "")
    CORREO_NOMBRE = os.getenv("CORREO_NOMBRE", "Banco de sangre HRL")

    # Dirección con la que se arman los enlaces de los correos. Hace falta
    # porque los recordatorios los manda un script fuera del servidor web,
    # donde no hay ningún pedido del que deducirla.
    URL_BASE = os.getenv("URL_BASE", "http://127.0.0.1:5000")
