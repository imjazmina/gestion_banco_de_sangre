"""
Sesión en la memoria del proceso.

`sesiones` guarda cada ingreso con su id. Un login agrega una entrada y
no borra las demás. El navegador tiene dos cookies HttpOnly, una por
ámbito (`portal` y `personal`): cada una lleva los tokens de las sesiones
de ese ámbito. La pestaña guarda solo el id en sessionStorage y lo manda
en `X-Sesion`. Ese id no autentica: el token de la cookie tiene que
existir y corresponder a esa entrada.

El access dura 15 minutos. El refresh dura una semana. Renovar rota
únicamente el par de la pestaña que lo pide. Cerrar sesión revoca solo
esa entrada. Reiniciar el proceso vacía el diccionario.
"""
import hashlib
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from flask import (flash, g, has_request_context, make_response, redirect,
                   request, session, url_for)

from app.models import Usuario

AMBITO_PORTAL = "portal"
AMBITO_PERSONAL = "personal"

ACCESS_MINUTOS = 15
REFRESH_DIAS = 7
GRACIA_SEGUNDOS = 5
RUTA_RENOVAR = "/sesion/renovar"

# Cada ingreso agrega una clave. Un login no pisa las otras.
sesiones = {}

COOKIE_AMBITO = {
    AMBITO_PORTAL: "portal_sesion",
    AMBITO_PERSONAL: "personal_sesion",
}
_LEGACY = (
    ("access_token", "/"),
    ("refresh_token", RUTA_RENOVAR),
    ("access_personal", "/"),
    ("refresh_personal", RUTA_RENOVAR),
)


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
        self._sesiones = sesiones
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

    def _emitir(self, id_usuario, ambito, familia, ahora, id_sesion=None):
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        fila = {
            "id": id_sesion or secrets.token_hex(16),
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
        id_sesion = fila["id"]
        expira = fila["expira_refresh"]
        self._quitar(fila)
        access, refresh, datos = self._emitir(
            id_usuario, ambito, familia, ahora, id_sesion)
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


def _parse_mapa(raw):
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    limpio = {}
    for sid, par in data.items():
        if (isinstance(sid, str) and isinstance(par, list) and len(par) == 2
                and all(isinstance(parte, str) for parte in par)):
            limpio[sid] = (par[0], par[1])
    return limpio


def _mapas():
    if getattr(g, "mapas_sesion", None) is None:
        g.mapas_sesion = {
            ambito: _parse_mapa(request.cookies.get(nombre))
            for ambito, nombre in COOKIE_AMBITO.items()
        }
        g.mapas_tocados = set()
    return g.mapas_sesion


def _tocar(ambito):
    _mapas()
    g.mapas_tocados.add(ambito)


def _sid_resuelto():
    """El id de esta pestaña, o None si el pedido todavía no lo dijo."""
    if getattr(g, "sid_nueva", None):
        return g.sid_nueva
    if request.headers.get("X-Sesion-Resuelta") != "1":
        return None
    return (request.headers.get("X-Sesion") or "").strip()


def _hay_cookies():
    return any(_mapas().values())


def _es_documento():
    destino = request.headers.get("Sec-Fetch-Dest", "")
    if destino:
        return destino == "document"
    if request.method not in ("GET", "HEAD"):
        return False
    return "text/html" in request.headers.get("Accept", "")


def _bootstrap():
    """El script corre oculto. La página real aparece cuando su CSS ya cargó."""
    src = url_for("static", filename="js/comun/sesion.js")
    return f"""<!DOCTYPE html>
<html style="visibility:hidden"><head><meta charset="utf-8">
<script src="{src}"></script>
<script>
(function () {{
  var sid = sessionStorage.getItem("sid") || "";
  var headers = {{"X-Sesion": sid, "X-Sesion-Resuelta": "1", "Accept": "text/html"}};
  fetch("/sesion/renovar", {{method: "POST", headers: headers, credentials: "same-origin"}})
    .catch(function () {{}})
    .then(function () {{
      return fetch(location.href, {{headers: headers, credentials: "same-origin", redirect: "follow"}});
    }})
    .then(function (r) {{
      if (r.redirected) {{ location.replace(r.url); return null; }}
      return r.text();
    }})
    .then(function (html) {{
      if (!html || !window.pintarDocumento) {{
        document.documentElement.style.visibility = "visible";
        return;
      }}
      window.pintarDocumento(html);
    }});
}})();
</script></head><body></body></html>"""


def _destino_limpio(url):
    partes = urlparse(url)
    if partes.netloc and partes.netloc != request.host:
        return url
    query = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
             if k != "sesion"]
    return urlunparse(partes._replace(query=urlencode(query)))


def _html_pestaña(js, destino):
    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body><script>"
        f"{js}location.replace({json.dumps(destino)});"
        "</script></body></html>"
    )
    respuesta = make_response(html)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def _elegir(ambito):
    """La entrada de este ámbito cuyo token coincide con el id de la pestaña."""
    if getattr(g, "sesion_cerrada", False):
        return None
    sid = _sid_resuelto()
    if not sid:
        return None
    mapa = _mapas()[ambito]
    par = mapa.get(sid)
    if not par:
        return None
    datos, desconocido = _almacen.validar_access(par[0])
    ajeno = datos is not None and (datos["id"] != sid or datos["ambito"] != ambito)
    if desconocido or ajeno:
        mapa.pop(sid, None)
        _tocar(ambito)
        return None
    if datos is None:
        return None
    return sid, datos


