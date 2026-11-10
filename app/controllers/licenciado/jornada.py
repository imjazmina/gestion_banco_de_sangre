"""
Jornada de enfermería sobre las tablas reales.

La cita del día se calcula con calendario.py. Los estados que se escriben
son los del CHECK de `cita`. «Diferido» de la maqueta queda como `No apto`
más un `registro_diferimiento`. No se agregan columnas.
"""
import secrets
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import calendario
from app.controllers.comun.estados import CITA_CERRADA, id_al_cerrar
from app.controllers.licenciado import criterios
from app.controllers.portal.agenda import (
    diferimiento_vigente, diferimientos_vigentes, elegir_vigente,
)
from app.models import (
    Auditoria, Cita, Cuestionario, Diferimiento, Extraccion, HorarioDisponible,
    Medicion, MuestraCompatibilidad, Notificacion, Pregunta, RegistroDiferimiento,
    TipoMedicion, TransicionEstado, Unidad, Usuario, db,
)

INSTITUCION_LOCAL = "Hospital Regional de Luque"

ETIQUETA_TIPO = {
    Cita.ALTRUISTA: "Altruista",
    Cita.SOLIDARIA: "Solidaria",
    Cita.COMPATIBILIDAD: "Compatibilidad",
    Cita.MUESTRA: "Muestra",
}

ETIQUETA_AGENDAMIENTO = {
    Cita.ALTRUISTA: "Donación altruista",
    Cita.SOLIDARIA: "Donación solidaria",
    Cita.MUESTRA: "Extracción de muestra para compatibilidad",
}

class ErrorJornada(Exception):
    """La acción no se puede guardar. El mensaje se muestra al personal."""


def _commit():
    guardar = db.session.commit
    try:
        guardar()
    except SQLAlchemyError as exc:
        db.session.rollback()
        texto = str(getattr(exc, "orig", exc)).splitlines()[0]
        raise ErrorJornada(texto)


def etiqueta_tipo(tipo_cita):
    return ETIQUETA_TIPO.get(tipo_cita, tipo_cita)


def citas_del_dia(hoy=None):
    """Citas cuya fecha calculada es hoy, salvo las canceladas."""
    hoy = hoy or date.today()
    candidatas = Cita.query.filter(Cita.estado != Cita.CANCELADA, Cita.estado != Cita.PENDIENTE).all()
    del_dia = [c for c in candidatas if c.fecha_cita == hoy]
    return sorted(del_dia, key=lambda c: c.horario.hora_inicio)


HORA_ESPONTANEA = time(0, 1)


def es_espontanea(cita):
    """
    `cita` no guarda el origen. La única marca que deja `abrir_espontanea`
    es la hora de creación fija a las 00:01 del mismo día: eso no lo
    produce ninguna reserva del portal.
    """
    creada = cita.fecha_hora_creacion
    return (creada is not None and creada.time() == HORA_ESPONTANEA
            and creada.date() == cita.fecha_cita)


def fila(cita):
    """Datos que pinta la agenda. Los nombres siguen el valor del CHECK."""
    grupo = None
    if cita.donante.tipo_sangre is not None:
        grupo = cita.donante.tipo_sangre.etiqueta
    return {
        "id": cita.id_cita,
        "hora": cita.horario.hora_inicio.strftime("%H:%M"),
        "donante": cita.donante.nombre_completo,
        "ci": cita.donante.documento_visible,
        "tipo": etiqueta_tipo(cita.tipo_cita),
        "estado": cita.estado,
        "donorId": cita.id_usuario,
        "tipoAgendamiento": ETIQUETA_AGENDAMIENTO.get(
            cita.tipo_cita, cita.tipo_cita),
        "origen": "Espontáneo" if es_espontanea(cita) else "Agendada",
        "solicitudId": cita.id_solicitud or "",
        "grupo": grupo,
    }


def pendientes_primero(filas):
    """Las que faltan atender arriba; dentro de cada grupo, por hora."""
    return sorted(filas, key=lambda f: (f["estado"] not in Cita.ACTIVAS, f["hora"]))


def resumen_estados(citas, orden, colores):
    total = len(citas) or 1
    return [
        {"estado": estado, "n": sum(1 for c in citas if c.estado == estado),
         "pct": round(100 * sum(1 for c in citas if c.estado == estado) / total, 1),
         "color": colores.get(estado, "#6B7280")}
        for estado in orden
    ]


