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
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"))
    unidades_requeridas = db.Column(db.Integer, nullable=False)
    unidades_asignadas = db.Column(db.Integer, nullable=False, default=0)
    # Sin consentimiento no se publica: lo exige ck_solicitud_publicacion.
    consentimiento_publicacion = db.Column(db.Boolean, nullable=False, default=False)
    fecha_limite = db.Column(db.Date)
    estado = db.Column(db.String(20), nullable=False, default="Creada")
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)

    solicitante = db.relationship("Usuario", lazy="joined")
    tipo_sangre = db.relationship("TipoSangre", lazy="joined")

    CREADA = "Creada"
    PUBLICADA = "Publicada"
    CERRADA = "Cerrada"
    VENCIDA = "Vencida"
    REVOCADA = "Revocada"
    ABIERTAS = (CREADA, PUBLICADA)


class HistorialSolicitud(db.Model):
    """Cada cambio de estado. No se actualiza ni se borra."""
    __tablename__ = "historial_solicitud"

    id_historial_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitud = db.Column(
        db.Integer, db.ForeignKey("solicitud.id_solicitud"), nullable=False)
    estado_anterior = db.Column(db.String(120))
    estado_nuevo = db.Column(db.String(120), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.now)


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
    tipo_cita = db.Column(db.String(50), nullable=False)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_solicitud = db.Column(
        db.Integer, db.ForeignKey("solicitud.id_solicitud"))
    # NULL hasta Ausente, No apto o Completada. Ahí se graba quien cerró.
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"))
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
    SOLIDARIA = "Donacion solidaria"
    COMPATIBILIDAD = "Extraccion de muestra para compatibilidad"
    MUESTRA = "Extraccion de muestra para compatibilidad"

    PENDIENTE = "Pendiente"
    CONFIRMADA = "Confirmada"
    CANCELADA = "Cancelada"
    AUSENTE = "Ausente"
    COMPLETADA = "Completada"
    NO_APTO = "No apto"

    ACTIVAS = (PENDIENTE, CONFIRMADA)


class HistorialCita(db.Model):
    """Cada cambio de estado. No se actualiza ni se borra."""
    __tablename__ = "historial_cita"

    id_historial_cita = db.Column(db.Integer, primary_key=True)
    id_cita = db.Column(
        db.Integer, db.ForeignKey("cita.id_cita"), nullable=False)
    estado_anterior = db.Column(db.String(120))
    estado_nuevo = db.Column(db.String(120), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.now)

    cita = db.relationship("Cita", foreign_keys=[id_cita])


