"""
Informes con la presentación de la maqueta (RF20, RF21).

Las series que el esquema no puede guardar (marcadores, hemovigilancia,
hemocomponentes, evolución de volumen, colectas mensuales) salen de
database/informes_simulados.json. El stock ABO actual y las unidades
próximas a vencer se leen de la base cuando hay filas.
"""
import csv as _csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from app.models import (
    Cita, Extraccion, RegistroDiferimiento, Unidad,
)

_SIM_PATH = Path(__file__).resolve().parents[3] / "database" / "informes_simulados.json"
_SIM = json.loads(_SIM_PATH.read_text(encoding="utf-8"))

SERIE_PRUEBA = _SIM["donaciones"]["colectas_mensuales_2026"]


def _periodo(desde, hasta):
    hoy = date.today()
    if desde is None:
        desde = hoy.replace(day=1)
    if hasta is None:
        hasta = hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _en_periodo(momento, desde, hasta):
    if momento is None:
        return False
    dia = momento.date() if isinstance(momento, datetime) else momento
    return desde <= dia <= hasta


def vista_previa():
    stock = _stock_por_grupo()
    motivos = [{"causa": f["label"], "n": f["n"]}
               for f in _SIM["diferimientos"]["por_motivo"][:4]]
    if not stock:
        stock = [{"grupo": f["label"], "n": f["n"]}
                 for f in _SIM["stock"]["por_grupo"] if f["n"]]
    return {
        "colectas": SERIE_PRUEBA[:9],
        "motivos": motivos or [{"causa": "Sin registros", "n": 0}],
        "stock": stock or [{"grupo": "—", "n": 0}],
    }


def armar(desde=None, hasta=None):
    desde, hasta = _periodo(desde, hasta)
    extracciones = Extraccion.query.all()
    del_periodo = [e for e in extracciones if _en_periodo(e.fecha, desde, hasta)]
    citas = Cita.query.all()
    no_aptas = [c for c in citas
                if c.estado == Cita.NO_APTO and c.fecha_cita
                and _en_periodo(c.fecha_cita, desde, hasta)]
    diferimientos = RegistroDiferimiento.query.all()
    difs = [d for d in diferimientos if _en_periodo(d.fecha_inicio, desde, hasta)]
    lipotimias = sum(1 for e in del_periodo if "lipotimia" in (e.observacion or "").lower())
    return {
        "desde": desde,
        "hasta": hasta,
        "simulacion": True,
        "donaciones": len(del_periodo),
        "no_aptos": len(no_aptas),
        "diferimientos": len(difs),
        "lipotimias": lipotimias,
        "motivos": _motivos(difs),
        "stock": _stock_por_grupo(),
        "serie": SERIE_PRUEBA,
        "nota_serie": ("La serie mensual es simulación con datos de prueba. "
                       "No representa la producción del hospital."),
        "nota_stock": ("El stock por grupo cuenta unidades en estado En stock "
                       "de sangre total ya registradas en este prototipo. "
                       "No es el inventario operativo del hospital."),
        "nota_huecos": ("No hay rangos etarios definidos ni un registro de PAI. "
                        "Esos cortes no se muestran."),
    }


def _motivos(filas=None):
    if filas is None:
        filas = RegistroDiferimiento.query.all()
    conteo = {}
    for fila in filas:
        nombre = fila.causa.nombre if fila.causa is not None else "Sin causa"
        conteo[nombre] = conteo.get(nombre, 0) + 1
    return [{"causa": k, "n": v} for k, v in sorted(conteo.items(), key=lambda p: -p[1])]


def _stock_por_grupo():
    unidades = Unidad.query.filter_by(estado=Unidad.EN_STOCK, componente="sangre_total").all()
    conteo = {}
    for unidad in unidades:
        etiqueta = unidad.id_tipo_sangre and _etiqueta(unidad) or "Sin tipificar"
        conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
    return [{"grupo": k, "n": v} for k, v in sorted(conteo.items())]


def _etiqueta(unidad):
    from app.models import TipoSangre, db
    tipo = db.session.get(TipoSangre, unidad.id_tipo_sangre)
    return tipo.etiqueta if tipo else "Sin tipificar"


PERIODO_MUESTRA = (
    date.fromisoformat(_SIM["periodo"]["desde"]),
    date.fromisoformat(_SIM["periodo"]["hasta"]),
)
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

