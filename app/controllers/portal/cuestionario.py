"""
Cuestionario previo a la donación.

Son 36 preguntas: en una sola pantalla de celular no se responden, así que
van en tres pasos, uno por bloque del formulario original. Cada paso se
guarda al pasar al siguiente, de modo que si se corta la conexión o se
cierra el navegador no hay que empezar de nuevo.

Lo que el portal NO hace: decidir. Una respuesta marcada no rechaza al
donante ni cancela la cita. El personal de salud lee el cuestionario y
decide en el momento, que es como tiene que ser.
"""
from datetime import datetime

from app.models import Cita, Cuestionario, Pregunta, db

# Los tres bloques, en el orden del formulario del banco de sangre.
SECCIONES = ["En la actualidad",
             "Antecedentes personales",
             "En los ultimos 12 meses"]

SI = "Si"
NO = "No"
LARGO_DETALLE = 180


def preguntas(seccion=None):
    """Las preguntas vigentes del cuestionario del donante, en orden."""
    consulta = (Pregunta.query
                .filter(Pregunta.parte == Pregunta.PARTE_DONANTE,
                        Pregunta.activa.is_(True)))
    if seccion is not None:
        consulta = consulta.filter(Pregunta.seccion == seccion)
    return consulta.order_by(Pregunta.orden).all()


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
    delcuestionario = preguntas(seccion)
    errores = []
    cambios = []

    for pregunta in delcuestionario:
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
    Las respuestas de la cita, ordenadas, con las marcadas al principio de
    la lista de atención.

    `atencion` son las que coinciden con alerta_si. No es un veredicto: es
    lo que el personal mira primero.
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


def cita_del_donante(id_cita, usuario):
    """
    La cita, solo si es de esta persona y todavía tiene sentido responderla.

    Devuelve None si no existe, si es de otro donante o si ya se cerró: un
    cuestionario de una cita cancelada o completada no se toca más.
    """
    cita = Cita.query.filter_by(id_cita=id_cita,
                                id_usuario=usuario.id_usuario).first()
    if cita is None or cita.estado not in Cita.ACTIVAS:
        return None
    return cita