def cita_por_id(cita_id):
    return db.session.get(Cita, cita_id)


def _exigir_ajeno(cita, personal):
    if cita.id_usuario == personal.id_usuario:
        raise ErrorJornada("No podés atender tu propia donación.")


def marcar_ausente(cita, personal):
    if cita.estado != Cita.CONFIRMADA:
        raise ErrorJornada("Solo una cita confirmada puede quedar ausente.")
    _exigir_ajeno(cita, personal)
    cita.id_personal = id_al_cerrar(Cita.AUSENTE, personal, CITA_CERRADA, ErrorJornada)
    cita.estado = Cita.AUSENTE
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
    _commit()


def preguntas_parte_b():
    """La parte B del catálogo. La aclaración no se lista como pregunta aparte."""
    from app.controllers.portal.cuestionario import principales

    filas = (Pregunta.query
             .filter_by(parte=Pregunta.PARTE_PERSONAL)
             .order_by(Pregunta.id_pregunta)
             .all())
    return principales(filas)


def respuestas_de(cita):
    filas = Cuestionario.query.filter_by(id_cita=cita.id_cita).all()
    return {f.id_pregunta: f for f in filas}


def parte_b_completa(cita):
    hechas = respuestas_de(cita)
    return all(p.id_pregunta in hechas for p in preguntas_parte_b())


def guardar_parte_b(cita, personal, formulario):
    _exigir_ajeno(cita, personal)
    if cita.estado not in (Cita.PENDIENTE, Cita.CONFIRMADA):
        raise ErrorJornada("Esta cita ya no admite el cuestionario de sala.")
    preguntas = preguntas_parte_b()
    if not preguntas:
        raise ErrorJornada("No hay preguntas de la parte B en el catálogo.")

    from app.controllers.portal.cuestionario import _valor

    ahora = datetime.now()
    existentes = respuestas_de(cita)
    nuevas = []
    modificadas = []
    for pregunta in preguntas:
        valor = (formulario.get(f"p{pregunta.id_pregunta}") or "").strip()
        if valor not in ("Si", "No"):
            raise ErrorJornada("Respondé todas las preguntas de la parte B.")
        detalle = formulario.get(f"p{pregunta.id_pregunta}_detalle")
        if getattr(pregunta, "exige_detalle", False) and valor != "Si":
            detalle = ""
        elif getattr(pregunta, "exige_detalle", False) and not (detalle or "").strip():
            raise ErrorJornada(
                "Completá la aclaración de las preguntas respondidas con sí.")
        if getattr(pregunta, "exige_detalle", False):
            valor = _valor(valor, detalle)
        fila_resp = existentes.get(pregunta.id_pregunta)
        if fila_resp is None:
            fila_resp = Cuestionario(
                id_cita=cita.id_cita,
                id_pregunta=pregunta.id_pregunta,
                id_donante=cita.id_usuario,
                id_personal=personal.id_usuario,
                valor=valor,
                fecha=ahora,
            )
            db.session.add(fila_resp)
            nuevas.append(fila_resp)
        else:
            fila_resp.valor = valor
            fila_resp.id_personal = personal.id_usuario
            fila_resp.fecha = ahora
            modificadas.append(fila_resp)
    db.session.flush()
    if nuevas:
        Auditoria.registrar(personal.id_usuario, "CUESTIONARIO",
                            nuevas[0].id_cuestionario, Auditoria.ALTA)
    elif modificadas:
        Auditoria.registrar(personal.id_usuario, "CUESTIONARIO",
                            modificadas[0].id_cuestionario, Auditoria.MODIFICACION)
    _commit()


def tipos_medicion():
    return TipoMedicion.query.order_by(TipoMedicion.id_tipo_medicion).all()


def mediciones_de(cita):
    return Medicion.query.filter_by(id_cita=cita.id_cita).all()


def mediciones_aptas(cita):
    filas = mediciones_de(cita)
    if len(filas) < TipoMedicion.query.count():
        return False
    return all(m.apto for m in filas)


