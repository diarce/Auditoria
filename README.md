# AuditMayorista

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/diarce/Auditoria/blob/main/AuditMayorista_Colab.ipynb)

Herramienta de auditoría automatizada de calidad funcional (QA) para plataformas
de comercio electrónico mayorista. Desarrollada como instrumento metodológico para
la Tesis de Maestría en Administración Estratégica de Negocios (UNaM FCE).

---

## Ejecución en Google Colab

**Un clic — sin instalación:**

1. Hacer clic en el badge **Open in Colab** (arriba)  
   ó abrir directamente:  
   `https://colab.research.google.com/github/diarce/Auditoria/blob/main/AuditMayorista_Colab.ipynb`

2. En Colab: **Entorno de ejecución → Ejecutar todo** (`Ctrl+F9`)

El notebook clona automáticamente este repositorio, instala las dependencias
y ejecuta el sistema completo. No requiere configuración adicional.

---

## Estructura del sistema

```
Tesis_Maen/
├── AuditMayorista_Colab.ipynb   ← Notebook principal (ejecutar en Colab)
├── app.py                        ← Interfaz Streamlit (versión web)
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
| Auditable (protocolo manual) | 3 | Sitios Auditables |
| Excluida del QA | 4 | Solo redes sociales — documentar como brecha digital |
| Pendiente de campo | 4 | Sin URL verificada — relevamiento presencial |
| Por verificar | 3 | Datos incompletos |

Los sitios con e-commerce propio bloquean el acceso automatizado vía `robots.txt`.
El sistema respeta esta directiva como parte del protocolo ético de investigación
y utiliza el modo demo para generar datos representativos del mercado.

---

## Marco teórico

- **Transformación Digital:** Verhoef et al. (2021)
- **Capacidades Dinámicas:** Teece et al. (1997); Teece (2007); Wilden et al. (2013)
- **Alianzas Estratégicas:** Dyer & Singh (1998); Cao & Zhang (2011)
- **ODS:** 8 (Trabajo decente), 9 (Innovación), 17 (Alianzas)

---

## Instrumento QA

| Dimensión | Indicadores | Peso |
|---|---|---|
| D1 — Estructura y navegación | 5 | 1.5 |
| D2 — Registro y autenticación | 4 | 1.0 |
| D3 — Ficha de producto | 6 | 2.0 |
| D4 — Carrito de compras | 4 | 1.5 |
| D5 — Proceso de checkout | 4 | 1.5 |
| D6 — Medios de pago | 4 | 1.5 |
| D7 — Comunicación de errores | 3 | 1.0 |
| D8 — Desempeño técnico | 4 | 1.5 |

**ICC** = Σ(S_ik × w_k) / Σw_k  |  Escala 0–3  |  Suma de pesos = 11.5

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

> Ver botón **"Cite this repository"** en el panel derecho de GitHub.

---

**Autor:** Diego Enrique Arce  
**Director:** Dr. Carlos Roberto Brys  
**Institución:** Universidad Nacional de Misiones — Facultad de Ciencias Económicas  
**Año:** 2026
