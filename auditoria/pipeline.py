"""Orquestador: candidatos -> filtro E1–E9 -> auditoría de 32 indicadores -> informe HTML.

Almacenamiento: solo el directorio temporal de la sesión (cfg.DIR_SALIDA). El archivo
``mapeo_privado.csv`` vincula alias y dominio: es confidencial, no se publica ni se sube a GitHub.
"""
import csv
import hashlib
import json
import os
from datetime import datetime

from . import fuentes
from .auditor import auditar, puntaje_dimension
from .config import DIMENSIONES, INDICADORES, TOKEN_UA, VERSION, indicadores_activos
from .ethics import Etica
from .filtro import filtrar
from .reporter import generar


def _alias(registros, sitios, cfg):
    ids = sorted(sitios, key=lambda cid: hashlib.sha256((cfg.SALT_ANONIMIZACION + "alias" + cid).encode()).hexdigest())
    return {cid: f"Sitio Auditado {i}" for i, cid in enumerate(ids, 1)}


def ejecutar(cfg, fuente="maps", ruta_csv=None, candidatos=None, log=print):
    os.makedirs(cfg.DIR_SALIDA, exist_ok=True)
    etica = Etica(cfg)
    inicio = datetime.now()
    if candidatos is None:
        if fuente == "maps":
            candidatos = fuentes.buscar_maps(etica, cfg, log=log)
        elif fuente == "csv":
            candidatos = fuentes.leer_csv(ruta_csv)
        else:
            raise ValueError("fuente debe ser 'maps' o 'csv'")
    log(f"Candidatos obtenidos: {len(candidatos)}")

    registros, sitios = filtrar(candidatos, etica, cfg, log)
    mapa = _alias(registros, sitios, cfg)
    aud_id = {}
    for cid, sitio in sitios.items():
        log(f"[auditoría] {mapa[cid]}")
        aud_id[cid] = auditar(sitio, etica, cfg)
    aud = {mapa[cid]: v for cid, v in aud_id.items()}
    alias = sorted(aud, key=lambda a: int(a.split()[-1]))

    meta = {
        "Fecha de ejecución": inicio.strftime("%Y-%m-%d %H:%M"), "Versión del instrumento": VERSION,
        "Fuente de candidatos": fuente, "Consultas": len(cfg.CONSULTAS) if fuente == "maps" else "n/a",
        "Candidatos obtenidos": len(candidatos), "Agente de usuario": f"{TOKEN_UA}/{VERSION} (con contacto institucional)",
        "Demora mínima / jitter (s)": f"{cfg.DEMORA_MIN} / {cfg.JITTER_MAX}",
        "Tope de peticiones por sitio": cfg.MAX_PETICIONES_SITIO,
        "E6: acepta mayorista declarada": cfg.ACEPTAR_MAYORISTA_DECLARADA,
        "E7: rubros mínimos": cfg.MIN_RUBROS_CONSUMO_MASIVO,
        "Indicadores evaluados": f"{len(indicadores_activos(cfg))} (automáticos)" if not cfg.INCLUIR_MANUALES else f"{len(INDICADORES)}",
    }
    guardar(cfg, registros, aud, alias, mapa, meta)
    return {"registros": registros, "aud": aud, "alias": alias, "mapa": mapa, "meta": meta, "bitacora": etica.bitacora}


def _manual_pendiente(aud, alias):
    return 0 if not aud or not any(i[3] == "M" and i[0] in next(iter(aud.values())) for i in INDICADORES) else sum(1 for a in alias for i in INDICADORES if i[3] == "M" and aud[a][i[0]][1].startswith("pendiente"))


def guardar(cfg, registros, aud, alias, mapa, meta):
    d = cfg.DIR_SALIDA
    os.makedirs(d, exist_ok=True)
    act = indicadores_activos(cfg)
    inv_ = {v: k for k, v in mapa.items()}      # alias -> id_estable (hash salado del dominio; vincula corridas sin exponerlo)
    pub = ["cand_id", "fuente", "etapa_excluyente", "motivo", "nivel_mayorista", "rubros", "senales_online", "no_verificables"]
    with open(f"{d}/filtro_elegibilidad.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, pub, extrasaction="ignore")
        w.writeheader()
        w.writerows(registros)
    with open(f"{d}/auditoria_indicadores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["plataforma", "id_estable", "indicador", "dimension", "modo", "puntaje", "evidencia"])
        for a in alias:
            for iid, dim, _, modo, _ in act:
                w.writerow([a, inv_[a], iid, dim, modo, aud[a][iid][0], aud[a][iid][1]])
    with open(f"{d}/perfiles_dimension.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["plataforma"] + list(DIMENSIONES))
        for a in alias:
            w.writerow([a] + [("" if (s := puntaje_dimension([aud[a][i[0]][0] for i in act if i[1] == dm])) is None else round(s, 3))
                              for dm in DIMENSIONES])
    if cfg.INCLUIR_MANUALES:
        with open(f"{d}/manual_plantilla.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["plataforma", "indicador", "puntaje_0a3", "observacion"])
            for a in alias:
                for iid, _, nombre, modo, _ in INDICADORES:
                    if modo == "M":
                        w.writerow([a, iid, "", nombre])
    inv = {v: k for k, v in mapa.items()}
    dom = {r["cand_id"]: r["dominio"] for r in registros}
    with open(f"{d}/mapeo_privado.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["CONFIDENCIAL_no_publicar", "plataforma", "cand_id", "dominio"])
        for a in alias:
            w.writerow(["", a, inv[a], dom.get(inv[a], "")])
    with open(f"{d}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    html = generar(meta, registros, aud, alias, _manual_pendiente(aud, alias), cfg)
    with open(f"{d}/informe_auditoria.html", "w", encoding="utf-8") as f:
        f.write(html)


def aplicar_manual(cfg, resultado, ruta_csv):
    """Opcional: incorpora el protocolo manual (requiere cfg.INCLUIR_MANUALES=True)."""
    if not cfg.INCLUIR_MANUALES:
        raise ValueError("La corrida automatizada no incluye indicadores manuales (INCLUIR_MANUALES=False).")
    validos = {i[0] for i in INDICADORES if i[3] == "M"}
    with open(ruta_csv, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            a, iid, p = fila["plataforma"], fila["indicador"], (fila.get("puntaje_0a3") or "").strip()
            if not p:
                continue
            if a not in resultado["aud"] or iid not in validos or p not in ("0", "1", "2", "3"):
                raise ValueError(f"Fila inválida: {fila}")
            resultado["aud"][a][iid] = (int(p), "verificación manual: " + (fila.get("observacion") or "").strip())
    guardar(cfg, resultado["registros"], resultado["aud"], resultado["alias"], resultado["mapa"], resultado["meta"])
    return resultado
