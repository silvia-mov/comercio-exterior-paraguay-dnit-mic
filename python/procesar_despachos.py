"""
Procesamiento de despachos aduaneros de la DNIT (Paraguay)
=========================================================

Filtra el comercio exterior de Paraguay por ACUERDO COMERCIAL y genera
estadísticas agregadas (valores FOB/CIF, tributos y presión tributaria).

Uso:
    python python/procesar_despachos.py                      # usa RUTA_DATOS
    python python/procesar_despachos.py "C:/mis_datos/dnit"  # ruta por argumento
    python python/procesar_despachos.py datos_ejemplo        # prueba con la muestra
    python python/procesar_despachos.py datos_dnit --anios 2021 --meses todos
    python python/procesar_despachos.py datos_dnit --anios 2019-2021 --meses enero,febrero

Las columnas del Excel final ("Detalle") se eligen en config/columnas.csv (SI / NO).

Acepta los archivos tal como los descarga la DNIT (JSON "nivel item" y
"nivel sub item") y también CSV / XLSX / Parquet ya aplanados.
Los valores siempre se toman a nivel ITEM: los sub-items solo detallan la
mercadería y no se suman (sumarlos duplicaría los montos).
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURACIÓN  <-- EDITE AQUÍ
# ==============================================================================

# Carpeta con los archivos descargados de la DNIT. Puede ser relativa a la
# carpeta del repositorio o absoluta, p. ej. r"C:\Users\usuario\Descargas\dnit".
RUTA_DATOS = "datos_dnit"

# Carpeta donde se guardan los resultados.
RUTA_SALIDAS = "salidas"

# Años y meses a juntar. AÑOS = None junta todos los años de la carpeta.
# Ejemplos: AÑOS = [2021]   AÑOS = list(range(2019, 2022))
#           MESES_ELEGIDOS = "TODOS"   MESES_ELEGIDOS = ["ENERO", "FEBRERO"]
# También se pueden pasar al correr: --anios 2019-2021 --meses enero,febrero
AÑOS = None
MESES_ELEGIDOS = "TODOS"

# Tipos de acuerdo (columna "tipo" de config/acuerdos.csv) que se conservan.
# - PREFERENCIAL: comercio negociado bajo un acuerdo comercial.
# - SIN_ACUERDO: comercio sin preferencia (OMC / NMF), útil como comparación.
# - MERCOSUR_INTRAZONA: comercio intra-MERCOSUR (ACE 18).
# Para analizar SOLO lo negociado por acuerdo, deje únicamente ["PREFERENCIAL"].
TIPOS_ACUERDO_INCLUIDOS = ["PREFERENCIAL", "MERCOSUR_INTRAZONA", "SIN_ACUERDO"]

# En exportaciones, conservar solo mercadería de origen paraguayo
# (excluye reexportaciones de bienes de otro origen).
EXPORTACIONES_SOLO_ORIGEN_PARAGUAY = True

# ==============================================================================

RAIZ_REPO = Path(__file__).resolve().parent.parent
RUTA_CONFIG = RAIZ_REPO / "config"
LIMITE_FILAS_EXCEL = 1_048_575

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}
NUM_A_MES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# Nombre canónico -> posibles nombres en los archivos. La comparación ignora
# mayúsculas, espacios, guiones, puntos y guiones bajos, por lo que
# "codRegimen", "COD_REGIMEN" y "Cod. Regimen" se reconocen igual.
# Se usa el primer sinónimo que exista en el archivo.
SINONIMOS = {
    "DESPACHO_CIFRADO": ["despachoCifrado", "DESPACHO", "DESPACH_CIFRADO"],
    "ITEM": ["itemInterno", "itemExterno", "ITEM", "NRO_ITEM"],
    "OPERACION": ["operacion", "TIPO_OPERACION", "OPERAC"],
    "COD_REGIMEN": ["codRegimen", "DESTINACION", "COD_DESTINACION", "DESTINAC"],
    "REGIMEN": ["regimen", "REGIMEN_ADUANERO"],
    "ACUERDO": ["acuerdoAjustado", "ACUERDO", "ACUERDO_COMERCIAL", "TRATADO"],
    "AÑO": ["anio", "AÑO", "ANO", "YEAR"],
    "MES": ["mes", "MONTH"],
    "ADUANA": ["aduanaDespacho", "ADUANA"],
    "PAIS_ORIGEN": ["paisOrigenAjustado", "PAIS_ORIGEN", "PAIS_DE_ORIGEN", "ORIGEN"],
    "PAIS_PROC_DEST": ["paisProcDestinoAjustado", "PAIS_PROCEDENCIA_DESTINO", "PAIS_PROC_DEST",
                       "PAIS_PROCEDENCIA", "PAIS_DESTINO"],
    "MEDIO_TRANSPORTE": ["medioTransporte", "MEDIO_DE_TRANSPORTE", "TRANSPORTE"],
    "USO": ["usoAjustado", "USO"],
    "POSICION_NCM": ["posicionAjustado", "POSICION_NCM", "POSICION", "NCM", "CODIGO_NCM"],
    "DESC_POSICION": ["descripcionAjustado", "DESC_POSICION", "DESCRIPCION_POSICION", "DESCRIPCION"],
    "DESC_PARTIDA": ["despartidaAjustado", "DESC_PARTIDA", "DESCRIPCION_PARTIDA"],
    "PESO_NETO_KG": ["pesoNeto", "KILO_NETO", "PESO_NETO"],
    "FOB_DOLAR": ["fobDolarAjustado", "FOB_DOLAR", "FOB_USD", "FOB"],
    "FLETE_DOLAR": ["fleteDolarAjustado", "FLETE_DOLAR", "FLETE_USD", "FLETE"],
    "SEGURO_DOLAR": ["seguroDolarAjustado", "SEGURO_DOLAR", "SEGURO_USD", "SEGURO"],
    "IMPONIBLE_GS": ["imponibleGsAjustado", "IMPONIBLE_GS"],
    "IMPONIBLE_DOLAR": ["IMPONIBLE_DOLAR", "IMPONIBLE_USD"],
    "DERECHO": ["derecho", "DERECHOS", "DERECHO_ADUANERO"],
    "IVA": ["iva"],
    "ISC": ["isc"],
    "SERVICIO": ["servicio", "TASA_SERVICIO"],
    "RENTA": ["renta", "ANTICIPO_RENTA"],
    "OTROS": ["otros", "OTROS_TRIBUTOS"],
    "COTIZACION": ["cotizacion", "TIPO_CAMBIO", "TIPO_DE_CAMBIO"],
}

COLUMNAS_TEXTO = ["DESPACHO_CIFRADO", "ITEM", "OPERACION", "COD_REGIMEN", "REGIMEN", "ACUERDO", "AÑO",
                  "MES", "ADUANA", "PAIS_ORIGEN", "PAIS_PROC_DEST", "MEDIO_TRANSPORTE", "USO",
                  "POSICION_NCM", "DESC_POSICION", "DESC_PARTIDA"]
# Montos en Gs. que se convierten a USD dividiendo por la cotización del despacho.
TRIBUTOS_GS = ["DERECHO", "IVA", "ISC", "SERVICIO", "RENTA", "OTROS"]
COLUMNAS_NUMERICAS = ["PESO_NETO_KG", "FOB_DOLAR", "FLETE_DOLAR", "SEGURO_DOLAR",
                      "IMPONIBLE_GS", "IMPONIBLE_DOLAR", "COTIZACION"] + TRIBUTOS_GS

DIMENSIONES_RESUMEN = ["OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO", "AÑO_INT", "MES_NUM",
                       "PAIS_ORIGEN", "PAIS_PROC_DEST", "MEDIO_TRANSPORTE", "USO"]
DIMENSIONES_DETALLE = DIMENSIONES_RESUMEN + ["POSICION_NCM", "DESCRIPCION_PRODUCTO"]
DIMENSIONES_ACUERDO = ["AÑO_INT", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO"]
MEDIDAS = ["PESO_NETO_KG", "FOB_DOLAR", "CIF_DOLAR", "IMPONIBLE_DOLAR",
           "DERECHO", "TRIBUTOS_INTERNOS", "TOTAL_TRIBUTOS"]


def clave(texto):
    """Normaliza un nombre de columna para compararlo: sin tildes ni separadores."""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return "".join(c for c in s.upper() if c.isalnum())


def normalizar_texto(serie):
    return serie.fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)


def a_numero(serie):
    """Convierte texto a número aceptando '1234.5', '1234,5' y '1.234,5'."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float).fillna(0.0)
    s = serie.fillna("").astype(str).str.strip()
    ambos = s.str.contains(",", regex=False) & s.str.contains(".", regex=False)
    s = s.where(~ambos, s.str.replace(".", "", regex=False))
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