COLECTAS_TIPO = _SIM["donaciones"]["por_tipo"]
GENEROS = _SIM["donaciones"]["por_genero"]
RANGOS_EDAD = _SIM["donaciones"]["por_edad"]
MOTIVOS_MUESTRA = _SIM["diferimientos"]["por_motivo"]
PROPORCION = [
    {"label": "Diferidas", "n": _SIM["diferimientos"]["diferidas"], "color": "#D97706"},
    {"label": "Aptas", "n": _SIM["diferimientos"]["aptas"], "color": "#059669"},
]
CLASIFICACION = [
    {"label": "Temporales", "n": _SIM["diferimientos"]["temporales"], "color": "#D97706"},
    {"label": "Permanentes", "n": _SIM["diferimientos"]["permanentes"], "color": "#B91C1C"},
]
SEROLOGIA = _SIM["serologia"]["marcadores"]
EVENTOS_TIPO = _SIM["hemovigilancia"]["por_tipo"]
EVENTOS_MOMENTO = _SIM["hemovigilancia"]["por_momento"]
EVENTOS_SEVERIDAD = _SIM["hemovigilancia"]["por_severidad"]
STOCK_MUESTRA = _SIM["stock"]["por_grupo"]
VOLUMEN = _SIM["stock"]["evolucion_volumen"]
SOLICITUDES = _SIM["stock"]["solicitudes"]
COLECTAS_LINEA = [{"label": m["mes"], "n": m["v"]} for m in SERIE_PRUEBA]


def _stock_tablero():
    """Stock ABO real si hay unidades; si no, la serie simulada."""
    real = {fila["grupo"].replace("−", "-"): fila["n"] for fila in _stock_por_grupo()}
    if not real:
        return [dict(fila) for fila in STOCK_MUESTRA]
    salida = []
    for fila in STOCK_MUESTRA:
        clave = fila["label"].replace("−", "-")
        item = dict(fila)
        item["n"] = real.get(clave, 0)
        salida.append(item)
    return salida


def _por_vencer_tablero():
    ref = PERIODO_MUESTRA[1]
    limite = ref + timedelta(days=_SIM["stock"]["umbral_dias"])
    unidades = Unidad.query.filter_by(estado=Unidad.EN_STOCK, componente="sangre_total").all()
    n = sum(
        1 for u in unidades
        if u.fecha_vencimiento and ref < u.fecha_vencimiento <= limite
    )
    return n if unidades else _SIM["stock"]["proximos_a_vencer"]


def leer_periodo(desde_txt, hasta_txt):
    """Devuelve (desde, hasta, error). Sin fechas, usa el período de la maqueta."""
    if not desde_txt and not hasta_txt:
        return PERIODO_MUESTRA[0], PERIODO_MUESTRA[1], ""
    try:
        desde = date.fromisoformat(desde_txt) if desde_txt else None
        hasta = date.fromisoformat(hasta_txt) if hasta_txt else None
    except ValueError:
        return PERIODO_MUESTRA[0], PERIODO_MUESTRA[1], "Indique fecha de inicio y de fin."
    if desde is None or hasta is None:
        return PERIODO_MUESTRA[0], PERIODO_MUESTRA[1], "Indique fecha de inicio y de fin."
    if hasta < desde:
        return desde, hasta, "La fecha de fin no puede ser anterior a la de inicio."
    return desde, hasta, ""


def _fecha_larga(dia):
    return f"{dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def _periodo_largo(desde, hasta):
    return f"{_fecha_larga(desde)} – {_fecha_larga(hasta)}"


def _conico(filas):
    total = sum(f["n"] for f in filas) or 1
    acc = 0.0
    tramos = []
    for fila in filas:
        inicio = acc / total * 100
        acc += fila["n"]
        fin = acc / total * 100
        tramos.append(f"{fila['color']} {inicio:.2f}% {fin:.2f}%")
    return "conic-gradient(" + ", ".join(tramos) + ")"


def _porcentaje(parte, total):
    if total <= 0:
        return 0
    return round(parte / total * 100)


def _barras(filas):
    maximo = max((f["n"] for f in filas), default=1) or 1
    total = sum(f["n"] for f in filas)
    salida = []
    for fila in filas:
        item = dict(fila)
        item["alto"] = 0 if fila["n"] <= 0 else round(fila["n"] / maximo * 80, 2)
        item["ancho"] = round(fila["n"] / maximo * 100, 2)
        item["parte"] = _porcentaje(fila["n"], total)
        item["color"] = fila.get("color", "#120C61")
        salida.append(item)
    return salida


