# ==============================================================================
# Procesamiento de despachos aduaneros de la DNIT (Paraguay) - versión R
# ==============================================================================
# Filtra el comercio exterior de Paraguay por ACUERDO COMERCIAL y genera
# estadísticas agregadas (valores FOB/CIF, tributos y presión tributaria).
#
# Uso en RStudio: abra el proyecto "paraguay-comercio-dnit.Rproj" (así el
# directorio de trabajo es la raíz del repositorio), edite RUTA_DATOS y
# ejecute el script completo (Ctrl + Shift + S / botón "Source").
#
# Uso por consola:  Rscript R/procesar_despachos.R "C:/mis_datos/dnit"
#                   Rscript R/procesar_despachos.R datos_dnit --anios 2019-2021 --meses enero,febrero
#
# Las columnas del Excel final ("Detalle") se eligen en config/columnas.csv (SI / NO).
# Definiciones y decisiones: docs/GLOSARIO.md
#
# Acepta los archivos tal como los descarga la DNIT (JSON "nivel item" y
# "nivel sub item") y también CSV / XLSX / Parquet ya aplanados.
# Los valores siempre se toman a nivel ITEM: los sub-items solo detallan la
# mercadería y no se suman (sumarlos duplicaría los montos).
# ==============================================================================

paquetes <- c("data.table", "jsonlite", "writexl", "readxl")
faltantes <- paquetes[!vapply(paquetes, requireNamespace, logical(1), quietly = TRUE)]
if (length(faltantes) > 0) install.packages(faltantes)
library(data.table)

options(scipen = 999)

# ==============================================================================
# 1. CONFIGURACIÓN  <-- EDITE AQUÍ
# ==============================================================================

# Carpeta con los archivos descargados de la DNIT. Puede ser relativa a la raíz
# del repositorio o absoluta, p. ej. "C:/Users/usuario/Descargas/dnit"
# (en Windows use "/" o "\\" en la ruta, no una sola "\").
RUTA_DATOS <- "datos_dnit"

# Carpeta donde se guardan los resultados.
RUTA_SALIDAS <- "salidas"

# Años y meses a juntar. ANIOS <- NULL junta todos los años de la carpeta.
# Ejemplos: ANIOS <- 2021   ANIOS <- 2019:2021
#           MESES_ELEGIDOS <- "TODOS"   MESES_ELEGIDOS <- c("ENERO", "FEBRERO")
# También se pueden pasar por consola: --anios 2019-2021 --meses enero,febrero
ANIOS <- NULL
MESES_ELEGIDOS <- "TODOS"

# Tipos de acuerdo (columna "tipo" de config/acuerdos.csv) que se conservan.
# - PREFERENCIAL: comercio negociado bajo un acuerdo comercial.
# - SIN_ACUERDO: comercio sin preferencia (OMC / NMF), útil como comparación.
# - MERCOSUR_INTRAZONA: comercio intra-MERCOSUR (ACE 18).
# Para analizar SOLO lo negociado por acuerdo, deje únicamente "PREFERENCIAL".
TIPOS_ACUERDO_INCLUIDOS <- c("PREFERENCIAL", "MERCOSUR_INTRAZONA", "SIN_ACUERDO")

# "Con acuerdo" = comercio que usó una preferencia (ver docs/GLOSARIO.md).
TIPOS_CON_ACUERDO <- c("PREFERENCIAL", "MERCOSUR_INTRAZONA")

# En exportaciones, conservar solo mercadería de origen paraguayo
# (excluye reexportaciones de bienes de otro origen).
EXPORTACIONES_SOLO_ORIGEN_PARAGUAY <- TRUE

# ==============================================================================

args <- commandArgs(trailingOnly = TRUE)
valor_opcion <- function(nombre) {
  i <- which(args == nombre)
  if (length(i) > 0 && i[1] < length(args)) args[i[1] + 1] else NULL
}
opcion_anios <- valor_opcion("--anios")
opcion_meses <- valor_opcion("--meses")
posicionales <- args[!(args %in% c("--anios", "--meses", opcion_anios, opcion_meses))]
if (length(posicionales) > 0) RUTA_DATOS <- posicionales[1]

