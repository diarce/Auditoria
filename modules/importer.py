"""
modules/importer.py
───────────────────
Importa datos de auditoría recolectados manualmente (CSV / Excel / Google Sheets)
hacia la base de datos de AuditMayorista.

Flujo:
  1. El investigador completa la planilla de auditoría manual
  2. La exporta como CSV o xlsx
  3. Este módulo valida e inserta los datos en audit_results

Columnas requeridas en la planilla:
  site_id, site_name, site_url, dimension_id, test_case_id,
  test_case_name, compliance, metodo, notas

Valores de compliance: 0 = N/A | 1 = No cumple | 2 = Parcial | 3 = Pleno
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd

from modules.storage import DatabaseManager
from config import QA_DIMENSIONS, TEST_CASES


# ─── Constantes ───────────────────────────────────────────────────────────────

COLUMNAS_REQUERIDAS = [
    "site_id", "site_name", "site_url",
    "dimension_id", "test_case_id", "test_case_name",
    "compliance",
]

COLUMNAS_OPCIONALES = ["metodo", "notas", "auditor", "fecha_auditoria"]

COMPLIANCE_VALIDOS = {0, 1, 2, 3}

METODOS_VALIDOS = {"manual", "automatico", "mixto"}


# ─── Clase principal ──────────────────────────────────────────────────────────

class AuditImporter:
    """
    Importa resultados de auditoría desde una planilla estructurada.

    Parámetros
    ----------
    db : DatabaseManager
        Instancia de la base de datos de destino.
    log_fn : callable, opcional
        Función para emitir mensajes de log (signature: log_fn(msg, nivel)).
    """

    def __init__(self, db: DatabaseManager, log_fn=None):
        self.db     = db
        self._log   = log_fn or (lambda msg, nivel="INFO": print(f"[{nivel}] {msg}"))

    # ── API pública ────────────────────────────────────────────────────────────

    def from_csv(self, path: str | Path,
                 encoding: str = "utf-8",
                 delimiter: str = ",") -> dict:
        """Importa desde un archivo CSV."""
        path = Path(path)
        self._log(f"Leyendo CSV: {path.name}", "INFO")
        df = pd.read_csv(path, encoding=encoding, delimiter=delimiter,
                         dtype=str, keep_default_na=False)
        return self._importar(df, str(path.name))

    def from_excel(self, path: str | Path, sheet: str | int = 0) -> dict:
        """Importa desde un archivo Excel (.xlsx / .xls)."""
        path = Path(path)
        self._log(f"Leyendo Excel: {path.name}", "INFO")
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        df = df.fillna("")
        return self._importar(df, str(path.name))

    def from_dataframe(self, df: pd.DataFrame, fuente: str = "dataframe") -> dict:
        """Importa desde un DataFrame de pandas (útil en Colab)."""
        return self._importar(df.astype(str).fillna(""), fuente)

    # ── Implementación ─────────────────────────────────────────────────────────

    def _importar(self, df: pd.DataFrame, fuente: str) -> dict:
        """Valida e inserta los datos en la BD."""
        resultado = {
            "fuente": fuente,
            "total_filas": len(df),
            "insertadas": 0,
            "omitidas": 0,
            "errores": [],
            "sitios_nuevos": [],
        }

        # 1. Normalizar nombres de columnas
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # 2. Verificar columnas requeridas
        faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltantes:
            msg = f"Columnas faltantes en la planilla: {faltantes}"
            self._log(msg, "ERR")
            resultado["errores"].append(msg)
            return resultado

        # 3. Registrar sitios en la tabla sites
        sitios_en_planilla = (
            df[["site_id", "site_name", "site_url"]]
            .drop_duplicates(subset=["site_id"])
        )
        for _, row in sitios_en_planilla.iterrows():
            sid = row["site_id"].strip()
            if not sid:
                continue
            sitio = {
                "id":       sid,
                "name":     row.get("site_name", sid).strip(),
                "base_url": row.get("site_url",  "").strip(),
                "dynamic":  False,
                "selectors": {},
                "localidades": [],
            }
            existente = self.db.get_site(sid)
            if not existente:
                self.db.upsert_site(sitio)
                resultado["sitios_nuevos"].append(sid)
                self._log(f"Sitio registrado: {sid} — {sitio['name']}", "OK")

        # 4. Insertar resultados de auditoría
        ahora = datetime.now().isoformat()

        for idx, row in df.iterrows():
            fila = idx + 2  # para mensajes (fila 1 = encabezado)

            # Extraer y validar campos
            sid          = str(row.get("site_id",       "")).strip()
            dim_id       = str(row.get("dimension_id",  "")).strip().upper()
            tc_id        = str(row.get("test_case_id",  "")).strip()
            tc_name      = str(row.get("test_case_name","")).strip()
            compliance_s = str(row.get("compliance",    "")).strip()
            metodo       = str(row.get("metodo", "manual")).strip().lower() or "manual"
            notas        = str(row.get("notas",  "")).strip()

            # Validar campos obligatorios
            if not sid or not dim_id or not tc_id:
                resultado["omitidas"] += 1
                resultado["errores"].append(f"Fila {fila}: campos obligatorios vacíos")
                continue

            # Validar compliance
            try:
                compliance = int(float(compliance_s))
                if compliance not in COMPLIANCE_VALIDOS:
                    raise ValueError
            except (ValueError, TypeError):
                resultado["omitidas"] += 1
                resultado["errores"].append(
                    f"Fila {fila}: compliance inválido ('{compliance_s}'). "
                    "Valores aceptados: 0, 1, 2, 3"
                )
                continue

            # Validar método
            if metodo not in METODOS_VALIDOS:
                metodo = "manual"

            # Insertar en audit_results
            try:
                self.db._conn.execute(
                    """
                    INSERT OR REPLACE INTO audit_results
                        (site_id, dimension_id, test_case_id, test_case_name,
                         compliance, timestamp, verification_method, notas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sid, dim_id, tc_id, tc_name,
                     compliance, ahora, metodo, notas)
                )
                resultado["insertadas"] += 1
            except Exception as e:
                resultado["omitidas"] += 1
                resultado["errores"].append(f"Fila {fila}: error DB — {e}")

        self.db._conn.commit()

        self._log(
            f"Importación completada: {resultado['insertadas']} filas insertadas, "
            f"{resultado['omitidas']} omitidas, "
            f"{len(resultado['sitios_nuevos'])} sitios nuevos.",
            "OK"
        )
        return resultado


