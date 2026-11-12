"""Gráficos de los productos que más usan los acuerdos (salidas/Productos_acuerdos.xlsx).

Uso (desde la raíz del repositorio), después de python python/productos_acuerdos.py:
    python docs/figuras_productos.py

Genera en docs/img/, en versión clara y oscura:
  productos_exportacion   los 12 productos con más exportaciones con acuerdo del último año completo
  productos_importacion   lo mismo para las importaciones
Cada barra muestra lo comerciado con socios con acuerdo (claro) y la parte que usó la preferencia
(color), con la tasa de utilización al lado.
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
# Nombres cortos y en lenguaje común de las partidas más frecuentes (4 dígitos de la NCM)
CORTOS = {
    "1201": "Soja en grano", "2304": "Harina y pellets de soja", "1507": "Aceite de soja",
    "0201": "Carne bovina fresca", "0202": "Carne bovina congelada", "1005": "Maíz", "1001": "Trigo",
    "1006": "Arroz", "1002": "Centeno", "1003": "Cebada", "1007": "Sorgo", "1206": "Girasol",
    "2306": "Tortas y residuos de oleaginosas", "2302": "Salvados y residuos de cereales",
    "3923": "Envases de plástico", "8544": "Cables eléctricos", "0206": "Menudencias bovinas",
    "4107": "Cueros curtidos", "4104": "Cueros curtidos (bovinos)", "1701": "Azúcar", "2207": "Alcohol etílico",
    "1208": "Harina de soja (sin grasa)", "1517": "Margarina y mezclas de aceites", "0203": "Carne de cerdo",
    "0207": "Carne de pollo", "6305": "Bolsas y sacos textiles", "3004": "Medicamentos",
    "3105": "Fertilizantes (abonos mixtos)", "3102": "Fertilizantes nitrogenados", "3808": "Agroquímicos",
    "8433": "Cosechadoras", "8432": "Máquinas agrícolas", "8701": "Tractores", "8704": "Camiones",
    "8703": "Autos", "8708": "Autopartes", "4011": "Neumáticos", "2710": "Combustibles (gasoil, nafta)",
    "2711": "Gas (GLP)", "2401": "Tabaco", "2402": "Cigarrillos", "7214": "Barras de hierro o acero",
    "7308": "Estructuras de hierro o acero", "3901": "Plásticos (polietileno)", "3902": "Plásticos (polipropileno)",
    "1905": "Panificados y galletitas", "2202": "Bebidas sin alcohol", "2203": "Cerveza",
    "4819": "Cajas y envases de papel", "2523": "Cemento", "1512": "Aceite de girasol",
    "3920": "Láminas de plástico", "8471": "Computadoras", "8517": "Teléfonos celulares",
    "0402": "Leche en polvo", "1101": "Harina de trigo", "1904": "Cereales para desayuno",
    "2106": "Preparaciones alimenticias", "3402": "Detergentes", "4802": "Papel", "7210": "Chapas de acero",
    "8418": "Heladeras", "8415": "Aires acondicionados", "8429": "Topadoras y excavadoras",
    "6403": "Calzado de cuero", "6109": "Remeras", "5205": "Hilado de algodón", "2309": "Alimentos balanceados",
    "0105": "Aves vivas", "0407": "Huevos", "1209": "Semillas para siembra", "1214": "Forrajes",
    "3824": "Productos químicos industriales", "3204": "Colorantes", "2933": "Compuestos químicos (medicamentos)",
    "4407": "Madera aserrada", "9401": "Asientos y muebles", "8507": "Baterías", "1604": "Conservas de pescado",
}
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
            ax.barh(y, d["CON_SOCIOS_USD"] / 1e6, color=t["socios"], height=0.72)
            ax.barh(y, d["CON_ACUERDO_USD"] / 1e6, color=t["con"], height=0.72)
            for k, (_, r) in enumerate(d.iterrows()):
                ax.text(r["CON_SOCIOS_USD"] / 1e6, k, f"  {r['UTILIZACION_PCT']:.0f} %", va="center",
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
                     "que usaron un acuerdo comercial. El número es la tasa de utilización: de lo comerciado con\n"
                     "países con acuerdo, qué parte usó la preferencia. Despachos de la DNIT, 4 dígitos de la NCM.",
                     fontsize=10, color=t["texto2"], va="top", linespacing=1.4)
            fig.text(0.27, 0.815, "■", color=t["con"], fontsize=11)
            fig.text(0.285, 0.815, "Usó el acuerdo", color=t["texto2"], fontsize=10)
            fig.text(0.42, 0.815, "■", color=t["socios"], fontsize=11)
            fig.text(0.435, 0.815, "Con países con acuerdo, pero sin usarlo", color=t["texto2"], fontsize=10)
            fig.savefig(IMG / f"productos_{nombre}_{modo}.png", dpi=200, facecolor=FONDO[modo])
            plt.close(fig)
    print("Listo:", sorted(p.name for p in IMG.glob("productos_*.png")))


if __name__ == "__main__":
    main()
