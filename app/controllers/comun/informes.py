"""
Informes de donaciones, diferimientos, serología y stock (RF20, RF21).

Todas las cifras salen de la base y responden al período elegido.
Una extracción de compatibilidad o de muestra no es una donación:
no produce una unidad para el banco y queda fuera de esos conteos.

El stock disponible es el estado En stock de una unidad ya extraída.
Reactiva, descartada, vencida o todavía sin extraer no entra.
La vida útil que usa «próximos a vencer» es la misma de la extracción:
30 días, cargados en unidad.fecha_vencimiento.
"""
import csv as _csv
import io
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.models import (
    Cita, Diferimiento, Extraccion, RegistroDiferimiento, ResultadoCompatibilidad,
    ResultadoLaboratorio,
    Rol, Solicitud, TipoSangre, TransicionEstado, Unidad, Usuario, UsuarioRol, db,
)

# La extracción deja el vencimiento a 30 días. El listado usa el mismo plazo.
UMBRAL_DIAS = 30
_NO_DONACION = (Cita.COMPATIBILIDAD, Cita.MUESTRA)
_CLAVES_OBS = ("Momento", "Tipo", "Reacción", "Severidad")
_COLOR_MOMENTO = {"Durante": "#D97706", "Posterior": "#2563EB"}
_COLOR_SEVERIDAD = {"Leve": "#059669", "Moderado": "#D97706", "Grave": "#B91C1C"}


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
        "serie": [{"mes": f["label"], "v": f["n"]}
                  for f in _colectas_del_año(hasta.year)],
        "nota_serie": "La serie mensual sale de las extracciones registradas.",
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
    """Unidades ya extraídas que siguen en stock. El resto no está disponible."""
    hoy = date.today()
    unidades = (Unidad.query
                .join(Extraccion, Extraccion.id_extraccion == Unidad.id_extraccion)
                .filter(Unidad.estado == Unidad.EN_STOCK,
                        func.date(Extraccion.fecha) <= hoy)
                .all())
    conteo = {}
    for unidad in unidades:
        etiqueta = unidad.id_tipo_sangre and _etiqueta(unidad) or "Sin tipificar"
        conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
    return [{"grupo": k, "n": v} for k, v in sorted(conteo.items())]


def _etiqueta(unidad):
    from app.models import TipoSangre, db
    tipo = db.session.get(TipoSangre, unidad.id_tipo_sangre)
    return tipo.etiqueta if tipo else "Sin tipificar"


def _periodo_default():
    """El año en curso, hasta hoy: es el recorte con el que abre el informe."""
    hoy = date.today()
    return date(hoy.year, 1, 1), hoy


_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Colores y orden de presentación. No son datos: definen cómo se dibuja
# cada serie, y por eso viven acá y no en la base.
COLOR_TIPO = {
    Cita.ALTRUISTA: "#0F766E",
    Cita.SOLIDARIA: "#2563EB",
}
ETIQUETA_TIPO = {
    Cita.ALTRUISTA: "Altruista",
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
                    ~Cita.tipo_cita.in_(_NO_DONACION))
            .all())


def _por_tipo(filas):
    conteo = {}
    for _, cita, _u in filas:
        conteo[cita.tipo_cita] = conteo.get(cita.tipo_cita, 0) + 1
    return [{"label": ETIQUETA_TIPO.get(t, t), "n": conteo.get(t, 0),
             "color": COLOR_TIPO[t]}
            for t in (Cita.ALTRUISTA, Cita.SOLIDARIA)]


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
                     ~Cita.tipo_cita.in_(_NO_DONACION))
             .group_by("mes").all())
    conteo = {int(f.mes): f.n for f in filas}
    return [{"label": MESES_CORTOS[m - 1], "n": conteo.get(m, 0)}
            for m in range(1, 13)]


