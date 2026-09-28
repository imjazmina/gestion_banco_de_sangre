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

    id_tipo_sangre es nulo a propósito. El grupo sanguíneo no se declara al
    registrarse: lo confirma el laboratorio a partir de una extracción.
    """
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(20), nullable=False, unique=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    genero = db.Column(db.String(20), nullable=False)
    # Nula cuando la cuenta fue suprimida (CHECK ck_usuario_supresion).
    contrasena = db.Column(db.String(255))
    consentimiento_privacidad = db.Column(db.Boolean, nullable=False)
    estado = db.Column(db.Boolean, nullable=False, default=True)
    cuenta_suprimida = db.Column(db.Boolean, nullable=False, default=False)
    # El schema no le pone DEFAULT now(): lo tiene que poner la aplicación.
    fecha_alta = db.Column(db.DateTime, nullable=False, default=datetime.now)
    id_tipo_sangre = db.Column(
        db.Integer, db.ForeignKey("tipo_sangre.id_tipo_sangre"))

    tipo_sangre = db.relationship("TipoSangre", lazy="joined")
    roles = db.relationship(
        "Rol", secondary="usuario_rol", lazy="selectin", viewonly=True)
    telefonos = db.relationship(
        "Telefono", back_populates="usuario", lazy="selectin")
    correos = db.relationship(
        "Correo", back_populates="usuario", lazy="selectin")

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def correo_principal(self):
        return next((c for c in self.correos if c.es_principal), None)

    @property
    def telefono_principal(self):
        return next((t for t in self.telefonos if t.es_principal), None)

    def tiene_rol(self, codigo):
        return any(r.codigo == codigo for r in self.roles)

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


class Telefono(db.Model):
    __tablename__ = "telefono"

    id_telefono = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    numero = db.Column(db.String(30), nullable=False)
    # Un solo principal por usuario: lo garantiza el índice parcial
    # uq_telefono_principal, no este modelo.
    es_principal = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario", back_populates="telefonos")


class Correo(db.Model):
    __tablename__ = "correo"

    id_correo = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    direccion = db.Column(db.String(120), nullable=False, unique=True)
    es_principal = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario", back_populates="correos")
