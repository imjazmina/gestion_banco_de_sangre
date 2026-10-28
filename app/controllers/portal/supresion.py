"""
Supresión de cuenta con período de gracia y seudonimización (RF07).

El pedido de baja no borra nada: suspende el acceso y arranca un plazo de
30 días durante los cuales la persona puede arrepentirse. Recién cumplido
el plazo se eliminan los datos que la identifican, y lo que queda es un
registro sanitario sin nombre.

Esa segunda parte es la que exige la Ley N.º 1682/01 junto con el deber de
conservación sanitaria: no se puede borrar la historia de una unidad de
sangre, pero tampoco se puede seguir teniéndola atada a una persona que
pidió que la borren. La salida es quedarse con los hechos y perder la
identidad.

Cómo se representan los tres estados, sin columnas nuevas:

    estado=True   cuenta_suprimida=False   cuenta normal
    estado=False  cuenta_suprimida=False   pedido de baja, en los 30 días
    estado=False  cuenta_suprimida=True    suprimida y seudonimizada

La combinación del medio estaba libre: `usuario.estado` solo lo tocaba
esta misma función. La fecha del pedido sale de `auditoria`, que ya guarda
qué pasó y cuándo, y que ningún trigger deja borrar.

Qué se borra y qué se conserva:

    se borra      nombre, apellido, documento, correos, teléfonos,
                  contraseña
    se cierra     la cita que estuviera agendada y la solicitud publicada
    se conserva   grupo sanguíneo, citas, cuestionarios, mediciones,
                  diferimientos, extracciones y unidades

`fecha_nacimiento` y `genero` se conservan a propósito: no identifican a
nadie por sí solos y los informes los necesitan para los cortes por rango
etario y por sexo (RF21). Si en algún momento se decide que tampoco deben
quedar, el lugar para hacerlo es `_seudonimizar()`.
"""
from datetime import date, timedelta

from app.models import Auditoria, Cita, Correo, Solicitud, Usuario, db

DIAS_DE_GRACIA = 30

# El prefijo del documento seudonimizado. Tiene que entrar en varchar(20) y
# ser único: se le pega el id, que no se repite.
PREFIJO_SUPRIMIDO = "SUP-"


class ErrorSupresion(Exception):
    """La acción no corresponde al estado actual de la cuenta."""


def en_gracia(usuario):
    """¿Pidió la baja y todavía está dentro del plazo para arrepentirse?"""
    return bool(usuario) and not usuario.estado and not usuario.cuenta_suprimida


def fecha_del_pedido(usuario):
    """Cuándo pidió la baja, según la auditoría. None si no hay pedido."""
    registro = (Auditoria.query
                .filter(Auditoria.id_usuario == usuario.id_usuario,
                        Auditoria.entidad == "USUARIO",
                        Auditoria.accion == Auditoria.SUPRESION_CUENTA)
                .order_by(Auditoria.fecha.desc())
                .first())
    return registro.fecha if registro else None


def fecha_definitiva(usuario):
    """El día en que se ejecuta la supresión, o None si no hay pedido."""
    pedido = fecha_del_pedido(usuario)
    return (pedido + timedelta(days=DIAS_DE_GRACIA)).date() if pedido else None


def dias_restantes(usuario, hoy=None):
    """Cuántos días le quedan para cancelar. 0 si el plazo ya venció."""
    limite = fecha_definitiva(usuario)
    if limite is None:
        return None
    return max((limite - (hoy or date.today())).days, 0)


def resumen(usuario, hoy=None):
    """
    Lo que necesita la pantalla de cuenta pendiente de supresión.

    La clave es `cuenta` y no `usuario` a propósito: `usuario` es la
    variable que el context processor usa en todas las plantillas para
    saber si hay sesión iniciada, y acá justamente no la hay.
    """
    return {
        "cuenta": usuario,
        "pedido": fecha_del_pedido(usuario),
        "limite": fecha_definitiva(usuario),
        "dias": dias_restantes(usuario, hoy),
        "dias_de_gracia": DIAS_DE_GRACIA,
    }


