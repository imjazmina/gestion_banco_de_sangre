"""Personas del sistema: donantes, personal y sus datos de contacto."""
from datetime import datetime

from app.models import db


class Rol(db.Model):
    __tablename__ = "rol"

    id_rol = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    nombre = db.Column(db.String(80), nullable=False)

    # Valores que admite el CHECK ck_rol_codigo.
    DONANTE = "DONANTE"
    ENFERMERIA = "ENFERMERIA"
    JEFATURA = "JEFATURA"
    ADMIN = "ADMIN"

    def __repr__(self):
        return f"<Rol {self.codigo}>"


class Usuario(db.Model):
    """
    Una sola tabla para donantes y personal: lo que distingue a uno de otro
    es el rol asignado en usuario_rol, no una tabla aparte.

    El grupo no se declara al registrarse ni se guarda en esta tabla.
    Lo confirma el laboratorio en resultado_laboratorio; tipo_sangre
    es solo el catálogo.
    """
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(64), nullable=False, unique=True)
    # Nulos cuando la cuenta fue suprimida.
    nombre = db.Column(db.String(80))
    apellido = db.Column(db.String(80))
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    genero = db.Column(db.String(20), nullable=False)
    # Nula cuando la cuenta fue suprimida (CHECK ck_usuario_supresion).
    contrasena = db.Column(db.String(64))
    consentimiento_privacidad = db.Column(db.Boolean, nullable=False)
    estado = db.Column(db.Boolean, nullable=False, default=True)
    cuenta_suprimida = db.Column(db.Boolean, nullable=False, default=False)
    # El schema no le pone DEFAULT now(): lo tiene que poner la aplicación.
    fecha_alta = db.Column(db.DateTime, nullable=False, default=datetime.now)

    roles = db.relationship(
        "Rol", secondary="usuario_rol", lazy="selectin", viewonly=True)
    correos = db.relationship(
        "Correo", back_populates="usuario", lazy="selectin")

    @property
    def nombre_completo(self):
        texto = " ".join(parte for parte in (self.nombre, self.apellido) if parte)
        if texto:
            return texto
        if self.cuenta_suprimida:
            return "Cuenta suprimida"
        return ""

    @property
    def documento_visible(self):
        """La cédula en claro. Tras la supresión no se muestra el hash."""
        if self.cuenta_suprimida:
            return "—"
        return self.documento

    @property
    def correo_principal(self):
        return next((c for c in self.correos if c.es_principal), None)

    def tiene_rol(self, codigo):
        return any(r.codigo == codigo for r in self.roles)

    @staticmethod
    def tipo_confirmado(id_usuario):
        """Primera tipificación de laboratorio del donante. No se vuelve a sortear."""
        from app.models.catalogos import TipoSangre
        from app.models.donacion import ResultadoLaboratorio, Unidad

        from app.models.donacion import (
            Cita, Extraccion, MuestraCompatibilidad, ResultadoCompatibilidad,
        )

        de_unidad = (
            db.session.query(TipoSangre, ResultadoLaboratorio.fecha,
                             ResultadoLaboratorio.id_resultado)
            .join(ResultadoLaboratorio,
                  ResultadoLaboratorio.id_tipo_sangre == TipoSangre.id_tipo_sangre)
            .join(Unidad, Unidad.id_unidad == ResultadoLaboratorio.id_unidad)
            .filter(Unidad.id_donante == id_usuario)
            .order_by(ResultadoLaboratorio.fecha.asc(),
                      ResultadoLaboratorio.id_resultado.asc())
            .first()
        )
        de_muestra = (
            db.session.query(TipoSangre, ResultadoCompatibilidad.fecha,
                             ResultadoCompatibilidad.id_resultado_compatibilidad)
            .join(ResultadoCompatibilidad,
                  ResultadoCompatibilidad.id_tipo_sangre == TipoSangre.id_tipo_sangre)
            .join(MuestraCompatibilidad,
                  MuestraCompatibilidad.id_muestra == ResultadoCompatibilidad.id_muestra)
            .join(Extraccion,
                  Extraccion.id_extraccion == MuestraCompatibilidad.id_extraccion)
            .join(Cita, Cita.id_cita == Extraccion.id_cita)
            .filter(Cita.id_usuario == id_usuario)
            .order_by(ResultadoCompatibilidad.fecha.asc(),
                      ResultadoCompatibilidad.id_resultado_compatibilidad.asc())
            .first()
        )
        candidatos = [fila for fila in (de_unidad, de_muestra) if fila is not None]
        if not candidatos:
            return None
        candidatos.sort(key=lambda fila: (fila[1], fila[2]))
        return candidatos[0][0]

    @property
    def tipo_sangre(self):
        return Usuario.tipo_confirmado(self.id_usuario)

    def __repr__(self):
        return f"<Usuario {self.documento} {self.nombre_completo}>"


class UsuarioRol(db.Model):
    """Tabla puente: un usuario puede tener más de un rol."""
    __tablename__ = "usuario_rol"

    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), primary_key=True)
    id_rol = db.Column(
        db.Integer, db.ForeignKey("rol.id_rol"), primary_key=True)


class PerfilPersonal(db.Model):
    """Datos que solo tiene el personal de salud, no los donantes."""
    __tablename__ = "perfil_personal"

    id_perfil_personal = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"),
        nullable=False, unique=True)
    registro_profesional = db.Column(db.String(30), nullable=False, unique=True)
    correo_institucional = db.Column(db.String(120), nullable=False, unique=True)
    fecha_alta_servicio = db.Column(db.Date)

    usuario = db.relationship("Usuario", lazy="joined")



class Correo(db.Model):
    __tablename__ = "correo"

    id_correo = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    direccion = db.Column(db.String(120), nullable=False, unique=True)
    es_principal = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario", back_populates="correos")
