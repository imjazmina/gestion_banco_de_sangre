"""
Migraciones de la base de datos.

El problema que resuelven: schema.sql solo se ejecuta cuando la base está
vacía. Si una de las dos agrega una tabla o una columna después, la base de
la otra no se entera nunca. Cuando corra el código nuevo va a fallar con
"column does not exist" y va a perder un rato buscando el motivo.

Cómo funciona:

  - Cada cambio del esquema es un archivo nuevo en esta carpeta, numerado:
        001_agregar_fecha_cita.sql
        002_notificacion_leido.sql
  - Los archivos no se editan nunca una vez subidos al repositorio. Si algo
    salió mal, se corrige con una migración nueva.
  - La tabla migracion_aplicada guarda cuáles ya corrieron en cada base.
  - `python database/migrar.py` aplica las que falten, en orden.

Como cada cambio es un archivo distinto, dos personas pueden agregar
migraciones el mismo día sin conflictos en Git.
"""
from pathlib import Path

from sqlalchemy import text

CARPETA = Path(__file__).resolve().parent

SQL_TABLA_CONTROL = """
CREATE TABLE IF NOT EXISTS migracion_aplicada (
    nombre  varchar(200) PRIMARY KEY,
    fecha   timestamp NOT NULL DEFAULT now()
)
"""


def archivos():
    """Las migraciones del repositorio, en orden por nombre."""
    return sorted(CARPETA.glob("[0-9]*.sql"), key=lambda p: p.name)


def aplicadas(engine):
    """Los nombres ya aplicados en esta base."""
    with engine.connect() as con:
        con.execute(text(SQL_TABLA_CONTROL))
        con.commit()
        filas = con.execute(text("SELECT nombre FROM migracion_aplicada")).scalars()
        return set(filas)


def pendientes(engine):
    """Los nombres que faltan aplicar en esta base."""
    ya = aplicadas(engine)
    return [p.name for p in archivos() if p.name not in ya]


def aplicar(engine, archivo):
    """
    Ejecuta una migración y la marca como aplicada, todo junto.

    Si el SQL falla, la transacción se deshace y el nombre no queda
    registrado: la migración se puede volver a intentar después de
    corregirla, sin que la base quede a medio camino.
    """
    sql = archivo.read_text(encoding="utf-8")
    with engine.begin() as con:
        con.execute(text(sql))
        con.execute(text("INSERT INTO migracion_aplicada (nombre) VALUES (:n)"),
                    {"n": archivo.name})
