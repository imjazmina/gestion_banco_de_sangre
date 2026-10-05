"""
Informes con la presentación de la maqueta (RF20, RF21).

Los gráficos usan las series de muestra de esa maqueta, para que el tablero
se vea igual aunque la base todavía no tenga filas. No son el inventario del
hospital. La vista previa del inicio sigue leyendo el stock real.
"""
import csv as _csv
import io
from datetime import date, datetime

from app.models import (
    Cita, Extraccion, RegistroDiferimiento, Unidad,
)


SERIE_PRUEBA = [
    {"mes": "Ene", "v": 112}, {"mes": "Feb", "v": 98}, {"mes": "Mar", "v": 124},
    {"mes": "Abr", "v": 103}, {"mes": "May", "v": 117}, {"mes": "Jun", "v": 89},
    {"mes": "Jul", "v": 131}, {"mes": "Ago", "v": 108}, {"mes": "Sep", "v": 87},
    {"mes": "Oct", "v": 96}, {"mes": "Nov", "v": 110}, {"mes": "Dic", "v": 94},
]


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
    motivos = _motivos()[:4]
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


PERIODO_MUESTRA = (date(2026, 9, 1), date(2026, 9, 10))
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

COLECTAS_TIPO = [
    {"label": "Altruista", "n": 54, "color": "#0F766E"},
    {"label": "Reposición", "n": 22, "color": "#120C61"},
    {"label": "Solicitud", "n": 8, "color": "#2563EB"},
    {"label": "Diagnóstico", "n": 3, "color": "#D97706"},
]
GENEROS = [
    {"label": "Femenino", "n": 38, "color": "#0F766E"},
    {"label": "Masculino", "n": 49, "color": "#120C61"},
]
RANGOS_EDAD = [
    {"label": "18-25", "n": 22, "color": "#120C61"},
    {"label": "26-35", "n": 31, "color": "#120C61"},
    {"label": "36-45", "n": 19, "color": "#120C61"},
    {"label": "46-55", "n": 11, "color": "#120C61"},
    {"label": "56-65", "n": 4, "color": "#120C61"},
]
MOTIVOS_MUESTRA = [
    {"label": "Hemoglobina baja", "n": 7},
    {"label": "Presión arterial fuera de rango", "n": 5},
    {"label": "Temperatura elevada", "n": 3},
    {"label": "Infección activa", "n": 3},
    {"label": "Medicación incompatible", "n": 2},
    {"label": "Peso insuficiente", "n": 2},
    {"label": "Otro", "n": 1},
]
PROPORCION = [
    {"label": "Diferidas", "n": 20, "color": "#D97706"},
    {"label": "Aptas", "n": 67, "color": "#059669"},
]
CLASIFICACION = [
    {"label": "Temporales", "n": 14, "color": "#D97706"},
    {"label": "Permanentes", "n": 6, "color": "#B91C1C"},
]
SEROLOGIA = [
    {"label": "VIH 1/2", "n": 10},
    {"label": "HBsAg (Hepatitis B)", "n": 8},
    {"label": "Anti-HCV (Hepatitis C)", "n": 7},
    {"label": "VDRL (Sífilis)", "n": 6},
    {"label": "Chagas (T. cruzi)", "n": 5},
    {"label": "HTLV I/II", "n": 4},
    {"label": "Anti-HBc (Hepatitis B)", "n": 3},
    {"label": "HBsAg(Hepatitis B)", "n": 2},
    {"label": "CMV", "n": 2},
    {"label": "Anti-HCV(Hepatitis C)", "n": 1},
]
EVENTOS_TIPO = [
    {"label": "Hematoma", "n": 4},
    {"label": "Febril", "n": 3},
    {"label": "Lipotimia", "n": 3},
    {"label": "Alérgica", "n": 2},
    {"label": "Náuseas", "n": 2},
    {"label": "Dolor local", "n": 2},
    {"label": "Hipotensión", "n": 1},
    {"label": "Hormigueo", "n": 1},
    {"label": "Vasovagal", "n": 1},
    {"label": "Otro", "n": 1},
]
EVENTOS_MOMENTO = [
    {"label": "Durante", "n": 12, "color": "#D97706"},
    {"label": "Post", "n": 8, "color": "#2563EB"},
]
EVENTOS_SEVERIDAD = [
    {"label": "Leve", "n": 12, "color": "#059669"},
    {"label": "Moderado", "n": 6, "color": "#D97706"},
    {"label": "Grave", "n": 2, "color": "#B91C1C"},
]
STOCK_MUESTRA = [
    {"label": "O+", "n": 21},
    {"label": "A+", "n": 10},
    {"label": "B+", "n": 4},
    {"label": "AB+", "n": 1},
    {"label": "O−", "n": 3},
    {"label": "A−", "n": 2},
    {"label": "B−", "n": 1},
    {"label": "AB−", "n": 0},
]
VOLUMEN = [
    {"label": "Ene", "n": 58, "color": "#0F766E"},
    {"label": "Feb", "n": 63, "color": "#0F766E"},
    {"label": "Mar", "n": 71, "color": "#0F766E"},
    {"label": "Abr", "n": 66, "color": "#0F766E"},
    {"label": "May", "n": 74, "color": "#0F766E"},
    {"label": "Jun", "n": 61, "color": "#0F766E"},
    {"label": "Jul", "n": 78, "color": "#0F766E"},
    {"label": "Ago", "n": 72, "color": "#0F766E"},
    {"label": "Sep", "n": 69, "color": "#0F766E"},
]
SOLICITUDES = [
    {"label": "Atendidas", "n": 28, "color": "#120C61"},
    {"label": "Pendientes", "n": 5, "color": "#2563EB"},
]
COLECTAS_LINEA = [
    {"label": m["mes"], "n": m["v"]}
    for m in SERIE_PRUEBA
    if m["mes"] != "Oct" and m["mes"] != "Nov" and m["mes"] != "Dic"
]


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
    volumen = sum(f["n"] for f in STOCK_MUESTRA)
    eventos = sum(f["n"] for f in EVENTOS_TIPO)
    solicitudes_total = sum(f["n"] for f in SOLICITUDES)
    atendidas = next(f["n"] for f in SOLICITUDES if f["label"] == "Atendidas")
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
    stock = _barras(STOCK_MUESTRA)
    volumen_mes = _barras(VOLUMEN)
    solicitudes = _barras(SOLICITUDES)
    linea = _linea(COLECTAS_LINEA)

    paneles = {
        "donaciones": {
            "nombre": "Donaciones",
            "filas": _filas(
                [["Indicador", "Valor"], ["Donaciones", "87"]],
                [["Tipo de donación", "Cantidad"], *([f["label"], str(f["n"])] for f in colectas)],
                [["Mes", "Colectas"], *([f["label"], str(f["n"])] for f in COLECTAS_LINEA)],
                [["Género", "Cantidad"], *([f["label"], str(f["n"])] for f in generos)],
                [["Rango de edad", "Cantidad"], *([f["label"], str(f["n"])] for f in edades)],
            ),
        },
        "diferimientos": {
            "nombre": "Diferimientos",
            "filas": _filas(
                [["Situación", "Cantidad"], ["Diferidas", "20"], ["Aptas", "67"]],
                [["Motivo de diferimiento", "Cantidad"], *([f["label"], str(f["n"])] for f in motivos)],
                [["Clasificación", "Cantidad"], *([f["label"], str(f["n"])] for f in clasificacion)],
            ),
        },
        "serologia": {
            "nombre": "Serología / Inmunohematología",
            "filas": _filas(
                [["Indicador", "Valor"], ["Volúmenes procesados", "87"],
                 ["Reactivos", "4"], ["No reactivos", "83"], ["En investigación", "2"]],
                [["Marcador", "Reactivos"], *([f["label"], str(f["n"])] for f in serologia)],
            ),
        },
        "hemovigilancia": {
            "nombre": "Hemovigilancia",
            "filas": _filas(
                [["Indicador", "Valor"], ["Extracciones", "87"], ["Eventos adversos", str(eventos)]],
                [["Momento", "Cantidad"], *([f["label"], str(f["n"])] for f in momentos)],
                [["Severidad", "Cantidad"], *([f["label"], str(f["n"])] for f in severidad)],
                [["Tipo de evento", "Cantidad"], *([f["label"], str(f["n"])] for f in tipos)],
            ),
        },
        "stock": {
            "nombre": "Stock / Transfusiones",
            "filas": _filas(
                [["Indicador", "Valor"], ["Volumen disponible", str(volumen)],
                 ["Próximos a vencer", "6"], ["Solicitudes atendidas", "28"],
                 ["Solicitudes pendientes", "5"]],
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
        "donaciones_n": 87,
        "colectas": colectas,
        "colectas_grad": _conico(colectas),
        "generos": generos,
        "edades": edades,
        "linea": linea,
        "proporcion": proporcion,
        "proporcion_grad": _conico(proporcion),
        "proporcion_centro": f"{_porcentaje(20, 87)}%",
        "motivos": motivos,
        "clasificacion": clasificacion,
        "procesados": 87,
        "reactivos": 4,
        "no_reactivos": 83,
        "investigacion": 2,
        "serologia": serologia,
        "extracciones": 87,
        "eventos": eventos,
        "momentos": momentos,
        "severidad": severidad,
        "severidad_grad": _conico(severidad),
        "tipos_evento": tipos,
        "volumen": volumen,
        "por_vencer": 6,
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
