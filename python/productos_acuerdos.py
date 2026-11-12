"""
Productos que más usan los acuerdos comerciales (exportaciones e importaciones), 2011–2026
==========================================================================================

Lee los resúmenes por producto de salidas/productos/ (resumen_productos.py) y arma:

  Ranking            los productos con más comercio CON ACUERDO, por año (4 y 8 dígitos de la NCM).
  Utilización        por producto: con acuerdo / comercio con SOCIOS CON ACUERDO.
  Sin aprovechar     productos con mucho comercio con socios con acuerdo que casi no usan la preferencia.
  Por acuerdo        los productos principales de cada acuerdo.

SOCIOS CON ACUERDO (el denominador de la utilización)
  Un país cuenta como socio con acuerdo en un año si ese año algún despacho hacia (o desde) ese
  país usó una preferencia. Así, la utilización de un producto es: de lo que se comerció con esos
  países, qué parte entró con preferencia. Es una aproximación: no todos los productos tienen
  preferencia en todos los acuerdos (algunos están excluidos o ya tienen arancel cero para todos).

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
    desc = desc.drop_duplicates("NCM", keep="last").set_index("NCM")
    t["CON_ACUERDO"] = np.where(t["TIPO_ACUERDO"].isin(CON), t["VALOR_USD"], 0.0)
    return t, desc


def tabla(t, nivel, desc):
    """Por año, operación y producto: total, con acuerdo, con socios con acuerdo y utilización."""
    t = t.copy()
    t["PRODUCTO"] = t["NCM"].str[:nivel]
    socios = (t[t["CON_ACUERDO"] > 0][["AÑO", "OPERACION", "CODIGO_PAIS"]].drop_duplicates()
              .assign(SOCIO=True))
    t = t.merge(socios, on=["AÑO", "OPERACION", "CODIGO_PAIS"], how="left", validate="many_to_one")
    t["CON_SOCIOS"] = np.where(t["SOCIO"].fillna(False).astype(bool), t["VALOR_USD"], 0.0)
    r = (t.groupby(["AÑO", "MESES", "OPERACION", "PRODUCTO"], as_index=False)
          .agg(TOTAL_USD=("VALOR_USD", "sum"), CON_ACUERDO_USD=("CON_ACUERDO", "sum"),
               CON_SOCIOS_USD=("CON_SOCIOS", "sum"), PESO_NETO_KG=("PESO_NETO_KG", "sum")))
    r["UTILIZACION_PCT"] = np.where(r["CON_SOCIOS_USD"] > 0, r["CON_ACUERDO_USD"] / r["CON_SOCIOS_USD"].where(r["CON_SOCIOS_USD"] > 0, 1) * 100, np.nan)
    r["SIN_APROVECHAR_USD"] = r["CON_SOCIOS_USD"] - r["CON_ACUERDO_USD"]
    if nivel == 4:
        d4 = desc.reset_index().assign(P=lambda x: x["NCM"].str[:4]).groupby("P")["DESCRIPCION_PARTIDA"].agg(
            lambda s: s[s != ""].value_counts().index[0] if (s != "").any() else "")
        r["DESCRIPCION"] = r["PRODUCTO"].map(d4).fillna("")
    else:
        r["DESCRIPCION"] = r["PRODUCTO"].map(desc["DESCRIPCION_COMPLETA"]).fillna("")
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

    sin_aprov = (p8[(p8["CON_SOCIOS_USD"] >= 5e6) & (p8["UTILIZACION_PCT"] < 50)]
                 .sort_values(["AÑO", "OPERACION", "SIN_APROVECHAR_USD"], ascending=[True, True, False])
                 .groupby(["AÑO", "OPERACION"]).head(20))
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
        "CON_SOCIOS_USD: comercio con los países con los que ese año se usó al menos una preferencia "
        "(socios con acuerdo).",
        "UTILIZACION_PCT = CON_ACUERDO_USD / CON_SOCIOS_USD. SIN_APROVECHAR_USD = la diferencia: comercio con "
        "socios con acuerdo que no usó la preferencia.",
        "Una utilización baja puede deberse a que el producto no tiene preferencia en ese acuerdo, a que el arancel "
        "ya es cero para todos o a que no conviene cumplir las reglas de origen. Es un punto de partida para mirar, "
        "no una conclusión.",
        "Sin aprovechar: productos (8 dígitos) con al menos USD 5 millones con socios con acuerdo y utilización "
        "menor al 50 %.",
        "El año en curso tiene solo los meses indicados en MESES.",
        "Fuente: DNIT, datos abiertos de aduanas. Elaboración propia. Código: "
        "https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic",
    ]})
    hojas = [("Ranking 4 dígitos", ranking(p4)), ("Ranking 8 dígitos", ranking(p8)),
             ("Sin aprovechar", sin_aprov), ("Por acuerdo", por_acuerdo),
             ("Todos 4 dígitos", p4), ("Notas", notas)]
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    for destino in (SALIDA, WEB / "Productos_acuerdos_Paraguay_2011_2026.xlsx"):
        with pd.ExcelWriter(destino, engine="xlsxwriter") as w:
            for nombre, h in hojas:
                cols = [c for c in ["AÑO", "MESES", "OPERACION", "ACUERDO_CONSOLIDADO", "PRODUCTO", "DESCRIPCION",
                                    "TOTAL_USD", "CON_SOCIOS_USD", "CON_ACUERDO_USD", "VALOR_USD",
                                    "UTILIZACION_PCT", "SIN_APROVECHAR_USD", "PESO_NETO_KG", "Nota"] if c in h]
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
        prod.append({"c": cod, "o": op[0], "d": g["DESCRIPCION"].dropna().iloc[-1] if g["DESCRIPCION"].notna().any() else "",
                     "t": v("TOTAL_USD"), "a": v("CON_ACUERDO_USD"), "s": v("CON_SOCIOS_USD")})
    (WEB / "productos.json").write_text(json.dumps(
        {"anios": anios, "parcial": {str(a): int(m) for a, m in meses.items() if m < 12}, "productos": prod},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ult = max(a for a in anios if meses[a] == 12)
    for op in ("EXPORTACION", "IMPORTACION"):
        r = ranking(p4[(p4["AÑO"] == ult) & (p4["OPERACION"] == op)], 8)
        print(f"\n{op} {ult}, productos con más comercio con acuerdo (millones de USD):")
        print(r.assign(M=r["CON_ACUERDO_USD"] / 1e6, U=r["UTILIZACION_PCT"])[["PRODUCTO", "M", "U", "DESCRIPCION"]]
              .round(1).to_string(index=False, max_colwidth=60))
    print("\nGuardado en", SALIDA)


if __name__ == "__main__":
    main()