def guardar_mediciones(cita, personal, formulario):
    _exigir_ajeno(cita, personal)
    if not parte_b_completa(cita):
        raise ErrorJornada("Primero completá la parte B del cuestionario.")
    if mediciones_de(cita):
        raise ErrorJornada("Los signos de esta cita ya fueron registrados.")
    if cita.estado not in (Cita.PENDIENTE, Cita.CONFIRMADA):
        raise ErrorJornada("Esta cita ya no admite mediciones.")

    tipos = tipos_medicion()
    ahora = datetime.now()
    filas = []
    for tipo in tipos:
        texto = (formulario.get(tipo.codigo) or "").strip().replace(",", ".")
        try:
            valor = float(texto)
        except ValueError:
            raise ErrorJornada(f"Ingresá un número para {tipo.nombre}.")
        fila = Medicion(
            id_cita=cita.id_cita,
            id_personal=personal.id_usuario,
            id_tipo_medicion=tipo.id_tipo_medicion,
            valor=valor,
            apto=False,
            observaciones=fuera_de_rango(tipo, valor),
            fecha=ahora,
        )
        db.session.add(fila)
        filas.append(fila)
    db.session.flush()
    for fila in filas:
        Auditoria.registrar(personal.id_usuario, "MEDICION",
                            fila.id_medicion, Auditoria.ALTA)
    _commit()


def fuera_de_rango(tipo, valor):
    """Qué umbral no cumplió el valor, o None si está en rango."""
    minimo, maximo = float(tipo.valor_minimo), float(tipo.valor_maximo)
    if valor < minimo:
        return f"Por debajo del mínimo ({minimo:g} {tipo.unidad})"
    if valor > maximo:
        return f"Por encima del máximo ({maximo:g} {tipo.unidad})"
    return None


def _causas_por_nombre(nombres):
    """Las filas del catálogo, en el orden pedido. Falla si falta alguna."""
    filas = {c.nombre: c for c in
             Diferimiento.query.filter(Diferimiento.nombre.in_(nombres)).all()}
    faltan = [n for n in nombres if n not in filas]
    if faltan:
        raise ErrorJornada(f"Falta en el catálogo la causa «{faltan[0]}».")
    return [filas[n] for n in nombres]


def mediciones_fuera_de_rango(cita):
    """
    Cada medición no apta con la causa que le corresponde según hacia dónde
    se salió del rango. `apto` lo calculó la base; acá solo se nombra.
    """
    filas = []
    for medicion in mediciones_de(cita):
        if medicion.apto:
            continue
        tipo = medicion.tipo
        nombre = criterios.causa_de_medicion(
            tipo.codigo, float(medicion.valor),
            float(tipo.valor_minimo), float(tipo.valor_maximo))
        filas.append((medicion, nombre))
    return filas


def causas_de_medicion_posibles():
    nombres = list(dict.fromkeys(
        n for par in criterios.MEDICION.values() for n in par))
    return _causas_por_nombre(nombres)


def causas_de_medicion(cita):
    nombres = list(dict.fromkeys(
        n for _, n in mediciones_fuera_de_rango(cita) if n))
    return _causas_por_nombre(nombres) if nombres else []


def causas_cuestionario():
    """Lo que ofrece el autocompletado: causas temporales del cuestionario."""
    return [c for c in _causas_por_nombre(list(criterios.CUESTIONARIO))
            if c.tipo == Diferimiento.TEMPORAL]


def motivos_cuestionario(cita):
    """
    Las preguntas que, según la respuesta, generan un diferimiento temporal.

    Parte A sale de lo que el donante ya envió. Parte B se pinta entera con
    la respuesta que difiere: la pantalla la muestra u oculta según lo que
    marque el personal, porque todavía no está guardada.
    """
    from app.controllers.portal import cuestionario as parte_a

    por_nombre = {c.nombre: c for c in causas_cuestionario()}
    respondidas = respuestas_de(cita)
    motivos = []

    def agregar(id_pregunta, enunciado, parte, numero):
        regla = criterios.POR_PREGUNTA.get(enunciado)
        if regla is None:
            return
        respuesta, nombres = regla
        causas = [por_nombre[n] for n in nombres if n in por_nombre]
        if not causas:
            return
        fila = respondidas.get(id_pregunta)
        dada = fila.valor.split(" — ")[0] if fila else None
        if parte == "A" and dada != respuesta:
            return
        motivos.append({
            "id_pregunta": id_pregunta, "parte": parte, "numero": numero,
            "enunciado": enunciado, "respuesta": respuesta,
            "activo": dada == respuesta, "causas": causas,
        })

    for item in parte_a.preguntas():
        agregar(item.id_pregunta, item.enunciado, "A", item.orden)
    for numero, pregunta in enumerate(preguntas_parte_b(), start=1):
        agregar(pregunta.id_pregunta, pregunta.enunciado, "B", numero)
    return motivos


