# Glosario y decisiones metodológicas

Este documento explica **cada término, cada columna del Excel y cada decisión** que toma el
programa. Si algo del reporte no se entiende, la respuesta debería estar aquí.

**Contenido**

1. [Conceptos básicos](#1-conceptos-básicos)
2. [Con acuerdo y sin acuerdo](#2-con-acuerdo-y-sin-acuerdo)
3. [Qué despachos se cuentan y cuáles no](#3-qué-despachos-se-cuentan-y-cuáles-no)
4. [Las hojas del Excel](#4-las-hojas-del-excel)
5. [Las columnas](#5-las-columnas)
6. [Limitaciones conocidas](#6-limitaciones-conocidas)

---

## 1. Conceptos básicos

| Término | Qué significa |
|---|---|
| **DNIT** | Dirección Nacional de Ingresos Tributarios. Su Gerencia General de Aduanas publica los despachos aduaneros en [Datos Abiertos](https://www.dnit.gov.py/web/portal-institucional/datos-abiertos). |
| **Despacho** | La declaración que se presenta en la aduana para importar o exportar. Un despacho puede incluir varios productos. Cada despacho tiene un código cifrado (anónimo). |
| **Ítem** | Cada producto distinto dentro de un despacho (una posición NCM, un país de origen, etc.). Los valores se suman a nivel de ítem. |
| **Sub-ítem** | Detalle adicional de un ítem (marca, modelo). Repite los valores del ítem, por eso **no se suma** (se duplicaría). El programa usa siempre el nivel ítem. |
| **Archivo "Nivel Item"** | El archivo mensual de la DNIT con una fila por ítem. Es el que usa este repositorio. |
| **NCM** | Nomenclatura Común del MERCOSUR: el código de 8 dígitos que identifica cada producto (los 6 primeros son el Sistema Armonizado internacional). La DNIT agrega dígitos y una letra de control (p. ej. `1201.90.00.000F`). |
| **Régimen aduanero** (o destinación) | El "tipo" de operación: importación a consumo, exportación definitiva, importación temporal, ingreso a depósito, etc. Se identifica con un código de 4 letras (p. ej. `IC04`, `EC01`). |
| **FOB** (*Free On Board*) | Valor de la mercadería puesta en el medio de transporte en el país de salida, **sin flete ni seguro internacional**. Es la medida estándar para comparar exportaciones e importaciones. En dólares. |
| **CIF** (*Cost, Insurance and Freight*) | FOB + flete + seguro. Solo tiene sentido en importaciones (es el valor de la mercadería al llegar). |
| **Cotización** | Tipo de cambio guaraníes por dólar del despacho. Se usa para pasar a dólares los montos que la DNIT publica en guaraníes (tributos e imponible). |

## 2. Con acuerdo y sin acuerdo

Cada ítem trae en la columna `ACUERDO` de la DNIT el acuerdo comercial bajo el que **se pidió
la preferencia arancelaria** (si se pidió). El archivo [`config/acuerdos.csv`](../config/acuerdos.csv)
traduce los nombres de la DNIT (que cambian según el año: `MERCOCHILE`, `ACE 35`, etc.) a un
nombre único (`ACUERDO_CONSOLIDADO`) y a un **tipo**:

| Tipo | Qué incluye | ¿Cuenta como "con acuerdo"? |
|---|---|:---:|
| `MERCOSUR_INTRAZONA` | Comercio con Argentina, Brasil y Uruguay bajo el MERCOSUR (ACE 18). | ✅ |
| `PREFERENCIAL` | Acuerdos del MERCOSUR con terceros (Chile, Bolivia, Perú, Colombia, Israel, Egipto, etc.) y acuerdos ALADI (bilaterales AAP.CE 13 y 74, AAP.R 38, Preferencia Arancelaria Regional). | ✅ |
| `SIN_ACUERDO` | Sin preferencia: se pagó el arancel general (NMF / OMC). | ❌ |

**"Con acuerdo" significa que el despacho efectivamente usó la preferencia**, no solo que el
país socio tiene un acuerdo con Paraguay. Por ejemplo, una venta a Chile declarada `SIN ACUERDO`
(porque el exportador no presentó el certificado de origen) cuenta como *sin acuerdo*.

Si aparece un nombre de acuerdo que no está en `config/acuerdos.csv`, el programa lo trata como
`PREFERENCIAL`, avisa en pantalla y lo muestra en la hoja **Control** como
`Otro acuerdo (sin clasificar): ...`. Para clasificarlo, se agrega una fila al archivo.

## 3. Qué despachos se cuentan y cuáles no

La idea es contar **solo el comercio definitivo** (lo que realmente se vendió o se compró), sin
operaciones de paso ni duplicados. Las reglas, en orden:

| Regla | Por qué |
|---|---|
| **Régimen definitivo** (`incluir = SI` en [`config/regimenes.csv`](../config/regimenes.csv)) | Se excluyen operaciones que no son compra/venta definitiva: importación temporal, ingreso a depósito o a zona franca, tránsito, etc. |
| **Exportaciones solo de origen paraguayo** | Se excluyen las reexportaciones de mercadería de otro origen (opción `EXPORTACIONES_SOLO_ORIGEN_PARAGUAY`). |
| **Tipos de acuerdo incluidos** | Por defecto los tres (`PREFERENCIAL`, `MERCOSUR_INTRAZONA`, `SIN_ACUERDO`), para poder calcular el total del año. |
| **Ítems duplicados entre archivos** | Si el mismo despacho e ítem aparece dos veces (p. ej. en el archivo de ítem y en el de sub-ítem), se cuenta una vez. |
| **Regímenes desconocidos** | Si un código de régimen no está en `config/regimenes.csv`, se **excluye** y se avisa. En 2021 aparecieron `DAAB, ERR1, ET02, IDMA, IT04, MZF1, NZF1, SPA1, TLI1` (temporales, depósitos, reservas de retorno, etc.). |

### Por qué se excluyen EFC1 e IFC1

| Código | Régimen |
|---|---|
| `EFC1` | Exportación complementaria |
| `IFC1` | Importación de fracciones complementarias |

Cuando una carga grande se mueve en varios camiones, se hace **un despacho principal** (`EC01`
en exportación, `IC04` en importación) con **todos los kilos y todo el valor**, y después **un
despacho complementario por cada fracción**. Cada complementario **repite el FOB total** del
despacho principal, aunque solo lleve los kilos de su camión. Sumarlos multiplicaría el valor.

Ejemplos reales de mayo 2021:

| Caso | Despacho principal | Complementarios |
|---|---|---|
| Harina de soja a Uruguay | `EC01`: 85.000 kg, USD 35.190 | 3 `EFC1` de ~28.000 kg, **cada uno** con USD 35.190 |
| Cemento importado | `IC04`: 3.100 t, USD 192.200 | 38 `IFC1`, **cada uno** con USD 192.200 |

Con estos regímenes incluidos, las exportaciones de 2021 daban USD 23.500 millones (imposible);
sin ellos, USD 8.877 millones. El despacho principal ya trae el valor completo, así que **no se
pierde nada** al excluirlos.

## 4. Las hojas del Excel

| Hoja | Qué tiene | Para qué sirve |
|---|---|---|
| **Totales por año** | Por año y operación: con acuerdo, sin acuerdo, total y % con acuerdo. | Los gráficos de evolución. |
| **Por acuerdo** | Por año y operación, el valor de cada acuerdo. | Ver qué acuerdos se usan más. |
| **Detalle** | Las columnas elegidas en [`config/columnas.csv`](../config/columnas.csv). | Ver qué productos y a qué países. |
| **Control** | Cuántos ítems y cuánto FOB se excluyó y por qué, régimen por régimen. | Revisar que las exclusiones tengan sentido. |

## 5. Las columnas

Las columnas de valores se eligen en [`config/columnas.csv`](../config/columnas.csv) poniendo
`SI` o `NO`. Todas están en **dólares** salvo que se indique otra cosa.

### Columnas de texto (agrupan)

| Columna | Qué es |
|---|---|
| `AÑO`, `MES` | Período del despacho según la DNIT. |
| `OPERACION` | `IMPORTACION` o `EXPORTACION`. |
| `TIPO_ACUERDO` | `PREFERENCIAL`, `MERCOSUR_INTRAZONA` o `SIN_ACUERDO` (ver sección 2). |
| `ACUERDO_CONSOLIDADO` | Nombre único del acuerdo usado (ver sección 2). |
| `PAIS_PROC_DEST` | País de **procedencia** (importación) o de **destino** (exportación). |
| `PAIS_ORIGEN` | País donde se produjo la mercadería (puede diferir del de procedencia). |
| `MEDIO_TRANSPORTE` | Camión, barcaza, avión, etc. |
| `USO` | Nuevo / usado. |
| `REGIMEN`, `ADUANA` | Régimen aduanero y aduana del despacho. |
| `POSICION_NCM` | Código NCM del producto. |
| `DESCRIPCION_PRODUCTO` | Descripción de la partida según la DNIT. |

### Columnas de valores (se suman)

| Columna | Qué es | Cómo se calcula |
|---|---|---|
| `FOB_DOLAR` | Valor FOB. **Es la medida principal del reporte.** | Dato de la DNIT. |
| `CIF_DOLAR` | Valor CIF (solo importaciones; en exportaciones vale 0). | FOB + flete + seguro. |
| `PESO_NETO_KG` | Kilos netos. | Dato de la DNIT. |
| `CONTEO_DESPACHOS` | Cantidad de **despachos distintos**. | Se cuentan los códigos cifrados únicos. |
| `CONTEO_ITEMS` | Cantidad de **ítems** (un despacho con 3 productos suma 3). | Se cuentan las filas. |
| `IMPONIBLE_DOLAR` | **Valor imponible**: la base sobre la que se calculan los tributos de importación (en general, el CIF más ajustes). | La DNIT lo publica en guaraníes; se divide por la cotización del despacho. |
| `DERECHO` | **Arancel** (derecho aduanero de importación) efectivamente pagado. Con un acuerdo suele ser menor o cero. | Guaraníes ÷ cotización. |
| `TRIBUTOS_INTERNOS` | Otros tributos cobrados en la aduana: IVA, ISC (selectivo al consumo), tasa de servicio, anticipo de renta y otros. | Suma de esos tributos, en guaraníes ÷ cotización. |
| `TOTAL_TRIBUTOS` | Todo lo pagado en la aduana. | `DERECHO` + `TRIBUTOS_INTERNOS`. |

### Columnas en porcentaje

Muestran **cuánto se pagó por cada 100 dólares importados**. Sirven para ver, por ejemplo, si
las importaciones con acuerdo pagan menos arancel que las sin acuerdo.

| Columna | Cálculo |
|---|---|
| `PRESION_ARANCELARIA_EFECTIVA_PCT` | `DERECHO` ÷ `IMPONIBLE_DOLAR` × 100 |
| `PRESION_INTERNA_EFECTIVA_PCT` | `TRIBUTOS_INTERNOS` ÷ `IMPONIBLE_DOLAR` × 100 |
| `PRESION_TRIBUTARIA_TOTAL_PCT` | `TOTAL_TRIBUTOS` ÷ `IMPONIBLE_DOLAR` × 100 |

Se llaman "efectivas" porque usan lo **realmente pagado**, no el arancel teórico del AEC.

### Columnas de la hoja "Totales por año"

| Columna | Qué es |
|---|---|
| `FOB_DOLAR_CON_ACUERDO` | FOB de los despachos con tipo `PREFERENCIAL` o `MERCOSUR_INTRAZONA`. |
| `FOB_DOLAR_SIN_ACUERDO` | FOB de los despachos `SIN_ACUERDO`. |
| `FOB_DOLAR_TOTAL` | Con acuerdo + sin acuerdo. |
| `FOB_DOLAR_CON_ACUERDO_PCT` | Con acuerdo ÷ total × 100. |

(Si en `config/columnas.csv` se elige otra medida, por ejemplo `CIF_DOLAR`, aparecen las mismas
cuatro columnas para esa medida.)

## 6. Limitaciones conocidas

- **Electricidad.** La energía de Itaipú y Yacyretá no pasa por estos despachos. Para comparar
  con el Banco Central del Paraguay (BCP), usar las cifras del BCP **sin energía eléctrica**.
- **El acuerdo es el declarado.** Se usa el acuerdo que figura en el despacho. Si la aduana
  luego rechazó la preferencia, el dato de datos abiertos puede no reflejarlo.
- **Nombres de países y acuerdos.** La DNIT los escribe distinto según el año; las tablas de
  `config/` los unifican, pero conviene revisar la hoja **Control** cada vez que se agrega un año.
- **Cifras preliminares.** Los datos abiertos pueden corregirse después de publicados.
