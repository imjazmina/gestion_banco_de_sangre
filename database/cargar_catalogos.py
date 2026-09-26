"""
Carga database/catalogos.sql en la base que usa la aplicación.

Se puede hacer lo mismo desde pgAdmin, pero con varios servidores de
PostgreSQL instalados es fácil ejecutarlo contra la base equivocada y no
darse cuenta. Este script lee la conexión del .env, la misma que usa Flask,
así que siempre da en la base correcta.

    python database/cargar_catalogos.py

Se puede correr más de una vez: el script SQL comprueba antes de insertar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text            # noqa: E402

from app import create_app             # noqa: E402
from app.models import db              # noqa: E402

ESPERADO = {
    "rol": 4, "tipo_sangre": 8, "compatibilidad_abo_rh": 27,
    "tipo_medicion": 5, "diferimiento": 12, "pregunta": 13,
    "horario_disponible": 88, "contenido_portal": 3,
}


def main():
    archivo = Path(__file__).resolve().parent / "catalogos.sql"
    if not archivo.is_file():
        print(f"No se encontró {archivo}")
        return 1

    app = create_app()
    with app.app_context():
        print(f"Base: {app.config['DB_NAME']} en "
              f"{app.config['DB_HOST']}:{app.config['DB_PORT']}")

        # Igual que hace create_app() con schema.sql: se ejecuta el archivo
        # entero por la conexión cruda, porque trae BEGIN y COMMIT propios.
        conexion = db.engine.raw_connection()
        try:
            conexion.autocommit = True
            with conexion.cursor() as cursor:
                cursor.execute(archivo.read_text(encoding="utf-8"))
        finally:
            conexion.close()

        print("catalogos.sql ejecutado.\n")

        faltantes = []
        for tabla, cuantos in ESPERADO.items():
            n = db.session.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()
            estado = "ok" if n == cuantos else f"ESPERABA {cuantos}"
            print(f"  {tabla:24} {n:>4}   {estado}")
            if n != cuantos:
                faltantes.append(tabla)

    if faltantes:
        print("\nQuedaron tablas incompletas:", ", ".join(faltantes))
        return 1

    print("\nCatálogos cargados correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
