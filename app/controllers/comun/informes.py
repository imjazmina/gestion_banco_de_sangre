"""
Informes de donaciones, diferimientos, serología y stock (RF20, RF21).

Casi todas las cifras salen de consultas a la base y responden al período
que se elija en pantalla. Lo que no se puede derivar sigue viniendo de
database/informes_simulados.json, porque el esquema no lo modela:

  - el detalle de marcadores serológicos: no hay columna de marcador, y
    resultado_laboratorio solo guarda Reactivo / No reactivo;
  - el estado «En investigación», por el mismo CHECK;
  - la hemovigilancia completa: no existe una tabla de eventos adversos
    con momento y severidad;
  - los hemocomponentes separados: unidad tiene CHECK componente =
    'sangre_total', así que solo hay bolsas enteras;
  - la evolución mensual del volumen de stock: haría falta reconstruir el
    saldo histórico con transicion_estado.

Una convención que vale para todo el módulo: una extracción de
compatibilidad NO es una donación. Se hace para pruebas cruzadas y no
produce una unidad para el banco, así que queda fuera de los conteos.
"""
import csv as _csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func

from app.models import (
    Cita, Diferimiento, Extraccion, RegistroDiferimiento, ResultadoLaboratorio,
    Solicitud, TipoSangre, Unidad, Usuario, db,
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
    """
    El resumen chico de la pantalla de inicio, con datos de la base.

    Los meses llegan hasta el actual: los que todavía no pasaron saldrían
    en cero y parecerían una caída de las donaciones.
    """
    hoy = date.today()
    colectas = [{"mes": f["label"], "v": f["n"]}
                for f in _colectas_del_año(hoy.year)[:hoy.month]]
    motivos = [{"causa": f["label"], "n": f["n"]}
               for f in _por_motivo(_registros_diferimiento(
                   date(hoy.year, 1, 1), hoy))[:4]]
    stock = _stock_por_grupo()
    return {
        "colectas": colectas or [{"mes": "—", "v": 0}],
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

# Series que el esquema no modela. Ver el encabezado del módulo.
SEROLOGIA = _SIM["serologia"]["marcadores"]
EVENTOS_TIPO = _SIM["hemovigilancia"]["por_tipo"]
EVENTOS_MOMENTO = _SIM["hemovigilancia"]["por_momento"]
EVENTOS_SEVERIDAD = _SIM["hemovigilancia"]["por_severidad"]
VOLUMEN = _SIM["stock"]["evolucion_volumen"]

# Colores y orden de presentación. No son datos: definen cómo se dibuja
# cada serie, y por eso viven acá y no en la base.
COLOR_TIPO = {
    Cita.ALTRUISTA: "#0F766E",
    Cita.REPOSICION: "#120C61",
    Cita.SOLIDARIA: "#2563EB",
}
ETIQUETA_TIPO = {
    Cita.ALTRUISTA: "Altruista",
    Cita.REPOSICION: "Reposición",
    Cita.SOLIDARIA: "Solicitud",
}
RANGOS = ((18, 25), (26, 35), (36, 45), (46, 55), (56, 65))
ORDEN_GRUPOS = ("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-")
MESES_CORTOS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def _donaciones(desde, hasta):
    """
    Las donaciones del período, con la cita y el donante de cada una.

    La fecha que manda es `extraccion.fecha`: es la única columna que
    guarda cuándo se atendió a la persona. `cita` no tiene fecha —se
    deriva de la franja semanal— y por eso no se puede filtrar por ella
    en SQL.

    Se trae todo junto en una consulta y los cortes por tipo, género y
    edad se hacen en Python: son unas decenas de filas por período y así
    no hacen falta cinco consultas que recorren las mismas tablas.
    """
    return (db.session.query(Extraccion, Cita, Usuario)
            .join(Cita, Cita.id_cita == Extraccion.id_cita)
            .join(Usuario, Usuario.id_usuario == Cita.id_usuario)
            .filter(func.date(Extraccion.fecha) >= desde,
                    func.date(Extraccion.fecha) <= hasta,
                    Cita.tipo_cita != Cita.COMPATIBILIDAD)
            .all())


def _por_tipo(filas):
    conteo = {}
    for _, cita, _u in filas:
        conteo[cita.tipo_cita] = conteo.get(cita.tipo_cita, 0) + 1
    return [{"label": ETIQUETA_TIPO.get(t, t), "n": conteo.get(t, 0),
             "color": COLOR_TIPO[t]}
            for t in (Cita.ALTRUISTA, Cita.REPOSICION, Cita.SOLIDARIA)]


def _por_genero(filas):
    conteo = {}
    for _e, _c, usuario in filas:
        conteo[usuario.genero] = conteo.get(usuario.genero, 0) + 1
    return [{"label": "Femenino", "n": conteo.get("Femenino", 0), "color": "#0F766E"},
            {"label": "Masculino", "n": conteo.get("Masculino", 0), "color": "#120C61"}]


def _edad(nacimiento, referencia):
    """Años cumplidos a la fecha de referencia."""
    if nacimiento is None:
        return None
    años = referencia.year - nacimiento.year
    if (referencia.month, referencia.day) < (nacimiento.month, nacimiento.day):
        años -= 1
    return años


def _por_edad(filas, hasta):
    """
    Reparto por rango etario, con la edad al cierre del período.

    Se calcula a esa fecha y no a hoy: si no, el mismo informe de
    septiembre daría distinto según el día en que se lo mire.
    """
    conteo = {f"{a}-{b}": 0 for a, b in RANGOS}
    for _e, _c, usuario in filas:
        años = _edad(usuario.fecha_nacimiento, hasta)
        if años is None:
            continue
        for a, b in RANGOS:
            if a <= años <= b:
                conteo[f"{a}-{b}"] += 1
                break
    return [{"label": k, "n": v, "color": "#120C61"} for k, v in conteo.items()]


def _colectas_del_año(año):
    """Donaciones mes a mes. El año se toma del cierre del período."""
    filas = (db.session.query(
                func.extract("month", Extraccion.fecha).label("mes"),
                func.count().label("n"))
             .join(Cita, Cita.id_cita == Extraccion.id_cita)
             .filter(func.extract("year", Extraccion.fecha) == año,
                     Cita.tipo_cita != Cita.COMPATIBILIDAD)
             .group_by("mes").all())
    conteo = {int(f.mes): f.n for f in filas}
    return [{"label": MESES_CORTOS[m - 1], "n": conteo.get(m, 0)}
            for m in range(1, 13)]


# A partir de acá el gráfico pasa de días a meses. Con más de seis semanas
# una barra por día deja etiquetas ilegibles.
DIAS_PARA_AGRUPAR_POR_MES = 45


def _serie_del_periodo(filas, desde, hasta):
    """
    La evolución de las colectas dentro del período elegido.

    Se arma sobre el período y no sobre el año entero: si no, al consultar
    diez días el gráfico muestra doce meses donde once están vacíos, y
    parece que la actividad se desplomó. Los días sin donaciones sí se
    incluyen, porque un hueco en la serie es información.
    """
    dias = (hasta - desde).days + 1
    if dias <= DIAS_PARA_AGRUPAR_POR_MES:
        conteo = {}
        for extraccion, _c, _u in filas:
            conteo[extraccion.fecha.date()] = conteo.get(extraccion.fecha.date(), 0) + 1
        serie = []
        for i in range(dias):
            dia = desde + timedelta(days=i)
            serie.append({"label": f"{dia.day}/{dia.month}", "n": conteo.get(dia, 0)})
        return serie, "Día"

    conteo = {}
    for extraccion, _c, _u in filas:
        clave = (extraccion.fecha.year, extraccion.fecha.month)
        conteo[clave] = conteo.get(clave, 0) + 1
    serie = []
    año, mes = desde.year, desde.month
    while (año, mes) <= (hasta.year, hasta.month):
        etiqueta = MESES_CORTOS[mes - 1]
        if hasta.year != desde.year:
            etiqueta = f"{etiqueta} {str(año)[2:]}"
        serie.append({"label": etiqueta, "n": conteo.get((año, mes), 0)})
        mes += 1
        if mes == 13:
            mes, año = 1, año + 1
    return serie, "Mes"


def _registros_diferimiento(desde, hasta):
    """
    Diferimientos aplicados en el período, con su causa del catálogo.

    Se filtra por `fecha_inicio`, que es cuándo se aplicó. La cita no
    sirve de ancla porque no guarda fecha, y además hay diferimientos
    cargados sin cita asociada (los que vienen de otra institución).
    """
    return (db.session.query(RegistroDiferimiento, Diferimiento)
            .join(Diferimiento,
                  Diferimiento.id_diferimiento == RegistroDiferimiento.id_diferimiento)
            .filter(RegistroDiferimiento.fecha_inicio >= desde,
                    RegistroDiferimiento.fecha_inicio <= hasta)
            .all())


def _por_motivo(registros):
    conteo = {}
    for _r, causa in registros:
        conteo[causa.nombre] = conteo.get(causa.nombre, 0) + 1
    return [{"label": k, "n": v, "color": "#120C61"}
            for k, v in sorted(conteo.items(), key=lambda p: -p[1])]


def _clasificacion(registros):
    temporales = sum(1 for _r, causa in registros if causa.tipo == "Temporal")
    permanentes = sum(1 for _r, causa in registros if causa.tipo == "Permanente")
    return [{"label": "Temporales", "n": temporales, "color": "#D97706"},
            {"label": "Permanentes", "n": permanentes, "color": "#B91C1C"}]


def _diferidas(registros):
    """
    Personas diferidas, no registros.

    Una misma persona puede tener más de una causa anotada en la misma
    atención, y contar filas la duplicaría en el indicador.
    """
    return len({r.id_donante for r, _c in registros})


def _serologia(desde, hasta):
    """Resultados de laboratorio de las unidades extraídas en el período."""
    filas = (db.session.query(ResultadoLaboratorio.resultado, func.count())
             .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
             .join(Extraccion, Extraccion.id_extraccion == Unidad.id_extraccion)
             .join(Cita, Cita.id_cita == Extraccion.id_cita)
             .filter(func.date(Extraccion.fecha) >= desde,
                     func.date(Extraccion.fecha) <= hasta,
                     Cita.tipo_cita != Cita.COMPATIBILIDAD)
             .group_by(ResultadoLaboratorio.resultado).all())
    conteo = dict(filas)
    reactivos = conteo.get("Reactivo", 0)
    no_reactivos = conteo.get("No reactivo", 0)
    return {"procesados": reactivos + no_reactivos,
            "reactivos": reactivos,
            "no_reactivos": no_reactivos,
            # El CHECK de resultado_laboratorio solo admite los dos valores
            # de arriba. «En investigación» no se puede representar.
            "en_investigacion": _SIM["serologia"]["en_investigacion"]}


def _solicitudes():
    """Solicitudes por estado. Es una foto del momento, no del período."""
    filas = dict(db.session.query(Solicitud.estado, func.count())
                 .group_by(Solicitud.estado).all())
    return [{"label": "Atendidas", "n": filas.get(Solicitud.COMPLETA, 0), "color": "#120C61"},
            {"label": "Pendientes", "n": filas.get(Solicitud.PUBLICADA, 0), "color": "#2563EB"}]


def _stock_tablero():
    """
    Unidades en stock por grupo sanguíneo.

    Se listan los ocho grupos aunque alguno esté en cero: un grupo que
    desaparece del gráfico se lee como que no existe, y lo que importa
    justamente es ver cuál falta.
    """
    real = {fila["grupo"].replace("−", "-"): fila["n"] for fila in _stock_por_grupo()}
    return [{"label": g, "n": real.get(g, 0), "color": "#120C61"}
            for g in ORDEN_GRUPOS]


def _por_vencer_tablero(hasta):
    """
    Unidades en stock que vencen dentro del umbral, contadas desde el
    cierre del período que se está mirando.
    """
    limite = hasta + timedelta(days=_SIM["stock"]["umbral_dias"])
    return (Unidad.query
            .filter(Unidad.estado == Unidad.EN_STOCK,
                    Unidad.componente == "sangre_total",
                    Unidad.fecha_vencimiento > hasta,
                    Unidad.fecha_vencimiento <= limite)
            .count())


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
    """Arma el tablero del período pedido, consultando la base."""
    filas = _donaciones(desde, hasta)
    registros = _registros_diferimiento(desde, hasta)
    donaciones_n = len(filas)
    diferidas = _diferidas(registros)

    COLECTAS_TIPO = _por_tipo(filas)
    GENEROS = _por_genero(filas)
    RANGOS_EDAD = _por_edad(filas, hasta)
    COLECTAS_LINEA, eje_serie = _serie_del_periodo(filas, desde, hasta)
    MOTIVOS_MUESTRA = _por_motivo(registros) or [{"label": "Sin registros", "n": 0, "color": "#120C61"}]
    CLASIFICACION = _clasificacion(registros)
    # Aptas y diferidas reparten el total de personas evaluadas: las que
    # llegaron a donar más las que quedaron fuera por una causa.
    PROPORCION = [
        {"label": "Diferidas", "n": diferidas, "color": "#D97706"},
        {"label": "Aptas", "n": donaciones_n, "color": "#059669"},
    ]
    SOLICITUDES = _solicitudes()

    stock_filas = _stock_tablero()
    volumen = sum(f["n"] for f in stock_filas)
    eventos = _SIM["hemovigilancia"]["eventos"]
    solicitudes_total = sum(f["n"] for f in SOLICITUDES)
    atendidas = next(f["n"] for f in SOLICITUDES if f["label"] == "Atendidas")
    pendientes = next(f["n"] for f in SOLICITUDES if f["label"] == "Pendientes")
    por_vencer = _por_vencer_tablero(hasta)
    sero = _serologia(desde, hasta)
    hemo = _SIM["hemovigilancia"]
    evaluadas = donaciones_n + diferidas
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
                [[eje_serie, "Colectas"], *([f["label"], str(f["n"])] for f in COLECTAS_LINEA)],
                [["Género", "Cantidad"], *([f["label"], str(f["n"])] for f in generos)],
                [["Rango de edad", "Cantidad"], *([f["label"], str(f["n"])] for f in edades)],
            ),
        },
        "diferimientos": {
            "nombre": "Diferimientos",
            "filas": _filas(
                [["Situación", "Cantidad"],
                 ["Diferidas", str(diferidas)], ["Aptas", str(donaciones_n)]],
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
        "proporcion_centro": f"{_porcentaje(diferidas, evaluadas)}%",
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
        "atendidas": atendidas,
        "pendientes": pendientes,
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
