"""
Cuestionario previo a la donación.

Son 36 preguntas: en una sola pantalla de celular no se responden, así que
van en tres pasos, uno por bloque del formulario original. Cada paso se
guarda al pasar al siguiente, de modo que si se corta la conexión o se
cierra el navegador no hay que empezar de nuevo.

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


def _valor(respuesta, detalle):
    """
    Arma el texto que se guarda.

    La columna `valor` es una sola: la respuesta y su aclaración van juntas
    separadas por un guion, que es como se leen después ("Si — ibuprofeno").
    """
    detalle = (detalle or "").strip()[:LARGO_DETALLE]
    return f"{respuesta} — {detalle}" if detalle else respuesta


def guardar_seccion(cita, usuario, seccion, formulario):
    """
    Guarda las respuestas de un bloque. Devuelve la lista de errores.

    Vuelve a escribir las que ya estaban: si alguien corrige una respuesta y
    reenvía el paso, gana la última. Lo garantiza uq_cuestionario_cita_pregunta.
    """
    errores = []
    cambios = []

    for pregunta in preguntas(seccion):
        clave = f"p{pregunta.id_pregunta}"
        respuesta = (formulario.get(clave) or "").strip()
        if respuesta not in (SI, NO):
            errores.append(f"Falta responder la pregunta {pregunta.orden}.")
            continue
        cambios.append((pregunta,
                        _valor(respuesta, formulario.get(f"{clave}_detalle"))))

    if errores:
        return errores

    ya = respuestas(cita)
    ahora = datetime.now()
    try:
        for pregunta, valor in cambios:
            fila = ya.get(pregunta.id_pregunta)
            if fila is None:
                db.session.add(Cuestionario(
                    id_cita=cita.id_cita, id_pregunta=pregunta.id_pregunta,
                    id_donante=usuario.id_usuario, valor=valor, fecha=ahora))
            else:
                fila.valor = valor
                fila.fecha = ahora
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return []


def completo(cita):
    """¿Están respondidas las 36?"""
    return len(respuestas(cita)) >= len(preguntas())


def seccion_pendiente(cita):
    """El primer bloque que le falta responder, o None si terminó."""
    ya = respuestas(cita)
    for seccion in SECCIONES:
        if any(p.id_pregunta not in ya for p in preguntas(seccion)):
            return seccion
    return None


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
