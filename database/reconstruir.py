"""
Deja la base exactamente como dice database/schema.sql.

Borra todo lo que haya y la vuelve a crear desde cero: la estructura del
schema.sql y después los catálogos. Es lo que hay que correr cuando la base
quedó con tablas o columnas que el esquema ya no tiene.

    python database/reconstruir.py

BORRA TODOS LOS DATOS. Pide que escribas el nombre de la base antes de
hacer nada, para que no se dispare por accidente.

Después de esto hay que volver a crear las cuentas de prueba desde el
portal: los donantes, las citas y los cuestionarios se van con el resto.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text                            # noqa: E402

from app import create_app                             # noqa: E402
from app.models import db                              # noqa: E402

CARPETA = Path(__file__).resolve().parent


def main():
    app = create_app()
    nombre = app.config["DB_NAME"]

    print()
    print("=" * 62)
    print("RECONSTRUIR LA BASE DESDE CERO")
    print("=" * 62)
    print(f"Base:     {nombre}")
    print(f"Servidor: {app.config['DB_HOST']}:{app.config['DB_PORT']}")
    print()
    print("Se va a borrar TODO lo que tenga: usuarios, citas, cuestionarios,")
    print("todo. Después se crea de nuevo con la estructura de schema.sql y")
    print("se cargan los catálogos.")
    print()

    if "--si" not in sys.argv:
        respuesta = input(f"Para confirmar, escribí el nombre de la base ({nombre}): ")
        if respuesta.strip() != nombre:
            print("\nNo coincide. No toqué nada.")
            return 1

    with app.app_context():
        print("\n  vaciando la base ... ", end="", flush=True)
        conexion = db.engine.raw_connection()
        try:
            conexion.autocommit = True
            with conexion.cursor() as cursor:
                # Se tira el esquema entero en lugar de tabla por tabla: así
                # no hay que averiguar el orden de las claves foráneas ni
                # quedan funciones o índices viejos dando vueltas.
                cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            print("ok")

            for archivo, titulo in ((CARPETA / "schema.sql", "estructura"),
                                    (CARPETA / "catalogos.sql", "catálogos")):
                if not archivo.is_file():
                    print(f"\nNo encontré {archivo}")
                    return 1
                print(f"  aplicando {titulo} ({archivo.name}) ... ",
                      end="", flush=True)
                with conexion.cursor() as cursor:
                    cursor.execute(archivo.read_text(encoding="utf-8"))
                print("ok")
        finally:
            conexion.close()

        print()
        for tabla in ("rol", "tipo_sangre", "diferimiento", "pregunta",
                      "horario_disponible", "contenido_portal", "usuario"):
            n = db.session.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()
            print(f"  {tabla:22} {n:>4}")

    print()
    print("Base reconstruida. Ahora:")
    print("  python database/verificar_modelos.py")
    print("  python database/verificar_preguntas.py")
    print("  python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
