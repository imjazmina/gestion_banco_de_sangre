"""Extracción y alta de las unidades completadas."""
import re

from flask import Blueprint, flash, redirect, request, url_for

from app.controllers.comun.acceso import operador_actual, pintar, requiere
from app.controllers.comun.simulacion import agendar_resultado
from app.controllers.licenciado import criterios, jornada
from app.controllers.licenciado.jornada import ErrorJornada

licenciado_extraccion_bp = Blueprint(
    "licenciado_extraccion", __name__, url_prefix="/licenciado")

BRAZOS = ("Derecho", "Izquierdo")
PUNCIONES = ("Punción única", "Varias")
REACCIONES = ("Normal", "Lipotimia", "Otras")
ANTICOAGULANTES = ("ACD-A", "CPD-A", "SAG MANITOL")
BOLSAS = ("Simple", "Doble", "Triple", "Cuádruple")
MOMENTOS = ("Durante", "Posterior")
TIPOS = tuple(criterios.EXTRACCION)
RESULTADOS = ("Sin sangre", "Parcial", "Completa")
CLAVES = (
    "Brazo", "Punción", "Reacción", "Anticoagulante", "Bolsa", "Marca",
    "Inicio", "Fin", "Cantidad", "Unidades", "Tabuladora", "Lote",
    "Vencimiento", "Momento", "Tipo", "Resultado", "Incidencia",
)
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PIEZAS = re.compile(
    r"(?:^| · )(" + "|".join(CLAVES) + r"): (.*?)(?= · (?:"
    + "|".join(CLAVES) + r"): |$)"
)


def _opcion(formulario, nombre, validos, obligatorio, etiqueta):
    valor = (formulario.get(nombre) or "").strip()
    if not valor:
        if obligatorio:
            raise ErrorJornada(f"Falta {etiqueta}.")
        return None
    if valor not in validos:
        raise ErrorJornada(f"{etiqueta} no es un valor admitido.")
    return valor


def _texto(formulario, nombre, obligatorio, etiqueta, limite=80):
    valor = (formulario.get(nombre) or "").strip()
    if not valor:
        if obligatorio:
            raise ErrorJornada(f"Falta {etiqueta}.")
        return None
    if len(valor) > limite:
        raise ErrorJornada(f"{etiqueta} supera los {limite} caracteres.")
    return valor.replace(" · ", " - ")


def _hora(formulario, nombre, etiqueta):
    valor = (formulario.get(nombre) or "").strip()
    if not valor:
        raise ErrorJornada(f"Falta {etiqueta}.")
    if not _HORA.fullmatch(valor):
        raise ErrorJornada(f"{etiqueta} no es una hora válida.")
    return valor


def _cantidad(formulario, resultado):
    bruto = (formulario.get("cantidad") or "").strip()
    if resultado == "Sin sangre":
        if not bruto:
            return None
        if not bruto.isdigit():
            raise ErrorJornada("La cantidad extraída no es un número.")
        if int(bruto) > 0:
            raise ErrorJornada(
                "Si se extrajo sangre, el resultado es parcial o completa.")
        return 0
    if not bruto or not bruto.isdigit() or int(bruto) < 1:
        raise ErrorJornada("Falta la cantidad extraída.")
    return int(bruto)


def _unidades(formulario, crear):
    if not crear:
        return 0
    bruto = (formulario.get("unidades") or "").strip()
    if not bruto or not bruto.isdigit() or int(bruto) < 1:
        raise ErrorJornada("Indicá cuántas unidades se completaron.")
    return int(bruto)


