# Datos de la VUE: exportaciones con certificado de origen

Copia de los archivos mensuales que publica la **Ventanilla Única de Exportación (VUE)**:
"Exportaciones con certificados de origen por categoría y país destino"
(<https://www.vue.gov.py/datos-de-exportaciones-con-certificados-de-origen-por-categoria-y-pais-destino/>).

Una carpeta por año (2011 a 2026) con los archivos mensuales **tal como están en el servidor de
la VUE**, con sus nombres originales (copiados en noviembre de 2026). Pesan poco, por eso están
en el repositorio y no en una release.

Para juntarlos en una sola tabla: `python python/leer_vue.py`
(genera `salidas/VUE_certificados_origen.csv`).

## Qué contiene cada archivo

| Columna | Qué es |
|---|---|
| `ANOMES` | Año y mes en que se **emitió el certificado** (no la fecha de la exportación). |
| `CAPITULO` | Partida del producto: los 4 primeros dígitos de la NCM. No está en los archivos de 2011. |
| `CATEGORIA` | **Sector del producto** ("Cereales y oleaginosas", "Carne, cuero y demás…"). **No es el acuerdo comercial.** |
| `PAISDESTINO` | País de destino que figura en el certificado (en general, el destino final). |
| `FOBDOLAR` | Valor FOB en dólares declarado en los certificados. |
| `TONELADA` | Peso neto en toneladas. |

**Importante:** los archivos suman **todos** los certificados de origen emitidos, no solo los
que se usan para un acuerdo comercial. También incluyen certificados no preferenciales y de
preferencias unilaterales (por ejemplo, SGP). Por eso el total se parece al total exportado y
no al exportado con acuerdo. Ver el [Glosario](../docs/GLOSARIO.md#8-datos-de-la-vue-certificados-de-origen).

## Lo que conviene saber de estos archivos

| Archivo(s) | Particularidad |
|---|---|
| 2011, enero a noviembre | No son Excel "real": son páginas web guardadas como `.xls`. Sin columna de capítulo. |
| 2011, diciembre | Formato de informe web que el programa todavía no puede leer. |
| 2013, marzo | El archivo termina en `.XLS` (mayúsculas). |
| 2018, enero a julio | Son `.xlsx` con extensión `.xls` (Excel avisa que el formato no coincide; se puede abrir igual). |
| 2019 | Cada mes está dos veces, en `.xls` y en `.csv` (mismos valores). |
| 2020 | Hay 3 meses repetidos en `.csv`. |
| 2021 a 2026 | Están en el servidor de la VUE pero la página no los enlaza. |
| 2023, febrero | No es una planilla: contiene instrucciones de base de datos (`Insert into …`). El programa lo lee igual. |
| 2022, octubre y noviembre | Contienen valores imposibles en la partida 6406 (partes de calzado) a Brasil: USD 1.078 millones por 57 t y USD 2.943 millones por 42 t, y en la 3904 (plásticos), USD 230 millones por 183 t. Inflan 2022 en unos USD 4.000 millones. Se dejan tal como vienen. |
