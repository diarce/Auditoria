"""Prueba extremo a extremo contra servidores HTTP locales (sin tocar Internet).
Ejecutar:  python tests/test_local.py   (o pytest -q tests)
"""
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auditoria import Config  # noqa: E402
from auditoria.pipeline import aplicar_manual, ejecutar  # noqa: E402

NAV = '<header><nav>' + ''.join(f'<a href="/categoria/c{i}">Cat {i}</a>' for i in range(6)) + '</nav></header>'
HOME = f"""<html><head><meta name="viewport" content="width=device-width"><title>Distribuidora Mayorista</title></head><body>{NAV}
<form role="search"><input type="search" name="q"></form>
<h1>Mayorista de almacén, bebidas y limpieza</h1><p>Venta por bulto. Cantidad mínima de compra: 3 cajas. Envío a domicilio. Retiro en sucursal.
Aceptamos Visa, Mastercard, Mercado Pago y transferencia bancaria. Factura A.</p>
<a href="/producto/yerba-1kg">Yerba 1kg</a><a href="/registro">Registrarse</a><a href="/envios">Envíos</a><button>Agregar al carrito</button>
<img src="a.jpg" alt="logo"><img src="b.jpg" alt="x"></body></html>"""
CAT = '<html><body><select name="orderby"><option>Ordenar</option></select><div class="filtros"></div><a href="/producto/yerba-1kg">Yerba</a></body></html>'
PROD = """<html><head><title>Yerba mate 1 kg</title><script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer","price":"1500","availability":"InStock"}}</script></head>
<body><nav class="breadcrumb"><a href="/">Inicio</a> &gt; <a href="/categoria/c0">Almacén</a> &gt; Yerba</nav><h1>Yerba mate 1 kg</h1><p>Precio por bulto x 10 unidades. Descuento por cantidad a partir de 5 cajas.</p><button class="add-to-cart">Agregar al carrito</button></body></html>"""
REG = '<html><body><form><label>CUIT</label><input name="cuit"><select name="tipo"><option>Mayorista</option><option>Minorista</option></select></form></body></html>'
ENV = "<html><body>Envíos a domicilio en Posadas. Pagos por transferencia.</body></html>"
MINORISTA = "<html><body><h1>Regalería</h1><p>Venta de souvenirs</p></body></html>"


def servidor(rutas, robots="User-agent: *\nDisallow: /privado/\n", robots_status=200):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/robots.txt":
                body, code = robots, robots_status
            elif isinstance(rutas.get(self.path), str) and rutas[self.path].startswith("REDIR:"):
                self.send_response(302); self.send_header("Location", rutas[self.path][6:]); self.end_headers(); return
            elif self.path in rutas:
                body, code = rutas[self.path], 200
            else:
                body, code = "<html><body><a href='/'>a</a><a href='/b'>b</a><a href='/c'>c</a></body></html>", 404
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def test_pipeline():
    ok = servidor({"/": HOME, "/categoria/c0": CAT, "/producto/yerba-1kg": PROD, "/registro": REG, "/envios": ENV})
    nogo = servidor({"/": HOME}, robots="User-agent: *\nDisallow: /\n")
    minor = servidor({"/": MINORISTA})
    u = lambda s: f"http://127.0.0.1:{s.server_port}"  # noqa: E731
    cfg = Config(CONTACTO="test@x.org", DIR_SALIDA=tempfile.mkdtemp(), DEMORA_MIN=0, JITTER_MAX=0, SALT_ANONIMIZACION="t")

    def c(direccion, web, cat=""):
        return {"nombre": "", "direccion": direccion, "categoria": cat, "web": web, "cerrado_permanente": False, "fuente": "csv"}

    cands = [c("Av. X, Posadas, Misiones", u(ok), "Mayorista"), c("Posadas, Misiones", u(nogo)), c("Posadas, Misiones", u(minor)),
             c("Oberá, Misiones", "https://x.com"), c("Posadas, Misiones", "https://facebook.com/tienda")]
    r = ejecutar(cfg, candidatos=cands, log=lambda *_: None)
    etapas = [x["etapa_excluyente"] for x in r["registros"]]
    assert etapas == ["", "E4", "E6", "E1", "E3"], etapas
    a = r["aud"]["Sitio Auditado 1"]
    esperado = {"D1.1": 3, "D1.2": 3, "D1.3": 3, "D1.4": 3, "D1.5": 3, "D2.1": 3, "D2.2": 3, "D2.3": 3, "D3.1": 3, "D3.2": 3,
                "D3.4": 3, "D3.5": 3, "D4.1": 3, "D4.2": 3, "D5.2": 3, "D5.3": 3, "D6.2": 3, "D6.3": 3, "D7.3": 3, "D8.2": 3, "D8.1": 3}
    malos = {k: (a[k][0], a[k][1]) for k, v in esperado.items() if a[k][0] != v}
    assert not malos, malos
    assert a["D8.3"][0] == 1  # servidor de prueba es HTTP
    assert len(a) == 25 and not any(k in a for k in ("D2.4", "D4.3", "D4.4", "D5.1", "D5.4", "D7.1", "D7.2"))
    assert not os.path.exists(os.path.join(cfg.DIR_SALIDA, "manual_plantilla.csv"))
    h = open(os.path.join(cfg.DIR_SALIDA, "informe_auditoria.html"), encoding="utf-8").read()
    assert "pendiente de verificación" not in h.lower() and "Indicadores evaluados (25)" in h and "duplicados" in h
    try:
        aplicar_manual(cfg, r, "x.csv"); raise SystemExit("debía fallar")
    except ValueError:
        pass
    print("automatizada OK:", len(a), "indicadores")
    # variante opcional con manuales
    cfg2 = Config(CONTACTO="test@x.org", DIR_SALIDA=tempfile.mkdtemp(), DEMORA_MIN=0, JITTER_MAX=0, SALT_ANONIMIZACION="t", INCLUIR_MANUALES=True)
    r2 = ejecutar(cfg2, candidatos=cands[:1], log=lambda *_: None)
    assert len(r2["aud"]["Sitio Auditado 1"]) == 32
    ruta = os.path.join(cfg2.DIR_SALIDA, "manual_plantilla.csv")
    contenido = open(ruta, encoding="utf-8").read().replace("D4.3,,", "D4.3,3,")
    open(ruta, "w", encoding="utf-8").write(contenido)
    aplicar_manual(cfg2, r2, ruta)
    assert r2["aud"]["Sitio Auditado 1"]["D4.3"][0] == 3
    print("variante con manuales OK")
    return cfg.DIR_SALIDA