# Columnas que pueden elegirse en config/columnas.csv
DIMENSIONES_ELEGIBLES = {"AÑO": "AÑO_INT", "MES": "MES_NUM", "OPERACION": "OPERACION",
                         "TIPO_ACUERDO": "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO": "ACUERDO_CONSOLIDADO",
                         "PAIS_PROC_DEST": "PAIS_PROC_DEST", "PAIS_ORIGEN": "PAIS_ORIGEN",
                         "MEDIO_TRANSPORTE": "MEDIO_TRANSPORTE", "USO": "USO", "REGIMEN": "REGIMEN",
                         "ADUANA": "ADUANA", "POSICION_NCM": "POSICION_NCM",
                         "DESCRIPCION_PRODUCTO": "DESCRIPCION_PRODUCTO"}
MEDIDAS_ELEGIBLES = MEDIDAS + ["CONTEO_DESPACHOS", "CONTEO_ITEMS", "PRESION_ARANCELARIA_EFECTIVA_PCT",
                               "PRESION_INTERNA_EFECTIVA_PCT", "PRESION_TRIBUTARIA_TOTAL_PCT"]
# "Con acuerdo" = comercio que usó una preferencia: acuerdos de MERCOSUR con terceros,
# acuerdos ALADI y el propio MERCOSUR (ACE 18). Ver docs/GLOSARIO.md.
TIPOS_CON_ACUERDO = ["PREFERENCIAL", "MERCOSUR_INTRAZONA"]


