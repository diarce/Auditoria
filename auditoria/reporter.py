"""Informe HTML autocontenido (sin recursos externos), con lectura por perfiles de dimensión.

No calcula ningún índice agregado (sección 7.4.2): se reportan frecuencias, puntajes por
dimensión (Ecuación B.1) y comparación de perfiles. Las plataformas aparecen con alias
determinísticos; los nombres reales no figuran en el informe.
"""
import html
import statistics
from datetime import datetime

from .auditor import puntaje_dimension
from .config import DIMENSIONES, ESCALA, INDICADORES, VERSION
from .filtro import ETAPAS

COL = {3: "#2e7d32", 2: "#f9a825", 1: "#c62828", 0: "#9e9e9e"}
e = html.escape

CSS = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1b1b1b;line-height:1.45}
h1{font-size:1.6rem}h2{border-bottom:2px solid #1f3a5f;padding-bottom:4px;margin-top:2rem;color:#1f3a5f}h3{color:#1f3a5f}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:.88rem}th,td{border:1px solid #ccc;padding:5px 8px;text-align:left}
th{background:#eef2f7}td.n,th.n{text-align:center}.sc{color:#fff;font-weight:700;text-align:center}
.bar{display:inline-block;height:12px;background:#1f3a5f;vertical-align:middle}.nota{font-size:.82rem;color:#444;background:#f6f6f6;padding:8px 10px;border-left:3px solid #1f3a5f}
.adv{background:#fff4e5;border-left:3px solid #e65100;padding:8px 10px;font-size:.85rem}.wrap{overflow-x:auto}
"""


def _celda(p):
    return f'<td class="sc" style="background:{COL[p]}">{p}</td>'


def _tabla(cabecera, filas, clases=None):
    h = "<tr>" + "".join(f"<th>{e(str(c))}</th>" for c in cabecera) + "</tr>"
    return f'<div class="wrap"><table>{h}{"".join(filas)}</table></div>'


def generar(meta, registros_filtro, aud, alias, manual_pendiente, cfg):
    """
    meta: dict con parámetros de la corrida.  registros_filtro: lista de registros del filtro.
    aud: {alias: {id: (puntaje, evidencia)}}.  alias: lista ordenada de alias auditados.
    """
    ind_por_dim = {d: [i for i in INDICADORES if i[1] == d] for d in DIMENSIONES}
    n = len(alias)
    out = [f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Auditoría de plataformas — informe</title><style>{CSS}</style></head><body>"]
    out.append("<h1>Exploración del desarrollo funcional de plataformas de comercio electrónico</h1>")
    out.append("<p>Tiendas mayoristas de bienes de consumo masivo — Posadas, Misiones. Instrumento: 32 indicadores (Anexo C), "
               "escala 0–3. Componente exploratorio, independiente de la encuesta.</p>")

    # --- 0. ficha
    out.append("<h2>0. Ficha del relevamiento</h2>")
    filas = [f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>" for k, v in meta.items()]
    out.append(_tabla(["Parámetro", "Valor"], filas))
    if cfg.SALT_ANONIMIZACION == "CAMBIAR-ESTA-SEMILLA":
        out.append("<p class='adv'>La semilla de anonimización es la predeterminada: cámbiela antes de usar los resultados en la tesis.</p>")

    # --- 1. embudo
    out.append("<h2>1. Embudo de elegibilidad (E1–E9)</h2>")
    total = len(registros_filtro)
    excl = {k: [r for r in registros_filtro if r["etapa_excluyente"] == k] for k in ETAPAS}
    filas, restantes = [], total
    for k, nombre in ETAPAS.items():
        x = len(excl[k])
        motivos = {}
        for r in excl[k]:
            motivos[r["motivo"]] = motivos.get(r["motivo"], 0) + 1
        ent = restantes
        restantes -= x
        filas.append(f"<tr><td>{k}</td><td>{e(nombre)}</td><td class='n'>{ent}</td><td class='n'>{x}</td><td class='n'>{restantes}</td>"
                     f"<td>{e('; '.join(f'{m} ({c})' for m, c in motivos.items()))}</td></tr>")
    out.append(_tabla(["Etapa", "Criterio", "Ingresan", "Excluidos", "Continúan", "Motivos"], filas))
    out.append(f"<p>Candidatos únicos evaluados: <b>{total}</b>. Plataformas observables auditadas: <b>{n}</b>. "
               "Las exclusiones por etapa constituyen un hallazgo en sí mismo (plataformas no observables o fuera de alcance).</p>")
    nv = {}
    for r in registros_filtro:
        for k in filter(None, r["no_verificables"].split(",")):
            nv[k] = nv.get(k, 0) + 1
    if nv:
        out.append("<p class='nota'>Etapas no verificables (no excluyen): " + e(", ".join(f"{k}: {v}" for k, v in nv.items())) + "</p>")
    niv = {}
    for r in registros_filtro:
        if r["nivel_mayorista"]:
            niv[r["nivel_mayorista"]] = niv.get(r["nivel_mayorista"], 0) + 1
    if niv:
        out.append("<p class='nota'>Evidencia de condición mayorista entre quienes la superaron: " + e(", ".join(f"{k}={v}" for k, v in niv.items())) + ".</p>")

    if n == 0:
        out.append("<p class='adv'>No hay plataformas auditables en esta corrida.</p></body></html>")
        return "".join(out)

    # --- 2. frecuencias
    out.append("<h2>2. Distribución de frecuencias de la escala</h2>")
    def frec(dims):
        c = {0: 0, 1: 0, 2: 0, 3: 0}
        for a in alias:
            for i in INDICADORES:
                if i[1] in dims:
                    c[aud[a][i[0]][0]] += 1
        return c
    filas = []
    for etiqueta, dims in [("Total", set(DIMENSIONES))] + [(f"{d} {nm}", {d}) for d, nm in DIMENSIONES.items()]:
        c = frec(dims)
        t = sum(c.values())
        filas.append(f"<tr><td>{e(etiqueta)}</td><td class='n'>{t}</td>" + "".join(
            f"<td class='n'>{c[k]} ({100 * c[k] / t:.0f}%)</td>" for k in (3, 2, 1, 0)) + "</tr>")
    out.append(_tabla(["Dimensión", "Observaciones", "3 Pleno", "2 Parcial", "1 Incumple", "0 N/A o no verificable"], filas))
    out.append("<p class='nota'>Las observaciones están anidadas en cada plataforma (no son unidades muestrales independientes). "
               "El 0 incluye los 7 indicadores de verificación manual mientras no se cargue ese protocolo.</p>")

    # --- 3. perfiles
    out.append("<h2>3. Perfiles por dimensión (Ec. B.1)</h2>")
    filas = []
    for a in alias:
        cel = []
        for d in DIMENSIONES:
            s = puntaje_dimension([aud[a][i[0]][0] for i in ind_por_dim[d]])
            cel.append("<td class='n'>—</td>" if s is None else
                       f"<td class='sc' style='background:{COL[max(1, min(3, round(s)))]}'>{s:.2f}</td>")
        filas.append(f"<tr><td>{e(a)}</td>{''.join(cel)}</tr>")
    resumen = []
    for d in DIMENSIONES:
        v = [s for a in alias if (s := puntaje_dimension([aud[a][i[0]][0] for i in ind_por_dim[d]])) is not None]
        resumen.append(f"{statistics.median(v):.2f} [{min(v):.2f}–{max(v):.2f}]" if v else "—")
    filas.append("<tr><th>Mediana [mín–máx]</th>" + "".join(f"<td class='n'>{x}</td>" for x in resumen) + "</tr>")
    out.append(_tabla(["Plataforma"] + [f"{d}<br>{nm}" for d, nm in DIMENSIONES.items()], filas))
    out.append("<p class='nota'>Sin índice agregado: la lectura es por perfil. El promedio por dimensión es una medida exploratoria de "
               "tendencia central sobre una escala ordinal, no una magnitud de intervalo. '—' = dimensión sin indicadores verificables.</p>")

    # --- 4. detalle por dimensión
    out.append("<h2>4. Detalle por dimensión</h2>")
    for d, nm in DIMENSIONES.items():
        out.append(f"<h3>{d} — {e(nm)}</h3>")
        filas = []
        for (iid, _, nombre, modo, fund) in ind_por_dim[d]:
            ps = [aud[a][iid][0] for a in alias]
            valid = [p for p in ps if p > 0]
            pleno = sum(1 for p in valid if p == 3)
            pct = f"{100 * pleno / len(valid):.0f}%" if valid else "—"
            cel = "".join(_celda(p) for p in ps)
            filas.append(f"<tr><td>{iid}</td><td>{e(nombre)}</td><td class='n'>{modo}</td><td class='n'>{fund[:4]}.</td>{cel}"
                         f"<td class='n'>{pct}</td><td class='n'>{len(valid)}/{n}</td></tr>")
        cab = ["ID", "Indicador", "A/M", "Fund."] + [f"S{j + 1}" for j in range(n)] + ["% pleno", "Válidos"]
        out.append(_tabla(cab, filas))
    out.append("<p class='nota'>S1…Sn corresponden a 'Sitio Auditado 1…n' (orden del perfil de la sección 3). "
               "Fund.: Dire.= concordancia directa, Parc.= parcial, Cont.= contextual (elaboración propia). "
               "% pleno se calcula sobre observaciones válidas (puntaje &gt; 0).</p>")
    out.append("<h3>Evidencia por plataforma</h3><details><summary>Mostrar la regla que originó cada puntaje</summary>")
    for a in alias:
        filas = [f"<tr><td>{iid}</td><td class='n'>{aud[a][iid][0]}</td><td>{e(aud[a][iid][1])}</td></tr>" for iid, *_ in INDICADORES]
        out.append(f"<h4>{e(a)}</h4>" + _tabla(["ID", "Puntaje", "Evidencia"], filas))
    out.append("</details>")

    # --- 5. manual
    out.append("<h2>5. Verificación manual pendiente</h2>")
    man = [i for i in INDICADORES if i[3] == "M"]
    out.append(f"<p>Indicadores con protocolo manual: {e(', '.join(i[0] for i in man))}. "
               f"Pendientes de carga en esta corrida: <b>{manual_pendiente}</b> de {len(man) * n}. "
               "Se completan en <code>manual_plantilla.csv</code> y se incorporan con <code>aplicar_manual()</code>.</p>")

    # --- 6. limitaciones
    out.append("<h2>6. Limitaciones y alcance de la lectura</h2><ul>"
               "<li>Resultados descriptivos y exploratorios de las plataformas efectivamente auditadas; no se proyectan al universo.</li>"
               "<li>Las plataformas auditables quedan determinadas por el protocolo ético (robots.txt) y por la fuente de candidatos; los sitios excluidos podrían diferir de los auditados.</li>"
               "<li>La fuente de candidatos es Google Maps (cobertura incompleta y sujeta a términos de servicio de terceros).</li>"
               "<li>Las reglas automáticas son heurísticas sobre HTML público: no ejecutan JavaScript, pueden subestimar funcionalidades y no verifican la operatoria interna (carrito, checkout, pago).</li>"
               "<li>El tiempo de respuesta se mide desde el entorno de ejecución (Colab), cuya ubicación de red puede diferir de la de un usuario en Argentina.</li>"
               "<li>Los puntajes intermedios (2) de varios indicadores son decisiones operativas del autor, sin respaldo en la literatura de referencia.</li>"
               "<li>La encuesta es anónima: no existe vínculo a nivel empresa con estos resultados.</li></ul>")
    out.append(f"<p class='nota'>Generado {datetime.now():%Y-%m-%d %H:%M} — Auditoria v{VERSION}.</p></body></html>")
    return "".join(out)
