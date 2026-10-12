"""
Cuestionario previo a la donación.

Son 36 preguntas: en una sola pantalla de celular no se responden, así que
la pantalla las muestra en tres pasos, uno por bloque del formulario
original. Esos pasos solo cambian de vista. Las respuestas viven en el
formulario hasta que la persona aprieta «Enviar cuestionario»: ahí se
validan las 36 y se insertan juntas. Si algo falla, no queda nada escrito
y la cita no pasa a confirmada.

La tabla `pregunta` guarda el enunciado y poco más; el bloque, el número y
la aclaración que piden algunas viven en preguntas.py y se emparejan por el
enunciado. Acá se juntan las dos mitades en un solo objeto para que las
pantallas no tengan que saber de dónde sale cada dato.

Lo que el portal NO hace: decidir. Una respuesta marcada no rechaza al
donante ni cancela la cita. El personal de salud lee el cuestionario y
decide en el momento, que es como tiene que ser.
"""
from collections import namedtuple
from datetime import date, datetime

from flask import current_app

from app.controllers.portal import preguntas as catalogo
from app.models import Cita, Cuestionario, Pregunta, db

SECCIONES = catalogo.SECCIONES

SI = "Si"
NO = "No"
LARGO_DETALLE = 180

# Una pregunta lista para mostrar: la fila de la base más los datos de
# formulario que el esquema no guarda.
Item = namedtuple(
    "Item", "id_pregunta orden seccion enunciado nota pide_detalle "
            "etiqueta_detalle alerta_si")


def _items():
    """
    Las preguntas del donante, ya emparejadas y en orden.

    Una fila de la base sin entrada en el catálogo queda afuera: es una
    pregunta vieja o de prueba, y mostrarla sin bloque ni número la pondría
    en cualquier lado del formulario.
    """
    filas = Pregunta.query.filter(
        Pregunta.parte == Pregunta.PARTE_DONANTE).all()

    items = []
    for fila in filas:
        datos = catalogo.datos_de(fila.enunciado)
        if datos is None:
            continue
        items.append(Item(
            id_pregunta=fila.id_pregunta,
            orden=datos.orden,
            seccion=datos.seccion,
            enunciado=fila.enunciado,
            nota=datos.nota,
            pide_detalle=datos.detalle is not None,
            etiqueta_detalle=datos.detalle,
            alerta_si=datos.alerta))
    return sorted(items, key=lambda i: i.orden)


def preguntas(seccion=None):
    """Las preguntas del cuestionario del donante, o las de un bloque."""
    items = _items()
    if seccion is None:
        return items
    return [i for i in items if i.seccion == seccion]


def respuestas(cita):
    """Lo ya respondido de esta cita, como {id_pregunta: fila}."""
    filas = Cuestionario.query.filter_by(id_cita=cita.id_cita).all()
    return {f.id_pregunta: f for f in filas}


class ErrorCuestionario(Exception):
    """El envío no se guardó. El texto es el que ve la persona."""


def _valor(respuesta, detalle):
    """
    Arma el texto que se guarda.

    La columna `valor` es una sola: la respuesta y su aclaración van juntas
    separadas por un guion, que es como se leen después ("Si — ibuprofeno").
    """
    detalle = (detalle or "").strip()[:LARGO_DETALLE]
    return f"{respuesta} — {detalle}" if detalle else respuesta


def _mensaje_faltantes(ordenes):
    """Texto corto para la persona cuando falta alguna de las 36."""
    if len(ordenes) == 1:
        cuales = f"la pregunta {ordenes[0]}"
    elif len(ordenes) <= 6:
        previas = ", ".join(str(n) for n in ordenes[:-1])
        cuales = f"las preguntas {previas} y {ordenes[-1]}"
    else:
        cuales = "varias preguntas"
    return (f"No pudimos enviar el cuestionario. Falta responder {cuales}. "
            f"Tus respuestas siguen en esta pantalla: completalas y volvé a enviarlo.")


