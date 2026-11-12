"""
Cruce de exportaciones: despachos de la DNIT vs. certificados de origen de la VUE
================================================================================

Compara, por año, país de destino y partida (4 dígitos de la NCM):
  - VUE : valor FOB de los certificados de origen emitidos (datos_vue/).
  - DNIT: valor FOB exportado según los despachos (los mismos filtros que
          procesar_despachos.py: regímenes definitivos, origen paraguayo, etc.),
          separado en "con acuerdo" y "sin acuerdo".

Salida: salidas/Cruce_DNIT_VUE.xlsx con las hojas
  Por año · Por país · Por partida · País y partida · Notas

Uso:
    python python/cruzar_dnit_vue.py --anios 2020-2021
    python python/cruzar_dnit_vue.py --anios 2015-2025 --dnit datos_dnit

Antes: tener los archivos de la DNIT de esos años (descargar_dnit.py) y los de la VUE
(carpeta datos_vue/, ya incluida en el repositorio).

Poco espacio en disco: el programa guarda un resumen por año en salidas/resumen_dnit/. Una vez
resumido un año, sus archivos de la DNIT se pueden borrar; la próxima vez se usa el resumen.

LO QUE HAY QUE TENER EN CUENTA (ver docs/GLOSARIO.md, sección 8):
  - La VUE cuenta TODOS los certificados de origen (preferenciales y no preferenciales);
    no indica el acuerdo. Por eso se compara con el total exportado y con "con acuerdo".
  - Fechas distintas: VUE = emisión del certificado; DNIT = cancelación del despacho.
    Por eso la comparación es anual.
  - Destino: VUE = el del certificado (en general, destino final); DNIT = el declarado
    en la aduana (puede ser un país de tránsito, como Argentina o Uruguay).
  - La VUE de 2011 no trae la partida: ese año solo entra en "Por año" y "Por país".
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leer_vue  # noqa: E402
import procesar_despachos as pd_dnit  # noqa: E402

RAIZ_REPO = Path(__file__).resolve().parent.parent
TIPOS_CON_ACUERDO = ["PREFERENCIAL", "MERCOSUR_INTRAZONA"]


def normalizar(texto):
    s = unicodedata.normalize("NFKD", str(texto).upper()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def cargar_vue(anios):
    """VUE por año, código de país y partida."""
    por_mes = {}
    for p in sorted((RAIZ_REPO / "datos_vue").rglob("Exportaciones_*")):
        if not p.is_file() or "_convertido" in p.stem:
            continue
        anio, mes = re.search(r"_(\d{4})_\|?(\d{2})", p.name).groups()
        if int(anio) in anios and ((anio, mes) not in por_mes or por_mes[(anio, mes)].suffix.lower() == ".csv"):
            por_mes[(anio, mes)] = p
    v = pd.concat([leer_vue.leer(p) for p in por_mes.values()], ignore_index=True)

    paises = pd.read_csv(RAIZ_REPO / "config" / "paises_vue.csv", dtype=str, keep_default_na=False)
    codigo = dict(zip(paises["pais_vue"], paises["codigo_dnit"]))
    v["PAIS_NORM"] = v["PAISDESTINO"].map(normalizar)
    v["CODIGO_PAIS"] = v["PAIS_NORM"].map(codigo)
    sin_codigo = sorted(v.loc[v["CODIGO_PAIS"].isna(), "PAIS_NORM"].unique())
    if sin_codigo:
        print("AVISO: países de la VUE sin código en config/paises_vue.csv (se omiten):", sin_codigo)
    v = v[v["CODIGO_PAIS"].notna()]
    v["AÑO"] = v["ANOMES"].astype(str).str[:4].astype(int)
    v["PARTIDA"] = v["CAPITULO"].fillna("s/d")
    return (v.groupby(["AÑO", "CODIGO_PAIS", "PARTIDA"], as_index=False)
             .agg(VUE_FOB=("FOBDOLAR", "sum"), VUE_TONELADAS=("TONELADA", "sum"),
                  VUE_NOMBRE_PAIS=("PAISDESTINO", "first")))


def codigos_por_nombre():
    """Nombre de país normalizado -> código de la DNIT (config/paises_dnit.csv y paises_vue.csv)."""
    tabla = {}
    for archivo, col in (("paises_vue.csv", "pais_vue"), ("paises_dnit.csv", "pais_dnit")):
        t = pd.read_csv(RAIZ_REPO / "config" / archivo, dtype=str, keep_default_na=False)
        tabla.update(dict(zip(t[col].map(normalizar), t["codigo_dnit"])))
    return tabla


def resumen_dnit_anio(carpeta, anio, regimenes_si, acuerdos):
    """Exportaciones de la DNIT de un año, por país y partida (con y sin acuerdo)."""
    archivos = sorted(p for p in carpeta.rglob("*")
                      if p.suffix.lower() in (".json", ".txt", ".csv", ".xlsx", ".parquet")
                      and pd_dnit.archivo_en_periodo(p, [anio], "TODOS"))
    if not archivos:
        return None
    partes = []
    for ruta in archivos:
        print(f"  Leyendo {ruta.name} ...", flush=True)
        df = pd_dnit.estandarizar_columnas(pd_dnit.leer_archivo(ruta))
        partes.append(df[df["OPERACION"].str.startswith("EXP")])
    base = pd.concat(partes, ignore_index=True)
    con_item = base["ITEM"] != ""
    base = pd.concat([base[con_item].drop_duplicates(["DESPACHO_CIFRADO", "ITEM"]), base[~con_item]],
                     ignore_index=True)
    d = pd_dnit.transformar(base, regimenes_si, acuerdos)
    d = d[(d["MOTIVO_EXCLUSION"] == "") & (d["AÑO_INT"] == anio)]

    # Desde ~2016 el país viene como "BR - BRASIL"; antes, muchas veces solo "BRASIL".
    # Sin código, se busca el nombre en config/paises_dnit.csv (y en paises_vue.csv).
    d["CODIGO_PAIS"] = d["PAIS_PROC_DEST"].str.extract(r"^([A-Z0-9]{2}) - ")[0]
    d["DNIT_NOMBRE_PAIS"] = d["PAIS_PROC_DEST"].str.replace(r"^[A-Z0-9]{2} - ", "", regex=True)
    sin = d["CODIGO_PAIS"].isna()
    if sin.any():
        tabla = codigos_por_nombre()
        d.loc[sin, "CODIGO_PAIS"] = d.loc[sin, "DNIT_NOMBRE_PAIS"].map(normalizar).map(tabla)
        # Despachos sin país de destino: se conservan como "SD" (sin dato) para no perder su valor
        vacio = d["DNIT_NOMBRE_PAIS"].str.strip() == ""
        d.loc[vacio, "CODIGO_PAIS"] = "SD"
        d.loc[vacio, "DNIT_NOMBRE_PAIS"] = "SIN DATO DE PAIS"
        faltan = sorted(d.loc[d["CODIGO_PAIS"].isna(), "DNIT_NOMBRE_PAIS"].unique())
        if faltan:
            print(f"  AVISO: países sin código (agregarlos a config/paises_dnit.csv): {faltan}")
    d["PARTIDA"] = d["POSICION_NCM"].str.replace(".", "", regex=False).str[:4]
    d["CON"] = np.where(d["TIPO_ACUERDO"].isin(TIPOS_CON_ACUERDO), d["FOB_DOLAR"], 0.0)
    d["SIN"] = d["FOB_DOLAR"] - d["CON"]
    meses = sorted(d["MES_NUM"].unique())
    d["CODIGO_PAIS"] = d["CODIGO_PAIS"].fillna("??")   # país sin código: no se pierde su valor
    r = (d.groupby(["AÑO_INT", "CODIGO_PAIS", "PARTIDA"], as_index=False)
          .agg(DNIT_FOB_TOTAL=("FOB_DOLAR", "sum"), DNIT_FOB_CON_ACUERDO=("CON", "sum"),
               DNIT_FOB_SIN_ACUERDO=("SIN", "sum"), DNIT_NOMBRE_PAIS=("DNIT_NOMBRE_PAIS", "first"))
          .rename(columns={"AÑO_INT": "AÑO"}))
    r["DNIT_MESES"] = len(meses)
    return r


def cargar_dnit(carpeta, anios, carpeta_resumen):
    """Un resumen por año. Si ya existe en carpeta_resumen, se reutiliza: así los archivos de la
    DNIT de un año pueden borrarse una vez resumidos (útil con poco espacio en disco)."""
    regimenes_si, _, acuerdos = pd_dnit.cargar_config()
    carpeta_resumen.mkdir(parents=True, exist_ok=True)
    partes, faltan = [], []
    for anio in anios:
        ruta = carpeta_resumen / f"dnit_exportaciones_{anio}.csv"
        if ruta.exists():
            print(f"{anio}: resumen ya calculado ({ruta.name})")
            partes.append(pd.read_csv(ruta, dtype={"CODIGO_PAIS": str, "PARTIDA": str}, keep_default_na=False,
                                      na_values=[""]))
            continue
        print(f"{anio}: procesando los archivos de la DNIT ...", flush=True)
        r = resumen_dnit_anio(carpeta, anio, regimenes_si, acuerdos)
        if r is None:
            faltan.append(anio)
            continue
        r.to_csv(ruta, index=False, encoding="utf-8-sig")
        partes.append(r)
    if faltan:
        sys.exit(f"Faltan los archivos de la DNIT de {faltan} en {carpeta}. "
                 "Descárguelos con: python python/descargar_dnit.py --anios ...")
    return pd.concat(partes, ignore_index=True)


def resumir(df, claves):
    medidas = ["VUE_FOB", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO", "DNIT_FOB_SIN_ACUERDO"]
    out = df.groupby(claves, as_index=False)[medidas].sum()
    out["DIFERENCIA_VUE_MENOS_DNIT"] = out["VUE_FOB"] - out["DNIT_FOB_TOTAL"]
    out["VUE_SOBRE_DNIT_TOTAL_PCT"] = np.where(out["DNIT_FOB_TOTAL"] > 0,
                                               out["VUE_FOB"] / out["DNIT_FOB_TOTAL"].where(out["DNIT_FOB_TOTAL"] > 0, 1) * 100,
                                               np.nan)
    out["DNIT_CON_ACUERDO_PCT"] = np.where(out["DNIT_FOB_TOTAL"] > 0,
                                           out["DNIT_FOB_CON_ACUERDO"] / out["DNIT_FOB_TOTAL"].where(out["DNIT_FOB_TOTAL"] > 0, 1) * 100,
                                           np.nan)
    return out


def main():
    parser = argparse.ArgumentParser(description="Cruce DNIT vs. VUE (exportaciones)")
    parser.add_argument("--anios", required=True, help="p. ej. 2020 o 2015-2025")
    parser.add_argument("--dnit", default="datos_dnit", help="carpeta con los archivos de la DNIT")
    parser.add_argument("--salida", default="salidas/Cruce_DNIT_VUE.xlsx")
    parser.add_argument("--resumenes", default="salidas/resumen_dnit",
                        help="carpeta donde se guarda el resumen anual de la DNIT (se reutiliza)")
    args = parser.parse_args()
    anios = pd_dnit.leer_rango_anios(args.anios)
    carpeta = Path(args.dnit) if Path(args.dnit).is_absolute() else RAIZ_REPO / args.dnit

    vue = cargar_vue(anios)
    carpeta_resumen = Path(args.resumenes) if Path(args.resumenes).is_absolute() else RAIZ_REPO / args.resumenes
    dnit = cargar_dnit(carpeta, anios, carpeta_resumen)
    cruce = vue.merge(dnit, on=["AÑO", "CODIGO_PAIS", "PARTIDA"], how="outer")
    for c in ["VUE_FOB", "VUE_TONELADAS", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO", "DNIT_FOB_SIN_ACUERDO"]:
        cruce[c] = cruce[c].fillna(0.0)
    nombres = (pd.concat([dnit[["CODIGO_PAIS", "DNIT_NOMBRE_PAIS"]].rename(columns={"DNIT_NOMBRE_PAIS": "PAIS"}),
                          vue[["CODIGO_PAIS", "VUE_NOMBRE_PAIS"]].rename(columns={"VUE_NOMBRE_PAIS": "PAIS"})])
               .drop_duplicates("CODIGO_PAIS").set_index("CODIGO_PAIS")["PAIS"])
    cruce["PAIS"] = cruce["CODIGO_PAIS"].map(nombres)

    por_anio = resumir(cruce, ["AÑO"])
    por_pais = resumir(cruce, ["AÑO", "CODIGO_PAIS", "PAIS"]).sort_values(["AÑO", "VUE_FOB"], ascending=[True, False])
    con_partida = cruce[cruce["PARTIDA"] != "s/d"]
    por_partida = resumir(con_partida, ["AÑO", "PARTIDA"]).sort_values(["AÑO", "VUE_FOB"], ascending=[True, False])
    detalle = resumir(con_partida, ["AÑO", "CODIGO_PAIS", "PAIS", "PARTIDA"]).sort_values(
        ["AÑO", "VUE_FOB"], ascending=[True, False])

    notas = pd.DataFrame({"Notas": [
        "VUE: valor FOB de TODOS los certificados de origen emitidos (preferenciales y no preferenciales). "
        "No indica el acuerdo. Origen de los datos: Ministerio de Industria y Comercio.",
        "DNIT: exportaciones definitivas de origen paraguayo según los despachos (mismos filtros que procesar_despachos.py). "
        "Con acuerdo = PREFERENCIAL + MERCOSUR intrazona.",
        "Fechas: VUE = emisión del certificado; DNIT = cancelación del despacho. Por eso se compara por año.",
        "Destino: VUE = el del certificado (en general, destino final); DNIT = el declarado en la aduana. "
        "Diferencias grandes en Argentina, Brasil o Uruguay suelen deberse a mercadería en tránsito hacia otros destinos.",
        "Partida = 4 primeros dígitos de la NCM. La VUE de 2011 no trae partida: solo aparece en 'Por año' y 'Por país'.",
        "Países: se cruzan por el código de la DNIT; las equivalencias de nombres están en config/paises_vue.csv.",
        "Valores atípicos conocidos de la VUE: octubre y noviembre de 2022, partidas 6406 y 3904 a Brasil (ver datos_vue/LEEME.md).",
    ]})

    salida = Path(args.salida) if Path(args.salida).is_absolute() else RAIZ_REPO / args.salida
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida, engine="xlsxwriter") as w:
        for nombre, t in (("Por año", por_anio), ("Por país", por_pais), ("Por partida", por_partida),
                          ("País y partida", detalle), ("Notas", notas)):
            t.to_excel(w, sheet_name=nombre, index=False)
            hoja = w.sheets[nombre]
            fmt_usd = w.book.add_format({"num_format": "#,##0"})
            fmt_pct = w.book.add_format({"num_format": "0.0"})
            for i, col in enumerate(t.columns):
                ancho = 14 if col != "Notas" else 120
                formato = fmt_pct if col.endswith("_PCT") else (fmt_usd if col.startswith(("VUE_FOB", "DNIT_FOB", "DIFERENCIA")) else None)
                hoja.set_column(i, i, ancho if col != "PAIS" else 28, formato)
            hoja.freeze_panes(1, 0)

    print(f"\nCruce guardado en {salida}")
    vista = por_anio.copy()
    for c in ["VUE_FOB", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO"]:
        vista[c] = (vista[c] / 1e6).round(1)
    print("\nMillones de USD:")
    print(vista[["AÑO", "VUE_FOB", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO", "VUE_SOBRE_DNIT_TOTAL_PCT"]]
          .round(1).to_string(index=False))


if __name__ == "__main__":
    main()
