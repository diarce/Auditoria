"""Módulo de ética (sección 7.4.1 de la tesis).

- Lee y respeta robots.txt (RFC 9309) ANTES de cada petición, con la biblioteca Protego.
  * robots.txt ausente (4xx)  -> todo permitido.
  * robots.txt ilegible (5xx / error de red) -> todo prohibido (criterio conservador del RFC).
- Solo peticiones GET sobre páginas públicas: sin login, sin formularios, sin carrito.
- Agente identificable con contacto, verificación de certificados TLS, demora mínima entre
  peticiones al mismo host (o Crawl-delay si es mayor) más variación aleatoria (jitter).
- Tope duro de peticiones por sitio y de bytes por respuesta.
"""
import random
import time
import urllib.parse as up
from dataclasses import dataclass, field

import requests
from protego import Protego

from .config import TOKEN_UA

_TEXTO_OK = ("text/", "application/xhtml", "application/xml", "application/json")


@dataclass
class Resp:
    url: str
    status: int | None
    texto: str = ""
    elapsed: float = 0.0
    headers: dict = field(default_factory=dict)
    error: str | None = None      # 'robots', 'ssl', 'limite_peticiones', nombre de excepción...
    ruta: list = field(default_factory=list)

    @property
    def ok(self):
        return self.status == 200 and self.error is None

    @property
    def bloqueado_robots(self):
        return self.error == "robots"


class Etica:
    def __init__(self, cfg):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": cfg.user_agent(),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "es-AR,es;q=0.9",
        })
        self._robots = {}      # origen -> (Protego|None, estado)
        self._ultimo = {}      # netloc -> instante de la última petición
        self.contador = {}     # netloc -> peticiones realizadas (sin robots.txt)
        self.bitacora = []     # (netloc, url, status|error) para trazabilidad

    # ---------- robots.txt ----------
    @staticmethod
    def _origen(url):
        p = up.urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def robots(self, url):
        """Devuelve (parser|None, estado) con estado en {'ok','sin_robots','ilegible'}."""
        o = self._origen(url)
        if o in self._robots:
            return self._robots[o]
        self._esperar(o)
        try:
            r = self.s.get(o + "/robots.txt", timeout=self.cfg.TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                res = (Protego.parse(r.text), "ok")
            elif 400 <= r.status_code < 500:
                res = (None, "sin_robots")
            else:
                res = (None, "ilegible")
        except requests.RequestException:
            res = (None, "ilegible")
        self._ultimo[up.urlsplit(o).netloc] = time.monotonic()
        self._robots[o] = res
        return res

    def estado_robots(self, url):
        return self.robots(url)[1]

    def permitido(self, url):
        parser, estado = self.robots(url)
        if estado == "ilegible":
            return False
        if parser is None:
            return True
        return bool(parser.can_fetch(url, TOKEN_UA))

    def _crawl_delay(self, url):
        parser, _ = self._robots.get(self._origen(url), (None, None))
        if parser is None:
            return 0
        try:
            return float(parser.crawl_delay(TOKEN_UA) or 0)
        except Exception:
            return 0

    def _esperar(self, url):
        netloc = up.urlsplit(url).netloc
        if netloc not in self._ultimo:
            return
        espera = max(self.cfg.DEMORA_MIN, self._crawl_delay(url)) + random.uniform(0, self.cfg.JITTER_MAX)
        falta = espera - (time.monotonic() - self._ultimo[netloc])
        if falta > 0:
            time.sleep(falta)

    # ---------- GET ético ----------
    def get(self, url, seguir=True):
        """GET ético. Con seguir=False devuelve la primera respuesta (útil para ver redirecciones)."""
        ruta, actual = [], url
        for _ in range(self.cfg.MAX_REDIRECCIONES + 1):
            if not self.permitido(actual):
                self.bitacora.append((up.urlsplit(actual).netloc, actual, "robots"))
                return Resp(actual, None, error="robots", ruta=ruta)
            netloc = up.urlsplit(actual).netloc
            if self.contador.get(netloc, 0) >= self.cfg.MAX_PETICIONES_SITIO:
                return Resp(actual, None, error="limite_peticiones", ruta=ruta)
            self._esperar(actual)
            t0 = time.perf_counter()
            try:
                r = self.s.get(actual, timeout=self.cfg.TIMEOUT, allow_redirects=False,
                               stream=True, verify=True)
                partes, n = [], 0
                for ch in r.iter_content(65536):
                    partes.append(ch)
                    n += len(ch)
                    if n >= self.cfg.MAX_BYTES:
                        break
                r.close()
                elapsed = time.perf_counter() - t0
            except requests.exceptions.SSLError:
                self._cerrar(netloc, actual, "ssl")
                return Resp(actual, None, error="ssl", ruta=ruta)
            except requests.RequestException as e:
                self._cerrar(netloc, actual, type(e).__name__)
                return Resp(actual, None, error=type(e).__name__, ruta=ruta)
            self._cerrar(netloc, actual, r.status_code)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                destino = up.urljoin(actual, r.headers["Location"])
                if not seguir:
                    return Resp(actual, r.status_code, "", elapsed, dict(r.headers), ruta=ruta + [destino])
                ruta.append(destino)
                actual = destino
                continue
            ctype = r.headers.get("Content-Type", "").lower()
            texto = ""
            if any(ctype.startswith(t) for t in _TEXTO_OK) or not ctype:
                texto = b"".join(partes).decode(r.encoding or "utf-8", errors="replace")
            return Resp(actual, r.status_code, texto, elapsed, dict(r.headers), ruta=ruta)
        return Resp(actual, None, error="demasiadas_redirecciones", ruta=ruta)

    def _cerrar(self, netloc, url, resultado):
        self.contador[netloc] = self.contador.get(netloc, 0) + 1
        self._ultimo[netloc] = time.monotonic()
        self.bitacora.append((netloc, url, resultado))
