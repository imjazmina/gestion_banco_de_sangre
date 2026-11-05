"""
Sesión en la memoria del proceso.

El navegador guarda dos identificadores opacos en cookies HttpOnly. En
memoria solo están sus hashes. El access dura 15 minutos y viaja a todas
las rutas. El refresh dura una semana y el navegador lo envía solo a
`/sesion/renovar`.

Renovar rota el par. Si el mismo refresh llega otra vez dentro de unos
segundos —dos pedidos a la vez—, se responde con el par ya emitido. Pasada
esa ventana, presentarlo revoca la familia. Cerrar sesión revoca solo el
par de este dispositivo.

Un token que no está en memoria no autentica y la respuesta borra las dos
cookies. Reiniciar el proceso vacía la memoria.
"""
import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import flash, g, has_request_context, redirect, request, session, url_for

from app.models import Usuario

AMBITO_PORTAL = "portal"
AMBITO_PERSONAL = "personal"

ACCESS_MINUTOS = 15
REFRESH_DIAS = 7
GRACIA_SEGUNDOS = 5
RUTA_RENOVAR = "/sesion/renovar"
COOKIE_ACCESS = "access_token"
COOKIE_REFRESH = "refresh_token"


def _ahora():
    return datetime.now(timezone.utc)


def _hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _copia(fila):
    return {
        "id": fila["id"],
        "familia": fila["familia"],
        "id_usuario": fila["id_usuario"],
        "ambito": fila["ambito"],
    }


