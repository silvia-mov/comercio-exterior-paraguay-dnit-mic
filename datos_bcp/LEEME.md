# Datos del BCP: comercio exterior mensual (SICEX)

Reportes del **Sistema Informático de Comercio Exterior (SICEX)** del Banco Central del Paraguay
(<https://apps.bcp.gov.py:8444/>), de acceso público y gratuito. Una carpeta por año con el
reporte tal como lo exporta el SICEX.

**Fuente: Banco Central del Paraguay (BCP), SICEX.** Este repositorio no está asociado al BCP ni
cuenta con su participación o apoyo.

## Cómo se bajó cada archivo

| Paso del SICEX | Elección |
|---|---|
| 1 | Exportaciones · SA – Sistema Armonizado |
| 2 | Todos los productos |
| 3 | Todos los países |
| 4 | Mensual, de enero a diciembre de un año · Kilos netos y dólares FOB · Mostrar producto a 8 dígitos (NCM) · Mostrar origen/destino |

Formato: texto separado por tabulaciones (UTF-8). Una fila por código NCM de 8 dígitos y país,
con dos columnas por mes (kilos netos y FOB en dólares) y el total del año. La última fila es el
total general.

| Archivo | Contenido | Fecha de descarga |
|---|---|---|
| `2024/BCP_DATOS_MENSUALES_2024_A_8D.csv` | Exportaciones 2024, enero a diciembre | noviembre de 2026 |
| `2025/BCP_DATOS_MENSUALES_2025_A_8D.csv` | Exportaciones 2025, enero a diciembre | noviembre de 2026 |

## Lo que hay que saber antes de usarlos

Según la *Nota técnica metodológica de elaboración de las estadísticas de comercio exterior* del BCP:

- **Incluye la electricidad** (NCM 2716) de Itaipú, Yacyretá y la ANDE, que no pasa por la
  aduana. En 2025: USD 1.212 millones de un total de 11.073 millones.
- **Incluye todos los regímenes aduaneros** (maquila, zonas francas, courier, turismo y otros),
  no solo los definitivos.
- **El país de destino es el del certificado de origen** de la VUE cuando existe (desde 2013,
  corregido hacia atrás hasta 2006), no el declarado en el despacho. Por eso Argentina y Uruguay
  pesan menos que en los datos abiertos de la DNIT: muchas exportaciones pasan por sus puertos
  hacia otros destinos.
- **Los datos son preliminares durante dos años.** En las exportaciones, lo que cambia es sobre
  todo el destino (cuando llega el certificado de origen); el valor y el volumen totales no
  deberían cambiar. Por eso cada archivo indica la fecha de descarga: si se vuelve a bajar un
  año reciente, puede diferir.
- Fecha de registro: la de cancelación del despacho, igual que en los datos abiertos de la DNIT.
