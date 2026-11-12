"""
Cruce de las cuatro fuentes de exportaciones de Paraguay, desde 2011
=====================================================================

  DNIT     despachos de aduana (datos abiertos): regímenes definitivos, origen paraguayo,
           destino DECLARADO, separados en "con acuerdo" y "sin acuerdo". Sin electricidad.
  VUE      certificados de origen (MIC): destino final, todos los certificados (con y sin
           preferencia). Sin electricidad.
  BCP      estadística oficial (SICEX): todos los regímenes, destino final según el certificado
           de origen, INCLUYE la electricidad (NCM 2716).
  ESPEJO   lo que cada país declara haber importado desde Paraguay (UN Comtrade). Valor CIF del
           país comprador. Anual; el último año suele estar incompleto.

TASA DE UTILIZACIÓN
  Parte de las exportaciones que usa efectivamente una preferencia de un acuerdo comercial:
      utilización = DNIT con acuerdo / DNIT total
  Se calcula con la DNIT en el numerador y el denominador (misma fuente, mismo destino).
  También se informa "con acuerdo / BCP sin electricidad" (denominador oficial).

AÑO EN CURSO
  Para que las fuentes sean comparables, el año en curso usa solo los meses que tiene el BCP
  (el que se publica más tarde). La DNIT de esos meses se resume aparte en
  salidas/resumen_dnit_<meses>/ (ver cargar_dnit_parcial).

Uso:
    python python/cruzar_fuentes.py                      # 2011 al último año del BCP
    python python/cruzar_fuentes.py --anios 2015-2025

Necesita: salidas/resumen_dnit/ (lo genera cruzar_dnit_vue.py), datos_vue/, datos_bcp/ y,
opcionalmente, datos_comtrade/espejo/ (descargar_comtrade.py --espejo).

Salida: salidas/Cruce_4_fuentes.xlsx
  Por año · Utilización por socio · Por país · Por partida · Notas
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leer_bcp  # noqa: E402
import leer_vue  # noqa: E402
from cruzar_dnit_vue import normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SALIDAS = RAIZ / "salidas"
# Comtrade no da código ISO2 a algunos informantes
ISO2_EXTRA = {490: "TW"}   # "Other Asia, nes" = Taiwán
CLAVES = ["AÑO", "CODIGO_PAIS", "PARTIDA"]


def leer_rango(texto):
    anios = set()
    for p in texto.split(","):
        a, _, b = p.partition("-")
        anios.update(range(int(a), int(b or a) + 1))
    return sorted(anios)


# --------------------------------------------------------------------------- fuentes
def cargar_bcp(anios):
    b = leer_bcp.leer(set(anios))
    meses = b.groupby("AÑO")["MES"].nunique().to_dict()
    b["BCP_ELECTRICIDAD"] = np.where(b["ELECTRICIDAD"], b["FOB_DOLAR"], 0.0)
    r = (b.groupby(CLAVES, as_index=False)
          .agg(BCP_FOB=("FOB_DOLAR", "sum"), BCP_ELECTRICIDAD=("BCP_ELECTRICIDAD", "sum"),
               BCP_NOMBRE_PAIS=("PAIS", "first")))
    return r, meses


def cargar_dnit(anios, meses):
    """Resúmenes anuales de la DNIT. Un año con menos de 12 meses en el BCP usa el resumen
    de esos meses (salidas/resumen_dnit_ene_<mes>/)."""
    partes = []
    for anio in anios:
        n = meses.get(anio, 12)
        if n == 12:
            ruta = SALIDAS / "resumen_dnit" / f"dnit_exportaciones_{anio}.csv"
        else:
            ruta = SALIDAS / f"resumen_dnit_{carpeta_meses(n)}" / f"dnit_exportaciones_{anio}.csv"
        if not ruta.exists():
            sys.exit(f"Falta {ruta}. Genérelo con cruzar_dnit_vue.py (ver docstring).")
        r = pd.read_csv(ruta, dtype={"CODIGO_PAIS": str, "PARTIDA": str}, keep_default_na=False, na_values=[""])
        if r["DNIT_MESES"].iloc[0] != n:
            sys.exit(f"{ruta} tiene {r['DNIT_MESES'].iloc[0]} meses y el BCP {n}.")
        partes.append(r.drop(columns="DNIT_MESES"))
    return pd.concat(partes, ignore_index=True)


def carpeta_meses(n):
    nombres = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"ene_{nombres[n - 1]}"


def cargar_vue(anios, meses):
    por_mes = {}
    for p in sorted((RAIZ / "datos_vue").rglob("Exportaciones_*")):
        if not p.is_file() or "_convertido" in p.stem:
            continue
        anio, mes = (int(x) for x in re.search(r"_(\d{4})_\|?(\d{2})", p.name).groups())
        if anio in anios and mes <= meses.get(anio, 12):
            if (anio, mes) not in por_mes or por_mes[(anio, mes)].suffix.lower() == ".csv":
                por_mes[(anio, mes)] = p
    v = pd.concat([leer_vue.leer(p) for p in por_mes.values()], ignore_index=True)
    paises = pd.read_csv(RAIZ / "config" / "paises_vue.csv", dtype=str, keep_default_na=False)
    v["CODIGO_PAIS"] = v["PAISDESTINO"].map(normalizar).map(dict(zip(paises["pais_vue"], paises["codigo_dnit"])))
    v["CODIGO_PAIS"] = v["CODIGO_PAIS"].fillna("??")
    v["AÑO"] = v["ANOMES"].astype(str).str[:4].astype(int)
    v["PARTIDA"] = v["CAPITULO"].fillna("s/d")
    return v.groupby(CLAVES, as_index=False).agg(VUE_FOB=("FOBDOLAR", "sum"))


def cargar_espejo(anios):
    archivos = sorted((RAIZ / "datos_comtrade" / "espejo").glob("Comtrade_espejo_PRY_*_AG6.csv"))
    archivos = [a for a in archivos if int(re.search(r"_(\d{4})_", a.name).group(1)) in anios]
    if not archivos:
        print("AVISO: no hay datos espejo de Comtrade (descargar_comtrade.py --espejo); se omiten.")
        return pd.DataFrame(columns=CLAVES + ["ESPEJO_CIF", "ESPEJO_ELECTRICIDAD"])
    e = pd.concat([pd.read_csv(a, dtype={"PARTIDA": str, "PAIS_CODIGO_ISO2": str}, keep_default_na=False)
                   for a in archivos], ignore_index=True)
    e["CODIGO_PAIS"] = e["PAIS_CODIGO_ISO2"].replace("", np.nan)
    e.loc[e["CODIGO_PAIS"].isna() & (e["PAIS"].str.contains("Other Asia")), "CODIGO_PAIS"] = "TW"
    e["CODIGO_PAIS"] = e["CODIGO_PAIS"].fillna("??")
    e["PARTIDA"] = e["PARTIDA"].str.zfill(6).str[:4]
    e["VALOR_DOLAR"] = pd.to_numeric(e["VALOR_DOLAR"], errors="coerce").fillna(0)
    e["ESPEJO_ELECTRICIDAD"] = np.where(e["PARTIDA"] == "2716", e["VALOR_DOLAR"], 0.0)
    return (e.groupby(CLAVES, as_index=False)
             .agg(ESPEJO_CIF=("VALOR_DOLAR", "sum"), ESPEJO_ELECTRICIDAD=("ESPEJO_ELECTRICIDAD", "sum")))


# --------------------------------------------------------------------------- tablas
MEDIDAS = ["DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO", "DNIT_FOB_SIN_ACUERDO", "VUE_FOB",
           "BCP_FOB", "BCP_ELECTRICIDAD", "ESPEJO_CIF", "ESPEJO_ELECTRICIDAD"]


def pct(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1) * 100, np.nan)


def agregar(base, claves):
    t = base.groupby(claves, as_index=False)[MEDIDAS].sum()
    t["BCP_SIN_ELECTRICIDAD"] = t["BCP_FOB"] - t["BCP_ELECTRICIDAD"]
    t["ESPEJO_SIN_ELECTRICIDAD"] = t["ESPEJO_CIF"] - t["ESPEJO_ELECTRICIDAD"]
    t["UTILIZACION_PCT"] = pct(t["DNIT_FOB_CON_ACUERDO"], t["DNIT_FOB_TOTAL"])
    t["CON_ACUERDO_SOBRE_BCP_PCT"] = pct(t["DNIT_FOB_CON_ACUERDO"], t["BCP_SIN_ELECTRICIDAD"])
    t["DNIT_SOBRE_BCP_PCT"] = pct(t["DNIT_FOB_TOTAL"], t["BCP_SIN_ELECTRICIDAD"])
    t["VUE_SOBRE_BCP_PCT"] = pct(t["VUE_FOB"], t["BCP_SIN_ELECTRICIDAD"])
    t["ESPEJO_SOBRE_BCP_PCT"] = pct(t["ESPEJO_SIN_ELECTRICIDAD"], t["BCP_SIN_ELECTRICIDAD"])
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anios", default="", help="por defecto: 2011 al último año del BCP")
    ap.add_argument("--salida", default=str(SALIDAS / "Cruce_4_fuentes.xlsx"))
    args = ap.parse_args()

    disponibles = sorted(int(p.name) for p in (RAIZ / "datos_bcp").iterdir() if p.name.isdigit())
    anios = leer_rango(args.anios) if args.anios else [a for a in disponibles if a >= 2011]

    bcp, meses = cargar_bcp(anios)
    print("Meses por año (BCP):", meses)
    dnit = cargar_dnit(anios, meses)
    vue = cargar_vue(anios, meses)
    espejo = cargar_espejo(anios)

    nombres = (pd.concat([dnit[["CODIGO_PAIS", "DNIT_NOMBRE_PAIS"]].rename(columns={"DNIT_NOMBRE_PAIS": "PAIS"}),
                          bcp[["CODIGO_PAIS", "BCP_NOMBRE_PAIS"]].rename(columns={"BCP_NOMBRE_PAIS": "PAIS"})])
               .dropna().drop_duplicates("CODIGO_PAIS").set_index("CODIGO_PAIS")["PAIS"])
    # Controles (McKinney, Python for Data Analysis, caps. 8 y 10): ninguna clave vacía (groupby las
    # descarta sin avisar) ni repetida (un merge de muchos a muchos duplica valores).
    for nombre, t in (("DNIT", dnit), ("VUE", vue), ("BCP", bcp), ("ESPEJO", espejo)):
        assert not t[CLAVES].isna().any().any(), f"{nombre}: claves vacías"
        assert not t.duplicated(CLAVES).any(), f"{nombre}: claves repetidas"
    base = (dnit.drop(columns="DNIT_NOMBRE_PAIS")
            .merge(vue, on=CLAVES, how="outer", validate="one_to_one")
            .merge(bcp.drop(columns="BCP_NOMBRE_PAIS"), on=CLAVES, how="outer", validate="one_to_one")
            .merge(espejo, on=CLAVES, how="outer", validate="one_to_one"))
    base[MEDIDAS] = base[MEDIDAS].fillna(0.0)
    # El cruce no cambia los totales de ninguna fuente
    for col, t in (("DNIT_FOB_TOTAL", dnit), ("VUE_FOB", vue), ("BCP_FOB", bcp), ("ESPEJO_CIF", espejo)):
        assert abs(base[col].sum() - t[col].sum()) < 1, f"{col}: el cruce cambió el total"
    base["PAIS"] = base["CODIGO_PAIS"].map(nombres).fillna(base["CODIGO_PAIS"])

    por_anio = agregar(base, ["AÑO"])
    por_anio.insert(1, "MESES", por_anio["AÑO"].map(meses))
    sin_espejo = ~por_anio["AÑO"].isin(espejo["AÑO"].unique())
    por_anio.loc[sin_espejo, ["ESPEJO_CIF", "ESPEJO_ELECTRICIDAD", "ESPEJO_SIN_ELECTRICIDAD",
                              "ESPEJO_SOBRE_BCP_PCT"]] = np.nan

    por_pais = agregar(base, ["AÑO", "CODIGO_PAIS", "PAIS"]).sort_values(["AÑO", "BCP_FOB"], ascending=[True, False])
    socios = por_pais[por_pais.groupby("CODIGO_PAIS")["DNIT_FOB_CON_ACUERDO"].transform("sum") > 0]
    utilizacion = socios[["AÑO", "CODIGO_PAIS", "PAIS", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO",
                          "DNIT_FOB_SIN_ACUERDO", "UTILIZACION_PCT"]]
    por_partida = agregar(base, ["AÑO", "PARTIDA"])

    notas = pd.DataFrame({"Nota": [
        "Valores en dólares. DNIT, VUE y BCP en FOB; ESPEJO en CIF del país comprador (incluye flete y seguro).",
        "Desde 2011, el primer año con las cuatro fuentes. El año en curso usa solo los meses que tiene el BCP "
        "(columna MESES), también en la DNIT y la VUE.",
        "UTILIZACION_PCT = DNIT con acuerdo / DNIT total: parte de lo exportado que usó una preferencia arancelaria.",
        "CON_ACUERDO_SOBRE_BCP_PCT = DNIT con acuerdo / BCP sin electricidad (denominador oficial, más amplio: "
        "incluye todos los regímenes).",
        "Electricidad (NCM 2716): solo en el BCP y en el espejo; no pasa por la aduana ni tiene certificado de origen. "
        "Para comparar se usan las columnas SIN_ELECTRICIDAD.",
        "Destino: la DNIT usa el país declarado en el despacho; la VUE y el BCP, el destino final del certificado de "
        "origen; el espejo, el país que informa la compra. Por eso la comparación por país difiere más que el total.",
        "Los dos últimos años del BCP son preliminares (cambian sobre todo los destinos).",
        "ESPEJO vacío = Comtrade todavía no tiene datos de ese año. Los últimos años suelen estar incompletos "
        "(faltan países por informar).",
        "La VUE de 2011 no trae la partida (PARTIDA = s/d).",
        "Fuentes: DNIT (datos abiertos de aduanas); VUE (origen de los datos: Ministerio de Industria y Comercio); "
        "BCP (SICEX); UN Comtrade.",
    ]})

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida, engine="xlsxwriter") as w:
        for nombre, t in (("Por año", por_anio), ("Utilización por socio", utilizacion),
                          ("Por país", por_pais), ("Por partida", por_partida), ("Notas", notas)):
            t.to_excel(w, sheet_name=nombre, index=False)
            ws = w.sheets[nombre]
            ws.freeze_panes(1, 0)
            ws.set_column(0, len(t.columns) - 1, 16 if nombre != "Notas" else 120)
    por_anio.to_csv(SALIDAS / "cruce_4_fuentes_por_anio.csv", index=False, encoding="utf-8-sig")
    utilizacion.to_csv(SALIDAS / "cruce_4_fuentes_utilizacion_socios.csv", index=False, encoding="utf-8-sig")

    m = por_anio.set_index("AÑO")
    vista = pd.DataFrame({
        "Meses": m["MESES"],
        "BCP s/elec.": m["BCP_SIN_ELECTRICIDAD"] / 1e6,
        "DNIT": m["DNIT_FOB_TOTAL"] / 1e6,
        "VUE": m["VUE_FOB"] / 1e6,
        "Espejo s/elec.": m["ESPEJO_SIN_ELECTRICIDAD"] / 1e6,
        "Con acuerdo": m["DNIT_FOB_CON_ACUERDO"] / 1e6,
        "Utiliz. %": m["UTILIZACION_PCT"],
    }).round(1)
    print("\nMillones de USD:\n" + vista.to_string())
    print("\nGuardado en", salida)


if __name__ == "__main__":
    main()
