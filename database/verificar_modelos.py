"""
Compara los modelos SQLAlchemy contra la estructura real de PostgreSQL.

Los modelos no crean las tablas (eso lo hace schema.sql), así que una
diferencia de nombre o de tipo no se nota hasta que una consulta falla en
ejecución, muchas veces en la pantalla equivocada. Esto la encuentra antes.

    python database/verificar_modelos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text          # noqa: E402

from app import create_app                    # noqa: E402
from app.models import db                     # noqa: E402


def main():
    app = create_app()
    problemas = []

    with app.app_context():
        inspector = inspect(db.engine)
        tablas_reales = set(inspector.get_table_names(schema="public"))
        modelos = {m.class_.__tablename__: m.class_
                   for m in db.Model.registry.mappers}

        # 1. ¿Cada modelo apunta a una tabla que existe?
        for tabla in sorted(modelos):
            if tabla not in tablas_reales:
                problemas.append(f"{tabla}: el modelo apunta a una tabla inexistente")

        # 2. ¿Las columnas coinciden?
        for tabla, modelo in sorted(modelos.items()):
            if tabla not in tablas_reales:
                continue
            reales = {c["name"]: c for c in inspector.get_columns(tabla, schema="public")}
            declaradas = {c.name: c for c in modelo.__table__.columns}

            for nombre in declaradas.keys() - reales.keys():
                problemas.append(f"{tabla}.{nombre}: declarada en el modelo, no existe en la base")
            for nombre in reales.keys() - declaradas.keys():
                problemas.append(f"{tabla}.{nombre}: existe en la base, falta en el modelo")

            for nombre in declaradas.keys() & reales.keys():
                # NOT NULL en la base pero opcional en el modelo: la fila se
                # rechaza recién al hacer el INSERT.
                if not reales[nombre]["nullable"] and declaradas[nombre].nullable:
                    if not declaradas[nombre].primary_key:
                        problemas.append(
                            f"{tabla}.{nombre}: es NOT NULL en la base y nullable en el modelo")

        # 3. ¿Alguna tabla quedó sin modelo?
        # migracion_aplicada es la bitácora del propio sistema de migraciones,
        # no parte del modelo de datos: no le corresponde tener una clase.
        SIN_MODELO = {"migracion_aplicada"}
        for tabla in sorted(tablas_reales - modelos.keys() - SIN_MODELO):
            problemas.append(f"{tabla}: la tabla existe y no tiene modelo")

        # 4. Los catálogos tienen que estar cargados.
        esperado = {"rol": 4, "tipo_sangre": 8, "compatibilidad_abo_rh": 27,
                    "tipo_medicion": 5, "diferimiento": 12, "pregunta": 49,
                    "horario_disponible": 88, "contenido_portal": 3}
        vacios = []
        for tabla, cuantos in esperado.items():
            n = db.session.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()
            if n != cuantos:
                vacios.append(f"  {tabla}: hay {n}, se esperaban {cuantos}")

    print(f"Modelos declarados: {len(modelos)}   Tablas en la base: {len(tablas_reales)}")

    if problemas:
        print("\nDiferencias encontradas:")
        for p in problemas:
            print("  -", p)
    else:
        print("Todos los modelos coinciden con la base.")

    if vacios:
        print("\nCatálogos incompletos (corré database/catalogos.sql):")
        print("\n".join(vacios))
    else:
        print("Catálogos cargados correctamente.")

    return 1 if (problemas or vacios) else 0


if __name__ == "__main__":
    sys.exit(main())
