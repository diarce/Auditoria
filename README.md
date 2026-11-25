# Auditoría de plataformas de e-commerce mayorista — Posadas, Misiones (v0.1.0)

Instrumento de la tesis *Factores Estratégicos Asociados al Desarrollo del Comercio Electrónico en Tiendas Mayoristas de Bienes de Consumo Masivo de Posadas, Misiones* (UNaM-FCE).
Implementa la sección 7.4 y los Anexos B y C: **32 indicadores, 8 dimensiones, escala 0–3, perfiles por dimensión, sin índice agregado**.

## Flujo
`fuentes.py` (Google Maps / CSV) → `filtro.py` (E1–E9) → `auditor.py` (32 indicadores) → `reporter.py` (HTML por dimensión). Todo GET pasa por `ethics.py`.

## Uso en Colab
Abrir `notebooks/Auditoria_Colab.ipynb` desde GitHub (badge en la primera celda), completar CONTACTO y SEMILLA, ejecutar en orden.
Almacenamiento solo temporal: descargar el `.zip` final.

## Subir a GitHub
```
git add . && git commit -m "Auditoria v0.1.0" && git push
```
`resultados/` y `mapeo_privado.csv` están en `.gitignore` (el mapeo alias↔dominio es confidencial).

## Pruebas
`python tests/test_local.py` (servidores HTTP locales; no usa Internet).

## Etapas del filtro
E1 Posadas (incluye Itaembé Guazú/Miní) · E2 activo · E3 sitio propio (no redes/marketplaces) · E4 robots permite inicio ·
E5 accesible (200, TLS válido) · E6 mayorista (acreditada = categoría de Maps; declarada = texto del sitio) · E7 rubro consumo masivo ·
E8 canal online público observable · E9 robots permite listado y ficha. Las exclusiones se reportan por etapa y motivo.

## Decisiones abiertas (marcadas como parámetros, no resueltas por el código)
1. **E6**: aceptar o no «mayorista declarada» (`ACEPTAR_MAYORISTA_DECLARADA`).
2. **E7**: rubros mínimos (`MIN_RUBROS_CONSUMO_MASIVO`) y palabras clave de cada rubro (`filtro.RUBROS`).
3. Consultas de búsqueda (`Config.CONSULTAS`) y calendario de corridas; mantener la misma fuente entre corridas comparadas.
4. Puntajes intermedios (2) de varios indicadores: son umbrales operativos del autor, no de la literatura.

## Limitaciones técnicas conocidas
* Google Maps: sus términos restringen la extracción automatizada; el módulo consulta robots.txt y se detiene si no se permite. Selectores CSS frágiles. **No pudo probarse fuera de la sesión real de Colab.**
* Heurísticas sobre HTML estático: no ejecutan JavaScript (SPA, catálogos dinámicos) → posibles falsos negativos en E6–E8 y en los indicadores.
* E6/E7/E8 se evalúan sobre la página de inicio: un sitio que declare «mayorista» solo en otra página queda excluido.
* D8.1 se mide desde Colab (ubicación de red distinta a la de un usuario en Argentina).
* Los 7 indicadores manuales quedan en 0 hasta cargar `manual_plantilla.csv`.