class _Almacen:
    """Índices en memoria. El candado cubre cada operación pública."""

    def __init__(self):
        self._candado = threading.RLock()
        self._sesiones = {}
        self._por_access = {}
        self._por_refresh = {}  
        self._refresh_revocado = {}
        self._gracia = {}

    def crear(self, id_usuario, ambito, ahora=None):
        ahora = ahora or _ahora()
        with self._candado:
            self._purgar(ahora)
            return self._emitir(id_usuario, ambito, secrets.token_hex(16), ahora)

    def validar_access(self, access, ahora=None):
        """Devuelve (datos o None, desconocido). Vencido no es desconocido."""
        ahora = ahora or _ahora()
        with self._candado:
            self._purgar(ahora)
            if not access:
                return None, False
            fila = self._sesiones.get(self._por_access.get(_hash(access)))
            if fila is None:
                return None, True
            if fila["expira_access"] <= ahora:
                return None, False
            return _copia(fila), False

    def renovar(self, refresh, ahora=None):
        """
        Devuelve (datos, par_nuevo, cerrar, desconocido).

        par_nuevo es el par vigente: recién emitido o el de una renovación
        simultánea todavía en gracia.
        """
        ahora = ahora or _ahora()
        with self._candado:
            self._purgar(ahora)
            if not refresh:
                return None, None, False, False
            huella = _hash(refresh)
            gracia = self._gracia.get(huella)
            if gracia is not None:
                if ahora <= gracia["repite_hasta"] and gracia.get("access"):
                    fila = self._sesiones.get(gracia["id"])
                    if fila is not None and fila["expira_refresh"] > ahora:
                        return (_copia(fila), (gracia["access"], gracia["refresh"]),
                                False, False)
                if ahora < gracia["expira"]:
                    self._consumir_reuso(huella, gracia, ahora)
                    return None, None, True, False
                self._gracia.pop(huella, None)
                return None, None, True, False
            revocado = self._refresh_revocado.get(huella)
            if revocado is not None and revocado[1] > ahora:
                self._revocar_familia(revocado[0], ahora)
                return None, None, True, False
            fila = self._sesiones.get(self._por_refresh.get(huella))
            if fila is None:
                return None, None, False, True
            if fila["expira_refresh"] <= ahora:
                self._quitar(fila)
                return None, None, True, False
            return self._rotar(fila, huella, ahora)

    def revocar_access(self, access, ahora=None):
        """Revoca la sesión de ese access aunque el access esté vencido."""
        ahora = ahora or _ahora()
        with self._candado:
            if not access:
                return
            fila = self._sesiones.get(self._por_access.get(_hash(access)))
            if fila is not None:
                self._revocar(fila, ahora)

    def revocar_id(self, id_sesion, ahora=None):
        ahora = ahora or _ahora()
        with self._candado:
            fila = self._sesiones.get(id_sesion)
            if fila is not None:
                self._revocar(fila, ahora)

    def _purgar(self, ahora):
        for fila in list(self._sesiones.values()):
            if fila["expira_refresh"] <= ahora:
                self._quitar(fila)
        for huella, gracia in list(self._gracia.items()):
            if gracia["repite_hasta"] < ahora:
                gracia.pop("access", None)
                gracia.pop("refresh", None)
            if gracia["expira"] <= ahora:
                self._gracia.pop(huella, None)
        self._refresh_revocado = {
            huella: dato
            for huella, dato in self._refresh_revocado.items()
            if dato[1] > ahora
        }

    def _quitar(self, fila):
        self._sesiones.pop(fila["id"], None)
        self._por_access.pop(fila["hash_access"], None)
        if self._por_refresh.get(fila["hash_refresh"]) == fila["id"]:
            self._por_refresh.pop(fila["hash_refresh"], None)

    def _revocar(self, fila, ahora):
        huella = fila["hash_refresh"]
        familia = fila["familia"]
        vence = fila["expira_refresh"]
        self._quitar(fila)
        if vence > ahora:
            self._refresh_revocado[huella] = (familia, vence)
        for previa, gracia in list(self._gracia.items()):
            if gracia["id"] == fila["id"] or gracia["familia"] == familia:
                expira = gracia["expira"]
                self._gracia.pop(previa, None)
                if expira > ahora:
                    self._refresh_revocado[previa] = (familia, expira)

    def _revocar_familia(self, familia, ahora):
        for fila in list(self._sesiones.values()):
            if fila["familia"] == familia:
                self._revocar(fila, ahora)

    def _consumir_reuso(self, huella, gracia, ahora):
        familia = gracia["familia"]
        expira = gracia["expira"]
        self._gracia.pop(huella, None)
        if expira > ahora:
            self._refresh_revocado[huella] = (familia, expira)
        self._revocar_familia(familia, ahora)

    def _emitir(self, id_usuario, ambito, familia, ahora):
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        fila = {
            "id": secrets.token_hex(16),
            "familia": familia,
            "id_usuario": id_usuario,
            "ambito": ambito,
            "hash_access": _hash(access),
            "expira_access": ahora + timedelta(minutes=ACCESS_MINUTOS),
            "hash_refresh": _hash(refresh),
            "expira_refresh": ahora + timedelta(days=REFRESH_DIAS),
        }
        self._sesiones[fila["id"]] = fila
        self._por_access[fila["hash_access"]] = fila["id"]
        self._por_refresh[fila["hash_refresh"]] = fila["id"]
        return access, refresh, _copia(fila)

    def _rotar(self, fila, huella, ahora):
        familia = fila["familia"]
        id_usuario = fila["id_usuario"]
        ambito = fila["ambito"]
        expira = fila["expira_refresh"]
        self._quitar(fila)
        access, refresh, datos = self._emitir(id_usuario, ambito, familia, ahora)
        self._gracia[huella] = {
            "familia": familia,
            "id": datos["id"],
            "access": access,
            "refresh": refresh,
            "repite_hasta": ahora + timedelta(seconds=GRACIA_SEGUNDOS),
            "expira": expira,
        }
        return datos, (access, refresh), False, False


_almacen = _Almacen()


def _olvidar_cookie_vieja():
    """Saca de la cookie firmada los datos que antes identificaban al usuario."""
    session.pop("id_usuario", None)
    session.pop("nombre", None)
    session.pop("ambito", None)


def _vigente():
    if not has_request_context():
        return None
    if getattr(g, "_sesion_lista", False):
        return g.sesion_datos
    datos, desconocido = _almacen.validar_access(request.cookies.get(COOKIE_ACCESS))
    g._sesion_lista = True
    g.sesion_datos = datos
    g.sesion_borrar = desconocido
    return datos


