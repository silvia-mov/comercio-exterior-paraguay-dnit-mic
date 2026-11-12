# Datos de UN Comtrade: datos espejo

**Fuente: UN Comtrade** (División de Estadística de las Naciones Unidas), <https://comtradeplus.un.org>.

## Qué hay

`espejo/Comtrade_espejo_PRY_<año>_AG6.csv`, de 2011 a 2025: lo que **cada país declara haber
importado desde Paraguay**, por año, país informante y producto (6 dígitos del Sistema Armonizado).
Es la única fuente del repositorio que no sale de documentos paraguayos: sirve para comparar con
la DNIT, la VUE y el BCP (ver `python/cruzar_fuentes.py`).

| Columna | Qué es |
|---|---|
| `AÑO` | año |
| `PAIS_CODIGO_ISO2`, `PAIS_CODIGO_ISO3`, `PAIS` | el país que compra (el que informa a Comtrade) |
| `PARTIDA` | código del Sistema Armonizado, 6 dígitos |
| `VALOR_DOLAR` | valor de la importación en dólares, CIF (incluye flete y seguro hasta el país comprador) |
| `FOB_DOLAR`, `CIF_DOLAR` | valores FOB y CIF, cuando el país los informa |
| `PESO_NETO_KG` | peso neto, cuando se informa |
| `CLASIFICACION` | versión del Sistema Armonizado que usó el país |

Son los registros originales de UN Comtrade, sin transformar (71.122 registros en total).
Fecha de descarga: ver `espejo/descarga.txt`.

## Para tener en cuenta

- El valor está en **CIF**, por eso suele ser algo mayor que el FOB que registra Paraguay.
- Cada país informa con su propio calendario: **el último año suele estar incompleto**
  (faltan países por informar) y los datos pueden corregirse después.
- Las diferencias entre lo que exporta un país y lo que su socio dice importar son normales
  (fechas, valoración, destino final, tránsito). Ver la ayuda de UN Comtrade sobre
  "bilateral asymmetries".

## Condiciones de uso

Se publican según la política de redifusión de UN Comtrade, que permite ofrecer gratuitamente hasta
100.000 registros originales. Si los usa, cite **"Fuente: UN Comtrade"**. Para obtener más datos,
use `python/descargar_comtrade.py --espejo` con su propia clave de UN Comtrade (la gratuita alcanza).
Los datos mensuales informados por Paraguay **no** se publican aquí: superan ese límite y son los
mismos que publica el BCP (ver `datos_bcp/`).
