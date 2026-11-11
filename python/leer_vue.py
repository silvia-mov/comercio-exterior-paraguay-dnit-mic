"""
Junta los archivos mensuales de la VUE en una sola tabla
========================================================

Lee los archivos de "Exportaciones con certificado de origen por categoría y país de
destino" de la Ventanilla Única de Exportación (carpeta datos_vue/<año>/) y los guarda en
salidas/VUE_certificados_origen.csv, con las columnas:

    ANOMES, CAPITULO, CATEGORIA, PAISDESTINO, FOBDOLAR, TONELADA, ARCHIVO, FORMATO

Los archivos de la VUE vienen en varios formatos aunque todos se llamen .xls (ver
datos_vue/LEEME.md); este programa reconoce cada uno por su contenido:
    xls   Excel 97-2003
    xlsx  Excel 2007 o posterior (aunque la extensión diga .xls)
    mhtml "página web" de Excel o informe web (2011)
    sql   instrucciones de base de datos "Insert into ..." (febrero 2023)
    csv   texto separado por comas

Si un mes está en .xls y también en .csv (2019 y parte de 2020), se usa el .xls.

Uso:
    python python/leer_vue.py
    python python/leer_vue.py --carpeta datos_vue --salida salidas/VUE_certificados_origen.csv
"""
import argparse
import csv
import email
import io
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
RAIZ_REPO = Path(__file__).resolve().parent.parent
COLUMNAS = ["ANOMES", "CAPITULO", "CATEGORIA", "PAISDESTINO", "FOBDOLAR", "TONELADA"]


def formato(ruta):
    inicio = Path(ruta).read_bytes()[:4096]
    if inicio.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    if inicio.startswith(b"PK"):
        return "xlsx"
    if inicio.startswith(b"MIME-Version"):
        return "mhtml"
    if b"Insert into" in inicio or b"REM INSERTING" in inicio:
        return "sql"
    if str(ruta).lower().endswith(".csv"):
        return "csv"
    return "desconocido"


def leer_mhtml(ruta):
    """2011: página web de Excel. Columnas: categoría, país, FOB, toneladas (sin capítulo NCM)."""
    mensaje = email.message_from_bytes(Path(ruta).read_bytes())
    tabla = None
    for parte in mensaje.walk():
        if parte.get_content_type() != "text/html" or tabla is not None:
            continue
        html = parte.get_payload(decode=True).decode(parte.get_content_charset() or "windows-1252",
                                                     errors="replace")
        try:
            for t in pd.read_html(io.StringIO(html), flavor="bs4"):
                if t.iloc[:, 0].astype(str).str.startswith("Categor").any():
                    tabla = t
                    break
        except ValueError:
            pass
    if tabla is None:
        raise ValueError("no se encontró la tabla")
    inicio = tabla.index[tabla.iloc[:, 0].astype(str).str.startswith("Categor")][0]
    tabla = tabla.iloc[inicio + 1:, :4]
    tabla.columns = ["CATEGORIA", "PAISDESTINO", "FOBDOLAR", "TONELADA"]
    for col in ("FOBDOLAR", "TONELADA"):
        tabla[col] = pd.to_numeric(tabla[col].astype(str).str.replace(".", "", regex=False)
                                   .str.replace(",", ".", regex=False), errors="coerce")
    tabla = tabla[tabla["FOBDOLAR"].notna() & ~tabla["CATEGORIA"].astype(str).str.upper().str.contains("TOTAL")]
    anio, mes = re.search(r"_(\d{4})_(\d{2})", Path(ruta).name).groups()
    tabla["ANOMES"] = f"{anio}/{mes}"
    tabla["CAPITULO"] = None
    return tabla


def leer_sql(ruta):
    texto = Path(ruta).read_bytes().decode("windows-1252")
    filas = [next(csv.reader([v], quotechar="'", skipinitialspace=True))
             for v in re.findall(r"values \((.*)\);", texto)]
    return pd.DataFrame(filas, columns=COLUMNAS)


def leer(ruta):
    fmt = formato(ruta)
    if fmt == "xls":
        d = pd.read_excel(ruta, sheet_name=0, engine="xlrd")
    elif fmt == "xlsx":
        d = pd.read_excel(ruta, sheet_name=0, engine="openpyxl")
    elif fmt == "mhtml":
        d = leer_mhtml(ruta)
    elif fmt == "sql":
        d = leer_sql(ruta)
    elif fmt == "csv":
        for encoding in ("utf-8-sig", "windows-1252"):
            try:
                d = pd.read_csv(ruta, encoding=encoding, sep=None, engine="python")
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
    else:
        raise ValueError("formato desconocido")
    d.columns = [re.sub(r"\s+", "", str(c).upper()) for c in d.columns]   # "PAIS DESTINO" -> "PAISDESTINO"
    d = d[[c for c in COLUMNAS if c in d.columns]].copy()
    for col in ("FOBDOLAR", "TONELADA"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d["ARCHIVO"] = Path(ruta).name
    d["FORMATO"] = fmt
    return d


def main():
    parser = argparse.ArgumentParser(description="Junta los archivos mensuales de la VUE")
    parser.add_argument("--carpeta", default="datos_vue")
    parser.add_argument("--salida", default="salidas/VUE_certificados_origen.csv")
    args = parser.parse_args()
    carpeta = Path(args.carpeta)
    if not carpeta.is_absolute():
        carpeta = RAIZ_REPO / carpeta

    archivos = sorted(p for p in carpeta.rglob("Exportaciones_*") if p.is_file())
    # Un archivo por mes: si hay .xls y .csv del mismo mes, se usa el .xls
    por_mes = {}
    for p in archivos:
        anio, mes = re.search(r"_(\d{4})_\|?(\d{2})", p.name).groups()
        actual = por_mes.get((anio, mes))
        if actual is None or (actual.suffix.lower() == ".csv" and p.suffix.lower() != ".csv"):
            por_mes[(anio, mes)] = p

    partes, no_leidos = [], []
    for (anio, mes), p in sorted(por_mes.items()):
        try:
            partes.append(leer(p))
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con el resto
            no_leidos.append(f"{p.name} ({e})")
    tabla = pd.concat(partes, ignore_index=True)[COLUMNAS + ["ARCHIVO", "FORMATO"]]

    salida = Path(args.salida)
    if not salida.is_absolute():
        salida = RAIZ_REPO / salida
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salida, index=False, encoding="utf-8-sig")

    print(f"Meses leídos: {len(partes)} de {len(por_mes)}  ({len(tabla):,} filas)")
    print(f"Guardado: {salida}")
    if no_leidos:
        print("No se pudieron leer:", "; ".join(no_leidos))
    anual = tabla.assign(AÑO=tabla["ANOMES"].astype(str).str[:4]).groupby("AÑO")["FOBDOLAR"].sum() / 1e6
    print("\nFOB con certificado de origen por año (millones de USD):")
    print(anual.round(1).to_string())


if __name__ == "__main__":
    main()