RUTA_CONFIG <- "config"
if (!dir.exists(RUTA_CONFIG)) {
  stop("No se encuentra la carpeta 'config'. Abra 'paraguay-comercio-dnit.Rproj' o ejecute ",
       "setwd(\"ruta/al/repositorio\") antes de correr el script.")
}
LIMITE_FILAS_EXCEL <- 1048575

MESES <- c(
  ENERO = 1, FEBRERO = 2, MARZO = 3, ABRIL = 4, MAYO = 5, JUNIO = 6,
  JULIO = 7, AGOSTO = 8, SEPTIEMBRE = 9, SETIEMBRE = 9, OCTUBRE = 10,
  NOVIEMBRE = 11, DICIEMBRE = 12,
  ENE = 1, FEB = 2, MAR = 3, ABR = 4, MAY = 5, JUN = 6,
  JUL = 7, AGO = 8, SEP = 9, SET = 9, OCT = 10, NOV = 11, DIC = 12
)
NUM_A_MES <- c("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
               "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")

# Nombre canónico -> posibles nombres en los archivos. La comparación ignora
# mayúsculas, espacios, guiones, puntos y guiones bajos, por lo que
# "codRegimen", "COD_REGIMEN" y "Cod. Regimen" se reconocen igual.
# Se usa el primer sinónimo que exista en el archivo.
SINONIMOS <- list(
  DESPACHO_CIFRADO = c("despachoCifrado", "DESPACHO", "DESPACH_CIFRADO"),
  ITEM = c("itemInterno", "itemExterno", "ITEM", "NRO_ITEM"),
  OPERACION = c("operacion", "TIPO_OPERACION", "OPERAC"),
  COD_REGIMEN = c("codRegimen", "DESTINACION", "COD_DESTINACION", "DESTINAC"),
  REGIMEN = c("regimen", "REGIMEN_ADUANERO"),
  ACUERDO = c("acuerdoAjustado", "ACUERDO", "ACUERDO_COMERCIAL", "TRATADO"),
  ANIO = c("anio", "A\u00d1O", "ANO", "YEAR"),
  MES = c("mes", "MONTH"),
  ADUANA = c("aduanaDespacho", "ADUANA"),
  PAIS_ORIGEN = c("paisOrigenAjustado", "PAIS_ORIGEN", "PAIS_DE_ORIGEN", "ORIGEN"),
  PAIS_PROC_DEST = c("paisProcDestinoAjustado", "PAIS_PROCEDENCIA_DESTINO", "PAIS_PROC_DEST",
                     "PAIS_PROCEDENCIA", "PAIS_DESTINO"),
  MEDIO_TRANSPORTE = c("medioTransporte", "MEDIO_DE_TRANSPORTE", "TRANSPORTE"),
  USO = c("usoAjustado", "USO"),
  POSICION_NCM = c("posicionAjustado", "POSICION_NCM", "POSICION", "NCM", "CODIGO_NCM"),
  DESC_POSICION = c("descripcionAjustado", "DESC_POSICION", "DESCRIPCION_POSICION", "DESCRIPCION"),
  DESC_PARTIDA = c("despartidaAjustado", "DESC_PARTIDA", "DESCRIPCION_PARTIDA"),
  PESO_NETO_KG = c("pesoNeto", "KILO_NETO", "PESO_NETO"),
  FOB_DOLAR = c("fobDolarAjustado", "FOB_DOLAR", "FOB_USD", "FOB"),
  FLETE_DOLAR = c("fleteDolarAjustado", "FLETE_DOLAR", "FLETE_USD", "FLETE"),
  SEGURO_DOLAR = c("seguroDolarAjustado", "SEGURO_DOLAR", "SEGURO_USD", "SEGURO"),
  IMPONIBLE_GS = c("imponibleGsAjustado", "IMPONIBLE_GS"),
  IMPONIBLE_DOLAR = c("IMPONIBLE_DOLAR", "IMPONIBLE_USD"),
  DERECHO = c("derecho", "DERECHOS", "DERECHO_ADUANERO"),
  IVA = c("iva"),
  ISC = c("isc"),
  SERVICIO = c("servicio", "TASA_SERVICIO"),
  RENTA = c("renta", "ANTICIPO_RENTA"),
  OTROS = c("otros", "OTROS_TRIBUTOS"),
  COTIZACION = c("cotizacion", "TIPO_CAMBIO", "TIPO_DE_CAMBIO")
)

