"""
Productos que más usan los acuerdos comerciales (exportaciones e importaciones), 2011–2026
==========================================================================================

Lee los resúmenes por producto de salidas/productos/ (resumen_productos.py) y arma:

  Ranking            los productos con más comercio CON ACUERDO, por año (4 y 8 dígitos de la NCM),
                     con el acuerdo más usado por cada uno.
  % con acuerdo      de todo lo comerciado de cada producto, qué parte usó un acuerdo.
  Por acuerdo        los productos principales de cada acuerdo.

Todo sale directamente del campo "acuerdo" de cada despacho; no se usan las listas de productos con
preferencia de cada acuerdo. Por eso no se calcula qué productos "podrían" usar un acuerdo y no lo
usan: eso necesita esas listas (un producto puede no tener rebaja, o ya tener arancel cero para todos).

Uso:
    python python/productos_acuerdos.py          -> salidas/Productos_acuerdos.xlsx y docs/datos/
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "salidas" / "productos"
SALIDA = RAIZ / "salidas" / "Productos_acuerdos.xlsx"
WEB = RAIZ / "docs" / "datos"
CON = ["PREFERENCIAL", "MERCOSUR_INTRAZONA"]


def cargar():
    archivos = sorted(ORIGEN.glob("productos_*.csv"))
    if not archivos:
        sys.exit("No hay resúmenes en salidas/productos/. Corra antes resumen_productos.py.")
    t = pd.concat([pd.read_csv(a, dtype={"NCM": str, "CODIGO_PAIS": str}, keep_default_na=False,
                               na_values=[""]) for a in archivos], ignore_index=True)
    desc = pd.concat([pd.read_csv(a, dtype={"NCM": str}, keep_default_na=False)
                      for a in sorted(ORIGEN.glob("descripciones_ncm_*.csv"))], ignore_index=True)
    # La descripción puede venir vacía en algunos años: se toma la del último año que la tenga
    partes = {}
    for col in ("DESCRIPCION_PARTIDA", "DESCRIPCION_COMPLETA"):
        c = desc[desc[col].str.strip() != ""].drop_duplicates("NCM", keep="last").set_index("NCM")[col]
        partes[col] = c.str.replace(r"\s+", " ", regex=True).str.strip()
    desc = pd.DataFrame(partes)
    # Sin descripción de la partida: la completa sin el capítulo ("CAPITULO 12 ...")
    sin = desc["DESCRIPCION_PARTIDA"].isna()
    desc.loc[sin, "DESCRIPCION_PARTIDA"] = desc.loc[sin, "DESCRIPCION_COMPLETA"]
    desc = desc.fillna("")
    t["CON_ACUERDO"] = np.where(t["TIPO_ACUERDO"].isin(CON), t["VALOR_USD"], 0.0)
    return t, desc


def tabla(t, nivel, desc):
    """Por año, operación y producto: total, con acuerdo, con socios con acuerdo y utilización."""
    t = t.copy()
    t["PRODUCTO"] = t["NCM"].str[:nivel]
    r = (t.groupby(["AÑO", "MESES", "OPERACION", "PRODUCTO"], as_index=False)
          .agg(TOTAL_USD=("VALOR_USD", "sum"), CON_ACUERDO_USD=("CON_ACUERDO", "sum"),
               PESO_NETO_KG=("PESO_NETO_KG", "sum")))
    r["SIN_ACUERDO_USD"] = r["TOTAL_USD"] - r["CON_ACUERDO_USD"]
    r["CON_ACUERDO_PCT"] = r["CON_ACUERDO_USD"] / r["TOTAL_USD"].where(r["TOTAL_USD"] != 0) * 100
    # acuerdo más usado por cada producto (por valor)
    principal = (t[t["CON_ACUERDO"] > 0]
                 .groupby(["AÑO", "OPERACION", "PRODUCTO", "ACUERDO_CONSOLIDADO"])["CON_ACUERDO"].sum()
                 .reset_index().sort_values("CON_ACUERDO", ascending=False)
                 .drop_duplicates(["AÑO", "OPERACION", "PRODUCTO"])
                 .rename(columns={"ACUERDO_CONSOLIDADO": "ACUERDO_PRINCIPAL"})
                 [["AÑO", "OPERACION", "PRODUCTO", "ACUERDO_PRINCIPAL"]])
    r = r.merge(principal, on=["AÑO", "OPERACION", "PRODUCTO"], how="left", validate="one_to_one")
    r["ACUERDO_PRINCIPAL"] = r["ACUERDO_PRINCIPAL"].fillna("")
    if nivel == 4:
        d4 = desc.reset_index().assign(P=lambda x: x["NCM"].str[:4]).groupby("P")["DESCRIPCION_PARTIDA"].agg(
            lambda s: s[s != ""].value_counts().index[0] if (s != "").any() else "")
        r["DESCRIPCION"] = r["PRODUCTO"].map(d4).fillna("")
    else:
        r["DESCRIPCION"] = r["PRODUCTO"].map(desc["DESCRIPCION_COMPLETA"]).fillna("")
    # Quitar el prefijo "CAPITULO 12" que traen algunas descripciones completas
    r["DESCRIPCION"] = r["DESCRIPCION"].str.replace(r"^CAPITULO\s*\d+\s*", "", regex=True)
    # Nombre corto en lenguaje común (config/nombres_cortos_ncm.csv), por partida
    cortos = pd.read_csv(RAIZ / "config" / "nombres_cortos_ncm.csv", dtype=str).set_index("partida")["nombre_corto"]
    r.insert(r.columns.get_loc("PRODUCTO") + 1, "NOMBRE_CORTO", r["PRODUCTO"].str[:4].map(cortos).fillna(""))
    return r


def ranking(r, n=20):
    return (r.sort_values(["AÑO", "OPERACION", "CON_ACUERDO_USD"], ascending=[True, True, False])
             .groupby(["AÑO", "OPERACION"]).head(n))


def main():
    t, desc = cargar()
    p4, p8 = tabla(t, 4, desc), tabla(t, 8, desc)
    for nivel, r in ((4, p4), (8, p8)):
        total = t.groupby("AÑO")["VALOR_USD"].sum()
        assert np.allclose(r.groupby("AÑO")["TOTAL_USD"].sum().reindex(total.index), total), f"{nivel}: total distinto"

    t4 = t.assign(PRODUCTO=t["NCM"].str[:4])
    por_acuerdo = (t4[t4["CON_ACUERDO"] > 0]
                   .groupby(["AÑO", "OPERACION", "ACUERDO_CONSOLIDADO", "PRODUCTO"], as_index=False)["VALOR_USD"].sum()
                   .sort_values(["AÑO", "OPERACION", "ACUERDO_CONSOLIDADO", "VALOR_USD"],
                                ascending=[True, True, True, False])
                   .groupby(["AÑO", "OPERACION", "ACUERDO_CONSOLIDADO"]).head(10))
    por_acuerdo["DESCRIPCION"] = por_acuerdo["PRODUCTO"].map(p4.drop_duplicates("PRODUCTO").set_index("PRODUCTO")["DESCRIPCION"])

    notas = pd.DataFrame({"Nota": [
        "Valores en dólares: exportaciones FOB, importaciones CIF. Despachos definitivos de la DNIT.",
        "CON_ACUERDO_USD: comercio que usó una preferencia arancelaria (MERCOSUR y demás acuerdos).",
        "CON_ACUERDO_PCT = CON_ACUERDO_USD / TOTAL_USD: de todo lo comerciado del producto, qué parte usó un acuerdo.",
        "ACUERDO_PRINCIPAL: el acuerdo con más valor comerciado de ese producto ese año.",
        "Sale del campo 'acuerdo' de cada despacho. No se usan las listas de productos con preferencia de cada "
        "acuerdo: un % bajo puede deberse a que el producto no tiene rebaja, a que el arancel ya es cero para todos, "
        "a que se vende sobre todo a países sin acuerdo o a que la mercadería sigue viaje a otro país.",
        "El año en curso tiene solo los meses indicados en MESES.",
        "Fuente: DNIT, datos abiertos de aduanas. Elaboración propia. Código: "
        "https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic",
    ]})
    hojas = [("Ranking 4 dígitos", ranking(p4)), ("Ranking 8 dígitos", ranking(p8)),
             ("Por acuerdo", por_acuerdo),
             ("Todos 4 dígitos", p4), ("Notas", notas)]
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    for destino in (SALIDA, WEB / "Productos_acuerdos_Paraguay_2011_2026.xlsx"):
        with pd.ExcelWriter(destino, engine="xlsxwriter") as w:
            for nombre, h in hojas:
                cols = [c for c in ["AÑO", "MESES", "OPERACION", "ACUERDO_CONSOLIDADO", "PRODUCTO", "NOMBRE_CORTO", "DESCRIPCION",
                                    "TOTAL_USD", "CON_ACUERDO_USD", "SIN_ACUERDO_USD", "VALOR_USD",
                                    "CON_ACUERDO_PCT", "ACUERDO_PRINCIPAL", "PESO_NETO_KG", "Nota"] if c in h]
                h[cols].to_excel(w, sheet_name=nombre, index=False)
                w.sheets[nombre].freeze_panes(1, 0)
                w.sheets[nombre].set_column(0, len(cols) - 1, 16 if nombre != "Notas" else 120)
                if "DESCRIPCION" in cols:
                    w.sheets[nombre].set_column(cols.index("DESCRIPCION"), cols.index("DESCRIPCION"), 60)
    p4.to_csv(WEB / "productos_4_digitos.csv", index=False, encoding="utf-8-sig")
    p8.to_csv(WEB / "productos_8_digitos.csv", index=False, encoding="utf-8-sig")

    # Datos del buscador por producto (4 dígitos)
    anios = sorted(p4["AÑO"].unique().tolist())
    meses = p4.groupby("AÑO")["MESES"].max().to_dict()
    prod = []
    for (cod, op), g in p4.groupby(["PRODUCTO", "OPERACION"]):
        g = g.set_index("AÑO").reindex(anios)
        v = lambda c: [None if pd.isna(x) else round(float(x)) for x in g[c]]
        prod.append({"c": cod, "o": op[0], "n": g["NOMBRE_CORTO"].dropna().iloc[-1] if g["NOMBRE_CORTO"].notna().any() else "",
                     "d": g["DESCRIPCION"].dropna().iloc[-1] if g["DESCRIPCION"].notna().any() else "",
                     "t": v("TOTAL_USD"), "a": v("CON_ACUERDO_USD"),
                     "ac": [x if isinstance(x, str) else "" for x in g["ACUERDO_PRINCIPAL"]]})
    (WEB / "productos.json").write_text(json.dumps(
        {"anios": anios, "parcial": {str(a): int(m) for a, m in meses.items() if m < 12}, "productos": prod},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ult = max(a for a in anios if meses[a] == 12)
    for op in ("EXPORTACION", "IMPORTACION"):
        r = ranking(p4[(p4["AÑO"] == ult) & (p4["OPERACION"] == op)], 8)
        print(f"\n{op} {ult}, productos con más comercio con acuerdo (millones de USD):")
        print(r.assign(M=r["CON_ACUERDO_USD"] / 1e6, U=r["CON_ACUERDO_PCT"])[["PRODUCTO", "M", "U", "DESCRIPCION"]]
              .round(1).to_string(index=False, max_colwidth=60))
    print("\nGuardado en", SALIDA)


if __name__ == "__main__":
    main()