# ─── Utilidades ───────────────────────────────────────────────────────────────

def generar_plantilla_csv(destino: str | Path = "plantilla_auditoria_manual.csv"):
    """
    Genera una plantilla CSV vacía con todas las columnas y los 34
    casos de prueba pre-cargados, lista para que el investigador
    complete los valores de compliance.
    """
    from config import TEST_CASES, QA_DIMENSIONS

    destino = Path(destino)
    filas   = []

    for dim_id, tc_list in sorted(TEST_CASES.items()):
        dim_nombre = QA_DIMENSIONS.get(dim_id, {}).get("name", dim_id)
        for tc in tc_list:
            filas.append({
                "site_id"         : "",          # ej. MIS004
                "site_name"       : "",          # ej. Distribuidora Los Cardales
                "site_url"        : "",          # ej. https://loscardales.com.ar
                "dimension_id"    : dim_id,
                "dimension_nombre": dim_nombre,
                "test_case_id"    : tc["id"],
                "test_case_name"  : tc["name"],
                "compliance"      : "",          # 0/1/2/3 (obligatorio)
                "metodo"          : "manual",    # manual / automatico / mixto
                "notas"           : "",          # observaciones del auditor
                "auditor"         : "",          # nombre del evaluador
                "fecha_auditoria" : datetime.now().strftime("%Y-%m-%d"),
            })

    df = pd.DataFrame(filas)
    df.to_csv(destino, index=False, encoding="utf-8-sig")  # utf-8-sig para Excel
    return destino
