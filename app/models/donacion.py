"""
El circuito de la donación: solicitud, cita, evaluación, extracción y el
recorrido de la unidad hasta que se asigna o se descarta.
"""
from datetime import datetime

from app import calendario
from app.models import db


class Solicitud(db.Model):
    """Pedido de unidades para un paciente."""
    __tablename__ = "solicitud"

    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    medico_tratante = db.Column(db.String(120))
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"), nullable=False)
    unidades_requeridas = db.Column(db.Integer, nullable=False)
    unidades_asignadas = db.Column(db.Integer, nullable=False, default=0)
    # Sin consentimiento no se publica: lo exige ck_solicitud_publicacion.
    consentimiento_publicacion = db.Column(db.Boolean, nullable=False, default=False)
    fecha_limite = db.Column(db.Date)
    estado = db.Column(db.String(20), nullable=False, default="Publicada")
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)

    solicitante = db.relationship("Usuario", lazy="joined")
    tipo_sangre = db.relationship("TipoSangre", lazy="joined")

    PUBLICADA = "Publicada"
    COMPLETA = "Completa"
    VENCIDA = "Vencida"
    REVOCADA = "Revocada"


class Cita(db.Model):
    """
    Turno de donación.

    No guarda el día: lo calcula. `id_horario` apunta a la franja del
    catálogo («Lunes 07:00») y `fecha_hora_creacion` dice cuándo se reservó;
    la cita es para la próxima vez que esa franja ocurre después de la
    reserva. La cuenta la hace `fecha_cita`, más abajo.
    """
    __tablename__ = "cita"

    id_cita = db.Column(db.Integer, primary_key=True)
    tipo_cita = db.Column(db.String(30), nullable=False)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_solicitud = db.Column(
        db.Integer, db.ForeignKey("solicitud.id_solicitud"))
    # NOT NULL en el esquema: toda cita nombra a quien atiende. Al reservar
    # por el portal todavía no se sabe quién va a ser, así que queda el
    # usuario de servicio «Personal de turno» y el panel lo reemplaza por la
    # persona real en el mostrador.
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_horario = db.Column(
        db.Integer, db.ForeignKey("horario_disponible.id_horario"), nullable=False)
    fecha_hora_creacion = db.Column(
        db.DateTime, nullable=False, default=datetime.now)
    estado = db.Column(db.String(20), nullable=False, default="Pendiente")

    donante = db.relationship(
        "Usuario", foreign_keys=[id_usuario], lazy="joined")
    personal = db.relationship("Usuario", foreign_keys=[id_personal])
    horario = db.relationship("HorarioDisponible", lazy="joined")
    solicitud = db.relationship("Solicitud")

    @property
    def fecha_cita(self):
        """
        El día concreto de la cita.

        No es una columna: sale de la franja y de cuándo se reservó (ver
        app/calendario.py). Por eso no se puede filtrar ni ordenar por este
        campo en una consulta SQL; las consultas traen las citas por estado
        y por usuario, y el orden por fecha se hace en Python.
        """
        if self.horario is None:
            return None
        return calendario.proxima_fecha(self.horario.dia_semana,
                                        self.horario.hora_inicio,
                                        self.fecha_hora_creacion)

    @property
    def momento(self):
        """Fecha y hora de inicio juntas."""
        fecha = self.fecha_cita
        if fecha is None:
            return None
        return calendario.momento(fecha, self.horario.hora_inicio)

    @property
    def paso(self):
        """¿La hora de la cita ya pasó?"""
        instante = self.momento
        return instante is not None and instante < datetime.now()

    ALTRUISTA = "Donacion altruista"
    REPOSICION = "Reposicion"
    SOLIDARIA = "Donacion solidaria"
    COMPATIBILIDAD = "Extraccion de compatibilidad"

    PENDIENTE = "Pendiente"
    CONFIRMADA = "Confirmada"
    CANCELADA = "Cancelada"
    AUSENTE = "Ausente"
    COMPLETADA = "Completada"
    NO_APTO = "No apto"

    ACTIVAS = (PENDIENTE, CONFIRMADA)


class Cuestionario(db.Model):
    """Una fila por pregunta respondida en una cita."""
    __tablename__ = "cuestionario"

    id_cuestionario = db.Column(db.Integer, primary_key=True)
    id_cita = db.Column(db.Integer, db.ForeignKey("cita.id_cita"), nullable=False)
    id_pregunta = db.Column(
        db.Integer, db.ForeignKey("pregunta.id_pregunta"), nullable=False)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_personal = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    valor = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    pregunta = db.relationship("Pregunta", lazy="joined")


class Medicion(db.Model):
    """
    Signos vitales del día de la donación.

    No asignes "apto" desde Python: el trigger fn_medicion_apto lo sobrescribe
    comparando el valor contra los umbrales del tipo de medición.
    """
    __tablename__ = "medicion"

    id_medicion = db.Column(db.Integer, primary_key=True)
    id_cita = db.Column(db.Integer, db.ForeignKey("cita.id_cita"), nullable=False)
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_tipo_medicion = db.Column(
        db.Integer, db.ForeignKey("tipo_medicion.id_tipo_medicion"), nullable=False)
    valor = db.Column(db.Numeric, nullable=False)
    apto = db.Column(db.Boolean, nullable=False, default=False)
    observaciones = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    tipo = db.relationship("TipoMedicion", lazy="joined")