def _por_grupo_donacion(filas):
    """
    Donaciones del período por ABO/Rh.

    Cuenta la extracción, no la bolsa. El estado actual de la unidad no
    entra: descartada, asignada o vencida sigue siendo una donación de
    ese grupo.
    """
    ids = [extraccion.id_extraccion for extraccion, _c, _u in filas]
    grupo_de = {}
    if ids:
        unidades = (db.session.query(Unidad.id_extraccion, TipoSangre)
                    .outerjoin(TipoSangre,
                               TipoSangre.id_tipo_sangre == Unidad.id_tipo_sangre)
                    .filter(Unidad.id_extraccion.in_(ids))
                    .order_by(Unidad.id_unidad)
                    .all())
        for id_extraccion, tipo in unidades:
            if id_extraccion in grupo_de or tipo is None:
                continue
            grupo_de[id_extraccion] = tipo.etiqueta.replace("−", "-")
    conteo = {grupo: 0 for grupo in ORDEN_GRUPOS}
    sin_tipificar = 0
    for extraccion, _c, _u in filas:
        grupo = grupo_de.get(extraccion.id_extraccion)
        if grupo in conteo:
            conteo[grupo] += 1
        else:
            sin_tipificar += 1
    salida = [{"label": grupo, "n": conteo[grupo], "color": "#120C61"}
              for grupo in ORDEN_GRUPOS]
    if sin_tipificar:
        salida.append({"label": "Sin tipificar", "n": sin_tipificar, "color": "#120C61"})
    return salida


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


def _pai_positivos(desde, hasta):
    """Muestras del período cuyo PAI quedó positivo."""
    return (db.session.query(func.count(ResultadoCompatibilidad.id_resultado_compatibilidad))
            .join(Diferimiento,
                  Diferimiento.id_diferimiento == ResultadoCompatibilidad.id_diferimiento)
            .filter(func.date(ResultadoCompatibilidad.fecha) >= desde,
                    func.date(ResultadoCompatibilidad.fecha) <= hasta,
                    Diferimiento.nombre == ResultadoCompatibilidad.PAI_POSITIVO)
            .scalar() or 0)


def _serologia(desde, hasta):
    """Resultados de laboratorio de las unidades extraídas en el período."""
    filas = (db.session.query(ResultadoLaboratorio.resultado, func.count())
             .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
             .join(Extraccion, Extraccion.id_extraccion == Unidad.id_extraccion)
             .join(Cita, Cita.id_cita == Extraccion.id_cita)
             .filter(func.date(Extraccion.fecha) >= desde,
                     func.date(Extraccion.fecha) <= hasta,
                     ~Cita.tipo_cita.in_(_NO_DONACION))
             .group_by(ResultadoLaboratorio.resultado).all())
    conteo = dict(filas)
    reactivos = conteo.get("Reactivo", 0)
    no_reactivos = conteo.get("No reactivo", 0)
    return {"procesados": reactivos + no_reactivos,
            "reactivos": reactivos,
            "no_reactivos": no_reactivos}