def cargar_columnas():
    """Columnas marcadas con SI en config/columnas.csv, en el orden del archivo."""
    ruta = RUTA_CONFIG / "columnas.csv"
    if not ruta.exists():
        return list(DIMENSIONES_ELEGIBLES), MEDIDAS_ELEGIBLES
    cfg = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    elegidas = [c.strip().upper() for c in cfg.loc[normalizar_texto(cfg["incluir"]) == "SI", "columna"]]
    desconocidas = [c for c in elegidas if c not in DIMENSIONES_ELEGIBLES and c not in MEDIDAS_ELEGIBLES]
    if desconocidas:
        print(f"AVISO: columnas desconocidas en config/columnas.csv (se ignoran): {desconocidas}")
    dims = [c for c in elegidas if c in DIMENSIONES_ELEGIBLES]
    medidas = [c for c in elegidas if c in MEDIDAS_ELEGIBLES]
    if not dims or not medidas:
        raise SystemExit("config/columnas.csv debe tener al menos una columna de texto "
                         "(p. ej. AÑO) y una de valores (p. ej. FOB_DOLAR) con SI.")
    return dims, medidas


def leer_rango_anios(texto):
    """'2021' -> [2021]; '2019-2021' -> [2019, 2020, 2021]; '2019,2021' -> [2019, 2021]."""
    anios = []
    for parte in str(texto).replace(" ", "").split(","):
        if "-" in parte:
            a, b = (int(x) for x in parte.split("-"))
            anios += list(range(min(a, b), max(a, b) + 1))
        elif parte:
            anios.append(int(parte))
    return sorted(set(anios))


def leer_meses(texto):
    if texto is None or str(texto).strip().upper() in ("", "TODOS"):
        return "TODOS"
    if isinstance(texto, (list, tuple)):
        partes = texto
    else:
        partes = str(texto).split(",")
    meses = set()
    for p in partes:
        p = str(p).strip().upper()
        n = MESES.get(p, int(p) if p.isdigit() else None)
        if n is None:
            raise SystemExit(f"Mes no reconocido: {p}")
        meses.add(n)
    return sorted(meses)


