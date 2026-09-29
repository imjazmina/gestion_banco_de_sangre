"""
Catálogos: datos fijos que el sistema necesita para funcionar.

Se cargan una vez con database/catalogos.sql. No son datos de prueba.
"""
from app.models import db


class TipoSangre(db.Model):
    __tablename__ = "tipo_sangre"

    id_tipo_sangre = db.Column(db.Integer, primary_key=True)
    # char(2): 'A ', 'B ', 'AB', 'O ' — PostgreSQL rellena con espacios.
    grupo = db.Column(db.String(2), nullable=False)
    factor = db.Column(db.String(1), nullable=False)

    @property
    def etiqueta(self):
        """'O-', 'AB+'. Sin el rstrip queda 'O -' por el relleno de char(2)."""
        return f"{self.grupo.rstrip()}{self.factor}"

    def __repr__(self):
        return f"<TipoSangre {self.etiqueta}>"


class CompatibilidadAboRh(db.Model):
    """Qué grupo puede donarle a qué grupo. O- dona a todos, AB+ recibe de todos."""
    __tablename__ = "compatibilidad_abo_rh"

    id_compatibilidad = db.Column(db.Integer, primary_key=True)
    id_tipo_donante = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"), nullable=False)
    id_tipo_receptor = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"), nullable=False)

    donante = db.relationship("TipoSangre", foreign_keys=[id_tipo_donante])
    receptor = db.relationship("TipoSangre", foreign_keys=[id_tipo_receptor])


class TipoMedicion(db.Model):
    """
    Umbrales de aptitud. El trigger fn_medicion_apto los lee para calcular
    solo el campo "apto": el personal carga el valor medido, nunca la
    conclusión (RN01).
    """
    __tablename__ = "tipo_medicion"

    id_tipo_medicion = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    nombre = db.Column(db.String(80), nullable=False)
    unidad = db.Column(db.String(20), nullable=False)
    valor_minimo = db.Column(db.Numeric, nullable=False)
    valor_maximo = db.Column(db.Numeric, nullable=False)

    def __repr__(self):
        return f"<TipoMedicion {self.codigo}>"


class Pregunta(db.Model):
    """
    Parte A: antecedentes, los responde el donante.
    Parte B: condiciones del día, las carga el personal en el check-in.

    preselecciona_exclusion marca las preguntas cuyo "sí" sugiere un
    diferimiento. Sugiere, no decide: la aptitud la determina el personal.
    """
    __tablename__ = "pregunta"

    id_pregunta = db.Column(db.Integer, primary_key=True)
    parte = db.Column(db.String(1), nullable=False)
    enunciado = db.Column(db.Text, nullable=False)
    preselecciona_exclusion = db.Column(db.Boolean, nullable=False)

    PARTE_DONANTE = "A"
    PARTE_PERSONAL = "B"


class Diferimiento(db.Model):
    """
    Catálogo de causas de diferimiento.

    dias_rehabilitacion alimenta el trigger fn_registro_fecha_fin, que
    calcula la fecha de habilitación. Los permanentes van en NULL.
    """
    __tablename__ = "diferimiento"

    id_diferimiento = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False)
    dias_rehabilitacion = db.Column(db.Integer)

    TEMPORAL = "Temporal"
    PERMANENTE = "Permanente"


class HorarioDisponible(db.Model):
    """
    Franja de atención semanal: día de la semana más rango horario.

    Ojo: es una franja recurrente ('Lunes 07:00'), no una fecha concreta.
    """
    __tablename__ = "horario_disponible"

    id_horario = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.String(15), nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    cupo_atencion = db.Column(db.Integer, nullable=False)
    cupo_consejeria = db.Column(db.Integer, nullable=False)
    disponible = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Horario {self.dia_semana} {self.hora_inicio}>"


class ContenidoPortal(db.Model):
    """Textos informativos que se muestran en el portal público."""
    __tablename__ = "contenido_portal"

    id_contenido = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    cuerpo = db.Column(db.Text, nullable=False)
    vigente = db.Column(db.Boolean, nullable=False, default=True)