def _solicitudes():
    """Solicitudes por estado. Es una foto del momento, no del período."""
    filas = dict(db.session.query(Solicitud.estado, func.count())
                 .group_by(Solicitud.estado).all())
    return [{"label": "Atendidas", "n": filas.get(Solicitud.CERRADA, 0), "color": "#120C61"},
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


def _proximas(hasta):
    """
    Unidades en stock que vencen dentro de los 30 días posteriores al
    cierre del período. La fecha ya viene calculada en la unidad.
    """
    limite = hasta + timedelta(days=UMBRAL_DIAS)
    filas = (db.session.query(Unidad, TipoSangre)
             .outerjoin(TipoSangre, TipoSangre.id_tipo_sangre == Unidad.id_tipo_sangre)
             .join(Extraccion, Extraccion.id_extraccion == Unidad.id_extraccion)
             .filter(Unidad.estado == Unidad.EN_STOCK,
                     Unidad.fecha_vencimiento > hasta,
                     Unidad.fecha_vencimiento <= limite,
                     func.date(Extraccion.fecha) <= hasta)
             .order_by(Unidad.fecha_vencimiento, Unidad.codigo)
             .all())
    return [{"codigo": unidad.codigo,
             "grupo": tipo.etiqueta if tipo else "Sin tipificar",
             "vence": unidad.fecha_vencimiento}
            for unidad, tipo in filas]


def leer_periodo(desde_txt, hasta_txt):
    """Devuelve (desde, hasta, error). Sin fechas, usa el año en curso."""
    defecto = _periodo_default()
    if not desde_txt and not hasta_txt:
        return defecto[0], defecto[1], ""
    try:
        desde = date.fromisoformat(desde_txt) if desde_txt else None
        hasta = date.fromisoformat(hasta_txt) if hasta_txt else None
    except ValueError:
        return defecto[0], defecto[1], "Indique fecha de inicio y de fin."
    if desde is None or hasta is None:
        return defecto[0], defecto[1], "Indique fecha de inicio y de fin."
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


def _filas(*bloques):
    salida = []
    for i, bloque in enumerate(bloques):
        if i:
            salida.append([])
        salida.extend(bloque)
    return salida


def _vacio(filas):
    return filas or [{"label": "Sin registros", "n": 0, "color": "#120C61"}]


def _campos_obs(texto):
    """Lee Momento, Tipo, Reacción y Severidad tal como los guarda la extracción."""
    campos = {}
    for parte in (texto or "").split(" · "):
        if ": " not in parte:
            continue
        clave, valor = parte.split(": ", 1)
        if clave in _CLAVES_OBS:
            campos[clave] = valor.strip()
    return campos


def _registrados(desde, hasta):
    """Donantes cuya cuenta se dio de alta en el período. Es el corte de RF20."""
    return (db.session.query(func.count(func.distinct(Usuario.id_usuario)))
            .join(UsuarioRol, UsuarioRol.id_usuario == Usuario.id_usuario)
            .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
            .filter(Rol.codigo == Rol.DONANTE,
                    Usuario.cuenta_suprimida.is_(False),
                    func.date(Usuario.fecha_alta) >= desde,
                    func.date(Usuario.fecha_alta) <= hasta)
            .scalar() or 0)


def _marcadores(desde, hasta):
    """Cada reactivo cuenta por la causa permanente que lo confirmó."""
    filas = (db.session.query(Diferimiento.nombre, func.count())
             .join(RegistroDiferimiento,
                   RegistroDiferimiento.id_diferimiento == Diferimiento.id_diferimiento)
             .join(ResultadoLaboratorio,
                   ResultadoLaboratorio.id_resultado == RegistroDiferimiento.id_resultado)
             .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
             .join(Extraccion, Extraccion.id_extraccion == Unidad.id_extraccion)
             .join(Cita, Cita.id_cita == Extraccion.id_cita)
             .filter(func.date(Extraccion.fecha) >= desde,
                     func.date(Extraccion.fecha) <= hasta,
                     ~Cita.tipo_cita.in_(_NO_DONACION),
                     ResultadoLaboratorio.resultado == ResultadoLaboratorio.REACTIVO)
             .group_by(Diferimiento.nombre)
             .all())
    return [{"label": nombre, "n": n, "color": "#D97706"} for nombre, n in filas]


def _hemovigilancia(desde, hasta):
    """
    Eventos leídos de extraccion.observacion.

    El formulario ya guarda momento y tipo. La severidad solo aparece si
    esa clave está en el texto: el formulario no la pide.
    """
    filas = (Extraccion.query
             .join(Cita, Cita.id_cita == Extraccion.id_cita)
             .filter(func.date(Extraccion.fecha) >= desde,
                     func.date(Extraccion.fecha) <= hasta,
                     ~Cita.tipo_cita.in_(_NO_DONACION))
             .all())
    momentos, tipos, severidad = {}, {}, {}
    eventos = 0
    for extraccion in filas:
        campos = _campos_obs(extraccion.observacion)
        momento = campos.get("Momento")
        tipo = campos.get("Tipo")
        reaccion = campos.get("Reacción")
        grado = campos.get("Severidad")
        if not (momento or tipo or grado or reaccion == "Lipotimia"):
            continue
        eventos += 1
        if momento:
            momentos[momento] = momentos.get(momento, 0) + 1
        if grado:
            severidad[grado] = severidad.get(grado, 0) + 1
        if tipo:
            tipos[tipo] = tipos.get(tipo, 0) + 1
        elif reaccion == "Lipotimia":
            tipos["Lipotimia"] = tipos.get("Lipotimia", 0) + 1

    def series(conteo, colores):
        return [{"label": k, "n": v, "color": colores.get(k, "#120C61")}
                for k, v in sorted(conteo.items(), key=lambda p: -p[1])]

    return {
        "extracciones": len(filas),
        "eventos": eventos,
        "momentos": _vacio(series(momentos, _COLOR_MOMENTO)),
        "severidad": _vacio(series(severidad, _COLOR_SEVERIDAD)),
        "tipos": _vacio(series(tipos, {})),
    }


def _stock_al(corte):
    """Cuántas unidades estaban en stock al cierre de esa fecha."""
    ultimas = (db.session.query(
                TransicionEstado.id_unidad,
                TransicionEstado.estado_destino,
                func.row_number().over(
                    partition_by=TransicionEstado.id_unidad,
                    order_by=(TransicionEstado.fecha.desc(),
                              TransicionEstado.id_transicion.desc()),
                ).label("rn"))
               .filter(func.date(TransicionEstado.fecha) <= corte)
               .subquery())
    return (db.session.query(func.count())
            .select_from(ultimas)
            .filter(ultimas.c.rn == 1,
                    ultimas.c.estado_destino == Unidad.EN_STOCK)
            .scalar() or 0)


def _volumen_mensual(desde, hasta):
    salida = []
    año, mes = desde.year, desde.month
    while (año, mes) <= (hasta.year, hasta.month):
        fin = date(año + (mes == 12), 1 if mes == 12 else mes + 1, 1) - timedelta(days=1)
        if fin > hasta:
            fin = hasta
        etiqueta = MESES_CORTOS[mes - 1]
        if hasta.year != desde.year:
            etiqueta = f"{etiqueta} {str(año)[2:]}"
        salida.append({"label": etiqueta, "n": _stock_al(fin), "color": "#0F766E"})
        mes += 1
        if mes == 13:
            mes, año = 1, año + 1
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
    GRUPOS_DONACION = _por_grupo_donacion(filas)
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
    solicitudes_total = sum(f["n"] for f in SOLICITUDES)
    atendidas = next(f["n"] for f in SOLICITUDES if f["label"] == "Atendidas")
    pendientes = next(f["n"] for f in SOLICITUDES if f["label"] == "Pendientes")
    proximas = _proximas(hasta)
    por_vencer = len(proximas)
    sero = _serologia(desde, hasta)
    pai = _pai_positivos(desde, hasta)
    marcadores = _marcadores(desde, hasta)
    hemo = _hemovigilancia(desde, hasta)
    eventos = hemo["eventos"]
    registrados_n = _registrados(desde, hasta)
    volumen_serie = _volumen_mensual(desde, hasta)
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
    serologia = _barras(_vacio(sorted(marcadores, key=lambda f: -f["n"])))
    momentos = _barras(hemo["momentos"])
    severidad = _barras(hemo["severidad"])
    tipos = _barras(sorted(hemo["tipos"], key=lambda f: -f["n"]))
    stock = _barras(stock_filas)
    volumen_mes = _barras(volumen_serie)
    solicitudes = _barras(SOLICITUDES)
    grupos_donacion = _barras(GRUPOS_DONACION)

    paneles = {
        "donaciones": {
            "nombre": "Donaciones",
            "filas": _filas(
                [["Indicador", "Valor"],
                 ["Donantes registrados", str(registrados_n)],
                 ["Donaciones", str(donaciones_n)]],
                [["Tipo de donación", "Cantidad"], *([f["label"], str(f["n"])] for f in colectas)],
                [["Grupo sanguíneo", "Donaciones"], *([f["label"], str(f["n"])] for f in grupos_donacion)],
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
                 ["PAI positivo", str(pai)]],
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
                [["Unidad", "Grupo", "Vencimiento"],
                 *([f["codigo"], f["grupo"], f["vence"].isoformat()] for f in proximas)],
            ),
        },
    }
    return {
        "desde": desde,
        "hasta": hasta,
        "hoy": date.today(),
        "sin_datos": donaciones_n == 0 and diferidas == 0,
        "registrados_n": registrados_n,
        "proximas": proximas,
        "periodo": _periodo_largo(desde, hasta),
        "error": error,
        "pestanas": [{"id": i, "nombre": n} for i, n in pestanas],
        "paneles": paneles,
        "donaciones_n": donaciones_n,
        "colectas": colectas,
        "colectas_grad": _conico(colectas),
        "generos": generos,
        "edades": edades,
        "grupos_donacion": grupos_donacion,
        "proporcion": proporcion,
        "proporcion_grad": _conico(proporcion),
        "proporcion_centro": f"{_porcentaje(diferidas, evaluadas)}%",
        "motivos": motivos,
        "clasificacion": clasificacion,
        "procesados": sero["procesados"],
        "reactivos": sero["reactivos"],
        "no_reactivos": sero["no_reactivos"],
        "pai": pai,
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
