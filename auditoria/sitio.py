"""Utilidades de texto/URL y la clase Sitio (descubrimiento y caché de páginas públicas)."""
import json
import re
import unicodedata
import urllib.parse as up

from bs4 import BeautifulSoup

DOMINIOS_NO_PROPIOS = (
    "facebook.com", "instagram.com", "wa.me", "whatsapp.com", "linktr.ee", "linktree.com",
    "mercadolibre.com", "mercadolibre.com.ar", "mercadoshops.com", "tiktok.com", "twitter.com",
    "x.com", "youtube.com", "google.com", "goo.gl", "bit.ly", "linkedin.com", "wixsite.com",
    "business.site", "tiendanube.com/ar", "pedidosya.com", "rappi.com",
)


def norm(s):
    """Minúsculas y sin acentos, para reglas de texto."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def sin_www(netloc):
    return netloc.lower().removeprefix("www.")


def normalizar_base(url):
    """Devuelve scheme://host de una URL (descarta ruta, query y parámetros de seguimiento)."""
    if not url:
        return None
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = up.urlsplit(url)
    if not p.netloc:
        return None
    return f"{p.scheme.lower()}://{p.netloc.lower()}"


def es_dominio_propio(base):
    host = sin_www(up.urlsplit(base).netloc)
    return not any(host == d or host.endswith("." + d) for d in DOMINIOS_NO_PROPIOS)


RE_PROD = re.compile(r"/(producto|productos|product|products|item|items|articulo|articulos|p)/[^/?#]{3,}", re.I)
RE_PROD_VTEX = re.compile(r"/[^/?#]{3,}/p/?(\?|$)", re.I)
RE_CAT = re.compile(r"/(categoria|categorias|category|categories|collections|collection|rubro|rubros|"
                    r"departamento|product-category|categoria-producto|c)(/|$)", re.I)
RAICES_LISTADO = ("/productos", "/products", "/tienda", "/shop", "/catalogo", "/tienda-online", "/store")


def es_producto(path):
    return bool(RE_PROD.search(path) or RE_PROD_VTEX.search(path))


def es_categoria(path):
    p = path.rstrip("/").lower()
    if p in RAICES_LISTADO:
        return True
    return bool(RE_CAT.search(path)) and not es_producto(path)


PRIORIDAD_INFO = [r"envio|entrega|despacho|logistica", r"medios? de pago|formas? de pago|\bpago", r"como comprar|como-comprar",
                  r"terminos|condiciones|politica", r"preguntas|faq|ayuda", r"mayorista", r"nosotros|quienes|empresa"]
RE_REGISTRO = re.compile(r"registr|crear cuenta|crear-cuenta|signup|sign-up|register|nueva cuenta|alta de cliente|ser cliente|quiero ser", re.I)
RE_LOGIN = re.compile(r"iniciar sesion|ingresar|login|acceder|mi cuenta|my-account|mi-cuenta", re.I)


def parse_jsonld(soup):
    """Lista plana de objetos JSON-LD (aplana @graph)."""
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                out.append(o)
                g = o.get("@graph")
                if isinstance(g, list):
                    stack.extend(g)
    return out


def tipos_jsonld(objs):
    t = set()
    for o in objs:
        v = o.get("@type")
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str):
                t.add(x)
    return t


class Pagina:
    def __init__(self, resp):
        self.resp = resp
        self.soup = BeautifulSoup(resp.texto, "lxml") if resp.ok and resp.texto else None
        self.texto = norm(self.soup.get_text(" ", strip=True)) if self.soup else ""
        self.jsonld = parse_jsonld(self.soup) if self.soup else []

    @property
    def ok(self):
        return self.soup is not None


class Sitio:
    """Contenedor por plataforma: páginas relevadas (caché) para el filtro y el auditor."""

    def __init__(self, base, etica, cfg):
        self.base, self.etica, self.cfg = base, etica, cfg
        self.host = sin_www(up.urlsplit(base).netloc)
        self.home = None
        self.cat = None
        self.prod = None
        self.registro = None
        self.info = []
        self.enlaces_home = []
        self.url_cat = self.url_prod = self.url_registro = None
        self.hay_login = False
        self.notas = []

    # ---- carga ----
    def _pagina(self, url):
        return Pagina(self.etica.get(url))

    def cargar_home(self):
        self.home = self._pagina(self.base + "/")
        return self.home

    def _mismo_host(self, url):
        return sin_www(up.urlsplit(url).netloc) == self.host

    def enlaces(self, pagina):
        """Enlaces internos únicos (url_abs, texto_norm) de una página."""
        vistos, out = set(), []
        if not pagina or not pagina.ok:
            return out
        for a in pagina.soup.find_all("a", href=True):
            h = a["href"].strip()
            if h.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absu = up.urljoin(pagina.resp.url, h).split("#")[0]
            if not absu.startswith("http") or not self._mismo_host(absu) or absu in vistos:
                continue
            vistos.add(absu)
            out.append((absu, norm(a.get_text(" ", strip=True))))
        return out

    def descubrir(self):
        """Ubica (sin enviar nada) una categoría, un producto, el registro y páginas informativas."""
        if not (self.home and self.home.ok):
            return
        self.enlaces_home = self.enlaces(self.home)
        cats = [u for u, _ in self.enlaces_home if es_categoria(up.urlsplit(u).path)]
        prods = [u for u, _ in self.enlaces_home if es_producto(up.urlsplit(u).path)]
        self.url_cat = cats[0] if cats else None
        self.url_prod = prods[0] if prods else None
        for u, t in self.enlaces_home:
            blob = norm(u) + " " + t
            if self.url_registro is None and RE_REGISTRO.search(blob):
                self.url_registro = u
            if RE_LOGIN.search(blob):
                self.hay_login = True
        self._hay_registro_link = self.url_registro is not None

    def cargar_listado_y_producto(self):
        if self.url_cat and self.cat is None and self.etica.permitido(self.url_cat):
            self.cat = self._pagina(self.url_cat)
        if self.url_prod is None and self.cat and self.cat.ok:
            for u, _ in self.enlaces(self.cat):
                if es_producto(up.urlsplit(u).path):
                    self.url_prod = u
                    break
        if self.url_prod and self.prod is None and self.etica.permitido(self.url_prod):
            self.prod = self._pagina(self.url_prod)

    def cargar_registro(self):
        if self.url_registro and self.registro is None:
            self.registro = self._pagina(self.url_registro)

    def cargar_info(self):
        if self.info:
            return
        elegidas = []
        for patron in PRIORIDAD_INFO:
            for u, t in self.enlaces_home:
                if u in elegidas or u in (self.url_cat, self.url_prod, self.url_registro):
                    continue
                if re.search(patron, norm(u) + " " + t) and not es_producto(up.urlsplit(u).path):
                    elegidas.append(u)
                    break
            if len(elegidas) >= self.cfg.MAX_PAGINAS_INFO:
                break
        self.info = [self._pagina(u) for u in elegidas]

    # ---- textos agregados ----
    def paginas(self):
        return [p for p in [self.home, self.cat, self.prod, self.registro, *self.info] if p and p.ok]

    def texto_total(self):
        return " ".join(p.texto for p in self.paginas())
