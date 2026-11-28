"""Auditor de los 32 indicadores del Anexo C.

Escala: 3 cumplimiento pleno, 2 parcial, 1 incumplimiento, 0 no aplicable / no verificable.
Los 7 indicadores de verificación manual se registran en 0 ("pendiente") hasta que se cargue el
protocolo manual (ver pipeline.aplicar_manual). Cada puntaje guarda una breve evidencia de la
regla que lo originó (trazabilidad); no se almacena contenido de las páginas.

IMPORTANTE: las reglas son heurísticas sobre HTML/texto público. Tienen falsos negativos
(p. ej. sitios que cargan contenido con JavaScript). Los umbrales intermedios (puntaje 2) son
decisiones operativas del autor, no valores de la literatura de referencia.
"""
import random
import re
import statistics
import string
import urllib.parse as up

from .config import INDICADORES, indicadores_activos
from .sitio import es_categoria, tipos_jsonld, norm


def _rx(p):
    return re.compile(p)


def _fuente_elementos(soup, patron, attrs=("class", "id", "aria-label")):
    rx = re.compile(patron, re.I)
    for el in soup.find_all(True):
        for a in attrs:
            v = el.get(a)
            v = " ".join(v) if isinstance(v, list) else (v or "")
            if v and rx.search(v):
                return True
    return False


def _migas(prod):
    """Migas de pan de ubicación (Franco Ruiz, 2017, Tabla 3.3): sendero con enlaces a niveles superiores.
    3 = sendero con >=2 enlaces o BreadcrumbList con >=2 niveles; 2 = elemento presente sin enlaces a niveles
    superiores (no cumple la función de ubicación jerárquica); 1 = no detectado. No distingue ubicación/atributo
    (Instone, 2002) y no puede observar las de 'ruta' (dependen del historial del usuario)."""
    for o in prod.jsonld:
        if "BreadcrumbList" in str(o.get("@type", "")):
            n = len(o.get("itemListElement") or [])
            return (3, f"BreadcrumbList con {n} niveles") if n >= 2 else (2, "BreadcrumbList con menos de 2 niveles")
    rx = re.compile(r"breadcrumb|migas|bread-crumb|ruta-de-navegacion", re.I)
    cont = []
    for el in prod.soup.find_all(True):
        for at in ("class", "id", "aria-label"):
            v = el.get(at)
            v = " ".join(v) if isinstance(v, list) else (v or "")
            if v and rx.search(v):
                cont.append(el)
                break
    if not cont:
        return 1, "migas de pan no detectadas en ficha"
    mx = max(len(c.find_all("a", href=True)) for c in cont)
    return (3, f"sendero de migas con {mx} enlaces") if mx >= 2 else (2, "elemento de migas sin enlaces a niveles superiores")


