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

    # RECORDATORIO_CITA es el tipo que el esquema ya tiene para esto. Se usa
    # solo para este aviso, así que su presencia sobre una cita significa
    # "ya se le mandó el cuestionario" y evita mandarlo dos veces.
    ya_avisadas = {
        n.id_cita for n in Notificacion.query
        .filter(Notificacion.tipo == Notificacion.RECORDATORIO_CITA,
                Notificacion.id_cita.isnot(None),
                Notificacion.mensaje.ilike("%cuestionario%")).all()
    }

    # La consulta filtra solo por estado: el día de la cita se calcula a
    # partir de la franja, así que no se puede acotar por fecha en SQL. Las
    # citas activas son pocas —como mucho una por donante— así que se
    # traen y se filtran acá.
    candidatas = Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()

    pendientes = [c for c in candidatas
                  if c.id_cita not in ya_avisadas
                  and c.momento is not None
                  and ahora <= c.momento <= limite]
    return sorted(pendientes, key=lambda c: c.momento)


def proximas_citas(limite=10, ahora=None):
    """Las citas activas que todavía no pasaron, la más cercana primero."""
    ahora = ahora or datetime.now()
    proximas = [c for c in Cita.query.filter(Cita.estado.in_(Cita.ACTIVAS)).all()
                if c.momento is not None and c.momento >= ahora]
    return sorted(proximas, key=lambda c: c.momento)[:limite]


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
        tipo=Notificacion.RECORDATORIO_CITA,
        mensaje=(f"Te enviamos a tu correo el cuestionario previo para tu cita "
                 f"de hoy a las {hora}. Respondelo antes de venir."),
        fecha_envio=datetime.now()))
    db.session.commit()

    return True, ("enviado por correo" if salio else "escrito en la consola")


def enviar_confirmacion(cita, url_base):
    """
    Manda el correo de confirmación de una cita recién agendada.

    Se llama desde la ruta, DESPUÉS de que agenda.crear() grabó la cita, no
    adentro: crear() retiene la franja con FOR UPDATE hasta el commit, y
    mandar un correo ahí dejaría ese bloqueo tomado mientras se espera al
    servidor SMTP. Para cuando esta función corre, la cita ya existe.

    Por eso mismo un fallo del correo no vuelve atrás nada: la cita está
    confirmada y su notificación en el buzón ya se guardó en crear(). El
    problema se registra y se sigue. Devuelve (enviado, detalle).
    """
    destino = cita.donante.correo_principal
    if destino is None:
        return False, "el donante no tiene correo principal cargado"

    cuerpo = render_template(
        "correos/confirmacion_cita.html",
        nombre=cita.donante.nombre,
        fecha=cita.fecha_cita.strftime("%d/%m/%Y"),
        hora_inicio=cita.horario.hora_inicio.strftime("%H:%M"),
        hora_fin=cita.horario.hora_fin.strftime("%H:%M"),
        tipo=_etiqueta_tipo(cita.tipo_cita),
        donas_para=(cita.solicitud.solicitante.nombre_completo
                    if cita.solicitud else None),
        enlace_cita=f"{url_base}/mi-cita/")

    try:
        salio = correo.enviar(
            destino.direccion, "Tu cita de donación quedó confirmada", cuerpo)
    except correo.ErrorCorreo as e:
        return False, str(e)
    return True, ("enviado por correo" if salio else "escrito en la consola")


def _etiqueta_tipo(tipo_cita):
    """La etiqueta legible del tipo de cita, sin arrastrar el import arriba."""
    from app.controllers.portal import agenda
    return agenda.etiqueta_tipo(tipo_cita)


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


def enviar_recordatorio(cita, url_base=None):
    """
    Deja el recordatorio de la cita en el buzón y, si hay correo, lo manda.

    La notificación se guarda siempre: es la marca que impide repetir el
    aviso en la próxima corrida. El correo es adicional; si falla, el
    recordatorio igual quedó registrado. Devuelve (enviado, detalle), donde
    enviado es None cuando no había a quién mandárselo.
    """
    hora = cita.horario.hora_inicio.strftime("%H:%M")
    db.session.add(Notificacion(
        id_usuario=cita.id_usuario,
        id_cita=cita.id_cita,
        tipo=Notificacion.RECORDATORIO_CITA,
        mensaje=(f"Recordatorio: tenés una cita de donación "
                 f"el {cita.fecha_cita.strftime('%d/%m/%Y')} a las {hora}."),
        fecha_envio=datetime.now()))
    db.session.commit()

    destino = cita.donante.correo_principal
    if destino is None:
        return None, "el donante no tiene correo principal cargado"

    cuerpo = render_template(
        "correos/recordatorio_cita.html",
        nombre=cita.donante.nombre,
        fecha=cita.fecha_cita.strftime("%d/%m/%Y"),
        hora_inicio=hora,
        hora_fin=cita.horario.hora_fin.strftime("%H:%M"),
        enlace_cita=f"{(url_base or '').rstrip('/')}/mi-cita/")

    try:
        salio = correo.enviar(
            destino.direccion,
            "Recordatorio: tu cita de donación es mañana", cuerpo)
    except correo.ErrorCorreo as e:
        return False, str(e)
    return True, ("enviado por correo" if salio else "escrito en la consola")


