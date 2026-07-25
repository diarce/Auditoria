"""
modules/discoverer.py
─────────────────────
Etapa 0 del pipeline: descubrimiento automático de empresas mayoristas
con presencia digital en Posadas, Garupá e Itaembé Guazú, Misiones.

Flujo completo del sistema:
  [Etapa 0] Descubrir  →  [Etapa 1] Auditar  →  [Etapa 2] Analizar  →  [Etapa 3] Reportar

Fuentes de descubrimiento:
  • Web search via duckduckgo-search (sin API key, sin robots restriction)
  • Lista estructurada del investigador (campo / Cámara de Comercio / AFIP)
  • Importación desde Google Maps export (CSV)
  • Exploración de directorios web (Páginas Amarillas, La Guía)

Para cada URL encontrada el módulo verifica:
  ✓ Disponibilidad HTTP
  ✓ robots.txt (con user-agent académico)
  ✓ Metadatos básicos (título, descripción, plataforma CMS)
  ✓ Clasificación del nivel de madurez digital (A/B/C/D)

Dependencias adicionales (instalar en Colab):
  pip install duckduckgo-search
"""

from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ─── Constantes ───────────────────────────────────────────────────────────────

UA_BOT = (
    "AuditMayoristaBot/1.0 "
    "(academic-research; tesis-MAEN-UNaM; "
    "+https://github.com/diarce/Tesis_Maen)"
)

HEADERS = {
    "User-Agent": UA_BOT,
    "Accept-Language": "es-AR,es;q=0.9",
}

TIMEOUT = 12  # segundos

# Términos de búsqueda para el mercado objetivo
QUERIES_DESCUBRIMIENTO = [
    "mayorista consumo masivo Posadas Misiones Argentina",
    "distribuidora mayorista Posadas Misiones tienda online",
    "supermercado mayorista Posadas Misiones sitio web",
    "distribuidora alimentos bebidas Posadas Garupá Misiones",
    "mayorista limpieza higiene Posadas Misiones",
    "distribuidora consumo masivo NEA Misiones comprar online",
]

# CMS y plataformas detectables en el HTML
FINGERPRINTS_PLATAFORMA = {
    "vtex":          re.compile(r'vtex|vteximg\.com', re.I),
    "tiendanube":    re.compile(r'tiendanube\.com|d3ugyf2q1y9x9l', re.I),
    "mercadoshops":  re.compile(r'mercadoshops\.com|myshopi', re.I),
    "woocommerce":   re.compile(r'woocommerce|wp-content', re.I),
    "shopify":       re.compile(r'shopify|myshopify', re.I),
    "prestashop":    re.compile(r'prestashop', re.I),
    "magento":       re.compile(r'magento', re.I),
    "instagram":     re.compile(r'instagram\.com', re.I),
    "facebook":      re.compile(r'facebook\.com/pages|facebook\.com/\w+mayorist', re.I),
    "linktree":      re.compile(r'linktr\.ee', re.I),
    "whatsapp":      re.compile(r'wa\.me|whatsapp\.com/send', re.I),
}


# ─── Estructuras de datos ─────────────────────────────────────────────────────

@dataclass
class EmpresaDescubierta:
    nombre:            str
    url:               str
    fuente:            str              # "web_search" | "campo" | "google_maps" | "manual"
    localidad:         str = "Posadas"
    http_status:       int = 0
    titulo:            str = ""
    descripcion:       str = ""
    plataforma:        str = "desconocida"
    robots_permite:    bool = False
    auditable:         bool = False
    nivel_digital:     str = "D"        # A / B / C / D
    site_id:           str = ""
    fecha_descubrimiento: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    )
    notas:             str = ""


# ─── Clase principal ──────────────────────────────────────────────────────────