def preparar_sid():
    """La navegación con cookies y sin id de pestaña no adivina el usuario."""
    if request.path.startswith("/static/") or request.path == RUTA_RENOVAR:
        return None
    if request.method not in ("GET", "HEAD"):
        return None
    if request.headers.get("X-Sesion-Resuelta") == "1":
        return None
    if not _es_documento() or not _hay_cookies():
        return None
    respuesta = make_response(_bootstrap())
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def entregar_sid(response):
    """Pasa el id a sessionStorage. No lo pone en la dirección."""
    if not has_request_context():
        return response
    if response.status_code not in (301, 302, 303, 307, 308):
        return response
    destino = _destino_limpio(response.headers.get("Location") or "/")
    if getattr(g, "sesion_cerrada", False):
        return _html_pestaña("sessionStorage.removeItem('sid');", destino)
    sid = getattr(g, "sid_nueva", None)
    if not sid:
        return response
    js = f"sessionStorage.setItem('sid', {json.dumps(sid)});"
    return _html_pestaña(js, destino)


def iniciar_sesion(usuario, ambito):
    """Agrega una sesión al diccionario y a la cookie de ese ámbito."""
    access, refresh, datos = _almacen.crear(usuario.id_usuario, ambito)
    sid = datos["id"]
    _olvidar_cookie_vieja()
    if has_request_context():
        _mapas()[ambito][sid] = (access, refresh)
        _tocar(ambito)
        g.sid_nueva = sid
        g.sesion_cerrada = False


def cerrar_sesion(ambito):
    """Quita solo la sesión de esta pestaña. El resto del diccionario queda."""
    if has_request_context():
        sid = _sid_resuelto()
        mapa = _mapas()[ambito]
        par = mapa.get(sid) if sid else None
        if par:
            datos, _desconocido = _almacen.validar_access(par[0])
            if datos is not None and datos["id"] == sid:
                _almacen.revocar_id(sid)
            else:
                _almacen.revocar_access(par[0])
            mapa.pop(sid, None)
            _tocar(ambito)
        g.sid_nueva = None
        g.sesion_cerrada = True
    _olvidar_cookie_vieja()


def renovar():
    """Rota el par de la pestaña que lo pide. Las otras entradas siguen."""
    sid = (request.headers.get("X-Sesion") or "").strip()
    if not sid or not has_request_context():
        return "", 401
    for ambito in (AMBITO_PORTAL, AMBITO_PERSONAL):
        mapa = _mapas()[ambito]
        par = mapa.get(sid)
        if not par:
            continue
        datos, nuevo, cerrar, desconocido = _almacen.renovar(par[1])
        if (nuevo and not cerrar and not desconocido
                and datos is not None and datos["id"] == sid):
            mapa[sid] = nuevo
            _tocar(ambito)
            return "", 204
        mapa.pop(sid, None)
        _tocar(ambito)
        return "", 401
    return "", 401


def aplicar_cookies_de_sesion(response):
    """Escribe la cookie del ámbito que este pedido modificó."""
    if not has_request_context():
        return response
    max_age = REFRESH_DIAS * 24 * 3600
    for ambito in getattr(g, "mapas_tocados", ()):
        nombre = COOKIE_AMBITO[ambito]
        mapa = _mapas()[ambito]
        if mapa:
            cuerpo = {sid: [par[0], par[1]] for sid, par in mapa.items()}
            _poner_cookie(response, nombre, json.dumps(cuerpo), max_age, "/")
        else:
            _borrar_cookie(response, nombre, "/")
    for nombre, path in _LEGACY:
        if nombre in request.cookies:
            _borrar_cookie(response, nombre, path)
    for nombre in request.cookies:
        if nombre.startswith("ses_"):
            _borrar_cookie(response, nombre, "/")
        elif nombre.startswith("ref_"):
            _borrar_cookie(response, nombre, RUTA_RENOVAR)
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
    """El Usuario de la sesión de esta pestaña en ese ámbito, o None."""
    elegida = _elegir(ambito)
    if elegida is None:
        return None
    sid, datos = elegida
    usuario = (Usuario.query
               .filter_by(id_usuario=datos["id_usuario"],
                          estado=True, cuenta_suprimida=False)
               .first())
    if usuario is None:
        _almacen.revocar_id(datos["id"])
        _mapas()[ambito].pop(sid, None)
        _tocar(ambito)
        return None
    return usuario


def usuario_actual():
    """El donante con sesión de portal en esta pestaña, o None."""
    return usuario_en_ambito(AMBITO_PORTAL)


def _redirigir_sin_sesion():
    flash("Iniciá sesión para continuar.", "info")
    return redirect(url_for("auth.ingresar"))


def requiere_login(vista):
    """Decorador: la vista solo se ve con sesión iniciada."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            return _redirigir_sin_sesion()
        return vista(*args, **kwargs)
    return envoltura


def requiere_rol(*codigos):
    """Decorador: además de sesión, exige uno de los roles indicados."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                return _redirigir_sin_sesion()
            if not any(usuario.tiene_rol(c) for c in codigos):
                flash("No tenés permiso para acceder a esa sección.", "error")
                return redirect(url_for("main.index"))
            return vista(*args, **kwargs)
        return envoltura
    return decorador