def _ids(crudos):
    vistos = []
    for crudo in crudos or []:
        try:
            clave = int(crudo)
        except (TypeError, ValueError):
            raise ErrorJornada("Esa causa no está en el catálogo.")
        if clave not in vistos:
            vistos.append(clave)
    return vistos


def _registrar_causas(cita, personal, causas, origen, institucion):
    """
    Un registro por causa, en la misma atención. No hace commit.

    `fecha_fin` la escribe el trigger: inicio más días si es temporal,
    nula si es permanente.
    """
    hoy = date.today()
    registros = []
    for causa in causas:
        registro = RegistroDiferimiento(
            id_donante=cita.id_usuario,
            id_diferimiento=causa.id_diferimiento,
            id_cita=cita.id_cita,
            id_personal=personal.id_usuario,
            origen=origen,
            institucion_diagnostico=institucion,
            fecha_inicio=hoy,
        )
        db.session.add(registro)
        registros.append(registro)
    db.session.flush()
    for causa, registro in zip(causas, registros):
        db.session.refresh(registro)
        if causa.tipo == Diferimiento.TEMPORAL and registro.fecha_fin is None:
            db.session.rollback()
            raise ErrorJornada(
                "El diferimiento temporal no quedó con fecha de finalización.")
        if causa.tipo == Diferimiento.PERMANENTE and registro.fecha_fin is not None:
            db.session.rollback()
            raise ErrorJornada(
                "El diferimiento permanente no admite fecha de finalización.")
    for registro in registros:
        Auditoria.registrar(personal.id_usuario, "REGISTRO_DIFERIMIENTO",
                            registro.id_registro, Auditoria.ALTA)
    return registros


def _cerrar_no_apto(cita, personal):
    cita.id_personal = id_al_cerrar(Cita.NO_APTO, personal, CITA_CERRADA, ErrorJornada)
    cita.estado = Cita.NO_APTO
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)


def registrar_diferimiento(cita, personal, ids_diferimiento, institucion):
    """
    Diferimiento desde el cuestionario de sala. Solo admite causas temporales
    del cuestionario. La cita pasa a No apto una sola vez.
    """
    _exigir_ajeno(cita, personal)
    if cita.estado != Cita.CONFIRMADA:
        raise ErrorJornada("Solo una cita confirmada puede quedar no apta.")
    vistos = _ids(ids_diferimiento)
    if not vistos:
        raise ErrorJornada("Elegí al menos un motivo.")
    permitidas = {c.id_diferimiento: c for c in causas_cuestionario()}
    if any(clave not in permitidas for clave in vistos):
        raise ErrorJornada(
            "Ese motivo no es un diferimiento temporal del cuestionario.")
    institucion = (institucion or "").strip() or INSTITUCION_LOCAL
    _registrar_causas(cita, personal, [permitidas[c] for c in vistos],
                      RegistroDiferimiento.CUESTIONARIO_PERSONAL, institucion)
    _cerrar_no_apto(cita, personal)
    _commit()


def diferir_por_mediciones(cita, personal):
    """
    Las causas salen de las mediciones no aptas; el personal no las elige.
    La cita pasa a No apto.
    """
    _exigir_ajeno(cita, personal)
    if cita.estado != Cita.CONFIRMADA:
        raise ErrorJornada("Solo una cita confirmada puede quedar no apta.")
    causas = causas_de_medicion(cita)
    if not causas:
        raise ErrorJornada("No hay mediciones fuera de rango para diferir.")
    _registrar_causas(cita, personal, causas,
                      RegistroDiferimiento.MEDICION, INSTITUCION_LOCAL)
    _cerrar_no_apto(cita, personal)
    _commit()


def _codigo(prefijo):
    marca = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefijo}-{marca}-{secrets.token_hex(2)}"


def extraccion_de(cita):
    return Extraccion.query.filter_by(id_cita=cita.id_cita).first()


