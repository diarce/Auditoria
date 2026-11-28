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

## Cambios v0.1.1 (revisión)
E1 exige Misiones o CP 3300 (Posadas también es nombre de calle) · enlaces de redirección de Maps · `cand_id` estable por dominio (columna `id_estable` para vincular corridas) ·
redirección de host en el inicio · robots.txt 401/403/429 se trata como ilegible · D4.1, D6.1 y D2.3 con menos falsos positivos · D1.4 distingue sendero con enlaces (3) de elemento sin enlaces (2) ·
el informe ya no muestra el correo de contacto · la semilla se lee de Colab Secretos.

## Limitaciones técnicas conocidas
* E7 es permisiva: basta una palabra clave de un rubro en el inicio. Revisar `MIN_RUBROS_CONSUMO_MASIVO` y `filtro.RUBROS`.
* D8.1 mide el tiempo del último salto de la página de inicio (no incluye redirecciones previas).
* D1.4 no distingue migas de ubicación y de atributo (Instone, 2002) ni observa las de ruta.
* Google Maps: sus términos restringen la extracción automatizada; el módulo consulta robots.txt y se detiene si no se permite. Selectores CSS frágiles. **No pudo probarse fuera de la sesión real de Colab.**
* Heurísticas sobre HTML estático: no ejecutan JavaScript (SPA, catálogos dinámicos) → posibles falsos negativos en E6–E8 y en los indicadores.
* E6/E7/E8 se evalúan sobre la página de inicio: un sitio que declare «mayorista» solo en otra página queda excluido.
* D8.1 se mide desde Colab (ubicación de red distinta a la de un usuario en Argentina).
* La corrida automatizada evalúa **25 de los 32** indicadores (`Config.INCLUIR_MANUALES=False`): los 7 manuales no se generan, no se computan como ceros y no aparecen en frecuencias ni perfiles. Con `INCLUIR_MANUALES=True` se habilita `manual_plantilla.csv` y `aplicar_manual()`.
* Indicadores por dimensión: D1 5, D2 3, D3 5, D4 2, D5 2, D6 3, D7 1, D8 4 (total 25). D7 queda representada por un solo indicador (D7.3).
