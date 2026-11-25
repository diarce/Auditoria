"""Configuración central y definición del instrumento (Anexos B y C de la tesis).

La definición de los 32 indicadores replica la Tabla C.1 del Anexo C. Al importar el
módulo se verifica que los conteos coincidan con los declarados en el texto de la tesis
(32 indicadores; 25 automáticos y 7 manuales; 18 directos, 8 parciales y 6 contextuales).
"""
from dataclasses import dataclass, field

VERSION = "0.1.0"


@dataclass
class Config:
    # --- Identificación (el protocolo exige un agente identificable con contacto) ---
    CONTACTO: str = "CONFIGURAR@ejemplo.edu.ar"
    SALT_ANONIMIZACION: str = "CAMBIAR-ESTA-SEMILLA"
    DIR_SALIDA: str = "resultados"

    # --- Protocolo ético (sección 7.4.1) ---
    DEMORA_MIN: float = 3.0          # segundos entre peticiones al mismo host
    JITTER_MAX: float = 2.0          # variación aleatoria adicional (0..JITTER_MAX)
    TIMEOUT: float = 15.0
    MAX_BYTES: int = 2_000_000       # tope de lectura por respuesta
    MAX_PETICIONES_SITIO: int = 20   # tope duro de GET por sitio (sin contar robots.txt)
    MAX_REDIRECCIONES: int = 5
    MAX_PAGINAS_INFO: int = 4
    REPETICIONES_TIEMPO: int = 3     # mediciones del tiempo de respuesta (se usa la mediana)
    UMBRAL_TIEMPO_S: float = 4.0     # Anexo B, dimensión D8

    # --- Fuente de candidatos: Google Maps (navegador) ---
    MAX_POR_CONSULTA: int = 40
    DEMORA_MAPS: tuple = (2.5, 5.0)  # rango (s) entre fichas de Maps
    CONSULTAS: list = field(default_factory=lambda: [
        "mayorista alimentos y bebidas Posadas Misiones",
        "distribuidora de bebidas Posadas Misiones",
        "mayorista productos de limpieza Posadas Misiones",
        "mayorista perfumería e higiene Posadas Misiones",
        "venta por mayor almacén Posadas Misiones",
        "distribuidora mayorista consumo masivo Posadas Misiones",
        "mayorista Itaembé Guazú Posadas",
        "mayorista Itaembé Miní Posadas",
    ])

    # --- Decisiones metodológicas abiertas (ver README) ---
    ACEPTAR_MAYORISTA_DECLARADA: bool = True   # E6: ¿alcanza con declararse mayorista en el sitio?
    MIN_RUBROS_CONSUMO_MASIVO: int = 1         # E7: rubros distintos requeridos (de 3)

    def user_agent(self) -> str:
        return f"{TOKEN_UA}/{VERSION} (investigacion academica UNaM; contacto: {self.CONTACTO})"


TOKEN_UA = "AuditoriaTesisUNaM"

DIMENSIONES = {
    "D1": "Estructura y navegación",
    "D2": "Registro y autenticación",
    "D3": "Ficha de producto",
    "D4": "Carrito de compras",
    "D5": "Proceso de checkout",
    "D6": "Medios de pago",
    "D7": "Comunicación de errores y feedback",
    "D8": "Desempeño técnico",
}

# (id, dimensión, indicador, modo A/M, fundamentación)  -- Tabla C.1
INDICADORES = [
    ("D1.1", "D1", "Menú de navegación principal visible en cabecera", "A", "Directa"),
    ("D1.2", "D1", "Buscador interno de productos presente", "A", "Directa"),
    ("D1.3", "D1", "Árbol de categorías accesible desde la página de inicio", "A", "Directa"),
    ("D1.4", "D1", "Breadcrumbs presentes en páginas de producto", "A", "Directa"),
    ("D1.5", "D1", "Filtros de ordenamiento en resultados de búsqueda", "A", "Directa"),
    ("D2.1", "D2", "Enlace o botón de registro de cuenta visible", "A", "Directa"),
    ("D2.2", "D2", "Campo CUIT/CUIL en formulario de alta", "A", "Contextual"),
    ("D2.3", "D2", "Diferenciación de tipo de cuenta (mayorista/minorista)", "A", "Parcial"),
    ("D2.4", "D2", "Formulario de inicio de sesión funcional", "M", "Parcial"),
    ("D3.1", "D3", "Precio de venta visible en ficha de producto", "A", "Parcial"),
    ("D3.2", "D3", "Precio por bulto, pack o caja indicado", "A", "Contextual"),
    ("D3.3", "D3", "Unidad de medida especificada", "A", "Contextual"),
    ("D3.4", "D3", "Indicador de disponibilidad de stock", "A", "Directa"),
    ("D3.5", "D3", "Descuento por volumen o escala visible", "A", "Contextual"),
    ("D4.1", "D4", "Botón de agregar al carrito presente y visible", "A", "Directa"),
    ("D4.2", "D4", "Cantidad mínima de compra comunicada", "A", "Contextual"),
    ("D4.3", "D4", "Selector de cantidad de unidades en carrito", "M", "Parcial"),
    ("D4.4", "D4", "Subtotal actualizado visible en carrito", "M", "Directa"),
    ("D5.1", "D5", "Indicador de etapas de progreso en checkout", "M", "Directa"),
    ("D5.2", "D5", "Opción de envío a domicilio disponible", "A", "Parcial"),
    ("D5.3", "D5", "Opción de retiro en sucursal disponible", "A", "Directa"),
    ("D5.4", "D5", "Formulario de dirección de entrega presente", "M", "Parcial"),
    ("D6.1", "D6", "Medios de pago listados en el sitio", "A", "Directa"),
    ("D6.2", "D6", "Opción de transferencia bancaria disponible", "A", "Directa"),
    ("D6.3", "D6", "Factura tipo A disponible para revendedores", "A", "Contextual"),
    ("D7.1", "D7", "Confirmación visual al agregar producto al carrito", "M", "Parcial"),
    ("D7.2", "D7", "Mensajes de error en formularios (validación)", "M", "Directa"),
    ("D7.3", "D7", "Página de error 404 con navegación útil", "A", "Parcial"),
    ("D8.1", "D8", "Tiempo de respuesta del servidor inferior al umbral", "A", "Directa"),
    ("D8.2", "D8", "Meta viewport para adaptación móvil presente", "A", "Directa"),
    ("D8.3", "D8", "Conexión segura HTTPS", "A", "Directa"),
    ("D8.4", "D8", "Imágenes del catálogo con atributo alt", "A", "Directa"),
]

ESCALA = {3: "Cumplimiento pleno", 2: "Cumplimiento parcial", 1: "Incumplimiento",
          0: "No aplicable / no verificable"}


def _verificar():
    assert len(INDICADORES) == 32
    assert sum(1 for i in INDICADORES if i[3] == "A") == 25
    assert sum(1 for i in INDICADORES if i[3] == "M") == 7
    assert sum(1 for i in INDICADORES if i[4] == "Directa") == 18
    assert sum(1 for i in INDICADORES if i[4] == "Parcial") == 8
    assert sum(1 for i in INDICADORES if i[4] == "Contextual") == 6
    por_dim = {d: sum(1 for i in INDICADORES if i[1] == d) for d in DIMENSIONES}
    assert por_dim == {"D1": 5, "D2": 4, "D3": 5, "D4": 4, "D5": 4, "D6": 3, "D7": 3, "D8": 4}


_verificar()