def unidades_de(cita):
    extraccion = extraccion_de(cita)
    if extraccion is None:
        return []
    return (Unidad.query
            .filter_by(id_extraccion=extraccion.id_extraccion)
            .order_by(Unidad.id_unidad)
            .all())


def causas_de_incidente():
    """Cada tipo de incidente de extracción con su fila del catálogo."""
    tipos = list(criterios.EXTRACCION)
    causas = _causas_por_nombre([criterios.EXTRACCION[t] for t in tipos])
    return list(zip(tipos, causas))


def registrar_extraccion(cita, personal, observacion, n_unidades=0, incidente=None):
    """
    Cierra la cita y deja la extracción.
    Cada unidad completada pasa a laboratorio, con vencimiento a 30 días.
    Si no se completó ninguna, no hay fila en unidad ni código de unidad.
    El incidente, si lo hay, deja su diferimiento de origen EXTRACCION; la
    cita igual queda Completada.
    """
    _exigir_ajeno(cita, personal)
    if cita.tipo_cita == Cita.MUESTRA:
        raise ErrorJornada("Esta cita registra una muestra, no unidades.")
    if extraccion_de(cita) is not None:
        raise ErrorJornada("Esta cita ya tiene una extracción.")
    if not mediciones_aptas(cita):
        raise ErrorJornada(
            "No se extrae si falta una medición o alguna no es apta.")
    if cita.estado != Cita.CONFIRMADA:
        raise ErrorJornada("Solo una cita confirmada puede completarse.")
    if n_unidades < 0:
        raise ErrorJornada("La cantidad de unidades no es válida.")
    causa_incidente = None
    if incidente is not None:
        if incidente not in criterios.EXTRACCION:
            raise ErrorJornada("Ese incidente no corresponde a la extracción.")
        causa_incidente = _causas_por_nombre([criterios.EXTRACCION[incidente]])[0]

    observacion = (observacion or "").strip()
    if not observacion:
        observacion = "Sin incidentes."

    fecha = datetime.now()
    extraccion = Extraccion(
        id_cita=cita.id_cita,
        id_personal=personal.id_usuario,
        codigo_unico=_codigo("EX"),
        fecha=fecha,
        observacion=observacion,
    )
    db.session.add(extraccion)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "EXTRACCION",
                        extraccion.id_extraccion, Auditoria.ALTA)

    unidades = []
    vencimiento = fecha.date() + timedelta(days=30)
    for _ in range(n_unidades):
        unidad = Unidad(
            id_extraccion=extraccion.id_extraccion,
            id_donante=cita.id_usuario,
            codigo=_codigo("UN"),
            estado=Unidad.REGISTRADA,
            fecha_vencimiento=vencimiento,
        )
        db.session.add(unidad)
        db.session.flush()
        Auditoria.registrar(personal.id_usuario, "UNIDAD", unidad.id_unidad,
                            Auditoria.ALTA)
        db.session.add(TransicionEstado(
            id_unidad=unidad.id_unidad,
            id_personal=personal.id_usuario,
            estado_origen=Unidad.REGISTRADA,
            estado_destino=Unidad.EN_LABORATORIO,
            fecha=fecha,
        ))
        unidad.estado = Unidad.EN_LABORATORIO
        Auditoria.registrar(personal.id_usuario, "UNIDAD", unidad.id_unidad,
                            Auditoria.CAMBIO_ESTADO)
        unidades.append(unidad)

    if unidades:
        db.session.add(Notificacion(
            id_usuario=cita.id_usuario,
            id_cita=cita.id_cita,
            tipo=Notificacion.AGRADECIMIENTO,
            mensaje="Gracias por donar. Tu extracción quedó registrada en el banco de sangre.",
        ))

    if causa_incidente is not None:
        _registrar_causas(cita, personal, [causa_incidente],
                          RegistroDiferimiento.EXTRACCION, INSTITUCION_LOCAL)

    cita.id_personal = id_al_cerrar(Cita.COMPLETADA, personal, CITA_CERRADA, ErrorJornada)
    cita.estado = Cita.COMPLETADA
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
    _commit()
    return unidades


def muestra_de(cita):
    extraccion = extraccion_de(cita)
    if extraccion is None:
        return None
    return (MuestraCompatibilidad.query
            .filter_by(id_extraccion=extraccion.id_extraccion)
            .first())


