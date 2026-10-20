"""
Jornada de enfermería sobre las tablas reales.

La cita del día se calcula con calendario.py. Los estados que se escriben
son los del CHECK de `cita`. «Diferido» de la maqueta queda como `No apto`
más un `registro_diferimiento`. No se agregan columnas.
"""
import secrets
from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import calendario
from app.controllers.portal.agenda import diferimiento_vigente
from app.models import (
    Auditoria, Cita, Cuestionario, Diferimiento, Extraccion, HorarioDisponible,
    Medicion, Notificacion, Pregunta, RegistroDiferimiento, TipoMedicion,
    TransicionEstado, Unidad, Usuario, db,
)

INSTITUCION_LOCAL = "Hospital Regional de Luque"

ETIQUETA_TIPO = {
    Cita.ALTRUISTA: "Altruista",
    Cita.REPOSICION: "Reposición",
    Cita.SOLIDARIA: "Solidaria",
    Cita.COMPATIBILIDAD: "Compatibilidad",
}

CAUSA_POR_MEDICION = {
    "TEMPERATURA": "Cuadro febril o gripal",
    "PESO": "Peso inferior al mínimo",
    "PAS": "Presión arterial fuera de rango",
    "PAD": "Presión arterial fuera de rango",
    "HB": "Hemoglobina baja",
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
        "ci": cita.donante.documento,
        "tipo": etiqueta_tipo(cita.tipo_cita),
        "estado": cita.estado,
        "donorId": cita.id_usuario,
        "tipoAgendamiento": (
            "Extracción de compatibilidad"
            if cita.tipo_cita == Cita.COMPATIBILIDAD else "Donación"),
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
    if cita.estado not in Cita.ACTIVAS:
        raise ErrorJornada("Esa cita ya no está pendiente de atención.")
    _exigir_ajeno(cita, personal)
    cita.estado = Cita.AUSENTE
    cita.id_personal = personal.id_usuario
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
    _commit()


def preguntas_parte_b():
    return (Pregunta.query
            .filter_by(parte=Pregunta.PARTE_PERSONAL)
            .order_by(Pregunta.id_pregunta)
            .all())


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

    ahora = datetime.now()
    existentes = respuestas_de(cita)
    for pregunta in preguntas:
        valor = (formulario.get(f"p{pregunta.id_pregunta}") or "").strip()
        if valor not in ("Si", "No"):
            raise ErrorJornada("Respondé todas las preguntas de la parte B.")
        fila_resp = existentes.get(pregunta.id_pregunta)
        if fila_resp is None:
            db.session.add(Cuestionario(
                id_cita=cita.id_cita,
                id_pregunta=pregunta.id_pregunta,
                id_donante=cita.id_usuario,
                id_personal=personal.id_usuario,
                valor=valor,
                fecha=ahora,
            ))
        else:
            fila_resp.valor = valor
            fila_resp.id_personal = personal.id_usuario
            fila_resp.fecha = ahora
    cita.estado = Cita.CONFIRMADA
    cita.id_personal = personal.id_usuario
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
    for tipo in tipos:
        texto = (formulario.get(tipo.codigo) or "").strip().replace(",", ".")
        try:
            valor = float(texto)
        except ValueError:
            raise ErrorJornada(f"Ingresá un número para {tipo.nombre}.")
        db.session.add(Medicion(
            id_cita=cita.id_cita,
            id_personal=personal.id_usuario,
            id_tipo_medicion=tipo.id_tipo_medicion,
            valor=valor,
            apto=False,
            fecha=ahora,
        ))
    cita.id_personal = personal.id_usuario
    _commit()


def causas_sugeridas(cita):
    """Nombres de catálogo que corresponden a mediciones no aptas."""
    nombres = []
    for medicion in mediciones_de(cita):
        if medicion.apto:
            continue
        nombre = CAUSA_POR_MEDICION.get(medicion.tipo.codigo)
        if nombre and nombre not in nombres:
            nombres.append(nombre)
    return nombres


def catalogo_diferimientos():
    return Diferimiento.query.order_by(Diferimiento.nombre).all()


def registrar_diferimiento(cita, personal, id_diferimiento, origen, institucion):
    _exigir_ajeno(cita, personal)
    causa = db.session.get(Diferimiento, id_diferimiento)
    if causa is None:
        raise ErrorJornada("Esa causa no está en el catálogo.")
    if origen not in (RegistroDiferimiento.CUESTIONARIO_PERSONAL,
                      RegistroDiferimiento.MEDICION):
        raise ErrorJornada("Ese origen no corresponde a esta pantalla.")
    institucion = (institucion or "").strip() or INSTITUCION_LOCAL
    if cita.estado not in (Cita.PENDIENTE, Cita.CONFIRMADA):
        raise ErrorJornada("Esta cita ya está cerrada.")

    db.session.add(RegistroDiferimiento(
        id_donante=cita.id_usuario,
        id_diferimiento=causa.id_diferimiento,
        id_cita=cita.id_cita,
        id_personal=personal.id_usuario,
        origen=origen,
        institucion_diagnostico=institucion,
        fecha_inicio=date.today(),
    ))
    cita.estado = Cita.NO_APTO
    cita.id_personal = personal.id_usuario
    Auditoria.registrar(personal.id_usuario, "CITA", cita.id_cita,
                        Auditoria.CAMBIO_ESTADO)
    _commit()


def _codigo(prefijo):
    marca = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefijo}-{marca}-{secrets.token_hex(2)}"


