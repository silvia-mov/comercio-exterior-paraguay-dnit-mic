"""
Lee los reportes mensuales del SICEX del BCP (datos_bcp/<año>/BCP_DATOS_MENSUALES_<año>_A_8D.csv)
y los pasa a formato largo: una fila por mes, código NCM de 8 dígitos y país.

Uso (desde la raíz del repositorio):
    python python/leer_bcp.py                  # todos los años -> salidas/BCP_exportaciones.csv
    python python/leer_bcp.py --anios 2021

Columnas: AÑO, MES, NCM (8 dígitos, sin puntos), PARTIDA (4 dígitos), DESCRIPCION,
CODIGO_PAIS (el de la DNIT, ver config/paises_dnit.csv), PAIS, KILOS_NETOS, FOB_DOLAR,
ELECTRICIDAD (True para la NCM 2716, que no pasa por la aduana).
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cruzar_dnit_vue import codigos_por_nombre, normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def leer_archivo(ruta):
    d = pd.read_csv(ruta, sep="\t", dtype=str, encoding="utf-8")
    d = d.loc[:, ~d.columns.str.startswith("Unnamed")]
    d = d[d.iloc[:, 0].str.strip() != "Total"]
    producto, pais = d.columns[:2]
    partes = []
    for col in d.columns[2:]:
        m = re.match(r"(\w+) - (\d{4})\s+(Kilos Netos|Fob D[oó]lar)", col)
        if not m:            # columnas del total anual
            continue
        mes, anio, medida = m.groups()
        partes.append(pd.DataFrame({
            "AÑO": int(anio), "MES": MESES[mes.lower()],
            "PRODUCTO": d[producto].values, "PAIS": d[pais].values,
            "MEDIDA": "KILOS_NETOS" if medida.startswith("Kilos") else "FOB_DOLAR",
            "VALOR": pd.to_numeric(d[col], errors="coerce").fillna(0).values,
        }))
    largo = pd.concat(partes, ignore_index=True)
    # Sin código o sin país, pivot_table descartaría la fila sin avisar
    assert largo["PRODUCTO"].notna().all() and largo["PAIS"].notna().all(), f"{ruta}: filas sin producto o país"
    t = (largo.pivot_table(index=["AÑO", "MES", "PRODUCTO", "PAIS"], columns="MEDIDA",
                           values="VALOR", aggfunc="sum").reset_index())
    t.columns.name = None
    t = t[(t["FOB_DOLAR"] != 0) | (t["KILOS_NETOS"] != 0)]
    t["NCM"] = t["PRODUCTO"].str.extract(r"^([\d.]+)")[0].str.replace(".", "", regex=False)
    t["DESCRIPCION"] = t["PRODUCTO"].str.replace(r"^[\d.]+\s*-\s*", "", regex=True)
    t["PARTIDA"] = t["NCM"].str[:4]
    t["CODIGO_PAIS"] = t["PAIS"].map(normalizar).map(codigos_por_nombre()).fillna("??")
    t["ELECTRICIDAD"] = t["PARTIDA"] == "2716"
    # Control: el total coincide con la fila "Total" del archivo (que el BCP calcula con decimales;
    # las filas vienen redondeadas a dólares, por eso se tolera una diferencia pequeña).
    total = pd.read_csv(ruta, sep="\t", dtype=str, encoding="utf-8")
    total = total[total.iloc[:, 0].str.strip() == "Total"]
    col = [c for c in total.columns if c.endswith("TOTAL FOB DOLAR")]
    if len(total) and col:
        diferencia = abs(t["FOB_DOLAR"].sum() - float(total[col[0]].iloc[0]))
        assert diferencia < 1000, f"{ruta}: el total leído difiere en USD {diferencia:,.0f} del archivo"
    return t[["AÑO", "MES", "NCM", "PARTIDA", "DESCRIPCION", "CODIGO_PAIS", "PAIS",
              "KILOS_NETOS", "FOB_DOLAR", "ELECTRICIDAD"]]


def leer(anios=None):
    rutas = sorted((RAIZ / "datos_bcp").glob("*/BCP_DATOS_MENSUALES_*_A_8D.csv"))
    if anios:
        rutas = [r for r in rutas if int(r.parent.name) in anios]
    if not rutas:
        raise SystemExit("No hay archivos del BCP en datos_bcp/ para esos años.")
    return pd.concat([leer_archivo(r) for r in rutas], ignore_index=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anios", default="", help="por ejemplo 2021 o 2011-2026 (vacío = todos)")
    ap.add_argument("--salida", default=str(RAIZ / "salidas" / "BCP_exportaciones.csv"))
    args = ap.parse_args()
    anios = None
    if args.anios:
        anios = set()
        for p in args.anios.split(","):
            a, _, b = p.partition("-")
            anios.update(range(int(a), int(b or a) + 1))
    t = leer(anios)
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(args.salida, index=False, encoding="utf-8-sig")
    print(t.groupby("AÑO")["FOB_DOLAR"].sum().div(1e6).round(1).to_string())
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
