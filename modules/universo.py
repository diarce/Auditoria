"""
modules/universo.py
───────────────────
Carga y gestiona el universo de empresas mayoristas relevadas
desde data/universo_mayoristas_posadas.csv.

El CSV es la fuente canónica del estudio. Clasifica cada empresa en:
  AUDITABLE_MANUAL_RECOMENDADO       → sitio web propio, robots.txt restrictivo
  AUDITABLE_AUTOMATICO               → sitio web propio, robots.txt permisivo
  EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO → solo redes sociales
  PENDIENTE_TRABAJO_DE_CAMPO         → sin URL verificada aún
  VERIFICAR                          → datos incompletos
"""

from __future__ import annotations

import csv
from pathlib import Path
from dataclasses import dataclass
from typing import List


UNIVERSO_CSV = Path(__file__).parent.parent / "data" / "universo_mayoristas_posadas.csv"

# Paleta de estado para display
ESTADO_CONFIG = {
    "AUDITABLE_AUTOMATICO": {
        "emoji": "✓", "color": "#1a4a6e", "texto_color": "white",
        "etiqueta": "Auditable — acceso automático",
    },
    "AUDITABLE_MANUAL_RECOMENDADO": {
        "emoji": "○", "color": "#5a8fb5", "texto_color": "white",
        "etiqueta": "Auditable — protocolo manual recomendado",
    },
    "EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO": {
        "emoji": "◇", "color": "#c8d8e8", "texto_color": "#333",
        "etiqueta": "Excluida del QA — documentar como brecha digital",
    },
    "PENDIENTE_TRABAJO_DE_CAMPO": {
        "emoji": "△", "color": "#f0f0f0", "texto_color": "#555",
        "etiqueta": "Pendiente — requiere relevamiento presencial",
    },
    "VERIFICAR": {
        "emoji": "?", "color": "#fff3cc", "texto_color": "#333",
        "etiqueta": "Por verificar — datos incompletos",
    },
}


@dataclass
class Empresa:
    id: str
    nombre: str
    ciudad: str
    url_principal: str
    url_alternativa: str
    tipo_presencia: str
    plataforma_cms: str
    nivel_digital: str
    robots_permite: str
    estado_auditoria: str
    fuente: str
    notas_eticas: str
    notas_metodologicas: str


def cargar_universo(csv_path: Path = UNIVERSO_CSV) -> List[Empresa]:
    """Lee el CSV del universo y devuelve la lista de empresas."""
    empresas = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            empresas.append(Empresa(**{
                k: row.get(k, "").strip() for k in Empresa.__dataclass_fields__
            }))
    return empresas


def empresas_auditables(universo: List[Empresa]) -> List[Empresa]:
    """Devuelve solo las empresas con plataforma propia auditable."""
    return [
        e for e in universo
        if e.estado_auditoria in (
            "AUDITABLE_AUTOMATICO",
            "AUDITABLE_MANUAL_RECOMENDADO",
        )
        and e.url_principal.startswith("http")
    ]


def empresas_excluidas(universo: List[Empresa]) -> List[Empresa]:
    """Devuelve empresas excluidas del QA (solo RRSS / sin presencia digital)."""
    return [
        e for e in universo
        if e.estado_auditoria == "EXCLUIR_QA_INCLUIR_ANALISIS_CUALITATIVO"
    ]


def registrar_en_db(universo: List[Empresa], db) -> int:
    """Registra las empresas auditables en la base de datos."""
    auditables = empresas_auditables(universo)
    for e in auditables:
        db.upsert_site({
            "id":         e.id,
            "name":       e.nombre,
            "base_url":   e.url_principal,
            "dynamic":    e.plataforma_cms.lower() in ("vtex", "tiendanube", "shopify"),
            "selectors":  {},
            "localidades": [e.ciudad],
        })
    return len(auditables)


def tabla_universo_html(universo: List[Empresa]) -> str:
    """Genera una tabla HTML del universo completo para mostrar en Colab."""
    filas = ""
    for e in universo:
        cfg   = ESTADO_CONFIG.get(e.estado_auditoria, ESTADO_CONFIG["VERIFICAR"])
        bg    = cfg["color"]
        fc    = cfg["texto_color"]
        emoji = cfg["emoji"]
        filas += (
            f"<tr>"
            f"<td style='padding:5px 8px;font-family:monospace;font-size:11px'>{e.id}</td>"
            f"<td style='padding:5px 8px;font-size:12px'><b>{e.nombre}</b></td>"
            f"<td style='padding:5px 8px;font-size:11px'>{e.ciudad}</td>"
            f"<td style='padding:5px 8px;font-size:11px'>{e.nivel_digital}</td>"
            f"<td style='padding:5px 8px;font-size:11px'>{e.tipo_presencia}</td>"
            f"<td style='background:{bg};color:{fc};padding:5px 8px;"
            f"font-size:11px;font-weight:bold;text-align:center'>"
            f"{emoji}</td>"
            f"</tr>"
        )

    # Leyenda
    leyenda = "".join(
        f"<span style='background:{v['color']};color:{v['texto_color']};"
        f"padding:2px 8px;margin:0 4px 4px 0;display:inline-block;"
        f"font-size:10px'>{v['emoji']} {v['etiqueta']}</span>"
        for v in ESTADO_CONFIG.values()
    )

    return f"""
<div style="font-family:Georgia,serif">
  <div style="font-size:14px;font-weight:bold;margin:10px 0 6px">
    Universo del estudio — Empresas mayoristas de consumo masivo
    (Posadas, Garupá, Itaembé Guazú)
  </div>
  <div style="margin-bottom:8px">{leyenda}</div>
  <div style="overflow-x:auto">
  <table style="border-collapse:collapse;width:100%;font-size:12px">
    <thead>
      <tr style="background:#1a1a1a;color:white">
        <th style="padding:6px 8px">ID</th>
        <th style="padding:6px 8px">Empresa</th>
        <th style="padding:6px 8px">Ciudad</th>
        <th style="padding:6px 8px">Nivel</th>
        <th style="padding:6px 8px">Presencia</th>
        <th style="padding:6px 8px">Estado</th>
      </tr>
    </thead>
    <tbody>{filas}</tbody>
  </table>
  </div>
  <div style="font-size:10px;color:#888;margin-top:6px;font-style:italic">
    Fuente: relevamiento del investigador · {len(universo)} empresas identificadas
  </div>
</div>
"""
