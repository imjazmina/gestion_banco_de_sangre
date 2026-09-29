"""
Revisa que las plantillas estén bien formadas.

Un `</div>` de más o de menos no rompe nada en Python ni da error en Flask:
el navegador cierra las etiquetas por su cuenta y la página simplemente se
ve mal, normalmente con el contenido escapándose del contenedor que lo
centra. Ese error es fácil de introducir al editar y difícil de ver leyendo.

    python database/verificar_plantillas.py
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VISTAS = RAIZ / "app" / "views"

# Etiquetas que se cierran siempre y conviene contar.
ETIQUETAS = ("div", "section", "form", "table", "ul", "ol", "nav",
             "header", "footer", "main", "label", "a", "p")


def revisar(archivo):
    """Devuelve la lista de etiquetas descompensadas de una plantilla."""
    texto = archivo.read_text(encoding="utf-8")

    # Los comentarios de Jinja pueden contener ejemplos de HTML que no son
    # etiquetas reales; se quitan antes de contar.
    texto = re.sub(r"\{#.*?#\}", "", texto, flags=re.S)

    problemas = []
    for etiqueta in ETIQUETAS:
        abre = len(re.findall(rf"<{etiqueta}\b", texto))
        cierra = len(re.findall(rf"</{etiqueta}>", texto))
        if abre != cierra:
            problemas.append((etiqueta, abre, cierra))
    return problemas


def main():
    if not VISTAS.is_dir():
        print(f"No encontré {VISTAS}")
        return 1

    plantillas = sorted(VISTAS.rglob("*.html"))
    con_problemas = 0

    for archivo in plantillas:
        problemas = revisar(archivo)
        if not problemas:
            continue
        con_problemas += 1
        relativa = archivo.relative_to(RAIZ)
        print(f"\n{relativa}")
        for etiqueta, abre, cierra in problemas:
            falta = "cierres" if abre > cierra else "aperturas"
            print(f"  <{etiqueta}>: {abre} abre, {cierra} cierra "
                  f"→ faltan {abs(abre - cierra)} {falta}")

    print(f"\n{len(plantillas)} plantillas revisadas.")
    if con_problemas:
        print(f"{con_problemas} con etiquetas descompensadas.")
        print("\nOjo: si una etiqueta se abre dentro de un {% if %} y se cierra")
        print("fuera, el conteo da distinto sin que haya error. Revisá a mano")
        print("antes de corregir.")
        return 1

    print("Todas las etiquetas están balanceadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