def pendientes_de_habilitacion(ahora=None):
    """
    Donantes cuyo diferimiento temporal ya venció, o cuyo intervalo desde
    la última extracción ya se cumplió, y todavía no recibieron el aviso.
    El texto no incluye la causa.
    """
    # Antes este import iba acá adentro para esquivar una referencia
    # circular con perfil.py. Ya no hace falta: la regla vive en
    # elegibilidad.py, que no importa de nadie.
    from app.controllers.portal.elegibilidad import habilitacion
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


# ----------------------------------------- solicitudes compatibles (RF12)
#
# Cuando hay una solicitud publicada, se avisa a los donantes cuyo grupo
# puede cubrirla. No lo dispara ninguna pantalla —el portal solo lista las
# solicitudes, no las publica—, así que vive acá, en el proceso automático,
# igual que el resto de los avisos. Funciona sin importar quién o desde
# dónde haya publicado la solicitud.
#
# El esquema fija los tipos de notificación con un CHECK y no hay uno propio
# para esto, así que se reutiliza CITACION_GENERICA ("Mensaje del banco de
# sangre"). Que lleve `id_solicitud` es lo que distingue este aviso del que
# usa el mismo tipo para la consejería (ese lleva `id_citacion`), y es la
# marca que evita avisarle dos veces al mismo donante por la misma solicitud.
def donantes_compatibles(solicitud):
    """
    Donantes a los que les corresponde el aviso de esta solicitud.

    Son los que cumplen todo esto: su grupo puede donarle al de la
    solicitud, hoy están en condiciones de donar (ni diferidos ni dentro del
    intervalo), no tienen ya una cita agendada, no son el propio solicitante
    (RN03) y todavía no recibieron el aviso de esta solicitud.

    La compatibilidad va donante → receptor: el grupo de la solicitud es el
    del paciente que recibe, y se buscan los grupos que pueden donarle.
    """
    from app.controllers.portal import agenda, elegibilidad
    from app.models import CompatibilidadAboRh, Usuario

    grupos = {c.id_tipo_donante for c in CompatibilidadAboRh.query
              .filter_by(id_tipo_receptor=solicitud.id_tipo_sangre).all()}
    if not grupos:
        return []

    ya_avisados = {
        n.id_usuario for n in Notificacion.query
        .filter(Notificacion.tipo == Notificacion.CITACION_GENERICA,
                Notificacion.id_solicitud == solicitud.id_solicitud).all()
    }

    candidatos = (Usuario.query
                  .filter(Usuario.estado.is_(True),
                          Usuario.cuenta_suprimida.is_(False),
                          Usuario.id_tipo_sangre.in_(grupos))
                  .all())

    listos = []
    for donante in candidatos:
        if donante.id_usuario in ya_avisados:
            continue
        if donante.id_usuario == solicitud.id_solicitante:
            continue
        if not donante.tiene_rol("DONANTE"):
            continue
        if not elegibilidad.habilitacion(donante)["apto"]:
            continue
        if agenda.cita_vigente(donante):
            continue
        listos.append(donante)
    return listos


def avisar_solicitud_compatible(solicitud, url_base):
    """
    Avisa a los donantes compatibles de una solicitud. Devuelve cuántos.

    Primero se guardan todas las notificaciones y se confirma una sola vez;
    después se mandan los correos. Si un correo falla, la notificación ya
    quedó —es la que importa y la que evita repetir— y el fallo se registra.
    """
    donantes = donantes_compatibles(solicitud)
    if not donantes:
        return 0

    mensaje = ("Hay una solicitud de sangre que tu grupo puede ayudar a "
               "cubrir. Entrá a Solicitudes para ver los detalles y, si "
               "querés y estás en condiciones, agendá una donación.")
    for donante in donantes:
        db.session.add(Notificacion(
            id_usuario=donante.id_usuario,
            id_solicitud=solicitud.id_solicitud,
            tipo=Notificacion.CITACION_GENERICA,
            mensaje=mensaje,
            fecha_envio=datetime.now()))
    db.session.commit()

    enlace = f"{url_base.rstrip('/')}/solicitudes/"
    for donante in donantes:
        destino = donante.correo_principal
        if destino is None:
            continue
        grupo = donante.tipo_sangre.etiqueta if donante.tipo_sangre else ""
        try:
            cuerpo = render_template("correos/solicitud_compatible.html",
                                     nombre=donante.nombre, grupo=grupo,
                                     enlace=enlace)
            correo.enviar(destino.direccion,
                          "Tu sangre puede ayudar: hay una solicitud compatible",
                          cuerpo)
        except correo.ErrorCorreo:
            # El aviso ya está en el buzón; el correo es adicional.
            pass
    return len(donantes)


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
        enviado, detalle = enviar_recordatorio(cita, url_base)
        lineas.append(f"  recordatorio cita {cita.id_cita}: {detalle}")
    for usuario in pendientes_de_habilitacion(ahora):
        enviar_habilitacion(usuario)
        lineas.append(f"  habilitación usuario {usuario.id_usuario}")

    from app.controllers.portal import solicitudes as ctrl_solicitudes
    for solicitud in ctrl_solicitudes.activas():
        n = avisar_solicitud_compatible(solicitud, url_base)
        if n:
            lineas.append(f"  solicitud {solicitud.id_solicitud}: "
                          f"avisada a {n} donante(s) compatible(s)")
    return lineas