def archivo_en_periodo(ruta, anios, meses):
    """Usa el nombre del archivo de la DNIT (p. ej. 2021_ENERO_Nivel_Item.csv) para no
    abrir archivos de otros períodos. Si el nombre no sigue ese patrón, se lee igual."""
    m = re.match(r"(\d{4})_([A-ZÁÉÍÓÚ]+)", ruta.name.upper())
    if not m:
        return True
    anio, mes = int(m.group(1)), MESES.get(m.group(2))
    if anios is not None and anio not in anios:
        return False
    if meses != "TODOS" and mes is not None and mes not in meses:
        return False
    return True


def cargar_config():
    reg = pd.read_csv(RUTA_CONFIG / "regimenes.csv", dtype=str, keep_default_na=False)
    reg["codigo"] = normalizar_texto(reg["codigo"])
    regimenes_si = set(reg.loc[normalizar_texto(reg["incluir"]) == "SI", "codigo"])
    regimenes_conocidos = set(reg["codigo"])

    acu = pd.read_csv(RUTA_CONFIG / "acuerdos.csv", dtype=str, keep_default_na=False)
    acu["acuerdo_dnit"] = normalizar_texto(acu["acuerdo_dnit"])
    acu = acu.drop_duplicates("acuerdo_dnit").set_index("acuerdo_dnit")
    return regimenes_si, regimenes_conocidos, acu


# ------------------------------------------------------------------------------
# 2. LECTURA
# ------------------------------------------------------------------------------

def leer_json(ruta):
    """Lee el JSON de la DNIT (despachos -> items -> subitems) y devuelve una fila por item."""
    texto = Path(ruta).read_text(encoding="utf-8-sig")
    try:
        despachos = json.loads(texto)
    except json.JSONDecodeError as e:
        # Archivo cortado (p. ej. copiado a mano en un editor de texto): se
        # recuperan los despachos completos y se avisa.
        despachos = recuperar_json_truncado(texto)
        print(f"  ADVERTENCIA: JSON inválido o incompleto ({e.msg}). "
              f"Se recuperaron {len(despachos)} despachos completos.")
    if isinstance(despachos, dict):
        despachos = next((v for v in despachos.values() if isinstance(v, list)), [despachos])

    filas = []
    for d in despachos:
        cabecera = {k: v for k, v in d.items() if not isinstance(v, (list, dict))}
        for item in d.get("items") or []:
            fila = dict(cabecera)
            fila.update({k: v for k, v in item.items() if not isinstance(v, (list, dict))})
            filas.append(fila)
    return pd.DataFrame(filas)


def recuperar_json_truncado(texto):
    decoder = json.JSONDecoder()
    inicio = texto.find("[") + 1
    i, despachos = inicio, []
    while i < len(texto):
        while i < len(texto) and texto[i] in " ,\r\n\t":
            i += 1
        try:
            obj, i = decoder.raw_decode(texto, i)
        except json.JSONDecodeError:
            break
        despachos.append(obj)
    return despachos


def columnas_utiles(columnas):
    """Columnas del archivo que corresponden a algún nombre de SINONIMOS."""
    claves = {clave(s) for canonico, sins in SINONIMOS.items() for s in [canonico] + sins}
    return [c for c in columnas if clave(c) in claves]