class HistorialCitaConsejeria(db.Model):
    """Cada cambio de estado de la citación. No se actualiza ni se borra."""
    __tablename__ = "historial_cita_consejeria"

    id_historial_cita_consejeria = db.Column(db.Integer, primary_key=True)
    id_cita_consejeria = db.Column(
        db.Integer, db.ForeignKey("citacion_consejeria.id_citacion"),
        nullable=False)
    estado_anterior = db.Column(db.String(120))
    estado_nuevo = db.Column(db.String(120), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.now)

    citacion = db.relationship(
        "CitacionConsejeria", foreign_keys=[id_cita_consejeria])


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

    Varios registros pueden compartir la misma cita o el mismo resultado.
    Cada uno guarda su causa, su tipo y sus fechas. fecha_fin la completa
    el trigger fn_registro_fecha_fin; queda nula si es permanente.
    Si el diagnóstico es de otra institución, no hay causa: id_diferimiento
    queda nulo y se conserva la fecha de inicio.
    """
    __tablename__ = "registro_diferimiento"

    id_registro = db.Column(db.Integer, primary_key=True)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_diferimiento = db.Column(
        db.Integer, db.ForeignKey("diferimiento.id_diferimiento"))
    id_cita = db.Column(db.Integer, db.ForeignKey("cita.id_cita"))
    id_personal = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    origen = db.Column(db.String(30), nullable=False)
    institucion_diagnostico = db.Column(db.String(120), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date)
    id_resultado = db.Column(
        db.Integer, db.ForeignKey("resultado_laboratorio.id_resultado"))
    id_resultado_compatibilidad = db.Column(
        db.Integer,
        db.ForeignKey("resultado_compatibilidad.id_resultado_compatibilidad"))

    causa = db.relationship("Diferimiento", lazy="joined")

    CUESTIONARIO_SISTEMA = "CUESTIONARIO_SISTEMA"
    CUESTIONARIO_PERSONAL = "CUESTIONARIO_PERSONAL"
    MEDICION = "MEDICION"
    EXTRACCION = "EXTRACCION"
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


class MuestraCompatibilidad(db.Model):
    """Muestra venosa para compatibilidad. No entra al inventario."""
    __tablename__ = "muestra_compatibilidad"

    id_muestra = db.Column(db.Integer, primary_key=True)
    id_extraccion = db.Column(
        db.Integer, db.ForeignKey("extraccion.id_extraccion"),
        nullable=False, unique=True)
    id_solicitud = db.Column(
        db.Integer, db.ForeignKey("solicitud.id_solicitud"), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    solicitud = db.relationship("Solicitud")
    extraccion = db.relationship("Extraccion")


class ResultadoCompatibilidad(db.Model):
    """Tipificación y PAI de una muestra. No descarta unidades."""
    __tablename__ = "resultado_compatibilidad"

    id_resultado_compatibilidad = db.Column(db.Integer, primary_key=True)
    id_muestra = db.Column(
        db.Integer, db.ForeignKey("muestra_compatibilidad.id_muestra"),
        nullable=False, unique=True)
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"), nullable=False)
    id_diferimiento = db.Column(
        db.Integer, db.ForeignKey("diferimiento.id_diferimiento"), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    tipo_sangre = db.relationship("TipoSangre", lazy="joined")
    pai = db.relationship("Diferimiento", lazy="joined")
    muestra = db.relationship("MuestraCompatibilidad")

    PAI_POSITIVO = "PAI positivo"
    PAI_NEGATIVO = "PAI negativo"


class Unidad(db.Model):
    """Bolsa de sangre obtenida de una extracción."""
    __tablename__ = "unidad"

    id_unidad = db.Column(db.Integer, primary_key=True)
    id_extraccion = db.Column(
        db.Integer, db.ForeignKey("extraccion.id_extraccion"),
        nullable=False, index=True)
    id_donante = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_solicitud = db.Column(db.Integer, db.ForeignKey("solicitud.id_solicitud"))
    codigo = db.Column(db.String(40), nullable=False, unique=True)
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"))
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
    fecha = db.Column("fecha_hora", db.DateTime, nullable=False, default=datetime.now)


class ResultadoLaboratorio(db.Model):
    __tablename__ = "resultado_laboratorio"

    id_resultado = db.Column(db.Integer, primary_key=True)
    id_unidad = db.Column(
        db.Integer, db.ForeignKey("unidad.id_unidad"), nullable=False, unique=True)
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
    # NULL hasta Ausente o Realizada. Ahí se graba quien cerró.
    id_personal = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"))
    id_horario = db.Column(
        db.Integer, db.ForeignKey("horario_disponible.id_horario"), nullable=False)
    id_resultado = db.Column(
        db.Integer, db.ForeignKey("resultado_laboratorio.id_resultado"),
        unique=True)
    id_resultado_compatibilidad = db.Column(
        db.Integer,
        db.ForeignKey("resultado_compatibilidad.id_resultado_compatibilidad"),
        unique=True)
    horario = db.relationship("HorarioDisponible", lazy="joined")
    fecha_hora = db.Column(db.DateTime)
    estado = db.Column(db.String(20), nullable=False, default="Pendiente")
    observaciones = db.Column(db.Text)

    PENDIENTE = "Pendiente"
    CONFIRMADA = "Confirmada"
    CANCELADA = "Cancelada"
    AUSENTE = "Ausente"
    REALIZADA = "Realizada"
    ABIERTAS = (PENDIENTE, CONFIRMADA)


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


from app.models.historial_estados import activar as _activar_historial  # noqa: E402

_activar_historial(
    Cita, HistorialCita, "cita",
    CitacionConsejeria, HistorialCitaConsejeria, "citacion",
)
