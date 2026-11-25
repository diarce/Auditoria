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
<body><nav class="breadcrumb"></nav><h1>Yerba mate 1 kg</h1><p>Precio por bulto x 10 unidades. Descuento por cantidad a partir de 5 cajas.</p><button class="add-to-cart">Agregar al carrito</button></body></html>"""
REG = '<html><body><form><label>CUIT</label><input name="cuit"><select name="tipo"><option>Mayorista</option><option>Minorista</option></select></form></body></html>'
ENV = "<html><body>Envíos a domicilio en Posadas. Pagos por transferencia.</body></html>"
MINORISTA = "<html><body><h1>Regalería</h1><p>Venta de souvenirs</p></body></html>"


def servidor(rutas, robots="User-agent: *\nDisallow: /privado/\n"):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/robots.txt":
                body, code = robots, 200
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

    cands = [c("Av. X, Posadas, Misiones", u(ok), "Mayorista"), c("Posadas", u(nogo)), c("Posadas", u(minor)),
             c("Oberá, Misiones", "https://x.com"), c("Posadas", "https://facebook.com/tienda")]
    r = ejecutar(cfg, candidatos=cands, log=lambda *_: None)
    etapas = [x["etapa_excluyente"] for x in r["registros"]]
    assert etapas == ["", "E4", "E6", "E1", "E3"], etapas
    a = r["aud"]["Sitio Auditado 1"]
    esperado = {"D1.1": 3, "D1.2": 3, "D1.3": 3, "D1.4": 3, "D1.5": 3, "D2.1": 3, "D2.2": 3, "D2.3": 3, "D3.1": 3, "D3.2": 3,
                "D3.4": 3, "D3.5": 3, "D4.1": 3, "D4.2": 3, "D5.2": 3, "D5.3": 3, "D6.2": 3, "D6.3": 3, "D7.3": 3, "D8.2": 3, "D8.1": 3}
    malos = {k: (a[k][0], a[k][1]) for k, v in esperado.items() if a[k][0] != v}
    assert not malos, malos
    assert a["D8.3"][0] == 1  # servidor de prueba es HTTP
    assert len(a) == 32
    print("puntajes:", {k: v[0] for k, v in a.items()})
    ruta = os.path.join(cfg.DIR_SALIDA, "manual_plantilla.csv")
    txt = open(ruta, encoding="utf-8").read().replace("D4.3,,", "D4.3,3,")
    open(ruta, "w", encoding="utf-8").write(txt)
    aplicar_manual(cfg, r, ruta)
    assert r["aud"]["Sitio Auditado 1"]["D4.3"][0] == 3
    assert os.path.getsize(os.path.join(cfg.DIR_SALIDA, "informe_auditoria.html")) > 5000
    print("salida:", cfg.DIR_SALIDA, sorted(os.listdir(cfg.DIR_SALIDA)))
    return cfg.DIR_SALIDA


if __name__ == "__main__":
    test_pipeline()