def leer_csv(ruta, filas_por_bloque=200_000):
    """Lee un CSV grande por bloques y solo con las columnas necesarias.

    El CSV "nivel sub item" de la DNIT trae una fila por sub-item con los valores
    del item repetidos; se deja una sola fila por despacho + item en cada bloque
    (la deduplicación final del programa principal cubre los bordes entre bloques).
    """
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with open(ruta, encoding=encoding) as f:
                cabecera = f.readline()
            break
        except UnicodeDecodeError:
            continue
    sep = max([",", ";", "\t", "|"], key=cabecera.count)
    columnas = pd.read_csv(ruta, sep=sep, nrows=0, encoding=encoding).columns
    usar = columnas_utiles(columnas)
    lector = pd.read_csv(ruta, sep=sep, dtype=str, usecols=usar, encoding=encoding,
                         keep_default_na=False, chunksize=filas_por_bloque)
    claves_item = [c for c in usar if clave(c) in (clave("DESPACHO_CIFRADO"), clave("ITEM"))]
    bloques = []
    for bloque in lector:
        if len(claves_item) == 2:
            bloque = bloque.drop_duplicates(claves_item)
        bloques.append(bloque)
    return pd.concat(bloques, ignore_index=True)


def leer_archivo(ruta):
    ext = ruta.suffix.lower()
    if ext in (".json", ".txt"):
        return leer_json(ruta)
    if ext == ".csv":
        return leer_csv(ruta)
    if ext == ".xlsx":
        return pd.read_excel(ruta, dtype=str)
    if ext == ".parquet":
        return pd.read_parquet(ruta)
    raise ValueError(f"Formato no soportado: {ext}")


def estandarizar_columnas(df):
    """Renombra las columnas al nombre canónico y crea las que falten."""
    por_clave = {}
    for col in df.columns:
        por_clave.setdefault(clave(col), col)
    renombrar = {}
    for canonico, sinonimos in SINONIMOS.items():
        for s in [canonico] + sinonimos:
            col = por_clave.get(clave(s))
            if col is not None and col not in renombrar:
                renombrar[col] = canonico
                break
    df = df[list(renombrar)].rename(columns=renombrar)

    for col in COLUMNAS_TEXTO:
        df[col] = normalizar_texto(df[col]) if col in df else ""
    for col in COLUMNAS_NUMERICAS:
        df[col] = a_numero(df[col]) if col in df else 0.0
    return df


# ------------------------------------------------------------------------------
# 3. FILTROS Y CÁLCULOS
# ------------------------------------------------------------------------------

def transformar(df, regimenes_si, acuerdos):
    """Aplica los filtros y calcula montos en USD. Devuelve (df_filtrado, df_control)."""
    df = df.copy()
    df["ACUERDO"] = normalizar_texto(df["ACUERDO"])
    mapeado = df["ACUERDO"].map(acuerdos["acuerdo_consolidado"])
    df["ACUERDO_CONSOLIDADO"] = mapeado.fillna("Otro acuerdo (sin clasificar): " + df["ACUERDO"])
    df["TIPO_ACUERDO"] = df["ACUERDO"].map(acuerdos["tipo"]).fillna("PREFERENCIAL")
    df["ACUERDO_SIN_CLASIFICAR"] = mapeado.isna()

    es_imp = df["OPERACION"].str.startswith("IMP")
    es_exp = df["OPERACION"].str.startswith("EXP")
    origen_py = df["PAIS_ORIGEN"].str.contains("PARAGUAY") | (df["PAIS_ORIGEN"] == "PY")

    df["MOTIVO_EXCLUSION"] = ""
    reglas = [
        (~(es_imp | es_exp), "Operación no reconocida"),
        (~df["COD_REGIMEN"].isin(regimenes_si), "Régimen no definitivo"),
        (es_exp & ~origen_py & EXPORTACIONES_SOLO_ORIGEN_PARAGUAY, "Exportación de origen no paraguayo"),
        (~df["TIPO_ACUERDO"].isin(TIPOS_ACUERDO_INCLUIDOS), "Tipo de acuerdo excluido"),
    ]
    for condicion, motivo in reglas:
        df.loc[condicion & (df["MOTIVO_EXCLUSION"] == ""), "MOTIVO_EXCLUSION"] = motivo

    # Cotización Gs/USD del despacho; se protege contra ceros y vacíos.
    cot = df["COTIZACION"].where(df["COTIZACION"] > 0, np.nan)
    for col in TRIBUTOS_GS:
        df[col] = (df[col] / cot).fillna(0.0)
    # El imponible de la DNIT viene en Gs.; si el archivo ya trae USD se respeta.
    df["IMPONIBLE_DOLAR"] = np.where(df["IMPONIBLE_DOLAR"] > 0, df["IMPONIBLE_DOLAR"],
                                     (df["IMPONIBLE_GS"] / cot).fillna(0.0))
    df["CIF_DOLAR"] = np.where(es_imp, df["FOB_DOLAR"] + df["FLETE_DOLAR"] + df["SEGURO_DOLAR"], 0.0)
    df["TRIBUTOS_INTERNOS"] = df[["IVA", "ISC", "SERVICIO", "RENTA", "OTROS"]].sum(axis=1)
    df["TOTAL_TRIBUTOS"] = df["DERECHO"] + df["TRIBUTOS_INTERNOS"]

    df["DESCRIPCION_PRODUCTO"] = df["DESC_PARTIDA"].where(df["DESC_PARTIDA"] != "", df["DESC_POSICION"])
    mes = df["MES"].map(MESES)
    df["MES_NUM"] = mes.fillna(pd.to_numeric(df["MES"], errors="coerce")).fillna(13).astype(int)
    df["AÑO_INT"] = pd.to_numeric(df["AÑO"], errors="coerce").fillna(9999).astype(int)
    return df