def registrar_muestra(cita, personal, observacion):
    """Cierra la cita con una muestra. No crea unidades ni vencimiento."""
    _exigir_ajeno(cita, personal)
    if cita.tipo_cita != Cita.MUESTRA:
        raise ErrorJornada("Esta cita no es una extracción de muestra.")
    from app.models import Solicitud
    solicitud = (Solicitud.query
                 .filter_by(id_solicitante=cita.id_usuario, estado=Solicitud.CREADA)
                 .order_by(Solicitud.fecha_creacion.desc())
                 .first())
    if solicitud is None:
        raise ErrorJornada("La muestra no está asociada a una solicitud creada.")
    if extraccion_de(cita) is not None:
        raise ErrorJornada("Esta cita ya tiene una extracción.")
    if not mediciones_aptas(cita):
        raise ErrorJornada(
            "No se extrae si falta una medición o alguna no es apta.")
    if cita.estado != Cita.CONFIRMADA:
        raise ErrorJornada("Solo una cita confirmada puede completarse.")

    observacion = (observacion or "").strip() or "Muestra venosa sin incidentes."
    fecha = datetime.now()
    extraccion = Extraccion(
        id_cita=cita.id_cita,
        id_personal=personal.id_usuario,
        codigo_unico=_codigo("EX"),
        fecha=fecha,
        observacion=observacion,
    )
    db.session.add(extraccion)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "EXTRACCION",
                        extraccion.id_extraccion, Auditoria.ALTA)
    muestra = MuestraCompatibilidad(
        id_extraccion=extraccion.id_extraccion,
        id_solicitud=solicitud.id_solicitud,
        fecha=fecha,
    )
    db.session.add(muestra)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "MUESTRA_COMPATIBILIDAD",
                        muestra.id_muestra, Auditoria.ALTA)
    cita.id_personal = id_al_cerrar(Cita.COMPLETADA, personal, CITA_CERRADA, ErrorJornada)
    cita.estado = Cita.COMPLETADA
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
    _commit()
    return muestra


def buscar_donante(documento):
    documento = (documento or "").strip()
    if not documento:
        return None
    return Usuario.query.filter_by(documento=documento).first()


def abrir_espontanea(donante, personal):
    """Crea la cita de quien llega sin reserva, si la base lo permite."""
    if donante.id_usuario == personal.id_usuario:
        raise ErrorJornada("No podés abrir una atención sobre tu propia cuenta.")
    if diferimiento_vigente(donante):
        raise ErrorJornada(
            "Hay un diferimiento vigente. No se abre una atención nueva.")
    vigente = (Cita.query
               .filter(Cita.id_usuario == donante.id_usuario,
                       Cita.estado.in_(Cita.ACTIVAS))
               .first())
    if vigente is not None:
        return vigente

    hoy = date.today()
    nombre_dia = calendario.INDICE_A_DIA.get(hoy.weekday())
    franjas = (HorarioDisponible.query
               .filter_by(dia_semana=nombre_dia, disponible=True)
               .order_by(HorarioDisponible.hora_inicio)
               .all())
    elegida = None
    for franja in franjas:
        ocupados = (db.session.query(func.count(Cita.id_cita))
                    .filter(Cita.id_horario == franja.id_horario,
                            Cita.estado.in_(Cita.ACTIVAS))
                    .scalar())
        if ocupados < franja.cupo_atencion:
            elegida = franja
            break
    if elegida is None:
        raise ErrorJornada("No queda cupo en las franjas de hoy.")

    cita = Cita(
        tipo_cita=Cita.ALTRUISTA,
        id_usuario=donante.id_usuario,
        id_horario=elegida.id_horario,
        fecha_hora_creacion=datetime.combine(hoy, HORA_ESPONTANEA),
        estado=Cita.CONFIRMADA,
    )
    db.session.add(cita)
    db.session.flush()
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.ALTA)
    db.session.add(Notificacion(
        id_usuario=donante.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.CONFIRMACION_CITA,
        mensaje="El banco de sangre registró tu atención de hoy.",
    ))
    _commit()
    return cita


