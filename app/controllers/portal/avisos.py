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
    return cita.momento


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

    # La consulta filtra solo por estado: el día de la cita se calcula a
    # partir de la franja, así que no se puede acotar por fecha en SQL. Las
    # citas activas son pocas —como mucho una por donante— así que se
    # traen y se filtran acá. ya_enviado mira el turno concreto, así una
    # reprogramación puede volver a avisar y un reintento del mismo turno no.
    candidatas = Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()

    pendientes = [c for c in candidatas
                  if not ya_enviado(c)
                  and c.momento is not None
                  and ahora <= c.momento <= limite]
    return sorted(pendientes, key=lambda c: c.momento)


def proximas_citas(limite=10, ahora=None):
    """Las citas activas que todavía no pasaron, la más cercana primero."""
    ahora = ahora or datetime.now()
    proximas = [c for c in Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()
                if c.momento is not None and c.momento >= ahora]
    return sorted(proximas, key=lambda c: c.momento)[:limite]


def marca_turno(cita):
    """Fecha y hora que identifican el turno avisado, dentro del mensaje."""
    return (f"del {cita.fecha_cita.strftime('%d/%m/%Y')} a las "
            f"{cita.horario.hora_inicio.strftime('%H:%M')}")


def ya_enviado(cita):
    """True si este turno ya tiene el correo del cuestionario registrado."""
    if cita is None or cita.fecha_cita is None or cita.horario is None:
        return False
    marca = marca_turno(cita)
    return (Notificacion.query
            .filter(Notificacion.id_cita == cita.id_cita,
                    Notificacion.tipo == Notificacion.RECORDATORIO_CITA,
                    Notificacion.mensaje.ilike(f"%cuestionario%{marca}%"))
            .first() is not None)


def enviar_cuestionario(cita, url_base):
    """
    Manda el correo del cuestionario de una cita y deja el registro.

    Devuelve (enviado, detalle). La notificación se guarda aunque el correo
    haya ido a la consola: lo que registra es que el aviso ya se generó para
    ese turno, y así no se repite. Una cita cancelada no genera registro.
    """
    if cita.estado not in Cita.ACTIVAS:
        return False, "la cita está cancelada"
    if ctrl_cuestionario.completo(cita):
        return False, "el cuestionario ya está completo"
    if ya_enviado(cita):
        return True, "ya enviado"

    destino = cita.donante.correo_principal
    if destino is None:
        return False, "el donante no tiene correo principal cargado"

    enlace = f"{url_base}/cuestionario/{cita.id_cita}"
    hora = cita.horario.hora_inicio.strftime("%H:%M")
    fecha = cita.fecha_cita.strftime("%d/%m/%Y")
    cuerpo = render_template(
        "correos/cuestionario.html",
        nombre=cita.donante.nombre, hora=hora, fecha=fecha, enlace=enlace,
        enlace_cita=f"{url_base}/mi-cita/")

    try:
        salio = correo.enviar(
            destino.direccion,
            f"Completá el cuestionario para tu cita del {fecha} a las {hora}",
            cuerpo)
    except correo.ErrorCorreo as e:
        return False, str(e)

    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.RECORDATORIO_CITA,
        mensaje=(f"Te enviamos a tu correo el cuestionario previo para tu cita "
                 f"{marca_turno(cita)}. Respondelo antes de venir."),
        fecha_envio=datetime.now()))
    db.session.commit()

    return True, ("enviado por correo" if salio else "escrito en la consola")


def pendientes_de_recordatorio(ahora=None):
    """Citas activas que empiezan dentro de un día y todavía no tienen recordatorio."""
    ahora = ahora or datetime.now()
    limite = ahora + timedelta(hours=24)
    ya = {
        n.id_cita for n in Notificacion.query
        .filter(Notificacion.tipo == Notificacion.RECORDATORIO_CITA,
                Notificacion.mensaje.ilike("Recordatorio:%")).all()
    }
    candidatas = Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()
    return [c for c in candidatas
            if c.id_cita not in ya and c.momento is not None
            and ahora <= c.momento <= limite]


