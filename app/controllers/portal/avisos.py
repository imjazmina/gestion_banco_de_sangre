"""
Avisos que salen solos, sin que nadie los pida desde una pantalla.

Por ahora hay uno: el correo con el cuestionario, unas horas antes de la
cita. Lo dispara `python enviar_avisos.py`, que se programa en el Programador
de tareas de Windows (o en cron) para que corra cada tanto.

Por qué un script aparte y no un hilo dentro de Flask: un hilo dentro del
servidor de desarrollo se duplica con el recargador y deja de existir cuando
se cierra la ventana. Un script que se puede correr a mano es además el que
se puede demostrar en una defensa.
"""
from datetime import datetime, timedelta

from flask import render_template

from app import correo
from app.controllers.portal import cuestionario as ctrl_cuestionario
from app.models import Cita, Correo, Notificacion, db

HORAS_ANTES = 3


def _momento(cita):
    """Fecha y hora exactas en que empieza la cita."""
    return datetime.combine(cita.fecha_cita, cita.horario.hora_inicio)


def pendientes_de_cuestionario(ahora=None):
    """
    Las citas a las que hay que mandarles el cuestionario ahora.

    La condición no es "faltan exactamente 3 horas" sino "faltan 3 horas o
    menos y todavía no empezó". Escrito así, si la tarea programada se
    atrasa o la computadora estuvo apagada, el aviso sale igual apenas
    vuelve; con una ventana exacta se perdería para siempre.

    Las que ya recibieron el aviso quedan afuera por la notificación que
    se guarda al enviarlo, así que correr el script de más no molesta.
    """
    ahora = ahora or datetime.now()
    limite = ahora + timedelta(hours=HORAS_ANTES)

    ya_avisadas = {
        n.id_cita for n in Notificacion.query
        .filter(Notificacion.tipo == Notificacion.CUESTIONARIO_PREVIO,
                Notificacion.id_cita.isnot(None)).all()
    }

    candidatas = (Cita.query
                  .filter(Cita.estado.in_(Cita.ACTIVAS),
                          Cita.fecha_cita >= ahora.date(),
                          Cita.fecha_cita <= limite.date())
                  .order_by(Cita.fecha_cita, Cita.id_cita)
                  .all())

    return [c for c in candidatas
            if c.id_cita not in ya_avisadas
            and ahora <= _momento(c) <= limite]


def proximas_citas(limite=10, ahora=None):
    """Las citas activas que todavía no pasaron, la más cercana primero."""
    ahora = ahora or datetime.now()
    return [c for c in (Cita.query
                        .filter(Cita.estado.in_(Cita.ACTIVAS),
                                Cita.fecha_cita >= ahora.date())
                        .order_by(Cita.fecha_cita)
                        .limit(limite * 3)
                        .all())
            if _momento(c) >= ahora][:limite]


def enviar_cuestionario(cita, url_base):
    """
    Manda el correo del cuestionario de una cita y deja el registro.

    Devuelve (enviado, detalle). La notificación se guarda aunque el correo
    haya ido a la consola: lo que registra es que el aviso ya se generó para
    esa cita, y así no se repite en la próxima corrida.
    """
    destino = cita.donante.correo_principal
    if destino is None:
        return False, "el donante no tiene correo principal cargado"

    enlace = f"{url_base}/cuestionario/{cita.id_cita}"
    hora = cita.horario.hora_inicio.strftime("%H:%M")
    cuerpo = render_template(
        "correos/cuestionario.html",
        nombre=cita.donante.nombre, hora=hora, enlace=enlace,
        enlace_cita=f"{url_base}/mi-cita/")

    try:
        salio = correo.enviar(destino.direccion,
                              f"Tu donación es hoy a las {hora}: completá el cuestionario",
                              cuerpo)
    except correo.ErrorCorreo as e:
        return False, str(e)

    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.CUESTIONARIO_PREVIO,
        mensaje=(f"Te enviamos a tu correo el cuestionario previo para tu cita "
                 f"de hoy a las {hora}. Respondelo antes de venir."),
        fecha_envio=datetime.now()))
    db.session.commit()

    return True, ("enviado por correo" if salio else "escrito en la consola")


def correr(url_base, ahora=None):
    """Manda todos los avisos que correspondan. Devuelve las líneas del informe."""
    citas = pendientes_de_cuestionario(ahora)
    if not citas:
        return ["No hay avisos para enviar en este momento."]

    lineas = []
    for cita in citas:
        if ctrl_cuestionario.completo(cita):
            lineas.append(f"  cita {cita.id_cita}: ya tiene el cuestionario "
                          f"completo, no se avisa")
            continue
        enviado, detalle = enviar_cuestionario(cita, url_base)
        estado = "ok" if enviado else "FALLÓ"
        lineas.append(f"  cita {cita.id_cita} ({cita.donante.nombre_completo}, "
                      f"{cita.horario.hora_inicio.strftime('%H:%M')}): {estado} — {detalle}")
    return lineas
