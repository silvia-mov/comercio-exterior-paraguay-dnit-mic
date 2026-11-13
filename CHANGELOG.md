# Versiones

## Sin publicar (próxima v1.1.0)

- **Excel por año para descargar** (`docs/descargas/`, `python/excel_descargas.py`): DNIT resumida por
  producto, país y acuerdo; BCP mensual; VUE con los 12 meses unidos. Calibri 10, hoja de tabla
  dinámica ya armada y hoja de notas. Los Excel de resultados también traen tabla dinámica.

- **Cruce de cuatro fuentes desde 2011** (`python/cruzar_fuentes.py`): DNIT, VUE, BCP (SICEX) y
  datos espejo de UN Comtrade; tasa de utilización anual y por país socio. Gráficos en
  `docs/figuras_cruce.py`.
- **Página web**: tasa de utilización 2011–2026, por país socio, cuatro fuentes y botones para
  descargar los resultados en Excel y CSV (`docs/datos/`, generados con `docs/datos_web.py`).
- **Productos que más usan los acuerdos** (`python/resumen_productos.py`, `python/productos_acuerdos.py`):
  por producto (4 y 8 dígitos de la NCM) y año, total, parte con acuerdo y acuerdo principal, 2011–2026;
  gráficos (`docs/figuras_productos.py`) y buscador por producto en la página.
- **Buscador "Consultá un dato"** en la página: por país y año, en lenguaje simple.
- **Gráficos por acuerdo de cada año 2011–2026** con selector de años en la página, y títulos con la conclusión.
- **Datos del BCP** (`datos_bcp/`): exportaciones mensuales 2011–2026 a 8 dígitos de la NCM, con
  lector `python/leer_bcp.py`.
- **Descarga de UN Comtrade** (`python/descargar_comtrade.py`): datos de Paraguay por mes y datos
  espejo (`--espejo`). Necesita una clave de UN Comtrade.

## v1.0.0 (noviembre de 2026)

Primera versión del código para medir el comercio exterior de Paraguay según el acuerdo
comercial usado, con los datos abiertos de la DNIT, y para compararlo con los certificados de
origen de la VUE.

### Qué incluye

| Programa | Para qué sirve | Cómo se usa |
|---|---|---|
| `python/descargar_dnit.py` | Baja los archivos mensuales "Nivel Item" de la DNIT (desde 1997) a `datos_dnit/<año>/`. Si el portal de la DNIT no responde, los baja del respaldo en las releases de este repositorio. Si un mes ya está, lo salta. | `python python/descargar_dnit.py --anios 2021` |
| `python/procesar_despachos.py` | Procesa los despachos y arma el reporte en Excel: **Totales por año** (con acuerdo, sin acuerdo, total y %), **Por acuerdo**, **Detalle** (columnas a elección) y **Control** (lo que se excluyó y por qué). | `python python/procesar_despachos.py datos_dnit --anios 2021` |
| `R/procesar_despachos.R` | Lo mismo que el anterior, en R / RStudio. Da exactamente los mismos resultados (verificado con los 12 meses de 2021). | `Rscript R/procesar_despachos.R datos_dnit --anios 2021` |
| `python/leer_vue.py` | Junta en una sola tabla los archivos mensuales de la VUE (`datos_vue/`), que vienen en cinco formatos distintos aunque todos se llamen `.xls`. | `python python/leer_vue.py` |
| `python/convertir_vue.py` | Deja al lado de cada archivo de la VUE con formato raro una copia `_convertido.xlsx` que abre en Excel sin avisos. No modifica los originales. | `python python/convertir_vue.py` |
| `python/cruzar_dnit_vue.py` | Compara, por año, país y partida, el FOB de los certificados de origen (VUE) con las exportaciones de la DNIT (total, con y sin acuerdo). | `python python/cruzar_dnit_vue.py --anios 2020-2021` |
| `docs/figuras.py` | Arma el gráfico del README a partir del reporte. | `python docs/figuras.py` |

### Configuración (se edita en Excel, sin programar)

| Archivo | Qué define |
|---|---|
| `config/regimenes.csv` | Qué regímenes aduaneros se cuentan: los **definitivos** según la tabla oficial de la DNIT (83 códigos). |
| `config/acuerdos.csv` | Cómo se agrupa cada nombre de acuerdo de la DNIT y si cuenta como *con acuerdo* o *sin acuerdo*. |
| `config/columnas.csv` | Qué columnas lleva la hoja *Detalle* (SI / NO). Por defecto, el valor en dólares (FOB en exportaciones, CIF en importaciones). |
| `config/paises_vue.csv` | Equivalencia entre los nombres de países de la VUE y el código de país de la DNIT. |

### Decisiones metodológicas principales

Todas están explicadas en el [Glosario](docs/GLOSARIO.md):

- Se cuentan solo los regímenes **definitivos** de la tabla de regímenes de la DNIT.
- Se excluyen **EFC1** (exportación complementaria) e **IFC1** (importación de fracciones
  complementarias), porque repiten el valor de un despacho principal ya contado.
- **Con acuerdo** = acuerdos preferenciales + MERCOSUR (ACE 18). **OMC**, **Sin acuerdo** y
  **Sin dato de acuerdo** se muestran por separado.
- **Valor**: FOB en exportaciones y CIF en importaciones.
- En exportaciones, solo mercadería de **origen paraguayo**.
- Los datos de la VUE se conservan **sin modificar**, como piden las condiciones de
  reutilización del Ministerio de Industria y Comercio.

### Datos

- **DNIT**: los archivos mensuales están en las releases `datos-AAAA` de este repositorio (copia de
  respaldo) y en el portal de Datos Abiertos de la DNIT.
- **VUE**: carpeta `datos_vue/` (2011 a octubre de 2026), con su `LEEME.md`.

### Requisitos

- Python 3.10 o posterior: `pip install -r python/requirements.txt`
- R 4.x (opcional): paquetes `data.table`, `jsonlite`, `writexl` y `readxl` (el script los instala si faltan).