# ---------- regresiones de los defectos corregidos ----------
NOBTN_HOME = """<html><head><meta name="viewport" content="width=device-width"></head><body><!-- woocommerce --><nav><a href="/a">a</a><a href="/b">b</a></nav>
<h1>Mayorista de almacén y bebidas</h1><a href="/producto/aceite-1l">Aceite 1 l</a><a href="/registro">Registrarse</a><a href="/carrito">Ir al carrito</a></body></html>"""
NOBTN_PROD = '<html><body><h1>Aceite 1 l</h1><a href="/como-comprar">Cómo comprar</a><p>Jugo de naranja. De modo que consulte. Precio $100</p><div class="breadcrumb">Aceite</div></body></html>'
REG2 = '<html><body><form><label>Empresa</label><input name="email"><select name="provincia"><option>Misiones</option><option>Corrientes</option></select></form></body></html>'


def test_regresiones():
    from auditoria.filtro import _e1, cand_id
    from auditoria.sitio import normalizar_base, es_dominio_propio
    cfg = Config(CONTACTO="t@x.org", DIR_SALIDA=tempfile.mkdtemp(), DEMORA_MIN=0, JITTER_MAX=0, SALT_ANONIMIZACION="t")
    # E1: calle 'Posadas' de otra ciudad no es Posadas, Misiones
    assert _e1("Posadas 1234, Recoleta, CABA")[0] == "no_cumple"
    assert _e1("Av. Corrientes 1, Posadas, Misiones")[0] == "cumple"
    assert _e1("Bolívar 100, N3300 Posadas")[0] == "cumple"
    assert _e1("Posadas")[0] == "no_verificable"
    # URL de redirección de Maps y estabilidad del identificador
    assert normalizar_base("https://www.google.com/url?q=https://tienda.com.ar/x&sa=U") == "https://tienda.com.ar"
    assert cand_id(cfg, {"web": "https://www.t.com.ar/?utm_source=gmb"}) == cand_id(cfg, {"web": "https://t.com.ar/"})
    # heurísticas: falsos positivos y migas de ubicación sin enlaces
    s1 = servidor({"/": NOBTN_HOME, "/producto/aceite-1l": NOBTN_PROD, "/registro": REG2})
    # redirección de host: A -> B
    b = servidor({"/": HOME, "/categoria/c0": CAT, "/producto/yerba-1kg": PROD})
    a = servidor({"/": f"REDIR:http://127.0.0.1:{b.server_port}/"})
    # robots: regla específica para nuestro agente y 403
    esp = servidor({"/": HOME}, robots="User-agent: AuditoriaTesisUNaM\nDisallow: /\n")
    r403 = servidor({"/": HOME}, robots_status=403)
    u = lambda s: f"http://127.0.0.1:{s.server_port}"  # noqa: E731
    c = lambda web: {"nombre": "", "direccion": "Posadas, Misiones", "categoria": "Mayorista", "web": web, "cerrado_permanente": False, "fuente": "csv"}  # noqa: E731
    r = ejecutar(cfg, candidatos=[c(u(s1)), c(u(a)), c(u(esp)), c(u(r403))], log=lambda *_: None)
    etapas = [x["etapa_excluyente"] for x in r["registros"]]
    motivos = [x["motivo"] for x in r["registros"]]
    assert etapas == ["", "", "E4", "E4"], (etapas, motivos)
    assert motivos[3] == "robots_txt_ilegible"
    aud = r["aud"]
    # alias estable por hash: localizar cada sitio por su dominio en el mapeo privado
    por_dom = {x["dominio"]: x["cand_id"] for x in r["registros"]}
    def de(srv):
        cid = [x["cand_id"] for x in r["registros"] if x["dominio"] and x["dominio"].endswith(str(srv.server_port))][0]
        return aud[r["mapa"][cid]]
    n = de(s1)
    assert n["D4.1"][0] == 1, n["D4.1"]            # 'Cómo comprar' y 'Ir al carrito' no son botón de compra
    assert n["D6.1"][0] == 1, n["D6.1"]            # 'naranja' y 'modo' genéricos no son medios de pago
    assert n["D2.3"][0] == 1, n["D2.3"]            # un select de provincia no es selector de tipo de cuenta
    assert n["D1.4"][0] == 2, n["D1.4"]            # elemento de migas sin enlaces a niveles superiores
    assert de(b)["D1.4"][0] == 3                    # con la redirección A->B se audita el host final
    print("regresiones OK")


if __name__ == "__main__":
    test_pipeline()
    test_regresiones()
