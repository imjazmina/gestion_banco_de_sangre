"""
Modelos del sistema.

La estructura de la base la define database/schema.sql, no estos modelos:
acá no se usa db.create_all(). Las clases son el mapeo que le permite a la
aplicación trabajar con objetos de Python en lugar de escribir SQL a mano.

Por eso cada clase declara __tablename__ con el nombre exacto de la tabla y
las columnas con el mismo nombre y tipo que en el schema. Si alguna difiere,
el error aparece recién al consultar, así que hay una prueba que compara
los modelos contra information_schema (ver database/verificar_modelos.py).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Los módulos se importan al final para que db ya exista cuando se definan
# las clases.
from app.models.usuarios import (      # noqa: E402
    Rol, Usuario, UsuarioRol, PerfilPersonal, Telefono, Correo,
    RecuperacionContrasena,
)
from app.models.catalogos import (     # noqa: E402
    TipoSangre, CompatibilidadAboRh, TipoMedicion, Pregunta,
    Diferimiento, HorarioDisponible, ContenidoPortal,
)
from app.models.donacion import (      # noqa: E402
    Solicitud, Cita, Cuestionario, Medicion, RegistroDiferimiento,
    Extraccion, Unidad, TransicionEstado, ResultadoLaboratorio,
    Asignacion, CitacionConsejeria, Derivacion,
)
from app.models.comunicacion import (  # noqa: E402
    Notificacion, Buzon, Auditoria,
)

__all__ = [
    "db",
    "Rol", "Usuario", "UsuarioRol", "PerfilPersonal", "Telefono", "Correo",
    "RecuperacionContrasena",
    "TipoSangre", "CompatibilidadAboRh", "TipoMedicion", "Pregunta",
    "Diferimiento", "HorarioDisponible", "ContenidoPortal",
    "Solicitud", "Cita", "Cuestionario", "Medicion", "RegistroDiferimiento",
    "Extraccion", "Unidad", "TransicionEstado", "ResultadoLaboratorio",
    "Asignacion", "CitacionConsejeria", "Derivacion",
    "Notificacion", "Buzon", "Auditoria",
]