class Discoverer:
    """
    Descubridor automático de empresas mayoristas con presencia digital.

    Parámetros
    ----------
    localidades : list[str]
        Localidades del estudio. Por defecto: Posadas, Garupá, Itaembé Guazú.
    log_fn : callable, opcional
        Función de log con firma log_fn(msg, nivel).
    delay : float
        Pausa en segundos entre requests (respeto de rate limiting).
    """

    def __init__(
        self,
        localidades: list[str] | None = None,
        log_fn=None,
        delay: float = 2.0,
    ):
        self.localidades = localidades or ["Posadas", "Garupá", "Itaembé Guazú"]
        self._log        = log_fn or (lambda msg, nivel="INFO": print(f"[{nivel}] {msg}"))
        self.delay       = delay
        self._robots_cache: dict[str, bool] = {}
        self._empresas: list[EmpresaDescubierta] = []

    # ── API pública ────────────────────────────────────────────────────────────

    def desde_busqueda_web(self, max_por_query: int = 8) -> list[EmpresaDescubierta]:
        """
        Busca empresas usando duckduckgo-search.
        Requiere: pip install duckduckgo-search
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            self._log(
                "Instale el paquete: pip install duckduckgo-search", "ERR"
            )
            return []

        nuevas: list[EmpresaDescubierta] = []
        urls_vistas: set[str] = set()

        with DDGS() as ddgs:
            for query in QUERIES_DESCUBRIMIENTO:
                self._log(f"Buscando: {query[:55]}...", "INFO")
                try:
                    resultados = list(ddgs.text(query, max_results=max_por_query))
                    time.sleep(self.delay)
                except Exception as e:
                    self._log(f"Error en búsqueda: {e}", "WARN")
                    continue

                for r in resultados:
                    url = r.get("href", "")
                    if not url or url in urls_vistas:
                        continue
                    if not self._es_url_candidata(url):
                        continue
                    urls_vistas.add(url)

                    emp = EmpresaDescubierta(
                        nombre  = r.get("title", url)[:80],
                        url     = url,
                        fuente  = "web_search",
                        notas   = r.get("body", "")[:200],
                    )
                    empresa_verificada = self._verificar(emp)
                    nuevas.append(empresa_verificada)
                    self._log(
                        f"  {'OK' if empresa_verificada.auditable else '--'} "
                        f"{empresa_verificada.nivel_digital} | "
                        f"{empresa_verificada.nombre[:40]}",
                        "OK" if empresa_verificada.auditable else "INFO",
                    )
                    time.sleep(self.delay)

        self._empresas.extend(nuevas)
        return nuevas

    def desde_lista_manual(self, empresas: list[dict]) -> list[EmpresaDescubierta]:
        """
        Verifica una lista ingresada por el investigador.

        Cada item puede tener:
            nombre   (requerido)
            url      (requerido si no hay solo nombre)
            localidad (opcional, default Posadas)
            notas    (opcional)

        Ejemplo:
            discoverer.desde_lista_manual([
                {'nombre': 'Distribuidora El Norteno', 'url': 'https://elnorteno.com.ar'},
                {'nombre': 'Vital NEA',                'url': 'https://vital.com.ar'},
            ])
        """
        nuevas = []
        for item in empresas:
            nombre = item.get("nombre", "").strip()
            url    = item.get("url",    "").strip()
            if not nombre or not url:
                self._log(f"Ítem incompleto (falta nombre o url): {item}", "WARN")
                continue
            emp = EmpresaDescubierta(
                nombre    = nombre,
                url       = url,
                fuente    = "manual",
                localidad = item.get("localidad", "Posadas"),
                notas     = item.get("notas", ""),
            )
            emp_v = self._verificar(emp)
            nuevas.append(emp_v)
            self._log(
                f"  {'OK' if emp_v.auditable else '--'} "
                f"[{emp_v.nivel_digital}] {emp_v.nombre[:45]} | {url}",
                "OK" if emp_v.auditable else "INFO",
            )
        self._empresas.extend(nuevas)
        return nuevas

    def desde_google_maps_csv(self, csv_path: str) -> list[EmpresaDescubierta]:
        """
        Importa desde el CSV exportado de Google Maps.

        Cómo exportar: Google Maps → buscar 'mayorista Posadas' →
        en los resultados abrir cada lugar → botón 'Compartir' →
        usar herramientas como 'outscraper.com' (plan free) o
        exportar desde Google My Business si se tiene acceso.

        Columnas mínimas esperadas: name, website (o url)
        Columnas opcionales: phone, address, category, rating
        """
        import pandas as pd

        df = pd.read_csv(csv_path, dtype=str).fillna("")
        # Normalizar nombres de columnas
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        url_col = next(
            (c for c in ["website", "url", "web", "sitio_web"] if c in df.columns),
            None
        )
        if not url_col:
            self._log("El CSV no tiene columna 'website' o 'url'", "ERR")
            return []

        nuevas = []
        for _, row in df.iterrows():
            url    = row.get(url_col, "").strip()
            nombre = row.get("name", row.get("nombre", url)).strip()
            if not url or not nombre:
                continue
            emp = EmpresaDescubierta(
                nombre    = nombre[:80],
                url       = url,
                fuente    = "google_maps",
                localidad = row.get("city", row.get("ciudad", "Posadas")),
                notas     = row.get("category", row.get("categoria", "")),
            )
            emp_v = self._verificar(emp)
            nuevas.append(emp_v)
        self._empresas.extend(nuevas)
        return nuevas

    def exportar_json(self, destino: str | Path) -> Path:
        """
        Exporta las empresas descubiertas al formato de empresas_mayoristas.json,
        listo para cargar en AuditMayorista como candidatas a auditar.
        """
        destino = Path(destino)
        datos = []
        for i, e in enumerate(self._empresas, start=4):  # MIS001-003 ya existen
            sid = e.site_id or f"DIS{i:03d}"
            datos.append({
                "id":         sid,
                "name":       e.nombre,
                "base_url":   e.url,
                "localidades": [e.localidad],
                "dynamic":    e.plataforma in ("vtex", "tiendanube", "shopify"),
                "auditable":  e.auditable,
                "nivel_digital": e.nivel_digital,
                "plataforma": e.plataforma,
                "robots_permite": e.robots_permite,
                "fuente_descubrimiento": e.fuente,
                "fecha": e.fecha_descubrimiento,
                "notas": e.notas,
                "selectors": {},
            })
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        self._log(f"Exportadas {len(datos)} empresas → {destino.name}", "OK")
        return destino

    def tabla_resumen(self) -> "pd.DataFrame":
        """Devuelve un DataFrame con el resumen del descubrimiento."""
        import pandas as pd
        if not self._empresas:
            return pd.DataFrame()
        filas = []
        for e in self._empresas:
            filas.append({
                "Nombre":          e.nombre[:40],
                "URL":             e.url[:50],
                "Nivel":           e.nivel_digital,
                "Plataforma":      e.plataforma,
                "robots OK":       "✓" if e.robots_permite else "✗",
                "Auditable":       "✓" if e.auditable      else "✗",
                "HTTP":            e.http_status,
                "Fuente":          e.fuente,
                "Localidad":       e.localidad,
            })
        return pd.DataFrame(filas)

    # ── Métodos internos ───────────────────────────────────────────────────────

    def _verificar(self, emp: EmpresaDescubierta) -> EmpresaDescubierta:
        """Completa los campos de verificación de una empresa."""
        url = emp.url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        emp.url = url

        # 1. Verificar robots.txt
        emp.robots_permite = self._check_robots(url)

        # 2. Obtener metadatos HTTP
        try:
            resp = requests.get(
                url, headers=HEADERS, timeout=TIMEOUT,
                allow_redirects=True
            )
            emp.http_status = resp.status_code

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                emp.titulo = (soup.title.string or "").strip()[:120]

                meta_desc = soup.find("meta", attrs={"name": re.compile("description", re.I)})
                if meta_desc:
                    emp.descripcion = (meta_desc.get("content", "") or "")[:200]

                # Detectar plataforma
                html_text = resp.text
                for plat, pattern in FINGERPRINTS_PLATAFORMA.items():
                    if pattern.search(html_text):
                        emp.plataforma = plat
                        break

        except requests.exceptions.SSLError:
            # Reintentar sin verificar SSL (algunos sitios argentinos tienen cert expirado)
            try:
                resp = requests.get(
                    url, headers=HEADERS, timeout=TIMEOUT,
                    allow_redirects=True, verify=False
                )
                emp.http_status = resp.status_code
            except Exception:
                emp.http_status = 0
        except Exception:
            emp.http_status = 0

        # 3. Clasificar nivel de madurez digital
        emp.nivel_digital = self._clasificar_nivel(emp)

        # 4. Determinar si es auditable
        emp.auditable = (
            emp.robots_permite
            and emp.http_status == 200
            and emp.nivel_digital in ("A", "B", "C")
            and emp.plataforma not in ("instagram", "facebook", "whatsapp", "linktree")
        )

        time.sleep(self.delay * 0.5)
        return emp

    def _check_robots(self, url: str) -> bool:
        """Verifica robots.txt con caché."""
        parsed   = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if base_url in self._robots_cache:
            return self._robots_cache[base_url]
        try:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(base_url, "/robots.txt"))
            rp.read()
            permitido = rp.can_fetch(UA_BOT, url)
        except Exception:
            permitido = True  # Si no se puede leer, asumir permiso
        self._robots_cache[base_url] = permitido
        return permitido

    def _clasificar_nivel(self, emp: EmpresaDescubierta) -> str:
        """Clasifica el nivel de madurez digital basado en plataforma y URL."""
        plat = emp.plataforma.lower()

        # Nivel D — solo redes sociales o sin web propia
        if plat in ("instagram", "facebook", "whatsapp", "linktree"):
            return "D"
        if emp.http_status != 200:
            return "D"

        # Nivel A — e-commerce completo
        if plat in ("vtex", "shopify", "magento"):
            return "A"

        # Nivel B — e-commerce parcial
        if plat in ("tiendanube", "mercadoshops", "woocommerce", "prestashop"):
            return "B"

        # Inferir por URL / título
        titulo_lower = (emp.titulo + emp.descripcion).lower()
        if any(w in titulo_lower for w in ["carrito", "comprar ahora", "agregar al carrito",
                                             "checkout", "pagar", "tienda"]):
            return "B"
        if any(w in titulo_lower for w in ["catálogo", "catalogo", "lista de precios",
                                             "productos", "distribuidor"]):
            return "C"

        # Por defecto para sitios web sin e-commerce claro
        return "C"

    def _es_url_candidata(self, url: str) -> bool:
        """Filtra URLs que no son relevantes para el estudio."""
        url_lower = url.lower()
        # Excluir resultados no comerciales o fuera del mercado objetivo
        excluir = [
            "wikipedia", "youtube", "facebook.com/video",
            "linkedin.com", "twitter.com", "instagram.com",
            ".gov.ar", ".edu.ar", "mercadolibre.com.ar/p/",
        ]
        return not any(e in url_lower for e in excluir)