def solicitar(usuario):
    """
    Registra el pedido de baja y suspende el acceso.

    No se borra ni un dato todavía, y en particular no se tocan el correo
    ni el teléfono: son por donde se le avisa, y sin ellos tampoco podría
    volver a entrar para cancelar.
    """
    if usuario.cuenta_suprimida:
        raise ErrorSupresion("Esta cuenta ya fue suprimida.")
    if en_gracia(usuario):
        raise ErrorSupresion("Ya hay un pedido de baja en curso.")

    try:
        usuario.estado = False
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.SUPRESION_CUENTA)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def cancelar(usuario):
    """Da marcha atrás con el pedido y devuelve el acceso."""
    if not en_gracia(usuario):
        raise ErrorSupresion("No hay un pedido de baja que cancelar.")

    try:
        usuario.estado = True
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.CAMBIO_ESTADO)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _seudonimizar(usuario):
    """
    Borra lo que identifica y deja lo que hay que conservar.

    La fila no se elimina: hay citas, extracciones y unidades que apuntan a
    ella, y borrarla rompería la trazabilidad de la sangre donada, que es
    justamente lo que no se puede perder. Lo que se va es el vínculo con la
    persona.
    """
    # El documento es único y NOT NULL, así que no se puede dejar vacío. El
    # id sirve de seudónimo: identifica el registro sin identificar a nadie.
    usuario.documento = f"{PREFIJO_SUPRIMIDO}{usuario.id_usuario:06d}"
    usuario.nombre = "Donante"
    usuario.apellido = f"#{usuario.id_usuario}"
    usuario.contrasena = None
    usuario.estado = False
    usuario.cuenta_suprimida = True

    for correo in list(usuario.correos):
        db.session.delete(correo)
    for telefono in list(usuario.telefonos):
        db.session.delete(telefono)

    _cerrar_pendientes(usuario)


def _cerrar_pendientes(usuario):
    """
    Cierra lo que quedó abierto a nombre de la cuenta.

    Son compromisos a futuro, no historia: una cita a la que ya nadie puede
    venir y una solicitud que nadie va a poder gestionar. Dejarlas abiertas
    le ocuparía un turno a otro donante y publicaría un pedido sin nadie
    detrás. Las que ya se cumplieron no se tocan: ésas son el historial que
    hay que conservar.
    """
    for cita in Cita.query.filter(Cita.id_usuario == usuario.id_usuario,
                                  Cita.estado.in_(Cita.ACTIVAS)).all():
        cita.estado = Cita.CANCELADA

    for solicitud in Solicitud.query.filter(
            Solicitud.id_solicitante == usuario.id_usuario,
            Solicitud.estado == Solicitud.PUBLICADA).all():
        solicitud.estado = Solicitud.REVOCADA


def ejecutar(usuario):
    """Ejecuta la supresión definitiva de una cuenta cuyo plazo ya venció."""
    if usuario.cuenta_suprimida:
        raise ErrorSupresion("Esta cuenta ya fue suprimida.")
    if not en_gracia(usuario):
        raise ErrorSupresion("Esta cuenta no tiene un pedido de baja.")

    try:
        _seudonimizar(usuario)
        Auditoria.registrar(usuario.id_usuario, "USUARIO",
                            usuario.id_usuario, Auditoria.BAJA)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def vencidas(hoy=None):
    """
    Las cuentas cuyo plazo de gracia ya se cumplió.

    Son pocas filas —solo las que están en gracia— así que el plazo se
    compara en Python: la fecha del pedido vive en auditoría y no es una
    columna de `usuario` por la que se pueda filtrar directo.
    """
    hoy = hoy or date.today()
    candidatas = (Usuario.query
                  .filter(Usuario.estado.is_(False),
                          Usuario.cuenta_suprimida.is_(False))
                  .all())
    listas = []
    for usuario in candidatas:
        limite = fecha_definitiva(usuario)
        # Sin fecha de pedido no se toca: es una cuenta suspendida por otra
        # razón, no una baja pedida por su titular.
        if limite is not None and limite <= hoy:
            listas.append(usuario)
    return listas


def ejecutar_vencidas(hoy=None):
    """
    Suprime todas las que cumplieron el plazo. Devuelve (hechas, errores).

    Cada una va en su propia transacción: si una falla, las demás se
    ejecutan igual en lugar de quedar todas pendientes.
    """
    hechas, errores = 0, []
    for usuario in vencidas(hoy):
        etiqueta = f"{usuario.nombre} {usuario.apellido}"
        try:
            ejecutar(usuario)
            hechas += 1
        except Exception as e:  # noqa: BLE001
            errores.append(f"{etiqueta}: {e}")
    return hechas, errores


def autenticar_en_gracia(correo, contrasena):
    """
    El usuario en período de gracia que corresponde a esas credenciales.

    `autenticacion.autenticar()` rechaza las cuentas con `estado` en falso,
    que es lo correcto para todo el resto del portal. Pero quien pidió la
    baja tiene que poder entrar a cancelarla, así que acá se la busca a
    propósito, verificando la contraseña igual que en el ingreso normal.
    """
    from sqlalchemy import func

    from app.controllers.portal.autenticacion import verificar

    correo = (correo or "").strip().lower()
    if not correo or not contrasena:
        return None

    usuario = (Usuario.query
               .join(Correo, Correo.id_usuario == Usuario.id_usuario)
               .filter(func.lower(Correo.direccion) == correo,
                       Correo.es_principal.is_(True))
               .first())

    if usuario is None or not en_gracia(usuario):
        return None
    if not verificar(contrasena, usuario.contrasena):
        return None
    return usuario