def enviar(cita, usuario, formulario):
    """
    Valida las 36 respuestas y, si están todas, las inserta y confirma la cita.

    Una sola transacción: o quedan las 36 filas y la cita en Confirmada, o
    no queda nada. No actualiza respuestas que ya existían.
    """
    items = preguntas()
    if len(items) != len(catalogo.PREGUNTAS):
        current_app.logger.error(
            "Cita %s: el cuestionario del donante tiene %s preguntas "
            "emparejadas y el catálogo tiene %s",
            cita.id_cita, len(items), len(catalogo.PREGUNTAS))
        raise ErrorCuestionario(
            "No pudimos enviar el cuestionario. Intentá de nuevo más tarde.")

    faltan = []
    cambios = []
    for pregunta in items:
        clave = f"p{pregunta.id_pregunta}"
        respuesta = (formulario.get(clave) or "").strip()
        if respuesta not in (SI, NO):
            faltan.append(pregunta.orden)
            continue
        cambios.append((pregunta,
                        _valor(respuesta, formulario.get(f"{clave}_detalle"))))

    if faltan:
        current_app.logger.warning(
            "Cita %s: cuestionario rechazado, faltan las preguntas %s",
            cita.id_cita, faltan)
        raise ErrorCuestionario(_mensaje_faltantes(faltan))

    ya = respuestas(cita)
    if any(p.id_pregunta in ya for p in items):
        current_app.logger.error(
            "Cita %s: ya tiene respuestas del cuestionario del donante; "
            "no se sobrescriben", cita.id_cita)
        raise ErrorCuestionario(
            "Este cuestionario ya fue enviado y no se puede modificar.")

    ahora = datetime.now()
    try:
        for pregunta, valor in cambios:
            db.session.add(Cuestionario(
                id_cita=cita.id_cita, id_pregunta=pregunta.id_pregunta,
                id_donante=usuario.id_usuario, valor=valor, fecha=ahora))
        cita.estado = Cita.CONFIRMADA
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Cita %s: falló el guardado del cuestionario", cita.id_cita)
        raise ErrorCuestionario(
            "No pudimos enviar el cuestionario. Tus respuestas siguen en "
            "esta pantalla: intentá de nuevo.")


def completo(cita):
    """True si las 36 preguntas del donante ya tienen fila en esta cita."""
    items = preguntas()
    if len(items) != len(catalogo.PREGUNTAS):
        return False
    ya = respuestas(cita)
    return all(p.id_pregunta in ya for p in items)


def avance(cita):
    """(respondidas, total) para la barra de progreso."""
    return len(respuestas(cita)), len(preguntas())


def resumen(cita):
    """
    Las respuestas de la cita, ordenadas, con las marcadas identificadas.

    `atencion` son las que coinciden con la respuesta que el personal tiene
    que revisar. No es un veredicto: es lo que mira primero.
    """
    ya = respuestas(cita)
    filas, atencion = [], []
    for pregunta in preguntas():
        fila = ya.get(pregunta.id_pregunta)
        if fila is None:
            continue
        marcada = (pregunta.alerta_si is not None
                   and fila.valor.split(" — ")[0] == pregunta.alerta_si)
        filas.append((pregunta, fila.valor, marcada))
        if marcada:
            atencion.append(pregunta.orden)
    return filas, atencion


def habilitado(cita):
    """
    ¿Se puede responder el cuestionario de esta cita ahora?

    Solo el mismo día. El cuestionario pregunta por el estado de salud de
    hoy —si durmió bien, si tomó alcohol, si está con fiebre—, así que una
    respuesta de hace tres días no dice nada sobre el donante que se
    presenta. Por eso se habilita recién el día de la cita, que es cuando el
    correo con el enlace también llega.
    """
    if cita is None or cita.estado not in Cita.ACTIVAS:
        return False
    return cita.fecha_cita == date.today()


def motivo_no_habilitado(cita):
    """Qué decirle a la persona cuando todavía no puede responderlo."""
    if cita is None or cita.estado not in Cita.ACTIVAS:
        return "No encontramos esa cita entre las tuyas."
    if cita.fecha_cita > date.today():
        return (f"El cuestionario se habilita el día de tu cita, el "
                f"{cita.fecha_cita.strftime('%d/%m/%Y')}. Te va a llegar el "
                f"enlace por correo unas horas antes.")
    return ("El día de esa cita ya pasó y el cuestionario quedó cerrado. "
            "Si necesitás ayuda, comunicate con el banco de sangre.")


def cita_del_donante(id_cita, usuario):
    """
    La cita, solo si es de esta persona y hoy se puede responder.

    Devuelve None si no existe, si es de otro donante, si ya se cerró o si
    todavía no es el día.
    """
    cita = Cita.query.filter_by(id_cita=id_cita,
                                id_usuario=usuario.id_usuario).first()
    return cita if habilitado(cita) else None


def cita_para_avisar(id_cita, usuario):
    """
    La cita del donante sin la restricción del día.

    La usan las pantallas que solo necesitan explicar por qué todavía no se
    puede responder, no dejar responder.
    """
    return Cita.query.filter_by(id_cita=id_cita,
                                id_usuario=usuario.id_usuario).first()
