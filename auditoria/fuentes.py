"""Fuentes de candidatos.

* ``buscar_maps``: Google Maps con navegador automatizado (Playwright). ADVERTENCIA: los términos de
  servicio de Google restringen la extracción automatizada. El módulo aplica el mismo protocolo que
  el resto del estudio: consulta robots.txt de la ruta ANTES de navegar y se detiene
  (``FuenteBloqueada``) si no está permitido. No intenta eludir ningún bloqueo.
  Los selectores CSS de Maps cambian sin aviso: si devuelve 0 fichas, hay que revisarlos.
* ``leer_csv``: respaldo con una lista propia (columna ``web``; opcionales ``direccion``,
  ``categoria``). No requiere ninguna plataforma externa.
"""
import csv
import random
import time
import urllib.parse as up
from concurrent.futures import ThreadPoolExecutor

from .config import TOKEN_UA


class FuenteBloqueada(Exception):
    pass


def _url_busqueda(q):
    return f"https://www.google.com/maps/search/{up.quote(q)}?hl=es-419&gl=ar"


def verificar_permiso_maps(etica, consultas):
    sondas = [_url_busqueda(q) for q in consultas[:1]] + ["https://www.google.com/maps/place/sonda"]
    bloqueadas = [u for u in sondas if not etica.permitido(u)]
    if bloqueadas:
        raise FuenteBloqueada(
            "robots.txt de Google no permite (o no se pudo leer) la ruta: " + "; ".join(bloqueadas)
            + ". El protocolo ético impide continuar con esta fuente.")


def buscar_maps(etica, cfg, consultas=None, log=print):
    consultas = consultas or cfg.CONSULTAS
    verificar_permiso_maps(etica, consultas)
    # Playwright sync no corre dentro del loop de asyncio de Jupyter/Colab: se ejecuta en un hilo aparte.
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(_scrape, cfg, consultas, log).result()


def _scrape(cfg, consultas, log):
    from playwright.sync_api import sync_playwright
    out, vistos = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua = browser.new_page().evaluate("navigator.userAgent") + f" {TOKEN_UA} ({cfg.CONTACTO})"
        ctx = browser.new_context(user_agent=ua, locale="es-AR")
        page = ctx.new_page()
        for q in consultas:
            log(f"[maps] consulta: {q}")
            try:
                page.goto(_url_busqueda(q), wait_until="domcontentloaded", timeout=30000)
                _consentimiento(page)
                page.wait_for_selector('div[role="feed"]', timeout=15000)
            except Exception as e:
                log(f"[maps]   sin lista de resultados ({type(e).__name__})")
                continue
            feed, previo = page.locator('div[role="feed"]'), -1
            for i in range(40):
                n = page.locator("a.hfpxzc").count()
                if n >= cfg.MAX_POR_CONSULTA or (n == previo and i > 2):
                    break
                previo = n
                feed.evaluate("e => e.scrollBy(0, e.scrollHeight)")
                time.sleep(random.uniform(1.5, 3.0))
            enlaces = [a.get_attribute("href") for a in page.locator("a.hfpxzc").all()[:cfg.MAX_POR_CONSULTA]]
            log(f"[maps]   fichas encontradas: {len(enlaces)}")
            for href in enlaces:
                if not href or href in vistos:
                    continue
                vistos.add(href)
                time.sleep(random.uniform(*cfg.DEMORA_MAPS))
                try:
                    out.append(_ficha(page, href, q))
                except Exception as e:
                    log(f"[maps]   ficha omitida ({type(e).__name__})")
        browser.close()
    return out


def _consentimiento(page):
    for t in ("Rechazar todo", "Aceptar todo", "Reject all", "Accept all"):
        b = page.get_by_role("button", name=t)
        if b.count():
            b.first.click()
            return


def _ficha(page, href, consulta):
    page.goto(href, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("h1", timeout=10000)

    def attr(sel, a):
        loc = page.locator(sel)
        return loc.first.get_attribute(a) if loc.count() else None

    dire = attr('button[data-item-id="address"]', "aria-label") or ""
    if ":" in dire:
        dire = dire.split(":", 1)[1].strip()
    cat = page.locator('button[jsaction*="category"]')
    cuerpo = page.locator("body").inner_text()[:6000].lower()
    return {
        "nombre": page.locator("h1").first.inner_text().strip(),
        "direccion": dire,
        "categoria": cat.first.inner_text().strip() if cat.count() else "",
        "web": attr('a[data-item-id="authority"]', "href"),
        "cerrado_permanente": any(t in cuerpo for t in ("cerrado permanentemente", "cerrado definitivamente", "permanently closed")),
        "fuente": "maps",
        "consulta": consulta,
    }


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    return [{
        "nombre": "", "direccion": (r.get("direccion") or "").strip(), "categoria": (r.get("categoria") or "").strip(),
        "web": (r.get("web") or "").strip() or None, "cerrado_permanente": False, "fuente": "csv", "consulta": "",
    } for r in filas]