def enviar_recordatorio(cita):
    hora = cita.horario.hora_inicio.strftime("%H:%M")
    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.RECORDATORIO_CITA,
        mensaje=(f"Recordatorio: tenés una cita de donación "
                 f"el {cita.fecha_cita.strftime('%d/%m/%Y')} a las {hora}."),
        fecha_envio=datetime.now()))
    db.session.commit()


def pendientes_de_habilitacion(ahora=None):
    """
    Donantes cuyo diferimiento temporal ya venció, o cuyo intervalo desde
    la última extracción ya se cumplió, y todavía no recibieron el aviso.
    El texto no incluye la causa.
    """
    from app.controllers.portal.perfil import habilitacion
    from app.models import RegistroDiferimiento, Usuario

    ahora = ahora or datetime.now()
    hoy = ahora.date()
    ya = {n.id_usuario for n in Notificacion.query
          .filter(Notificacion.tipo == Notificacion.HABILITACION,
                  Notificacion.fecha_envio >= datetime.combine(hoy, datetime.min.time()))
          .all()}
    por_diferimiento = {
        r.id_donante for r in RegistroDiferimiento.query
        .filter(RegistroDiferimiento.fecha_fin == hoy).all()
    }
    listos = []
    for usuario in Usuario.query.filter_by(estado=True, cuenta_suprimida=False).all():
        if usuario.id_usuario in ya:
            continue
        if usuario.id_usuario in por_diferimiento:
            listos.append(usuario)
            continue
        dato = habilitacion(usuario)
        if dato["motivo"] == "intervalo" and dato["apto"] and dato["fecha"] == hoy:
            listos.append(usuario)
    return listos


def enviar_habilitacion(usuario):
    db.session.add(Notificacion(
        id_usuario=usuario.id_usuario,
        tipo=Notificacion.HABILITACION,
        mensaje=("Ya podés consultar al banco de sangre para una nueva donación. "
                 "La fecha es orientativa: la aptitud la confirma el personal."),
        fecha_envio=datetime.now()))
    db.session.commit()


def correr(url_base, ahora=None):
    """Manda todos los avisos que correspondan. Devuelve las líneas del informe."""
    lineas = []
    citas = pendientes_de_cuestionario(ahora)
    if not citas:
        lineas.append("No hay cuestionarios para avisar en este momento.")
    for cita in citas:
        if ctrl_cuestionario.completo(cita):
            lineas.append(f"  cita {cita.id_cita}: ya tiene el cuestionario "
                          f"completo, no se avisa")
            continue
        enviado, detalle = enviar_cuestionario(cita, url_base)
        estado = "ok" if enviado else "FALLÓ"
        lineas.append(f"  cita {cita.id_cita} ({cita.donante.nombre_completo}, "
                      f"{cita.horario.hora_inicio.strftime('%H:%M')}): {estado} — {detalle}")

    for cita in pendientes_de_recordatorio(ahora):
        enviar_recordatorio(cita)
        lineas.append(f"  recordatorio cita {cita.id_cita}")
    for usuario in pendientes_de_habilitacion(ahora):
        enviar_habilitacion(usuario)
        lineas.append(f"  habilitación usuario {usuario.id_usuario}")

    from app.controllers.comun.simulacion import marcar_vencidas, vencer_publicadas
    from app.controllers.portal.agenda import DOCUMENTO_PERSONAL_DE_TURNO
    from app.models import Usuario

    personal = Usuario.query.filter_by(documento=DOCUMENTO_PERSONAL_DE_TURNO).first()
    if personal is None:
        lineas.append("  solicitudes: falta el usuario Personal de turno.")
    else:
        try:
            n = vencer_publicadas(personal, (ahora or datetime.now()).date())
            lineas.append(f"  solicitudes vencidas: {n}")
            lineas.append(f"  unidades vencidas: {marcar_vencidas(personal)}")
        except Exception as exc:
            db.session.rollback()
            lineas.append(f"  solicitudes: FALLÓ — {exc}")
    return lineas