def _observacion(formulario, accion):
    """
    `extraccion` solo tiene `observacion`. El procedimiento, el material,
    los horarios, la cantidad y la incidencia van ahí. El vencimiento
    no se pide: se calcula al crear cada unidad.
    """
    if accion not in ("finalizar", "incidencia"):
        raise ErrorJornada("Acción no admitida.")

    if accion == "incidencia":
        momento = _opcion(formulario, "momento", MOMENTOS, True, "el momento")
        tipo = _opcion(formulario, "tipo", TIPOS, True, "el tipo")
        descripcion = _texto(
            formulario, "incidencia", True, "la descripción", limite=500)
        resultado = _opcion(
            formulario, "resultado", RESULTADOS, True, "el resultado")
    else:
        momento = tipo = descripcion = None
        resultado = "Completa"

    completo = resultado == "Completa"
    con_sangre = resultado != "Sin sangre"
    brazo = _opcion(formulario, "brazo", BRAZOS, con_sangre, "el brazo")
    puncion = _opcion(formulario, "puncion", PUNCIONES, con_sangre, "la punción")
    reaccion = _opcion(formulario, "reaccion", REACCIONES, False, "la reacción")
    anticoagulante = _opcion(
        formulario, "anticoagulante", ANTICOAGULANTES, con_sangre,
        "el anticoagulante")
    bolsa = _opcion(formulario, "bolsa_tipo", BOLSAS, con_sangre, "el tipo de bolsa")
    marca = _texto(formulario, "marca", con_sangre, "la marca")
    inicio = _hora(formulario, "hora_inicio", "la hora de inicio")
    fin = _hora(formulario, "hora_fin", "la hora de finalización")
    if fin < inicio:
        raise ErrorJornada("La hora de finalización es anterior al inicio.")
    cantidad = _cantidad(formulario, resultado)
    n_unidades = _unidades(formulario, completo)
    tabuladora = _texto(
        formulario, "codigo_tabuladora", con_sangre, "el código de tabuladora")
    lote = _texto(formulario, "lote", con_sangre, "el lote")

    pares = (
        ("Brazo", brazo),
        ("Punción", puncion),
        ("Reacción", reaccion),
        ("Anticoagulante", anticoagulante),
        ("Bolsa", bolsa),
        ("Marca", marca),
        ("Inicio", inicio),
        ("Fin", fin),
        ("Cantidad", None if cantidad is None else f"{cantidad} ml"),
        ("Unidades", str(n_unidades)),
        ("Tabuladora", tabuladora),
        ("Lote", lote),
        ("Momento", momento),
        ("Tipo", tipo),
        ("Resultado", resultado),
        ("Incidencia", descripcion),
    )
    partes = [f"{clave}: {valor}" for clave, valor in pares if valor]
    return " · ".join(partes), n_unidades


def leer_campos(texto):
    return {m.group(1): m.group(2) for m in _PIEZAS.finditer(texto or "")}


def _resumen(extraccion, unidades):
    campos = leer_campos(extraccion.observacion if extraccion else "")
    flebotomia = " · ".join(
        v for v in (campos.get("Brazo"), campos.get("Punción")) if v)
    bolsa = " · ".join(
        v for v in (campos.get("Bolsa"), campos.get("Marca")) if v)
    vencimiento = None
    if unidades and unidades[0].fecha_vencimiento:
        vencimiento = unidades[0].fecha_vencimiento.strftime("%d/%m/%Y")
    filas = [
        ("Flebotomía", flebotomia, False),
        ("Reacción post-extracción", campos.get("Reacción"), False),
        ("Anticoagulante", campos.get("Anticoagulante"), False),
        ("Bolsa", bolsa, False),
        ("Hora de inicio", campos.get("Inicio"), False),
        ("Hora de finalización", campos.get("Fin"), False),
        ("Cantidad extraída", campos.get("Cantidad"), False),
        ("Unidades obtenidas", campos.get("Unidades"), False),
        ("Código de tabuladora", campos.get("Tabuladora"), True),
        ("Lote", campos.get("Lote"), True),
        ("Vencimiento", vencimiento, False),
        ("Momento", campos.get("Momento"), False),
        ("Tipo de incidencia", campos.get("Tipo"), False),
        ("Resultado", campos.get("Resultado"), False),
        ("Incidencia", campos.get("Incidencia"), False),
    ]
    return [f for f in filas if f[1]], campos


@licenciado_extraccion_bp.route("/atencion/<int:cita_id>/extraccion", methods=["GET", "POST"])
@requiere("lic", "personal_auth.ingresar")
def ver(cita_id):
    cita = jornada.cita_por_id(cita_id)
    if cita is None:
        flash("No existe esa cita.", "error")
        return redirect(url_for("licenciado_agendamientos.lista"))
    if cita.tipo_cita == jornada.Cita.MUESTRA:
        return redirect(url_for("licenciado_muestra.ver", cita_id=cita_id))
    personal = operador_actual()["usuario"]
    if request.method == "POST":
        try:
            accion = request.form.get("accion") or ""
            observacion, n_unidades = _observacion(request.form, accion)
            incidente = request.form.get("tipo") if accion == "incidencia" else None
            unidades = jornada.registrar_extraccion(
                cita, personal, observacion, n_unidades=n_unidades,
                incidente=incidente)
            for unidad in unidades:
                agendar_resultado(unidad.id_unidad)
        except ErrorJornada as exc:
            flash(str(exc), "error")
        else:
            return redirect(url_for("licenciado_extraccion.ver", cita_id=cita_id))
    extraccion = jornada.extraccion_de(cita)
    unidades = jornada.unidades_de(cita)
    filas, campos = _resumen(extraccion, unidades)
    return pintar(
        "licenciado/extraccion.html",
        cita=cita,
        apto=jornada.mediciones_aptas(cita),
        extraccion=extraccion,
        unidades=unidades,
        filas=filas,
        campos=campos,
        brazos=BRAZOS,
        punciones=PUNCIONES,
        reacciones=REACCIONES,
        anticoagulantes=ANTICOAGULANTES,
        bolsas=BOLSAS,
        momentos=MOMENTOS,
        incidentes=[] if extraccion else jornada.causas_de_incidente(),
        resultados=RESULTADOS,
    )
