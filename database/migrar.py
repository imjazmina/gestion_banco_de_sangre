"""
Aplica las migraciones que falten en tu base.

    python database/migrar.py            aplica las pendientes
    python database/migrar.py --ver      solo muestra cuáles faltan

Corré esto cada vez que hagas `git pull`. Es lo que mantiene tu base al día
con los cambios de esquema que subió la otra integrante, sin tener que
borrar la base ni perder tus datos de prueba.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app                                   # noqa: E402
from app.models import db                                     # noqa: E402
from database.migraciones import archivos, pendientes, aplicar  # noqa: E402


def main():
    solo_ver = "--ver" in sys.argv

    app = create_app()
    with app.app_context():
        print(f"Base: {app.config['DB_NAME']} en "
              f"{app.config['DB_HOST']}:{app.config['DB_PORT']}")

        faltan = pendientes(db.engine)
        total = len(archivos())

        if not faltan:
            print(f"Tu base está al día ({total} migración/es aplicada/s).")
            return 0

        print(f"\nFaltan {len(faltan)} de {total}:")
        for nombre in faltan:
            print(f"  - {nombre}")

        if solo_ver:
            print("\n(--ver: no se aplicó nada)")
            return 0

        print()
        por_nombre = {p.name: p for p in archivos()}
        for nombre in faltan:
            print(f"  aplicando {nombre} ...", end=" ", flush=True)
            try:
                aplicar(db.engine, por_nombre[nombre])
            except Exception as e:
                print("FALLÓ")
                print(f"\n{type(e).__name__}: {e}")
                print("\nNo se aplicó esta migración ni las siguientes. "
                      "La base quedó como estaba antes de intentarla.")
                return 1
            print("ok")

        print("\nBase actualizada.")
        print("Acordate de revisar si algún modelo de app/models/ "
              "necesita la columna nueva.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