def agregar(df, dimensiones):
    out = (df.groupby(dimensiones, dropna=False)
             .agg(CONTEO_DESPACHOS=("DESPACHO_CIFRADO", "nunique"),
                  CONTEO_ITEMS=("DESPACHO_CIFRADO", "size"),
                  **{m: (m, "sum") for m in MEDIDAS})
             .reset_index())
    imp = out["IMPONIBLE_DOLAR"]
    for nombre, num in [("PRESION_ARANCELARIA_EFECTIVA_PCT", "DERECHO"),
                        ("PRESION_INTERNA_EFECTIVA_PCT", "TRIBUTOS_INTERNOS"),
                        ("PRESION_TRIBUTARIA_TOTAL_PCT", "TOTAL_TRIBUTOS")]:
        out[nombre] = np.where(imp > 0, out[num] / imp.where(imp > 0, 1) * 100, 0.0)

    if "AÑO_INT" in out:
        out["AÑO"] = out["AÑO_INT"]
    if "MES_NUM" in out:
        out["MES"] = out["MES_NUM"].map(NUM_A_MES).fillna("S/D")
    orden = [c for c in ["AÑO_INT", "MES_NUM", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO"] if c in out]
    out = out.sort_values(orden, ascending=[c != "AÑO_INT" for c in orden])
    primeras = [c for c in ("AÑO", "MES") if c in out]
    resto = [c for c in dimensiones if c not in ("AÑO_INT", "MES_NUM")]
    return out[primeras + resto + [c for c in out.columns if c not in primeras + resto + dimensiones]]


def totales_por_anio(df, medidas):
    """Por año y operación: con acuerdo, sin acuerdo, total y % con acuerdo (para gráficos)."""
    medidas = [m for m in medidas if not m.endswith("_PCT") and not m.startswith("CONTEO")]
    d = df.assign(GRUPO=np.where(df["TIPO_ACUERDO"].isin(TIPOS_CON_ACUERDO), "CON_ACUERDO", "SIN_ACUERDO"))
    t = d.pivot_table(index=["AÑO_INT", "OPERACION"], columns="GRUPO", values=medidas,
                      aggfunc="sum", fill_value=0.0)
    out = pd.DataFrame(index=t.index)
    for m in medidas:
        con = t[(m, "CON_ACUERDO")] if (m, "CON_ACUERDO") in t else 0.0
        sin = t[(m, "SIN_ACUERDO")] if (m, "SIN_ACUERDO") in t else 0.0
        out[f"{m}_CON_ACUERDO"] = con
        out[f"{m}_SIN_ACUERDO"] = sin
        out[f"{m}_TOTAL"] = con + sin
        out[f"{m}_CON_ACUERDO_PCT"] = np.where(out[f"{m}_TOTAL"] > 0, con / out[f"{m}_TOTAL"].where(out[f"{m}_TOTAL"] > 0, 1) * 100, 0.0)
    out = out.reset_index().rename(columns={"AÑO_INT": "AÑO"})
    return out.sort_values(["AÑO", "OPERACION"])


# ------------------------------------------------------------------------------
# 4. EXPORTACIÓN
# ------------------------------------------------------------------------------

def formatear_hoja(writer, nombre, df):
    libro, hoja = writer.book, writer.sheets[nombre]
    f_cab = libro.add_format({"bold": True, "text_wrap": True, "valign": "top",
                              "fg_color": "#1F4E78", "font_color": "white", "border": 1})
    f_usd = libro.add_format({"num_format": "#,##0"})
    f_pct = libro.add_format({"num_format": '0.00"%"'})
    for i, col in enumerate(df.columns):
        hoja.write(0, i, col, f_cab)
        if col.endswith("_PCT"):
            hoja.set_column(i, i, 12, f_pct)
        elif col.startswith(tuple(MEDIDAS)) or col.startswith("CONTEO"):
            hoja.set_column(i, i, 16, f_usd)
        else:
            largo = df[col].astype(str).str.len().max() if len(df) else 10
            hoja.set_column(i, i, min(max(int(largo), len(col)) + 2, 45))
    hoja.freeze_panes(1, 0)
    hoja.autofilter(0, 0, max(len(df), 1), len(df.columns) - 1)


def exportar(hojas, detalle, carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_excel = carpeta / "Reporte_Comercio_Paraguay_Acuerdos.xlsx"
    if len(detalle) <= LIMITE_FILAS_EXCEL:
        hojas = {**hojas, "Detalle": detalle}
    else:
        ruta_det = carpeta / "Detalle_Paraguay.parquet"
        try:
            detalle.to_parquet(ruta_det, index=False)
        except ImportError:
            ruta_det = carpeta / "Detalle_Paraguay.csv.gz"
            detalle.to_csv(ruta_det, index=False, encoding="utf-8")
        print(f"El detalle supera el límite de filas de Excel; se guardó en: {ruta_det}")

    with pd.ExcelWriter(ruta_excel, engine="xlsxwriter") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            formatear_hoja(writer, nombre, df)
    print(f"Reporte generado: {ruta_excel}")


# ------------------------------------------------------------------------------
# 5. PROGRAMA PRINCIPAL
# ------------------------------------------------------------------------------

def resolver_ruta(ruta):
    p = Path(ruta).expanduser()
    if not p.is_absolute() and not p.exists():
        p = RAIZ_REPO / p
    return p


def main():
    parser = argparse.ArgumentParser(description="Comercio exterior de Paraguay por acuerdo comercial (DNIT)")
    parser.add_argument("ruta", nargs="?", default=RUTA_DATOS, help="carpeta con los archivos de la DNIT")
    parser.add_argument("--anios", help="años a juntar, p. ej. 2021 o 2019-2021 o 2019,2021")
    parser.add_argument("--meses", help="meses, p. ej. todos o enero,febrero o 1,2")
    args = parser.parse_args()
    anios = leer_rango_anios(args.anios) if args.anios else (sorted(AÑOS) if AÑOS else None)
    meses = leer_meses(args.meses if args.meses else MESES_ELEGIDOS)
    dims_elegidas, medidas_elegidas = cargar_columnas()

    ruta_datos = resolver_ruta(args.ruta)
    carpeta_salida = resolver_ruta(RUTA_SALIDAS)
    print("=== Pipeline de Comercio Exterior DNIT Paraguay ===")
    print(f"Carpeta de datos: {ruta_datos}")
    print(f"Años: {anios if anios else 'todos'} | Meses: "
          f"{meses if meses == 'TODOS' else [NUM_A_MES[m] for m in meses]}")

    if not ruta_datos.exists():
        ruta_datos.mkdir(parents=True)
    archivos = sorted(p for p in ruta_datos.rglob("*")
                      if p.suffix.lower() in (".json", ".txt", ".csv", ".xlsx", ".parquet")
                      and archivo_en_periodo(p, anios, meses))
    if not archivos:
        print("No se encontraron archivos (.json, .txt, .csv, .xlsx, .parquet).\n"
              "Coloque los archivos de la DNIT en esa carpeta, edite RUTA_DATOS o pase la ruta\n"
              "como argumento. Para probar: python python/procesar_despachos.py datos_ejemplo")
        return

    regimenes_si, regimenes_conocidos, acuerdos = cargar_config()
    partes = []
    for ruta in archivos:
        print(f"Leyendo {ruta.name} ...")
        try:
            df = estandarizar_columnas(leer_archivo(ruta))
        except Exception as e:
            print(f"  ERROR leyendo {ruta.name}: {e}")
            continue
        print(f"  {len(df):,} items")
        partes.append(df)
    if not partes:
        print("Ningún archivo pudo leerse.")
        return

    base = pd.concat(partes, ignore_index=True)
    # Un mismo despacho/item puede venir en el archivo "item" y en el "sub item";
    # se elimina la duplicación para no sumar dos veces.
    n0 = len(base)
    con_item = base["ITEM"] != ""
    base = pd.concat([base[con_item].drop_duplicates(["DESPACHO_CIFRADO", "ITEM"]), base[~con_item]],
                     ignore_index=True)
    if len(base) < n0:
        print(f"Se eliminaron {n0 - len(base):,} items duplicados entre archivos.")

    todo = transformar(base, regimenes_si, acuerdos)
    # Filtro de período también por el contenido (por si un archivo trae otros meses)
    en_periodo = pd.Series(True, index=todo.index)
    if anios is not None:
        en_periodo &= todo["AÑO_INT"].isin(anios)
    if meses != "TODOS":
        en_periodo &= todo["MES_NUM"].isin(meses)
    todo = todo[en_periodo]
    datos = todo[todo["MOTIVO_EXCLUSION"] == ""]
    print(f"Items válidos para el análisis: {len(datos):,} de {len(todo):,}")

    # Hoja de control: qué se excluyó y por qué, y qué códigos no están en la configuración.
    control = (todo.groupby(["MOTIVO_EXCLUSION", "OPERACION", "COD_REGIMEN", "REGIMEN", "ACUERDO"], dropna=False)
                   .agg(ITEMS=("DESPACHO_CIFRADO", "size"), FOB_DOLAR=("FOB_DOLAR", "sum"))
                   .reset_index()
                   .sort_values(["MOTIVO_EXCLUSION", "FOB_DOLAR"], ascending=[True, False]))
    control["MOTIVO_EXCLUSION"] = control["MOTIVO_EXCLUSION"].replace("", "(incluido)")
    control["REGIMEN_EN_CONFIG"] = np.where(control["COD_REGIMEN"].isin(regimenes_conocidos), "SI", "NO")
    control["ACUERDO_EN_CONFIG"] = np.where(control["ACUERDO"].isin(acuerdos.index), "SI", "NO")

    nuevos_reg = sorted(set(todo["COD_REGIMEN"]) - regimenes_conocidos - {""})
    if nuevos_reg:
        print(f"AVISO: regímenes no listados en config/regimenes.csv (se excluyeron): {nuevos_reg}")
    nuevos_acu = sorted(set(todo.loc[todo["ACUERDO_SIN_CLASIFICAR"], "ACUERDO"]))
    if nuevos_acu:
        print(f"AVISO: acuerdos no listados en config/acuerdos.csv (tratados como PREFERENCIAL): {nuevos_acu}")

    por_acuerdo = agregar(datos, DIMENSIONES_ACUERDO)
    por_acuerdo = por_acuerdo[["AÑO", "OPERACION", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO"] + medidas_elegidas]
    hojas = {
        "Totales por año": totales_por_anio(datos, medidas_elegidas),
        "Por acuerdo": por_acuerdo,
        "Control": control,
    }
    detalle = agregar(datos, [DIMENSIONES_ELEGIBLES[c] for c in dims_elegidas])
    detalle = detalle[dims_elegidas + medidas_elegidas]
    exportar(hojas, detalle, carpeta_salida)
    print("=== Proceso finalizado ===")


if __name__ == "__main__":
    main()