def extraccion_de(cita):
    return Extraccion.query.filter_by(id_cita=cita.id_cita).first()


def unidad_de(cita):
    extraccion = extraccion_de(cita)
    if extraccion is None:
        return None
    return Unidad.query.filter_by(id_extraccion=extraccion.id_extraccion).first()


def registrar_extraccion(cita, personal, observacion):
    _exigir_ajeno(cita, personal)
    if extraccion_de(cita) is not None:
        raise ErrorJornada("Esta cita ya tiene una extracción.")
    if not mediciones_aptas(cita):
        raise ErrorJornada(
            "No se extrae si falta una medición o alguna no es apta.")
    if cita.estado not in (Cita.PENDIENTE, Cita.CONFIRMADA):
        raise ErrorJornada("Esta cita ya está cerrada.")

    observacion = (observacion or "").strip()
    if not observacion:
        observacion = "Sin incidentes."

    extraccion = Extraccion(
        id_cita=cita.id_cita,
        id_personal=personal.id_usuario,
        codigo_unico=_codigo("EX"),
        fecha=datetime.now(),
        observacion=observacion,
    )
    db.session.add(extraccion)
    db.session.flush()

    unidad = Unidad(
        id_extraccion=extraccion.id_extraccion,
        id_donante=cita.id_usuario,
        codigo=_codigo("UN"),
        componente="sangre_total",
        estado=Unidad.REGISTRADA,
    )
    db.session.add(unidad)
    db.session.flush()

    # La base solo admite la transición Registrada → En laboratorio.
    # El alta es la fila en Registrada; no hay una fila con origen «Alta».
    db.session.add(TransicionEstado(
        id_unidad=unidad.id_unidad,
        id_personal=personal.id_usuario,
        estado_origen=Unidad.REGISTRADA,
        estado_destino=Unidad.EN_LABORATORIO,
        fecha=datetime.now(),
    ))
    unidad.estado = Unidad.EN_LABORATORIO
    cita.estado = Cita.COMPLETADA
    cita.id_personal = personal.id_usuario

    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.AGRADECIMIENTO,
        mensaje="Gracias por donar. Tu extracción quedó registrada en el banco de sangre.",
    ))
    Auditoria.registrar(personal.id_usuario, "UNIDAD", unidad.id_unidad,
                        Auditoria.CAMBIO_ESTADO)
    _commit()
    return unidad


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
        id_personal=personal.id_usuario,
        id_horario=elegida.id_horario,
        fecha_hora_creacion=datetime.combine(hoy, HORA_ESPONTANEA),
        estado=Cita.CONFIRMADA,
    )
    db.session.add(cita)
    db.session.flush()
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
    Una fila por cita cerrada, con la causa del diferimiento si esa cita
    terminó en No apto. La institución es siempre la local: las citas se
    atienden acá. Los diferimientos externos no tienen cita y van aparte.
    """
    causa_por_cita = {d.id_cita: d for d in diferimientos if d.id_cita}
    filas = []
    for cita in citas:
        if cita.estado in Cita.ACTIVAS:
            continue
        registro = causa_por_cita.get(cita.id_cita)
        filas.append({
            "fecha": cita.fecha_cita,
            "tipo": etiqueta_tipo(cita.tipo_cita),
            "estado": cita.estado,
            "institucion": INSTITUCION_LOCAL,
            "causa": registro.causa.nombre if registro else None,
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
    vigente = diferimiento_vigente(donante)
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
        "restriccion": restriccion_de(vigente),
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
