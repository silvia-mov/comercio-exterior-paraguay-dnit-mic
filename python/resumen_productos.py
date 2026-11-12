"""
Resumen por producto de un año de despachos de la DNIT (exportaciones e importaciones)
======================================================================================

Agrupa los despachos válidos (mismos filtros que procesar_despachos.py: regímenes definitivos,
origen paraguayo en las exportaciones, sin fracciones complementarias, etc.) por:

    AÑO, OPERACION, NCM (8 dígitos), CODIGO_PAIS, TIPO_ACUERDO, ACUERDO_CONSOLIDADO

con VALOR_USD (FOB en exportaciones, CIF en importaciones) y PESO_NETO_KG. Con este resumen se
arman los rankings de productos y la tasa de utilización por producto (productos_acuerdos.py).

Uso:
    python python/resumen_productos.py datos_dnit --anios 2021
    -> salidas/productos/productos_2021.csv  (y descripciones_ncm_2021.csv)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import procesar_despachos as pd_dnit  # noqa: E402
from cruzar_dnit_vue import codigos_por_nombre, normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def resumen_anio(carpeta, anio):
    regimenes_si, _, acuerdos = pd_dnit.cargar_config()
    archivos = sorted(p for p in Path(carpeta).rglob("*")
                      if p.suffix.lower() in (".json", ".txt", ".csv", ".xlsx", ".parquet")
                      and pd_dnit.archivo_en_periodo(p, [anio], "TODOS"))
    if not archivos:
        raise SystemExit(f"No hay archivos de {anio} en {carpeta}")
    partes = []
    for ruta in archivos:
        print(f"  Leyendo {ruta.name} ...", flush=True)
        partes.append(pd_dnit.estandarizar_columnas(pd_dnit.leer_archivo(ruta)))
    base = pd.concat(partes, ignore_index=True)
    con_item = base["ITEM"] != ""
    base = pd.concat([base[con_item].drop_duplicates(["DESPACHO_CIFRADO", "ITEM"]), base[~con_item]],
                     ignore_index=True)
    d = pd_dnit.transformar(base, regimenes_si, acuerdos)
    d = d[(d["MOTIVO_EXCLUSION"] == "") & (d["AÑO_INT"] == anio)].copy()

    # País: "BR - BRASIL" -> BR; en los archivos viejos solo viene el nombre
    d["CODIGO_PAIS"] = d["PAIS_PROC_DEST"].str.extract(r"^([A-Z0-9]{2}) - ")[0]
    sin = d["CODIGO_PAIS"].isna()
    if sin.any():
        nombres = d.loc[sin, "PAIS_PROC_DEST"].str.replace(r"^[A-Z0-9]{2} - ", "", regex=True)
        d.loc[sin, "CODIGO_PAIS"] = nombres.map(normalizar).map(codigos_por_nombre())
        d.loc[sin & (nombres.str.strip() == ""), "CODIGO_PAIS"] = "SD"
    d["CODIGO_PAIS"] = d["CODIGO_PAIS"].fillna("??")
    d["NCM"] = d["POSICION_NCM"].str.replace(r"\D", "", regex=True).str[:8].replace("", "sin_dato")

    claves = ["AÑO_INT", "OPERACION", "NCM", "CODIGO_PAIS", "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO"]
    assert not d[claves].isna().any().any(), "claves vacías: se perderían filas al agrupar"
    r = (d.groupby(claves, as_index=False)
          .agg(VALOR_USD=("VALOR_DOLAR", "sum"), PESO_NETO_KG=("PESO_NETO_KG", "sum"))
          .rename(columns={"AÑO_INT": "AÑO"}))
    assert abs(r["VALOR_USD"].sum() - d["VALOR_DOLAR"].sum()) < 1
    # Descripción corta (partida) y completa (posición, con el capítulo y los guiones de la NCM)
    def mas_comun(s):
        s = s[s.str.strip() != ""]
        return s.value_counts().index[0] if len(s) else ""
    desc = (d.groupby("NCM").agg(DESCRIPCION_PARTIDA=("DESC_PARTIDA", mas_comun),
                                 DESCRIPCION_COMPLETA=("DESC_POSICION", mas_comun)).reset_index())
    meses = int(d["MES_NUM"].nunique())
    return r, desc, meses


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ruta", help="carpeta con los archivos de la DNIT")
    ap.add_argument("--anios", required=True, help="un año o un rango, p. ej. 2021 o 2011-2026")
    ap.add_argument("--salida", default=str(RAIZ / "salidas" / "productos"))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for anio in pd_dnit.leer_rango_anios(args.anios):
        r, desc, meses = resumen_anio(args.ruta, anio)
        r["MESES"] = meses
        r.to_csv(salida / f"productos_{anio}.csv", index=False, encoding="utf-8-sig")
        desc.to_csv(salida / f"descripciones_ncm_{anio}.csv", index=False, encoding="utf-8-sig")
        t = r.groupby("OPERACION")["VALOR_USD"].sum() / 1e6
        print(f"{anio}: {len(r):,} filas, {r['NCM'].nunique():,} códigos NCM, {meses} meses; "
              + ", ".join(f"{k}: USD {v:,.1f} M" for k, v in t.items()))


if __name__ == "__main__":
    main()