def _linea(filas):
    maximo = max((f["n"] for f in filas), default=1) or 1

    def y(valor):
        return round(8 + (1 - valor / maximo) * 84, 2)

    puntos = []
    cantidad = len(filas)
    for i, fila in enumerate(filas):
        x = 50 if cantidad == 1 else round(2 + (i / (cantidad - 1)) * 96, 2)
        puntos.append({**fila, "x": x, "y": y(fila["n"])})
    marcas = [maximo, round(maximo / 2), 0]
    return {
        "puntos": puntos,
        "trazo": " ".join(f"{p['x']},{p['y']}" for p in puntos),
        "marcas": [{"n": m, "y": y(m)} for m in marcas],
    }


def _filas(*bloques):
    salida = []
    for i, bloque in enumerate(bloques):
        if i:
            salida.append([])
        salida.extend(bloque)
    return salida


def presentacion(desde, hasta, error="", con_hemovigilancia=True):
    """Arma el tablero con las cifras de la maqueta."""
    stock_filas = _stock_tablero()
    volumen = sum(f["n"] for f in stock_filas)
    eventos = _SIM["hemovigilancia"]["eventos"]
    solicitudes_total = sum(f["n"] for f in SOLICITUDES)
    atendidas = next(f["n"] for f in SOLICITUDES if f["label"] == "Atendidas")
    por_vencer = _por_vencer_tablero()
    donaciones_n = _SIM["donaciones"]["total"]
    dif = _SIM["diferimientos"]
    sero = _SIM["serologia"]
    hemo = _SIM["hemovigilancia"]
    pestanas = [
        ("donaciones", "Donaciones"),
        ("diferimientos", "Diferimientos"),
        ("serologia", "Serología / Inmunohematología"),
    ]
    if con_hemovigilancia:
        pestanas.append(("hemovigilancia", "Hemovigilancia"))
    pestanas.append(("stock", "Stock / Transfusiones"))

    colectas = _barras(COLECTAS_TIPO)
    generos = _barras(GENEROS)
    edades = _barras(RANGOS_EDAD)
    motivos = _barras(MOTIVOS_MUESTRA)
    proporcion = _barras(PROPORCION)
    clasificacion = _barras(CLASIFICACION)
    serologia = _barras(sorted(SEROLOGIA, key=lambda f: -f["n"]))
    momentos = _barras(EVENTOS_MOMENTO)
    severidad = _barras(EVENTOS_SEVERIDAD)
    tipos = _barras(sorted(EVENTOS_TIPO, key=lambda f: -f["n"]))
    stock = _barras(stock_filas)
    volumen_mes = _barras(VOLUMEN)
    solicitudes = _barras(SOLICITUDES)
    linea = _linea(COLECTAS_LINEA)

    paneles = {
        "donaciones": {
            "nombre": "Donaciones",
            "filas": _filas(
                [["Indicador", "Valor"], ["Donaciones", str(donaciones_n)]],
                [["Tipo de donación", "Cantidad"], *([f["label"], str(f["n"])] for f in colectas)],
                [["Mes", "Colectas"], *([f["label"], str(f["n"])] for f in COLECTAS_LINEA)],
                [["Género", "Cantidad"], *([f["label"], str(f["n"])] for f in generos)],
                [["Rango de edad", "Cantidad"], *([f["label"], str(f["n"])] for f in edades)],
            ),
        },
        "diferimientos": {
            "nombre": "Diferimientos",
            "filas": _filas(
                [["Situación", "Cantidad"],
                 ["Diferidas", str(dif["diferidas"])], ["Aptas", str(dif["aptas"])]],
                [["Motivo de diferimiento", "Cantidad"], *([f["label"], str(f["n"])] for f in motivos)],
                [["Clasificación", "Cantidad"], *([f["label"], str(f["n"])] for f in clasificacion)],
            ),
        },
        "serologia": {
            "nombre": "Serología / Inmunohematología",
            "filas": _filas(
                [["Indicador", "Valor"], ["Volúmenes procesados", str(sero["procesados"])],
                 ["Reactivos", str(sero["reactivos"])], ["No reactivos", str(sero["no_reactivos"])],
                 ["En investigación", str(sero["en_investigacion"])]],
                [["Marcador", "Reactivos"], *([f["label"], str(f["n"])] for f in serologia)],
            ),
        },
        "hemovigilancia": {
            "nombre": "Hemovigilancia",
            "filas": _filas(
                [["Indicador", "Valor"], ["Extracciones", str(hemo["extracciones"])],
                 ["Eventos adversos", str(eventos)]],
                [["Momento", "Cantidad"], *([f["label"], str(f["n"])] for f in momentos)],
                [["Severidad", "Cantidad"], *([f["label"], str(f["n"])] for f in severidad)],
                [["Tipo de evento", "Cantidad"], *([f["label"], str(f["n"])] for f in tipos)],
            ),
        },
        "stock": {
            "nombre": "Stock / Transfusiones",
            "filas": _filas(
                [["Indicador", "Valor"], ["Volumen disponible", str(volumen)],
                 ["Próximos a vencer", str(por_vencer)],
                 ["Solicitudes atendidas", str(atendidas)],
                 ["Solicitudes pendientes", str(next(f["n"] for f in SOLICITUDES if f["label"] == "Pendientes"))]],
                [["Grupo sanguíneo", "Volumen"], *([f["label"], str(f["n"])] for f in stock)],
                [["Mes", "Volumen disponible"], *([f["label"], str(f["n"])] for f in volumen_mes)],
                [["Estado de solicitud", "Cantidad"], *([f["label"], str(f["n"])] for f in solicitudes)],
            ),
        },
    }
    return {
        "desde": desde,
        "hasta": hasta,
        "periodo": _periodo_largo(desde, hasta),
        "error": error,
        "pestanas": [{"id": i, "nombre": n} for i, n in pestanas],
        "paneles": paneles,
        "donaciones_n": donaciones_n,
        "colectas": colectas,
        "colectas_grad": _conico(colectas),
        "generos": generos,
        "edades": edades,
        "linea": linea,
        "proporcion": proporcion,
        "proporcion_grad": _conico(proporcion),
        "proporcion_centro": f"{_porcentaje(dif['diferidas'], donaciones_n)}%",
        "motivos": motivos,
        "clasificacion": clasificacion,
        "procesados": sero["procesados"],
        "reactivos": sero["reactivos"],
        "no_reactivos": sero["no_reactivos"],
        "investigacion": sero["en_investigacion"],
        "serologia": serologia,
        "extracciones": hemo["extracciones"],
        "eventos": eventos,
        "momentos": momentos,
        "severidad": severidad,
        "severidad_grad": _conico(severidad),
        "tipos_evento": tipos,
        "volumen": volumen,
        "por_vencer": por_vencer,
        "atendidas": 28,
        "pendientes": 5,
        "stock": stock,
        "volumen_mes": volumen_mes,
        "solicitudes": solicitudes,
        "solicitudes_grad": _conico(solicitudes),
        "solicitudes_centro": f"{_porcentaje(atendidas, solicitudes_total)}%",
    }