def auditar(sitio, etica, cfg):
    """Devuelve dict id -> (puntaje, evidencia)."""
    R = {i[0]: (0, "pendiente de verificación manual") for i in INDICADORES if i[3] == "M" and cfg.INCLUIR_MANUALES}
    home, cat, prod, reg = sitio.home, sitio.cat, sitio.prod, None
    sitio.descubrir() if not sitio.enlaces_home else None
    sitio.cargar_listado_y_producto()
    sitio.cargar_registro()
    sitio.cargar_info()
    reg = sitio.registro
    soup = home.soup
    texto_all = sitio.texto_total()
    nov = "no verificable: no se localizó"

    # ---------------- D1 ----------------
    enl_nav = {a["href"] for el in soup.select("nav, header") for a in el.find_all("a", href=True)}
    n = len(enl_nav)
    R["D1.1"] = (3 if n >= 5 else 2 if n >= 2 else 1, f"{n} enlaces en nav/header")

    busc = bool(soup.select('input[type=search], form[role=search], input[name=q], input[name=s], '
                            'input[name=search], input[name=buscar], input[name=busqueda]'))
    if not busc:
        busc = any(re.search(r"buscar|search", norm(i.get("placeholder", ""))) for i in soup.find_all("input"))
    if not busc:
        busc = any(re.search(r"buscar|search|\?s=", norm(f.get("action", ""))) for f in soup.find_all("form"))
    R["D1.2"] = (3 if busc else 1, "campo de búsqueda " + ("detectado" if busc else "no detectado"))

    ncat = sum(1 for u, _ in sitio.enlaces_home if es_categoria(up.urlsplit(u).path))
    ncat = max(ncat, sum(1 for _, t in sitio.enlaces_home if re.search(r"categoria", t)))
    R["D1.3"] = (3 if ncat >= 5 else 2 if ncat >= 2 else 1, f"{ncat} enlaces de categoría en inicio")

    if prod and prod.ok:
        R["D1.4"] = _migas(prod)
    else:
        R["D1.4"] = (0, f"{nov} una ficha de producto")

    listado = cat if (cat and cat.ok) else None
    if listado:
        s = listado.soup
        orden = bool(s.find("select", attrs={"name": re.compile(r"orden|sort|order", re.I)})) \
            or _fuente_elementos(s, r"orderby|sort-by|ordenar|sortby") \
            or any(re.search(r"(orderby|sort|order|orden)=", h["href"]) for h in s.find_all("a", href=True))
        filtros = _fuente_elementos(s, r"filter|filtro|facet")
        R["D1.5"] = (3 if orden else 2 if filtros else 1,
                     "ordenamiento detectado" if orden else "solo filtros" if filtros else "sin ordenamiento ni filtros")
    else:
        R["D1.5"] = (0, f"{nov} un listado de productos")

    # ---------------- D2 ----------------
    if sitio.url_registro:
        R["D2.1"] = (3, "enlace de registro detectado")
    elif sitio.hay_login:
        R["D2.1"] = (2, "solo enlace de inicio de sesión")
    else:
        R["D2.1"] = (1, "sin enlace de registro ni de sesión")

    if reg and reg.ok and reg.soup.find("input"):
        campos = " ".join(norm(" ".join(str(i.get(k, "")) for k in ("name", "id", "placeholder", "aria-label")))
                          for i in reg.soup.find_all("input"))
        campos += " " + " ".join(norm(l.get_text(" ")) for l in reg.soup.find_all("label"))
        if re.search(r"cuit|cuil", campos):
            R["D2.2"] = (3, "campo CUIT/CUIL detectado")
        elif re.search(r"dni|documento|identificacion|condicion.?iva|razon.?social", campos):
            R["D2.2"] = (2, "identificación alternativa (DNI/razón social/condición IVA)")
        else:
            R["D2.2"] = (1, "sin campo de identificación fiscal")
        grupo = re.compile(r"mayorista|minorista|particular|revendedor|consumidor final|tipo de (cuenta|cliente|usuario)")
        opciones = [norm(x.get_text(" ")) for x in reg.soup.select("select")] + [norm(x.get_text(" ")) for x in reg.soup.find_all("label")]
        tiene_sel = bool(reg.soup.select("select, input[type=radio]")) and any(grupo.search(x) for x in opciones)
        both = "mayorista" in reg.texto and "minorista" in reg.texto
        R["D2.3"] = (3 if tiene_sel else 2 if both else 1,
                     "selector de tipo de cuenta" if tiene_sel else "menciona ambos tipos" if both else "sin diferenciación")
    else:
        R["D2.2"] = (0, f"{nov} un formulario público de registro")
        R["D2.3"] = (0, f"{nov} un formulario público de registro")

    # ---------------- D3 (ficha de producto) ----------------
    if prod and prod.ok:
        t, s = prod.texto, prod.soup
        tipos = tipos_jsonld(prod.jsonld)
        ofertas = [o for o in prod.jsonld if "Offer" in str(o.get("@type", "")) or "offers" in o]
        meta_precio = s.select_one('meta[property="product:price:amount"], [itemprop=price]')
        if ofertas or meta_precio:
            R["D3.1"] = (3, "precio en datos estructurados (schema.org/meta)")
        elif re.search(r"\$\s?\d", t):
            R["D3.1"] = (2, "precio en texto de la página")
        elif re.search(r"inicia sesion para ver|registrate para ver|ver precio|consultar precio|precios? para clientes", t):
            R["D3.1"] = (1, "precio oculto tras registro/consulta")
        else:
            R["D3.1"] = (1, "precio no detectado")

        if re.search(r"precio (por )?(bulto|caja|pack|display)|por (bulto|caja|pack)|unidades por (bulto|caja|pack)", t):
            R["D3.2"] = (3, "precio/presentación por bulto, caja o pack explícito")
        elif re.search(r"\b(bulto|caja|pack|display)\b|\bx\s?\d+\s?(un|unid|u)\b", t):
            R["D3.2"] = (2, "menciona presentación por bulto/caja/pack sin precio explícito")
        else:
            R["D3.2"] = (1, "sin referencia a bulto/caja/pack")

        um = re.compile(r"\b\d+([.,]\d+)?\s?(kg|kgs|gr|grs|g|ml|cc|lt|lts|l|litros?|gramos?|kilos?|un|unid|unidades)\b")
        titulo = norm(" ".join(x.get_text(" ") for x in s.find_all(["h1", "title"])))
        if um.search(titulo):
            R["D3.3"] = (3, "unidad de medida en título/encabezado")
        elif um.search(t):
            R["D3.3"] = (2, "unidad de medida solo en el cuerpo")
        else:
            R["D3.3"] = (1, "sin unidad de medida detectada")

        if any("availability" in str(o) for o in prod.jsonld) or s.select_one("[itemprop=availability]"):
            R["D3.4"] = (3, "disponibilidad en datos estructurados")
        elif re.search(r"sin stock|agotado|en stock|stock disponible|disponible|hay stock|unidades disponibles", t):
            R["D3.4"] = (2, "disponibilidad en texto")
        else:
            R["D3.4"] = (1, "sin indicador de stock")

        tcat = (cat.texto if cat and cat.ok else "")
        tv = t + " " + tcat
        if re.search(r"descuentos? por (cantidad|volumen|mayor)|precios? por (cantidad|volumen)|escalas? de precios?", tv):
            R["D3.5"] = (3, "descuento por cantidad/volumen explícito")
        elif re.search(r"(a partir de|desde) \d+ (unidades|u\b|bultos|cajas)|comprando \d+|llevando \d+", tv):
            R["D3.5"] = (2, "escala de precio sugerida por cantidad")
        else:
            R["D3.5"] = (1, "sin descuento por volumen detectado")
    else:
        for k in ("D3.1", "D3.2", "D3.3", "D3.4", "D3.5"):
            R[k] = (0, f"{nov} una ficha de producto")

    # ---------------- D4 ----------------
    fuerte = re.compile(r"agregar al carrito|anadir al carrito|add to cart|sumar al carrito|agregar al pedido|comprar ahora")
    debil = re.compile(r"^(comprar|agregar|anadir|sumar|pedir)\b")      # solo en <button>/<input>, texto corto

    def hay_boton(p):
        if not (p and p.ok):
            return False
        for el in p.soup.find_all(["button", "input", "a"]):
            txt = norm(el.get_text(" ", strip=True) + " " + str(el.get("value", ""))).strip()
            if fuerte.search(txt):
                return True
            if el.name in ("button", "input") and len(txt) < 25 and debil.search(txt):
                return True
        return _fuente_elementos(p.soup, r"add[-_ ]?to[-_ ]?cart|addtocart|btn-comprar|agregar-carrito")
    if prod and prod.ok:
        b = hay_boton(prod)
        R["D4.1"] = (3 if b else 1, "botón de compra " + ("detectado" if b else "no detectado") + " en ficha")
    elif hay_boton(cat) or hay_boton(home):
        R["D4.1"] = (3, "botón de compra detectado en listado/inicio (sin ficha localizada)")
    else:
        R["D4.1"] = (0, f"{nov} una ficha de producto")

    minimo = re.compile(r"(compra|pedido|cantidad|monto|importe|venta)s? minim[oa]s?|minimo de (compra|pedido|venta|unidades)|compra minima|pedido minimo")
    qty_min = False
    if prod and prod.ok:
        for i in prod.soup.select("input[type=number]"):
            try:
                qty_min = qty_min or float(i.get("min", 0)) >= 2
            except ValueError:
                pass
    if minimo.search(texto_all) or qty_min:
        R["D4.2"] = (3, "cantidad/monto mínimo comunicado")
    else:
        R["D4.2"] = (1, "sin cantidad mínima comunicada")

    # ---------------- D5 ----------------
    if re.search(r"envios? a domicilio|entregas? a domicilio|delivery|reparto|despacho a domicilio|enviamos a|llevamos a", texto_all):
        R["D5.2"] = (3, "envío a domicilio explícito")
    elif re.search(r"\benvios?\b|\bentregas?\b", texto_all):
        R["D5.2"] = (2, "menciona envíos/entregas sin precisar domicilio")
    else:
        R["D5.2"] = (1, "sin información de envío")
    if re.search(r"retiro en (sucursal|local|tienda|deposito|negocio)|retirar en|retiro por|pasar a retirar|pick ?up|retira(s)? (en|por)", texto_all):
        R["D5.3"] = (3, "retiro en sucursal explícito")
    else:
        R["D5.3"] = (1, "sin información de retiro")

    # ---------------- D6 ----------------
    medios = {"visa": r"\bvisa\b", "mastercard": r"master ?card", "amex": r"american express|amex", "cabal": r"\bcabal\b",
              "naranja": r"tarjeta naranja|\bnaranja x\b", "mercadopago": r"mercado ?pago", "transferencia": r"transferencia|\bcbu\b",
              "efectivo": r"efectivo", "debito": r"debito", "credito": r"credito|tarjeta", "modo": r"\bmodo\b.{0,30}(pago|qr|billetera)|(pago|qr|billetera).{0,30}\bmodo\b",
              "cuenta_dni": r"cuenta dni", "cheque": r"cheque"}
    hallados = [k for k, p in medios.items() if re.search(p, texto_all)]
    R["D6.1"] = (3 if len(hallados) >= 3 else 2 if hallados else 1, f"{len(hallados)} medios de pago mencionados")
    R["D6.2"] = ((3, "transferencia/CBU mencionada") if re.search(r"transferencia|\bcbu\b", texto_all) else (1, "sin transferencia"))
    R["D6.3"] = ((3, "factura A mencionada") if re.search(r"factura\s+(tipo\s+)?a\b|facturacion a\b|comprobante a\b", texto_all)
                 else (1, "sin mención de factura A"))

    # ---------------- D7 ----------------
    ruta = "/pagina-inexistente-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    r404 = etica.get(sitio.base + ruta, seguir=False)
    if r404.status is None:
        R["D7.3"] = (0, "no verificable: " + (r404.error or "sin respuesta"))
    elif r404.status == 404:
        from bs4 import BeautifulSoup
        enl = len(BeautifulSoup(r404.texto, "lxml").find_all("a", href=True)) if r404.texto else 0
        R["D7.3"] = (3 if enl >= 3 else 2, f"404 correcto con {enl} enlaces de navegación")
    else:
        R["D7.3"] = (1, f"ruta inexistente responde HTTP {r404.status} (no 404)")

    # ---------------- D8 ----------------
    tiempos = [home.resp.elapsed]
    for _ in range(max(0, cfg.REPETICIONES_TIEMPO - 1)):
        r = etica.get(sitio.base + "/")
        if r.ok:
            tiempos.append(r.elapsed)
    med = statistics.median(tiempos)
    R["D8.1"] = ((3 if med < cfg.UMBRAL_TIEMPO_S else 1),
                 f"mediana {med:.2f}s de {len(tiempos)} mediciones (umbral {cfg.UMBRAL_TIEMPO_S}s; medido desde el entorno de ejecución)")

    R["D8.2"] = ((3, "meta viewport presente") if soup.find("meta", attrs={"name": re.compile("viewport", re.I)}) else (1, "sin meta viewport"))

    https_final = home.resp.url.startswith("https://")
    if https_final and sitio.base.startswith("https://"):
        rh = etica.get("http://" + up.urlsplit(sitio.base).netloc + "/", seguir=False)
        redir = rh.status in (301, 302, 307, 308) and rh.ruta and rh.ruta[0].startswith("https://")
        R["D8.3"] = ((3, "HTTPS con redirección desde HTTP") if redir else (2, "HTTPS sin redirección automática desde HTTP"))
    else:
        R["D8.3"] = (1, "el sitio no se sirve por HTTPS")

    imgs = list(soup.find_all("img")) + (list(prod.soup.find_all("img")) if prod and prod.ok else [])
    if imgs:
        con_alt = sum(1 for i in imgs if (i.get("alt") or "").strip())
        pr = con_alt / len(imgs)
        R["D8.4"] = (3 if pr >= 0.9 else 2 if pr >= 0.5 else 1, f"{con_alt}/{len(imgs)} imágenes con alt")
    else:
        R["D8.4"] = (0, "sin imágenes en las páginas relevadas")

    activos = {i[0] for i in indicadores_activos(cfg)}
    R = {k: v for k, v in R.items() if k in activos}
    faltan = activos - set(R)
    assert not faltan, faltan
    return R


def puntaje_dimension(puntajes):
    """Ecuación B.1: promedio de los puntajes > 0 (excluye no aplicables/no verificables)."""
    v = [p for p in puntajes if p > 0]
    return sum(v) / len(v) if v else None