def edad_de(donante, hoy=None):
    hoy = hoy or date.today()
    nacio = donante.fecha_nacimiento
    if nacio is None:
        return None
    return hoy.year - nacio.year - ((hoy.month, hoy.day) < (nacio.month, nacio.day))


def restriccion_de(registro):
    """
    Cómo se muestra un diferimiento vigente: `externo` si el diagnóstico es
    de otra institución, si no el tipo del catálogo. Es solo presentación.
    """
    if registro is None:
        return "ninguna"
    if registro.institucion_diagnostico != INSTITUCION_LOCAL:
        return "externo"
    if registro.causa.tipo == Diferimiento.PERMANENTE:
        return "permanente"
    return "temporal"


def historial(citas, diferimientos):
    """
    Una fila por cita cerrada. Si esa atención tiene varios diferimientos,
    cada uno conserva motivo, tipo, inicio y fin. Los externos no tienen
    cita y van aparte.
    """
    por_cita = {}
    for registro in diferimientos:
        if registro.id_cita:
            por_cita.setdefault(registro.id_cita, []).append(registro)
    filas = []
    for cita in citas:
        if cita.estado in Cita.ACTIVAS:
            continue
        filas.append({
            "fecha": cita.fecha_cita,
            "tipo": etiqueta_tipo(cita.tipo_cita),
            "estado": cita.estado,
            "institucion": INSTITUCION_LOCAL,
            "causas": [{
                "nombre": registro.causa.nombre,
                "tipo": registro.causa.tipo,
                "inicio": registro.fecha_inicio,
                "fin": registro.fecha_fin,
            } for registro in por_cita.get(cita.id_cita, [])],
        })
    filas.sort(key=lambda f: f["fecha"] or date.min, reverse=True)
    return filas


def ficha(id_usuario):
    """Historial interno. Incluye serología: esta pantalla no es del portal."""
    from app.models import ResultadoLaboratorio

    donante = db.session.get(Usuario, id_usuario)
    if donante is None:
        return None
    citas = (Cita.query
             .filter_by(id_usuario=id_usuario)
             .order_by(Cita.fecha_hora_creacion.desc())
             .filter(Cita.estado.in_([Cita.COMPLETADA, Cita.NO_APTO]))
             .all()
            )
    diferimientos = (RegistroDiferimiento.query
                     .filter_by(id_donante=id_usuario)
                     .order_by(RegistroDiferimiento.fecha_inicio.desc())
                     .all())
    vigentes = diferimientos_vigentes(donante)
    vigente = elegir_vigente(vigentes)
    completadas = [c for c in citas if c.estado == Cita.COMPLETADA]
    fechas_completadas = [c.fecha_cita for c in completadas if c.fecha_cita]
    unidades = Unidad.query.filter_by(id_donante=id_usuario).all()
    transiciones = []
    resultados = []
    for unidad in unidades:
        transiciones.extend(
            TransicionEstado.query
            .filter_by(id_unidad=unidad.id_unidad)
            .order_by(TransicionEstado.fecha)
            .all())
        resultado = ResultadoLaboratorio.query.filter_by(
            id_unidad=unidad.id_unidad).first()
        if resultado is not None:
            resultados.append(resultado)
    confirmada = (Cita.query
                  .filter_by(id_usuario=id_usuario, estado=Cita.CONFIRMADA)
                  .order_by(Cita.fecha_hora_creacion.desc())
                  .first())
    return {
        "donante": donante,
        "edad": edad_de(donante),
        "cita_abierta": confirmada,
        "citas": citas,
        "historial": historial(citas, diferimientos),
        "total_donaciones": len(completadas),
        "ultima_donacion": max(fechas_completadas) if fechas_completadas else None,
        "vigente": vigente,
        "vigentes": vigentes,
        "restriccion": restriccion_de(vigente),
        "externo_activo": any(
            r.institucion_diagnostico.strip().lower() != INSTITUCION_LOCAL.lower()
            for r in vigentes),
        "diferimientos": diferimientos,
        "unidades": unidades,
        "transiciones": transiciones,
        "resultados": resultados,
        "mediciones": (Medicion.query
                       .join(Cita, Cita.id_cita == Medicion.id_cita)
                       .filter(Cita.id_usuario == id_usuario)
                       .all()),
        "cuestionarios": (Cuestionario.query
                          .filter_by(id_donante=id_usuario)
                          .all()),
    }