def csv_maqueta(datos, tab):
    panel = datos["paneles"][tab]
    buffer = io.StringIO()
    escritor = _csv.writer(buffer)
    escritor.writerow([f"Informe: {panel['nombre']}"])
    escritor.writerow([f"Período: {datos['periodo']}"])
    escritor.writerow(["Hospital Regional de Luque"])
    escritor.writerow([])
    for fila in panel["filas"]:
        escritor.writerow(fila)
    return buffer.getvalue()


def csv(datos):
    lineas = [
        "Informe simulado",
        f"Periodo,{datos['desde'].isoformat()},{datos['hasta'].isoformat()}",
        f"Donaciones registradas,{datos['donaciones']}",
        f"Citas no aptas,{datos['no_aptos']}",
        f"Diferimientos,{datos['diferimientos']}",
        f"Lipotimias en observacion,{datos['lipotimias']}",
        "",
        "Motivo,Cantidad",
    ]
    for fila in datos["motivos"]:
        lineas.append(f"{fila['causa']},{fila['n']}")
    lineas.append("")
    lineas.append("Grupo,Unidades en stock (sangre total)")
    for fila in datos["stock"]:
        lineas.append(f"{fila['grupo']},{fila['n']}")
    lineas.append("")
    lineas.append(datos["nota_serie"])
    lineas.append(datos["nota_stock"])
    return "\n".join(lineas) + "\n"
