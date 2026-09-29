"""
Comprueba que el cuestionario esté completo y bien emparejado.

El enunciado de cada pregunta vive en dos lados: en la base (lo carga
database/catalogos.sql) y en app/controllers/portal/preguntas.py, que es
donde están el bloque, el número y la aclaración, porque el esquema no
tiene columnas para eso.

Se emparejan por el texto del enunciado. Si alguien edita uno de los dos y
no el otro, la pregunta se queda sin bloque y desaparece de la pantalla sin
ningún error: el cuestionario pasa de 36 a 35 preguntas y nadie se entera.
Esto lo detecta.

    python database/verificar_preguntas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app                                   # noqa: E402
from app.controllers.portal import preguntas as catalogo     # noqa: E402
from app.models import Pregunta                              # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        en_base = {p.enunciado for p in Pregunta.query.filter_by(
            parte=Pregunta.PARTE_DONANTE).all()}
        en_codigo = {p.enunciado for p in catalogo.PREGUNTAS}

        print(f"Parte A en la base:    {len(en_base)}")
        print(f"Parte A en el código:  {len(en_codigo)}")

        faltan_en_base = en_codigo - en_base
        faltan_en_codigo = en_base - en_codigo

        if faltan_en_base:
            print(f"\n{len(faltan_en_base)} pregunta(s) del código que no están "
                  f"en la base (¿falta cargar catalogos.sql?):")
            for e in sorted(faltan_en_base):
                print(f"  - {e[:70]}")

        if faltan_en_codigo:
            print(f"\n{len(faltan_en_codigo)} pregunta(s) de la base sin datos "
                  f"de formulario (no se van a mostrar):")
            for e in sorted(faltan_en_codigo):
                print(f"  - {e[:70]}")

        # Los números tienen que ir del 1 al 36 sin huecos ni repetidos.
        ordenes = sorted(p.orden for p in catalogo.PREGUNTAS)
        esperados = list(range(1, len(catalogo.PREGUNTAS) + 1))
        if ordenes != esperados:
            print(f"\nLos números de orden no van del 1 al "
                  f"{len(catalogo.PREGUNTAS)} sin repetir: {ordenes}")
            return 1

        for p in catalogo.PREGUNTAS:
            if p.seccion not in catalogo.SECCIONES:
                print(f"\nLa pregunta {p.orden} tiene un bloque desconocido: "
                      f"{p.seccion!r}")
                return 1
            if p.alerta not in (None, "Si", "No"):
                print(f"\nLa pregunta {p.orden} tiene una alerta inválida: "
                      f"{p.alerta!r}")
                return 1

        if faltan_en_base or faltan_en_codigo:
            return 1

        reparto = {s: len(catalogo.de_seccion(s)) for s in catalogo.SECCIONES}
        print("\nReparto por bloque:")
        for seccion, cuantas in reparto.items():
            print(f"  {seccion:28} {cuantas:>2}")
        print("\nEl cuestionario coincide en la base y en el código.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
