"""Filtro de elegibilidad automático (sección 7.3 + protocolo ético), etapas E1–E9.

Cada candidato recorre las etapas en orden y se detiene en la primera que no cumple.
Las exclusiones NO se descartan: se contabilizan por etapa y motivo, porque son un hallazgo
para el capítulo de resultados (plataformas no observables).

Estados por etapa: 'cumple' | 'no_cumple' | 'no_verificable' (no excluye; queda registrado).
Los nombres y direcciones del origen se usan solo aquí y NO se conservan en la salida.
"""
import hashlib
import re
import urllib.parse as up

from .sitio import Sitio, es_dominio_propio, normalizar_base, norm, es_producto, es_categoria, tipos_jsonld

ETAPAS = {
    "E1": "Localización en Posadas", "E2": "Establecimiento activo", "E3": "Sitio web propio",
    "E4": "robots.txt permite la página de inicio", "E5": "Sitio accesible (HTTP 200, TLS válido)",
    "E6": "Modalidad mayorista o mixta", "E7": "Rubro de consumo masivo",
    "E8": "Canal de venta en línea público observable", "E9": "robots.txt permite listado y ficha de producto",
}

RE_MAYORISTA_CAT = re.compile(r"mayorist|distribuidor|wholesale|por mayor", re.I)
RE_MAYORISTA_TXT = re.compile(r"mayorist|por mayor|venta mayor|distribuidora|distribuidor|bulto|cantidad(es)? minima|venta por cajas")
RUBROS = {
    "alimentos_bebidas": re.compile(r"almacen|alimento|bebida|gaseosa|cerveza|vino|fiambre|golosina|snack|yerba|arroz|fideo|aceite|harina|galletita|lacteo|congelado|azucar|conserva"),
    "limpieza_hogar": re.compile(r"limpieza|detergente|lavandina|jabon|suavizante|desinfectante|papel higienico|esponja"),
    "higiene_personal": re.compile(r"shampoo|champu|desodorante|higiene|perfumeria|cuidado personal|panal|toallita|dental|cepillo"),
}
SENIALES_ONLINE = [
    (r"agregar al carrito|anadir al carrito|add to cart|sumar al carrito", "texto_agregar_carrito"),
    (r"/(carrito|cart|checkout|finalizar-compra)(/|\"|'|\?|$)", "enlace_carrito_checkout"),
    (r"tiendanube|nuvemshop|shopify|woocommerce|vtex|magento|prestashop|mercadoshops", "plataforma_ecommerce"),
]


def _e1(direccion):
    d = norm(direccion)
    if not d:
        return "no_verificable", "sin_direccion"
    if "posadas" in d or "itaembe" in d:
        return "cumple", ""
    return "no_cumple", "direccion_fuera_de_posadas"


def cand_id(cfg, c):
    clave = (c.get("web") or "") or (c.get("nombre", "") + c.get("direccion", ""))
    return hashlib.sha256((cfg.SALT_ANONIMIZACION + norm(clave)).encode()).hexdigest()[:10]


def evaluar(c, etica, cfg):
    """Devuelve (registro, Sitio|None). El registro no contiene nombre ni dirección."""
    reg = {"cand_id": cand_id(cfg, c), "dominio": None, "fuente": c.get("fuente"), "etapa_excluyente": "",
           "motivo": "", "nivel_mayorista": "", "rubros": "", "senales_online": "", "no_verificables": ""}
    nover = []

    def cerrar(etapa, motivo):
        reg["etapa_excluyente"], reg["motivo"] = etapa, motivo
        reg["no_verificables"] = ",".join(nover)
        return reg, None

    st, mot = _e1(c.get("direccion", ""))
    if st == "no_cumple":
        return cerrar("E1", mot)
    if st == "no_verificable":
        nover.append("E1")
    if c.get("cerrado_permanente"):
        return cerrar("E2", "cerrado_permanentemente")

    base = normalizar_base(c.get("web"))
    if not base or not es_dominio_propio(base):
        return cerrar("E3", "sin_sitio_propio" if not base else "red_social_o_marketplace")
    reg["dominio"] = up.urlsplit(base).netloc

    estado = etica.estado_robots(base)
    if estado == "ilegible":
        return cerrar("E4", "robots_txt_ilegible")
    if not etica.permitido(base + "/"):
        return cerrar("E4", "robots_bloquea_inicio")

    sitio = Sitio(base, etica, cfg)
    home = sitio.cargar_home()
    if not home.ok:
        return cerrar("E5", home.resp.error or f"http_{home.resp.status}")

    # E6 mayorista: acreditada (categoría en el origen) o declarada (texto del sitio)
    if RE_MAYORISTA_CAT.search(c.get("categoria", "")):
        reg["nivel_mayorista"] = "acreditada"
    elif RE_MAYORISTA_TXT.search(home.texto):
        reg["nivel_mayorista"] = "declarada"
    if not reg["nivel_mayorista"]:
        return cerrar("E6", "sin_evidencia_mayorista")
    if reg["nivel_mayorista"] == "declarada" and not cfg.ACEPTAR_MAYORISTA_DECLARADA:
        return cerrar("E6", "mayorista_solo_declarada")

    # E7 rubro
    rubros = [k for k, rx in RUBROS.items() if rx.search(home.texto)]
    reg["rubros"] = ",".join(rubros)
    if len(rubros) < cfg.MIN_RUBROS_CONSUMO_MASIVO:
        return cerrar("E7", "rubro_no_consumo_masivo")

    # E8 canal online
    html_norm = norm(home.resp.texto)
    senales = [nombre for rx, nombre in SENIALES_ONLINE if re.search(rx, html_norm)]
    if "Product" in tipos_jsonld(home.jsonld) or "Offer" in tipos_jsonld(home.jsonld):
        senales.append("jsonld_producto")
    reg["senales_online"] = ",".join(senales)
    if not senales:
        return cerrar("E8", "sin_canal_online_observable")

    # E9 robots sobre listado y ficha
    sitio.descubrir()
    candidatos = [u for u in (sitio.url_cat, sitio.url_prod) if u]
    if candidatos and not any(etica.permitido(u) for u in candidatos):
        return cerrar("E9", "robots_bloquea_listado_y_producto")
    if not candidatos:
        nover.append("E9")
    sitio.cargar_listado_y_producto()
    reg["no_verificables"] = ",".join(nover)
    return reg, sitio


def filtrar(candidatos, etica, cfg, log=print):
    vistos, registros, sitios = set(), [], {}
    for i, c in enumerate(candidatos, 1):
        base = normalizar_base(c.get("web"))
        clave = up.urlsplit(base).netloc.removeprefix("www.") if base else None
        if clave and clave in vistos:
            continue
        if clave:
            vistos.add(clave)
        reg, sitio = evaluar(c, etica, cfg)
        registros.append(reg)
        if sitio:
            sitios[reg["cand_id"]] = sitio
        log(f"[filtro {i}/{len(candidatos)}] {'OBSERVABLE' if sitio else 'excluido en ' + reg['etapa_excluyente'] + ': ' + reg['motivo']}")
    return registros, sitios