COLUMNAS_TEXTO <- c("DESPACHO_CIFRADO", "ITEM", "OPERACION", "COD_REGIMEN", "REGIMEN", "ACUERDO", "ANIO",
                    "MES", "ADUANA", "PAIS_ORIGEN", "PAIS_PROC_DEST", "MEDIO_TRANSPORTE", "USO",
                    "POSICION_NCM", "DESC_POSICION", "DESC_PARTIDA")
# Montos en Gs. que se convierten a USD dividiendo por la cotización del despacho.
TRIBUTOS_GS <- c("DERECHO", "IVA", "ISC", "SERVICIO", "RENTA", "OTROS")
COLUMNAS_NUMERICAS <- c("PESO_NETO_KG", "FOB_DOLAR", "FLETE_DOLAR", "SEGURO_DOLAR",
                        "IMPONIBLE_GS", "IMPONIBLE_DOLAR", "COTIZACION", TRIBUTOS_GS)

DIMENSIONES_RESUMEN <- c("OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO", "ANIO_INT", "MES_NUM",
                         "PAIS_ORIGEN", "PAIS_PROC_DEST", "MEDIO_TRANSPORTE", "USO")
DIMENSIONES_DETALLE <- c(DIMENSIONES_RESUMEN, "POSICION_NCM", "DESCRIPCION_PRODUCTO")
DIMENSIONES_ACUERDO <- c("ANIO_INT", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO")
MEDIDAS <- c("VALOR_DOLAR", "PESO_NETO_KG", "FOB_DOLAR", "CIF_DOLAR", "IMPONIBLE_DOLAR",
             "DERECHO", "TRIBUTOS_INTERNOS", "TOTAL_TRIBUTOS")

# Columnas que pueden elegirse en config/columnas.csv (nombre en el CSV -> nombre interno)
DIMENSIONES_ELEGIBLES <- c(ANIO = "ANIO_INT", MES = "MES_NUM", OPERACION = "OPERACION",
                           TIPO_ACUERDO = "TIPO_ACUERDO", ACUERDO_CONSOLIDADO = "ACUERDO_CONSOLIDADO",
                           PAIS_PROC_DEST = "PAIS_PROC_DEST", PAIS_ORIGEN = "PAIS_ORIGEN",
                           MEDIO_TRANSPORTE = "MEDIO_TRANSPORTE", USO = "USO", REGIMEN = "REGIMEN",
                           ADUANA = "ADUANA", POSICION_NCM = "POSICION_NCM",
                           DESCRIPCION_PRODUCTO = "DESCRIPCION_PRODUCTO")
MEDIDAS_ELEGIBLES <- c(MEDIDAS, "CONTEO_DESPACHOS", "CONTEO_ITEMS", "PRESION_ARANCELARIA_EFECTIVA_PCT",
                       "PRESION_INTERNA_EFECTIVA_PCT", "PRESION_TRIBUTARIA_TOTAL_PCT")

# Normaliza un nombre de columna para compararlo: sin tildes ni separadores.
clave <- function(x) {
  s <- iconv(enc2utf8(as.character(x)), from = "UTF-8", to = "ASCII//TRANSLIT", sub = "")
  gsub("[^A-Z0-9]", "", toupper(s))
}

normalizar_texto <- function(x) {
  s <- as.character(x)
  s[is.na(s)] <- ""
  toupper(gsub("\\s+", " ", trimws(s)))
}

# Convierte texto a número aceptando "1234.5", "1234,5" y "1.234,5".
a_numero <- function(x) {
  if (is.numeric(x)) {
    v <- as.numeric(x)
  } else {
    s <- trimws(as.character(x))
    s[is.na(s)] <- ""
    ambos <- grepl(",", s, fixed = TRUE) & grepl(".", s, fixed = TRUE)
    s[ambos] <- gsub(".", "", s[ambos], fixed = TRUE)
    v <- suppressWarnings(as.numeric(gsub(",", ".", s, fixed = TRUE)))
  }
  v[is.na(v)] <- 0
  v
}

# Columnas marcadas con SI en config/columnas.csv, en el orden del archivo.
cargar_columnas <- function() {
  ruta <- file.path(RUTA_CONFIG, "columnas.csv")
  if (!file.exists(ruta)) return(list(dims = names(DIMENSIONES_ELEGIBLES), medidas = MEDIDAS_ELEGIBLES))
  cfg <- fread(ruta, colClasses = "character", na.strings = NULL, encoding = "UTF-8")
  elegidas <- clave(cfg[normalizar_texto(incluir) == "SI", columna])  # "AÑO" -> "ANO"
  elegidas[elegidas == "ANO"] <- "ANIO"
  conocidas <- c(names(DIMENSIONES_ELEGIBLES), MEDIDAS_ELEGIBLES)
  desconocidas <- elegidas[!(elegidas %in% clave(conocidas))]
  if (length(desconocidas) > 0) cat("AVISO: columnas desconocidas en config/columnas.csv (se ignoran):",
                                    paste(desconocidas, collapse = ", "), "\n")
  dims <- names(DIMENSIONES_ELEGIBLES)[match(elegidas, clave(names(DIMENSIONES_ELEGIBLES)))]
  medidas <- MEDIDAS_ELEGIBLES[match(elegidas, clave(MEDIDAS_ELEGIBLES))]
  dims <- dims[!is.na(dims)]; medidas <- medidas[!is.na(medidas)]
  if (length(dims) == 0 || length(medidas) == 0) {
    stop("config/columnas.csv debe tener al menos una columna de texto (p. ej. A\u00d1O) ",
         "y una de valores (p. ej. VALOR_DOLAR) con SI.")
  }
  list(dims = dims, medidas = medidas)
}

# "2021" -> 2021; "2019-2021" -> 2019:2021; "2019,2021" -> c(2019, 2021)
leer_rango_anios <- function(texto) {
  partes <- strsplit(gsub(" ", "", texto), ",")[[1]]
  anios <- unlist(lapply(partes, function(p) {
    if (grepl("-", p)) { ab <- as.integer(strsplit(p, "-")[[1]]); seq(min(ab), max(ab)) } else as.integer(p)
  }))
  sort(unique(anios[!is.na(anios)]))
}

leer_meses <- function(x) {
  if (is.null(x) || length(x) == 0 || toupper(trimws(x[1])) %in% c("", "TODOS")) return("TODOS")
  partes <- toupper(trimws(unlist(strsplit(x, ","))))
  n <- ifelse(partes %in% names(MESES), MESES[partes], suppressWarnings(as.integer(partes)))
  if (any(is.na(n))) stop("Mes no reconocido: ", paste(partes[is.na(n)], collapse = ", "))
  sort(unique(as.integer(n)))
}

# Usa el nombre del archivo de la DNIT (p. ej. 2021_ENERO_Nivel_Item.csv) para no abrir
# archivos de otros períodos. Si el nombre no sigue ese patrón, se lee igual.
archivo_en_periodo <- function(ruta, anios, meses) {
  m <- regmatches(toupper(basename(ruta)), regexec("^([0-9]{4})_([A-Z]+)", toupper(basename(ruta))))[[1]]
  if (length(m) == 0) return(TRUE)
  anio <- as.integer(m[2]); mes <- unname(MESES[m[3]])
  if (!is.null(anios) && !(anio %in% anios)) return(FALSE)
  if (!identical(meses, "TODOS") && !is.na(mes) && !(mes %in% meses)) return(FALSE)
  TRUE
}

cargar_config <- function() {
  reg <- fread(file.path(RUTA_CONFIG, "regimenes.csv"), colClasses = "character",
               na.strings = NULL, encoding = "UTF-8")
  reg[, codigo := normalizar_texto(codigo)]
  acu <- fread(file.path(RUTA_CONFIG, "acuerdos.csv"), colClasses = "character",
               na.strings = NULL, encoding = "UTF-8")
  acu[, acuerdo_dnit := normalizar_texto(acuerdo_dnit)]
  acu <- unique(acu, by = "acuerdo_dnit")
  list(regimenes_si = reg[normalizar_texto(incluir) == "SI", codigo],
       regimenes_conocidos = reg$codigo,
       acuerdos = acu)
}

# ------------------------------------------------------------------------------
# 2. LECTURA
# ------------------------------------------------------------------------------

# Lee el JSON de la DNIT (despachos -> items -> subitems) y devuelve una fila por item.
leer_json <- function(ruta) {
  raw <- tryCatch(
    jsonlite::fromJSON(ruta, simplifyVector = TRUE),
    error = function(e) stop("JSON inválido o incompleto (", conditionMessage(e), "). ",
                             "Si el archivo se copió a mano puede estar cortado; ",
                             "la versión Python recupera los despachos completos.")
  )
  if (!is.data.frame(raw) || !("items" %in% names(raw))) stop("estructura JSON no reconocida")

  atomicas <- function(df) df[, vapply(df, is.atomic, logical(1)), drop = FALSE]
  n <- vapply(raw$items, function(x) if (is.data.frame(x)) nrow(x) else 0L, integer(1))
  items <- rbindlist(lapply(raw$items[n > 0], atomicas), fill = TRUE)
  cabecera <- as.data.table(atomicas(raw))[rep(seq_len(nrow(raw)), n)]
  cbind(cabecera, items)
}

# Columnas del archivo que corresponden a algún nombre de SINONIMOS.
columnas_utiles <- function(columnas) {
  claves <- clave(unlist(lapply(names(SINONIMOS), function(k) c(k, SINONIMOS[[k]]))))
  columnas[clave(columnas) %in% claves]
}

# Lee un CSV grande solo con las columnas necesarias. El CSV "nivel sub item" de
# la DNIT trae una fila por sub-item con los valores del item repetidos; se deja
# una sola fila por despacho + item.
leer_csv <- function(ruta) {
  columnas <- names(fread(ruta, nrows = 0, encoding = "UTF-8"))
  usar <- columnas_utiles(columnas)
  dt <- fread(ruta, select = usar, colClasses = "character", encoding = "UTF-8", na.strings = NULL)
  # Comillas dobles escapadas ("") dentro de los textos: se dejan como una sola, igual que Python.
  for (col in names(dt)) set(dt, j = col, value = gsub('""', '"', dt[[col]], fixed = TRUE))
  claves_item <- usar[clave(usar) %in% clave(c("DESPACHO_CIFRADO", "ITEM"))]
  if (length(claves_item) == 2) dt <- unique(dt, by = claves_item)
  dt
}

leer_archivo <- function(ruta) {
  ext <- tolower(tools::file_ext(ruta))
  switch(ext,
    json = , txt = leer_json(ruta),
    csv = leer_csv(ruta),
    xlsx = as.data.table(readxl::read_excel(ruta, col_types = "text")),
    parquet = as.data.table(arrow::read_parquet(ruta)),
    stop("Formato no soportado: ", ext)
  )
}

# Renombra las columnas al nombre canónico y crea las que falten.
estandarizar_columnas <- function(dt) {
  claves <- clave(names(dt))
  origen <- character(0)
  for (canonico in names(SINONIMOS)) {
    for (s in c(canonico, SINONIMOS[[canonico]])) {
      idx <- which(claves == clave(s))
      if (length(idx) > 0 && !(names(dt)[idx[1]] %in% origen)) {
        origen[canonico] <- names(dt)[idx[1]]
        break
      }
    }
  }
  dt <- dt[, unname(origen), with = FALSE]
  setnames(dt, names(origen))

  for (col in COLUMNAS_TEXTO) {
    set(dt, j = col, value = if (col %in% names(dt)) normalizar_texto(dt[[col]]) else "")
  }
  for (col in COLUMNAS_NUMERICAS) {
    set(dt, j = col, value = if (col %in% names(dt)) a_numero(dt[[col]]) else 0)
  }
  dt
}

# ------------------------------------------------------------------------------
# 3. FILTROS Y CÁLCULOS
# ------------------------------------------------------------------------------

transformar <- function(dt, cfg) {
  acu <- cfg$acuerdos
  dt[, ACUERDO := normalizar_texto(ACUERDO)]
  idx <- match(dt$ACUERDO, acu$acuerdo_dnit)
  dt[, ACUERDO_SIN_CLASIFICAR := is.na(idx)]
  dt[, ACUERDO_CONSOLIDADO := ifelse(is.na(idx), paste0("Otro acuerdo (sin clasificar): ", ACUERDO),
                                     acu$acuerdo_consolidado[idx])]
  dt[, TIPO_ACUERDO := ifelse(is.na(idx), "PREFERENCIAL", acu$tipo[idx])]

  es_imp <- startsWith(dt$OPERACION, "IMP")
  es_exp <- startsWith(dt$OPERACION, "EXP")
  origen_py <- grepl("PARAGUAY", dt$PAIS_ORIGEN, fixed = TRUE) | dt$PAIS_ORIGEN == "PY"

  dt[, MOTIVO_EXCLUSION := ""]
  reglas <- list(
    list(!(es_imp | es_exp), "Operaci\u00f3n no reconocida"),
    list(!(dt$COD_REGIMEN %in% cfg$regimenes_si), "R\u00e9gimen no definitivo"),
    list(es_exp & !origen_py & EXPORTACIONES_SOLO_ORIGEN_PARAGUAY, "Exportaci\u00f3n de origen no paraguayo"),
    list(!(dt$TIPO_ACUERDO %in% TIPOS_ACUERDO_INCLUIDOS), "Tipo de acuerdo excluido")
  )
  for (r in reglas) dt[r[[1]] & MOTIVO_EXCLUSION == "", MOTIVO_EXCLUSION := r[[2]]]

  # Cotización Gs/USD del despacho; se protege contra ceros y vacíos.
  cot <- ifelse(dt$COTIZACION > 0, dt$COTIZACION, NA_real_)
  for (col in TRIBUTOS_GS) {
    v <- dt[[col]] / cot
    v[is.na(v)] <- 0
    set(dt, j = col, value = v)
  }
  # El imponible de la DNIT viene en Gs.; si el archivo ya trae USD se respeta.
  imp_gs <- dt$IMPONIBLE_GS / cot
  imp_gs[is.na(imp_gs)] <- 0
  dt[, IMPONIBLE_DOLAR := ifelse(IMPONIBLE_DOLAR > 0, IMPONIBLE_DOLAR, imp_gs)]
  dt[, CIF_DOLAR := ifelse(es_imp, FOB_DOLAR + FLETE_DOLAR + SEGURO_DOLAR, 0)]
  # Valor del comercio según la convención habitual: exportaciones FOB, importaciones CIF.
  dt[, VALOR_DOLAR := ifelse(es_imp, CIF_DOLAR, FOB_DOLAR)]
  dt[, TRIBUTOS_INTERNOS := IVA + ISC + SERVICIO + RENTA + OTROS]
  dt[, TOTAL_TRIBUTOS := DERECHO + TRIBUTOS_INTERNOS]

  dt[, DESCRIPCION_PRODUCTO := ifelse(DESC_PARTIDA != "", DESC_PARTIDA, DESC_POSICION)]
  mes <- unname(MESES[dt$MES])
  mes[is.na(mes)] <- suppressWarnings(as.integer(dt$MES[is.na(mes)]))
  mes[is.na(mes)] <- 13L
  dt[, MES_NUM := as.integer(mes)]
  anio <- suppressWarnings(as.integer(dt$ANIO))
  anio[is.na(anio)] <- 9999L
  dt[, ANIO_INT := anio]
  dt
}

agregar <- function(dt, dims) {
  out <- dt[, c(list(CONTEO_DESPACHOS = uniqueN(DESPACHO_CIFRADO), CONTEO_ITEMS = .N),
                lapply(.SD, sum)),
            by = dims, .SDcols = MEDIDAS]
  imp <- out$IMPONIBLE_DOLAR
  pct <- function(num) ifelse(imp > 0, num / imp * 100, 0)
  out[, PRESION_ARANCELARIA_EFECTIVA_PCT := pct(DERECHO)]
  out[, PRESION_INTERNA_EFECTIVA_PCT := pct(TRIBUTOS_INTERNOS)]
  out[, PRESION_TRIBUTARIA_TOTAL_PCT := pct(TOTAL_TRIBUTOS)]

  if ("ANIO_INT" %in% names(out)) out[, ANIO := ANIO_INT]
  if ("MES_NUM" %in% names(out)) {
    out[, MES := ifelse(MES_NUM %in% 1:12, NUM_A_MES[pmin(MES_NUM, 12L)], "S/D")]
  }
  orden <- intersect(c("ANIO_INT", "MES_NUM", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO"), names(out))
  setorderv(out, orden, order = ifelse(orden == "ANIO_INT", -1L, 1L))

  primeras <- intersect(c("ANIO", "MES"), names(out))
  resto <- setdiff(dims, c("ANIO_INT", "MES_NUM"))
  final <- c(primeras, resto, setdiff(names(out), c(primeras, resto, dims)))
  out[, final, with = FALSE]
}

# Por año y operación: con acuerdo, sin acuerdo, total y % con acuerdo (para gráficos).
totales_por_anio <- function(dt, medidas) {
  medidas <- medidas[!grepl("_PCT$", medidas) & !startsWith(medidas, "CONTEO")]
  d <- dt[, c("ANIO_INT", "OPERACION", "TIPO_ACUERDO", medidas), with = FALSE]
  d[, CON := TIPO_ACUERDO %in% TIPOS_CON_ACUERDO]
  out <- unique(d[, .(ANIO = ANIO_INT, OPERACION)])
  for (m in medidas) {
    t <- d[, .(con = sum(get(m)[CON]), sin = sum(get(m)[!CON])), by = .(ANIO = ANIO_INT, OPERACION)]
    t[, total := con + sin]
    t[, pct := ifelse(total > 0, con / total * 100, 0)]
    setnames(t, c("con", "sin", "total", "pct"),
             paste0(m, c("_CON_ACUERDO", "_SIN_ACUERDO", "_TOTAL", "_CON_ACUERDO_PCT")))
    out <- merge(out, t, by = c("ANIO", "OPERACION"))
  }
  setorder(out, ANIO, OPERACION)
  out
}

# ------------------------------------------------------------------------------
# 4. EXPORTACIÓN
# ------------------------------------------------------------------------------

exportar <- function(hojas, detalle, carpeta) {
  # Las columnas usan "ANIO" internamente (ASCII) para evitar problemas de
  # codificación en R; en el reporte se publica como "AÑO".
  a_anio <- function(h) setnames(copy(h), "ANIO", "A\u00d1O", skip_absent = TRUE)
  hojas <- lapply(hojas, a_anio)
  detalle <- a_anio(detalle)
  dir.create(carpeta, showWarnings = FALSE, recursive = TRUE)
  ruta_excel <- file.path(carpeta, "Reporte_Comercio_Paraguay_Acuerdos.xlsx")
  if (nrow(detalle) <= LIMITE_FILAS_EXCEL) {
    hojas[["Detalle"]] <- detalle
  } else if (requireNamespace("arrow", quietly = TRUE)) {
    ruta_det <- file.path(carpeta, "Detalle_Paraguay.parquet")
    arrow::write_parquet(detalle, ruta_det)
    cat("El detalle supera el límite de filas de Excel; se guardó en:", ruta_det, "\n")
  } else {
    ruta_det <- file.path(carpeta, "Detalle_Paraguay.csv.gz")
    fwrite(detalle, ruta_det)
    cat("El detalle supera el límite de filas de Excel; se guardó en:", ruta_det, "\n")
  }
  writexl::write_xlsx(hojas, ruta_excel)
  cat("Reporte generado:", ruta_excel, "\n")
}

# ------------------------------------------------------------------------------
# 5. PROGRAMA PRINCIPAL
# ------------------------------------------------------------------------------

cat("=== Pipeline de Comercio Exterior DNIT Paraguay ===\n")
anios <- if (!is.null(opcion_anios)) leer_rango_anios(opcion_anios) else if (!is.null(ANIOS)) sort(ANIOS) else NULL
meses <- leer_meses(if (!is.null(opcion_meses)) opcion_meses else MESES_ELEGIDOS)
columnas <- cargar_columnas()
cat("Carpeta de datos:", RUTA_DATOS, "\n")
cat("A\u00f1os:", if (is.null(anios)) "todos" else paste(anios, collapse = ", "),
    "| Meses:", if (identical(meses, "TODOS")) "TODOS" else paste(NUM_A_MES[meses], collapse = ", "), "\n")
if (!dir.exists(RUTA_DATOS)) dir.create(RUTA_DATOS, recursive = TRUE)

archivos <- list.files(RUTA_DATOS, pattern = "\\.(json|txt|csv|xlsx|parquet)$",
                       full.names = TRUE, recursive = TRUE, ignore.case = TRUE)
archivos <- archivos[vapply(archivos, archivo_en_periodo, logical(1), anios = anios, meses = meses)]

if (length(archivos) == 0) {
  cat("No se encontraron archivos (.json, .txt, .csv, .xlsx, .parquet).\n",
      "Coloque los archivos de la DNIT en esa carpeta o edite RUTA_DATOS.\n",
      "Para probar: RUTA_DATOS <- \"datos_ejemplo\"\n", sep = "")
} else {
  cfg <- cargar_config()
  partes <- list()
  for (f in archivos) {
    cat("Leyendo", basename(f), "...\n")
    dt <- tryCatch(estandarizar_columnas(leer_archivo(f)),
                   error = function(e) { cat("  ERROR:", conditionMessage(e), "\n"); NULL })
    if (!is.null(dt)) {
      cat(sprintf("  %s items\n", format(nrow(dt), big.mark = ",")))
      partes[[f]] <- dt
    }
    gc()
  }
  if (length(partes) == 0) stop("Ningún archivo pudo leerse.")

  base <- rbindlist(partes, use.names = TRUE, fill = TRUE)
  rm(partes)
  # Un mismo despacho/item puede venir en el archivo "item" y en el "sub item";
  # se elimina la duplicación para no sumar dos veces.
  n0 <- nrow(base)
  base <- rbind(unique(base[ITEM != ""], by = c("DESPACHO_CIFRADO", "ITEM")), base[ITEM == ""])
  if (nrow(base) < n0) cat(sprintf("Se eliminaron %s items duplicados entre archivos.\n",
                                   format(n0 - nrow(base), big.mark = ",")))

  todo <- transformar(base, cfg)
  # Filtro de período también por el contenido (por si un archivo trae otros meses)
  if (!is.null(anios)) todo <- todo[ANIO_INT %in% anios]
  if (!identical(meses, "TODOS")) todo <- todo[MES_NUM %in% meses]
  datos <- todo[MOTIVO_EXCLUSION == ""]
  cat(sprintf("Items válidos para el análisis: %s de %s\n",
              format(nrow(datos), big.mark = ","), format(nrow(todo), big.mark = ",")))

  # Hoja de control: qué se excluyó y por qué, y qué códigos no están en la configuración.
  control <- todo[, .(ITEMS = .N, FOB_DOLAR = sum(FOB_DOLAR)),
                  by = .(MOTIVO_EXCLUSION, OPERACION, COD_REGIMEN, REGIMEN, ACUERDO)]
  setorder(control, MOTIVO_EXCLUSION, -FOB_DOLAR)
  control[MOTIVO_EXCLUSION == "", MOTIVO_EXCLUSION := "(incluido)"]
  control[, REGIMEN_EN_CONFIG := ifelse(COD_REGIMEN %in% cfg$regimenes_conocidos, "SI", "NO")]
  control[, ACUERDO_EN_CONFIG := ifelse(ACUERDO %in% cfg$acuerdos$acuerdo_dnit, "SI", "NO")]

  nuevos_reg <- setdiff(unique(todo$COD_REGIMEN), c(cfg$regimenes_conocidos, ""))
  if (length(nuevos_reg) > 0) {
    cat("AVISO: regímenes no listados en config/regimenes.csv (se excluyeron):",
        paste(sort(nuevos_reg), collapse = ", "), "\n")
  }
  nuevos_acu <- unique(todo[ACUERDO_SIN_CLASIFICAR == TRUE, ACUERDO])
  if (length(nuevos_acu) > 0) {
    cat("AVISO: acuerdos no listados en config/acuerdos.csv (tratados como PREFERENCIAL):",
        paste(sort(nuevos_acu), collapse = ", "), "\n")
  }

  por_acuerdo <- agregar(datos, DIMENSIONES_ACUERDO)
  por_acuerdo <- por_acuerdo[, c("ANIO", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO",
                                 columnas$medidas), with = FALSE]
  hojas <- list(
    "Totales por a\u00f1o" = totales_por_anio(datos, columnas$medidas),
    "Por acuerdo" = por_acuerdo,
    "Control" = control
  )
  detalle <- agregar(datos, unname(DIMENSIONES_ELEGIBLES[columnas$dims]))
  detalle <- detalle[, c(columnas$dims, columnas$medidas), with = FALSE]
  exportar(hojas, detalle, RUTA_SALIDAS)
  cat("=== Proceso finalizado ===\n")
}