class RegistroDiferimiento(db.Model):
    """
    Diferimiento aplicado a un donante concreto.

    fecha_fin la completa el trigger fn_registro_fecha_fin a partir de los
    días de rehabilitación del catálogo; queda nula si es permanente.
    """
    __tablename__ = "registro_diferimiento"

    id_registro = db.Column(db.Integer, primary_key=True)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_diferimiento = db.Column(
        db.Integer, db.ForeignKey("diferimiento.id_diferimiento"), nullable=False)
    id_cita = db.Column(db.Integer, db.ForeignKey("cita.id_cita"))
    id_personal = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    origen = db.Column(db.String(30), nullable=False)
    institucion_diagnostico = db.Column(db.String(120), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date)

    causa = db.relationship("Diferimiento", lazy="joined")

    CUESTIONARIO_SISTEMA = "CUESTIONARIO_SISTEMA"
    CUESTIONARIO_PERSONAL = "CUESTIONARIO_PERSONAL"
    MEDICION = "MEDICION"
    LABORATORIO = "LABORATORIO"


class Extraccion(db.Model):
    __tablename__ = "extraccion"

    id_extraccion = db.Column(db.Integer, primary_key=True)
    id_cita = db.Column(
        db.Integer, db.ForeignKey("cita.id_cita"), nullable=False, unique=True)
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    codigo_unico = db.Column(db.String(40), nullable=False, unique=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
    observacion = db.Column(db.Text, nullable=False)


class Unidad(db.Model):
    """Bolsa de sangre obtenida de una extracción."""
    __tablename__ = "unidad"

    id_unidad = db.Column(db.Integer, primary_key=True)
    id_extraccion = db.Column(
        db.Integer, db.ForeignKey("extraccion.id_extraccion"),
        nullable=False, unique=True)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_solicitud = db.Column(db.Integer, db.ForeignKey("solicitud.id_solicitud"))
    codigo = db.Column(db.String(40), nullable=False, unique=True)
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"))
    componente = db.Column(db.String(20), nullable=False, default="sangre_total")
    estado = db.Column(db.String(20), nullable=False, default="Registrada")
    fecha_vencimiento = db.Column(db.Date)

    REGISTRADA = "Registrada"
    EN_LABORATORIO = "En laboratorio"
    EN_STOCK = "En stock"
    ASIGNADA = "Asignada"
    UTILIZADA = "Utilizada"
    DESCARTADA = "Descartada"
    VENCIDA = "Vencida"


class TransicionEstado(db.Model):
    """
    Bitácora de los cambios de estado de una unidad.

    Es inmutable: el trigger trg_transicion_estado_inmutable rechaza
    cualquier UPDATE o DELETE (RN12).
    """
    __tablename__ = "transicion_estado"

    id_transicion = db.Column(db.Integer, primary_key=True)
    id_unidad = db.Column(
        db.Integer, db.ForeignKey("unidad.id_unidad"), nullable=False)
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    estado_origen = db.Column(db.String(20), nullable=False)
    estado_destino = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.Text)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)


class ResultadoLaboratorio(db.Model):
    __tablename__ = "resultado_laboratorio"

    id_resultado = db.Column(db.Integer, primary_key=True)
    id_unidad = db.Column(
        db.Integer, db.ForeignKey("unidad.id_unidad"), nullable=False, unique=True)
    id_diferimiento = db.Column(
        db.Integer, db.ForeignKey("diferimiento.id_diferimiento"))
    id_registro_diferimiento = db.Column(
        db.Integer, db.ForeignKey("registro_diferimiento.id_registro"))
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"), nullable=False)
    resultado = db.Column(db.String(20), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    NO_REACTIVO = "No reactivo"
    REACTIVO = "Reactivo"


class Asignacion(db.Model):
    """Unidad entregada a una solicitud."""
    __tablename__ = "asignacion"

    id_asignacion = db.Column(db.Integer, primary_key=True)
    id_unidad = db.Column(
        db.Integer, db.ForeignKey("unidad.id_unidad"), nullable=False, unique=True)
    id_solicitud = db.Column(
        db.Integer, db.ForeignKey("solicitud.id_solicitud"), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)


class CitacionConsejeria(db.Model):
    """Citación para comunicar un resultado reactivo, en persona."""
    __tablename__ = "citacion_consejeria"

    id_citacion = db.Column(db.Integer, primary_key=True)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_horario = db.Column(
        db.Integer, db.ForeignKey("horario_disponible.id_horario"), nullable=False)
    id_resultado = db.Column(
        db.Integer, db.ForeignKey("resultado_laboratorio.id_resultado"),
        nullable=False, unique=True)
    fecha_hora = db.Column(db.DateTime)
    estado = db.Column(db.String(20), nullable=False, default="Pendiente")
    observaciones = db.Column(db.Text)


class Derivacion(db.Model):
    """Derivación del donante a otro establecimiento de salud."""
    __tablename__ = "derivacion"

    id_derivacion = db.Column(db.Integer, primary_key=True)
    id_registro_diferimiento = db.Column(
        db.Integer, db.ForeignKey("registro_diferimiento.id_registro"),
        nullable=False, unique=True)
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    establecimiento_destino = db.Column(db.String(120), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    motivo_interno = db.Column(db.Text)
