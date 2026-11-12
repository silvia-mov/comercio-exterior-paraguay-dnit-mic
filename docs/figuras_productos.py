"""Gráficos de los productos que más usan los acuerdos (salidas/Productos_acuerdos.xlsx).

Uso (desde la raíz del repositorio), después de python python/productos_acuerdos.py:
    python docs/figuras_productos.py

Genera en docs/img/, en versión clara y oscura:
  productos_exportacion   los 12 productos con más exportaciones con acuerdo del último año completo
  productos_importacion   lo mismo para las importaciones
Cada barra muestra todo lo comerciado del producto (claro) y la parte que usó un acuerdo (color),
con el porcentaje con acuerdo al lado.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["axes.facecolor"] = "none"
import matplotlib.ticker
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
IMG = RAIZ / "docs" / "img"
FONDO = {"light": "#ffffff", "dark": "#0d1117"}
TEMAS = {
    "light": dict(texto="#1d1a1c", texto2="#5c5459", grilla="#ece6e8", eje="#c9bfc3",
                  con="#39b89a", socios="#fec9d7", rosa="#ff5883"),
    "dark": dict(texto="#f5eef1", texto2="#bfb3b8", grilla="#2a2427", eje="#4a4044",
                 con="#39b89a", socios="#6b3a4a", rosa="#ff91ad"),
}
# Nombres cortos y en lenguaje común de las partidas más frecuentes (config/nombres_cortos_ncm.csv)
CORTOS = pd.read_csv(RAIZ / "config" / "nombres_cortos_ncm.csv", dtype=str).set_index("partida")["nombre_corto"].to_dict()
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def corto(cod, desc):
    if cod in CORTOS:
        return CORTOS[cod]
    d = str(desc).split(",")[0].split(";")[0].strip().capitalize()
    return d if len(d) <= 34 else d[:32].rstrip() + "…"


def millones(x, _p=None):
    return f"{x:,.0f}".replace(",", ".")


def main():
    p4 = pd.read_excel(RAIZ / "salidas" / "Productos_acuerdos.xlsx", sheet_name="Todos 4 dígitos",
                       dtype={"PRODUCTO": str})
    anio = int(p4.loc[p4["MESES"] == 12, "AÑO"].max())
    for op, nombre, valor in (("EXPORTACION", "exportacion", "FOB"), ("IMPORTACION", "importacion", "CIF")):
        d = p4[(p4["AÑO"] == anio) & (p4["OPERACION"] == op)]
        total_con = d["CON_ACUERDO_USD"].sum()
        d = d.sort_values("CON_ACUERDO_USD", ascending=False).head(12).iloc[::-1]
        d = d.assign(N=[corto(c, x) for c, x in zip(d["PRODUCTO"], d["DESCRIPCION"])])
        top3 = d.iloc[::-1].head(3)
        parte = top3["CON_ACUERDO_USD"].sum() / total_con * 100
        verbo = "exportado" if op == "EXPORTACION" else "importado"
        for modo, t in TEMAS.items():
            fig, ax = plt.subplots(figsize=(10, 5.6))
            fig.subplots_adjust(left=0.27, right=0.9, top=0.78, bottom=0.08)
            y = range(len(d))
            ax.barh(y, d["TOTAL_USD"] / 1e6, color=t["socios"], height=0.72)
            ax.barh(y, d["CON_ACUERDO_USD"] / 1e6, color=t["con"], height=0.72)
            for k, (_, r) in enumerate(d.iterrows()):
                ax.text(r["TOTAL_USD"] / 1e6, k, f"  {r['CON_ACUERDO_PCT']:.0f} %", va="center",
                        fontsize=9.5, color=t["texto"], fontweight="bold")
            ax.set_yticks(list(y), d["N"], color=t["texto"], fontsize=10)
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(millones))
            for lado in ("top", "right", "left"):
                ax.spines[lado].set_visible(False)
            ax.spines["bottom"].set_color(t["eje"])
            ax.tick_params(colors=t["texto2"], labelsize=9.5, length=0)
            ax.tick_params(axis="y", colors=t["texto"])
            ax.grid(axis="x", color=t["grilla"], linewidth=0.8)
            ax.set_axisbelow(True)
            ax.set_xlabel(f"millones de USD {valor}", fontsize=9.5, color=t["texto2"])
            nombres = ", ".join(top3["N"].str.lower().tolist()[:2]) + " y " + top3["N"].str.lower().iloc[2]
            fig.text(0.01, 0.975, f"{nombres.capitalize()}: el {parte:.0f} % de lo {verbo} con acuerdo en {anio}",
                     fontsize=14, fontweight="bold", color=t["texto"], va="top")
            fig.text(0.01, 0.91, f"Los 12 productos con más {'exportaciones' if op == 'EXPORTACION' else 'importaciones'} "
                     "que usaron un acuerdo comercial. El número es la parte de todo lo comerciado del\n"
                     "producto que usó un acuerdo. Despachos de la DNIT, 4 dígitos de la NCM.",
                     fontsize=10, color=t["texto2"], va="top", linespacing=1.4)
            fig.text(0.27, 0.815, "■", color=t["con"], fontsize=11)
            fig.text(0.285, 0.815, "Usó el acuerdo", color=t["texto2"], fontsize=10)
            fig.text(0.42, 0.815, "■", color=t["socios"], fontsize=11)
            fig.text(0.435, 0.815, "Sin acuerdo", color=t["texto2"], fontsize=10)
            fig.savefig(IMG / f"productos_{nombre}_{modo}.png", dpi=200, facecolor=FONDO[modo])
            plt.close(fig)
    print("Listo:", sorted(p.name for p in IMG.glob("productos_*.png")))


if __name__ == "__main__":
    main()
