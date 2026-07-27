# AuditMayorista

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/diarce/Auditoria/blob/main/AuditMayorista_Colab.ipynb)

Herramienta de auditoría automatizada de calidad funcional (QA) para plataformas
de comercio electrónico mayorista. Desarrollada como instrumento metodológico para
la Tesis de Maestría en Administración Estratégica de Negocios (UNaM FCE).

---

## Ejecución en Google Colab

**Un clic — sin instalación:**

1. Hacer clic en el badge **Open in Colab** (arriba), o abrir directamente:
   `https://colab.research.google.com/github/diarce/Auditoria/blob/main/AuditMayorista_Colab.ipynb`
2. En Colab: **Entorno de ejecución → Ejecutar todo** (`Ctrl+F9`)

El notebook clona automáticamente este repositorio, instala las dependencias
y ejecuta el sistema completo sin configuración adicional.

---

## Estructura del sistema

```
Auditoria/
├── AuditMayorista_Colab.ipynb   ← Notebook principal (ejecutar en Colab)
├── config.py                     ← Configuración del sistema
├── CITATION.cff                  ← Metadatos de cita académica
│
├── modules/
│   ├── auditor.py    ← Motor de auditoría QA (8 dimensiones, 34 indicadores)
│   ├── reporter.py   ← Generador de informes HTML y visualizaciones SVG
│   ├── universo.py   ← Gestión del universo de empresas del estudio
│   ├── importer.py   ← Importación de auditorías manuales (CSV/Excel)
│   ├── storage.py    ← Base de datos SQLite
│   ├── demo.py       ← Datos representativos del mercado mayorista
│   └── ethics.py     ← Protocolo ético (robots.txt, rate limiting)
│
└── data/
    ├── universo_mayoristas_posadas.csv  ← Universo relevado (14 empresas)
    ├── empresas_mayoristas.json         ← Catálogo de sitios configurados
    └── provincias_localidades.json      ← Localidades del estudio
```

---

## Universo del estudio

| Estado | Empresas | Tratamiento |
|---|---|---|
| Auditable — protocolo manual | 3 | Sitios Auditables |
| Excluida del QA | 4 | Solo redes sociales — documentar como brecha digital |
| Pendiente de campo | 4 | Sin URL verificada — relevamiento presencial |
| Por verificar | 3 | Datos incompletos |

Los sitios con e-commerce propio bloquean el acceso automatizado vía `robots.txt`.
El sistema respeta esta directiva como parte del protocolo ético de investigación.

---

## Instrumento QA — Dimensiones e indicadores

| Dimensión | Indicadores | Peso $w_k$ |
|---|:---:|:---:|
| D1 — Estructura y navegación | 5 | 1,5 |
| D2 — Registro y autenticación | 4 | 1,0 |
| D3 — Ficha de producto | 6 | 2,0 |
| D4 — Carrito de compras | 4 | 1,5 |
| D5 — Proceso de checkout | 4 | 1,5 |
| D6 — Medios de pago | 4 | 1,5 |
| D7 — Comunicación de errores y feedback | 3 | 1,0 |
| D8 — Desempeño técnico | 4 | 1,5 |

### Escala de cumplimiento

Cada indicador se evalúa en una escala de cuatro niveles:

| Valor | Etiqueta |
|:---:|---|
| 0 | N/A — no aplica |
| 1 | No cumple |
| 2 | Cumplimiento parcial |
| 3 | Cumplimiento pleno |

### Puntaje por dimensión

El puntaje de la plataforma $i$ en la dimensión $k$ se calcula como el
promedio de los indicadores evaluados, excluyendo los casos N/A:

```math
S_{i,k} = \frac{\displaystyle\sum_{j \,:\, s_{i,k,j} > 0} s_{i,k,j}}
               {\left|\{j : s_{i,k,j} > 0\}\right|}
```

### Índice de Calidad Compuesto (ICC)

El ICC es la media ponderada de los ocho puntajes dimensionales,
donde la suma total de pesos es $\sum_{k=1}^{8} w_k = 11{,}5$:

```math
ICC(i) = \frac{\displaystyle\sum_{k=1}^{8} S_{i,k} \cdot w_k}
              {\displaystyle\sum_{k=1}^{8} w_k}
```

### Escala de interpretación del ICC

| Rango | Nivel |
|---|---|
| $ICC \geq 2{,}5$ | Cumplimiento pleno |
| $1{,}5 \leq ICC < 2{,}5$ | Cumplimiento parcial |
| $ICC < 1{,}5$ | Estado crítico |

---

## Marco teórico

| Eje | Autor(es) | Concepto central |
|---|---|---|
| Transformación Digital | Verhoef et al. (2021) | Modelo de tres fases: digitalización → digitalización de procesos → TD |
| Capacidades Dinámicas | Teece et al. (1997); Teece (2007); Wilden et al. (2013) | *Sensing* / *Seizing* / *Transforming* |
| Alianzas Estratégicas | Dyer & Singh (1998); Cao & Zhang (2011) | Ventaja relacional interorganizacional |
| ODS | Agenda 2030 | ODS 8 (trabajo digno), ODS 9 (innovación), ODS 17 (alianzas) |

---

## Cita

```bibtex
@software{AuditMayorista2026,
  author  = {Arce, Diego Enrique},
  title   = {{AuditMayorista}: Herramienta de auditoria automatizada
             de calidad funcional para plataformas de comercio
             electronico mayorista},
  year    = {2026},
  version = {5.0},
  url     = {https://github.com/diarce/Auditoria}
}
```

> Ver también el botón **"Cite this repository"** en el panel derecho de GitHub,
> generado automáticamente desde `CITATION.cff`.

---

**Autor:** Diego Enrique Arce  
**Director:** Dr. Carlos Roberto Brys  
**Institución:** Universidad Nacional de Misiones — Facultad de Ciencias Económicas  
**Año:** 2026
