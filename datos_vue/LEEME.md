# Datos de la VUE: exportaciones con certificado de origen

Copia de los archivos mensuales que publica la **Ventanilla Única de Exportación (VUE)**:
"Exportaciones con certificados de origen por categoría y país destino"
(<https://www.vue.gov.py/datos-de-exportaciones-con-certificados-de-origen-por-categoria-y-pais-destino/>).

Una carpeta por año (2011 a 2026) con un archivo Excel por mes, **tal como está en el servidor de
la VUE**, con su nombre original (copiados en noviembre de 2026). Pesan poco, por eso están
en el repositorio y no en una release.

**Origen de los datos: Ministerio de Industria y Comercio.** Datos publicados por la VUE (MIC)
como información pública (Ley N.º 5282/2014), bajo la
[Licencia abierta del Estado Paraguayo](https://datos.vue.gov.py). Los archivos se conservan
sin modificar, con sus nombres y contenidos originales. Este repositorio no está asociado al
MIC ni cuenta con su participación, patrocinio o apoyo. Contacto de la VUE para consultas sobre
los datos: datos@vue.gov.py.

## Copias en Excel ("_convertido.xlsx")

Los **22 archivos** que no son un Excel normal (2011 completo, enero a septiembre de 2018 y
febrero de 2023) tienen al lado una copia que abre en Excel sin avisos, con el sufijo
`_convertido.xlsx`. Los valores son los mismos; solo cambia el formato del archivo. Cada copia
tiene una hoja **Origen** con el nombre y el enlace del archivo original y, en 2011, la fecha de
ejecución del informe. Los originales se mantienen sin cambios, como piden las condiciones de
reutilización del MIC. Las copias se generan con `python python/convertir_vue.py`.

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
| 2011, diciembre | Otro formato de informe web (Oracle BI). Sin columna de capítulo. |
| 2013, marzo | El archivo termina en `.XLS` (mayúsculas). |
| 2018, enero a septiembre | Son `.xlsx` con extensión `.xls` (Excel avisa que el formato no coincide; se puede abrir igual). |
| 2019 y 2020 | En la VUE algunos meses también están en `.csv`, con los mismos valores que el `.xls`; aquí se dejaron solo los `.xls`. |
| 2021 a 2026 | Están en el servidor de la VUE pero la página no los enlaza. |
| 2023, febrero | No es una planilla: contiene instrucciones de base de datos (`Insert into …`). El programa lo lee igual. |
| 2022, octubre y noviembre | Contienen valores imposibles en la partida 6406 (partes de calzado) a Brasil: USD 1.078 millones por 57 t y USD 2.943 millones por 42 t, y en la 3904 (plásticos), USD 230 millones por 183 t. Inflan 2022 en unos USD 4.000 millones. Se dejan tal como vienen. |

Los 12 meses de cada año unidos en un solo Excel, con tabla dinámica y sin cambiar los valores: `docs/descargas/vue/` (también desde la página web).