def iniciar_sesion(usuario, ambito):
    ahora = _ahora()
    if has_request_context():
        _almacen.revocar_access(request.cookies.get(COOKIE_ACCESS), ahora)
    access, refresh, datos = _almacen.crear(usuario.id_usuario, ambito, ahora)
    _olvidar_cookie_vieja()
    if has_request_context():
        g._sesion_lista = True
        g.sesion_datos = datos
        g.sesion_cookies = (access, refresh)
        g.sesion_cerrar = False
        g.sesion_borrar = False


def cerrar_sesion():
    if has_request_context():
        _almacen.revocar_access(request.cookies.get(COOKIE_ACCESS))
        g._sesion_lista = True
        g.sesion_datos = None
        g.sesion_cookies = None
        g.sesion_borrar = False
        g.sesion_cerrar = True
    _olvidar_cookie_vieja()


def renovar():
    """Rota el par si el refresh sigue vigente. Si no, borra las cookies."""
    token = request.cookies.get(COOKIE_REFRESH)
    datos, par, cerrar, desconocido = _almacen.renovar(token)
    g._sesion_lista = True
    if par and not cerrar and not desconocido:
        g.sesion_datos = datos
        g.sesion_cookies = par
        g.sesion_cerrar = False
        g.sesion_borrar = False
        return "", 204
    g.sesion_datos = None
    g.sesion_cookies = None
    g.sesion_borrar = False
    g.sesion_cerrar = token is not None
    return "", 401


def aplicar_cookies_de_sesion(response):
    """Escribe o borra las cookies después de la vista."""
    if not has_request_context():
        return response
    if getattr(g, "sesion_cerrar", False) or getattr(g, "sesion_borrar", False):
        _borrar_cookie(response, COOKIE_ACCESS, "/")
        _borrar_cookie(response, COOKIE_REFRESH, RUTA_RENOVAR)
        return response
    par = getattr(g, "sesion_cookies", None)
    if par:
        _poner_cookie(response, COOKIE_ACCESS, par[0], ACCESS_MINUTOS * 60, "/")
        _poner_cookie(
            response, COOKIE_REFRESH, par[1], REFRESH_DIAS * 24 * 3600, RUTA_RENOVAR)
    return response


def _poner_cookie(response, nombre, valor, max_age, path):
    response.set_cookie(
        nombre,
        valor,
        max_age=max_age,
        httponly=True,
        secure=request.is_secure,
        samesite="Lax",
        path=path,
    )


def _borrar_cookie(response, nombre, path):
    response.delete_cookie(
        nombre,
        path=path,
        secure=request.is_secure,
        samesite="Lax",
        httponly=True,
    )


def usuario_en_ambito(ambito):
    """El Usuario de ese ámbito, o None si la sesión es de otro o no sirve."""
    datos = _vigente()
    if not datos or datos["ambito"] != ambito:
        return None
    usuario = (Usuario.query
               .filter_by(id_usuario=datos["id_usuario"],
                          estado=True, cuenta_suprimida=False)
               .first())
    if usuario is None:
        _almacen.revocar_id(datos["id"])
        g.sesion_datos = None
        g.sesion_cookies = None
        g.sesion_borrar = False
        g.sesion_cerrar = True
        return None
    return usuario


def usuario_actual():
    """El donante con sesión de portal, o None."""
    return usuario_en_ambito(AMBITO_PORTAL)


def requiere_login(vista):
    """Decorador: la vista solo se ve con sesión iniciada."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            flash("Iniciá sesión para continuar.", "info")
            return redirect(url_for("auth.ingresar"))
        return vista(*args, **kwargs)
    return envoltura


def requiere_rol(*codigos):
    """Decorador: además de sesión, exige uno de los roles indicados."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                flash("Iniciá sesión para continuar.", "info")
                return redirect(url_for("auth.ingresar"))
            if not any(usuario.tiene_rol(c) for c in codigos):
                flash("No tenés permiso para acceder a esa sección.", "error")
                return redirect(url_for("main.index"))
            return vista(*args, **kwargs)
        return envoltura
    return decorador
