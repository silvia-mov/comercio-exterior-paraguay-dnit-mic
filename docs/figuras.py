"""Gráficos del README a partir del reporte (salidas/Reporte_Comercio_Paraguay_Acuerdos.xlsx).

Uso (desde la raíz del repositorio), después de procesar los datos:
    python docs/figuras.py

Genera cada gráfico en versión clara y oscura (temas de GitHub) en docs/img/.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["axes.facecolor"] = "none"  # el panel toma el fondo de la figura
import matplotlib.ticker
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
REPORTE = RAIZ / "salidas" / "Reporte_Comercio_Paraguay_Acuerdos.xlsx"
IMG = RAIZ / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

# Fondo propio (no transparente): GitHub elige la versión clara u oscura según la computadora,
# no según el tema de GitHub, y con fondo transparente las letras pueden quedar ilegibles.
FONDO = {"light": "#ffffff", "dark": "#0d1117"}
TEMAS = {
    "light": dict(texto="#0b0b0b", texto2="#52514e", grilla="#e4e3df", eje="#c3c2b7",
                  con="#39b89a", sin="#fec9d7"),
    "dark": dict(texto="#f0efec", texto2="#c3c2b7", grilla="#33332f", eje="#52514e",
                 con="#39b89a", sin="#6b3a4a"),
}
NOMBRES_CORTOS = {
    "MERCOSUR intrazona (ACE 18)": "MERCOSUR (ACE 18)",
    "ALADI Bilateral Argentina (AAP.CE 13)": "Argentina (AAP.CE 13)",
    "ALADI Bilateral Brasil (AAP.CE 74)": "Brasil (AAP.CE 74)",
    "ALADI Bilateral México (AAP.R 38)": "México (AAP.R 38)",
    "ALADI Preferencia Arancelaria Regional (PAR 4)": "ALADI PAR 4",
}


def millones(x, _pos=None):
    return f"{x:,.0f}".replace(",", ".")


MESES_TXT = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]


def meses_del_anio(anio):
    """Meses incluidos de un año (12 salvo el año en curso), según el resumen de la DNIT."""
    ruta = RAIZ / "salidas" / "resumen_dnit" / f"dnit_exportaciones_{anio}.csv"
    if ruta.exists():
        return int(pd.read_csv(ruta, usecols=["DNIT_MESES"], nrows=1)["DNIT_MESES"].iloc[0])
    return 12


def grafico_acuerdos(por_acuerdo, anio, modo, t):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    fig.subplots_adjust(left=0.2, right=0.97, top=0.74, bottom=0.1, wspace=0.75)
    for ax, (op, titulo) in zip(axes, (("EXPORTACION", "Exportaciones (FOB)"),
                                       ("IMPORTACION", "Importaciones (CIF)"))):
        d = por_acuerdo[(por_acuerdo["AÑO"] == anio) & (por_acuerdo["OPERACION"] == op)].copy()
        d["M"] = d["VALOR_DOLAR"] / 1e6
        d["nombre"] = d["ACUERDO_CONSOLIDADO"].replace(NOMBRES_CORTOS)
        d = d[d["M"] >= 1].sort_values("M")
        colores = [t["con"] if tipo != "SIN_ACUERDO" else t["sin"] for tipo in d["TIPO_ACUERDO"]]
        ax.barh(d["nombre"], d["M"], color=colores, height=0.7)
        for y, v in enumerate(d["M"]):
            ax.text(v, y, " " + millones(v), va="center", fontsize=8.5, color=t["texto2"])
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(millones))
        ax.set_title(titulo, loc="left", fontsize=11.5, color=t["texto"], pad=8)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(t["eje"])
        ax.tick_params(colors=t["texto2"], labelsize=9, length=0)
        ax.tick_params(axis="y", colors=t["texto"])
        ax.grid(axis="x", color=t["grilla"], linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel("millones de USD (escala logarítmica)", fontsize=9, color=t["texto2"])
    n = meses_del_anio(anio)
    periodo = f"{anio} (enero a {MESES_TXT[n]})" if n < 12 else str(anio)
    # Título con la conclusión (Storytelling with Data); el subtítulo dice qué se mide
    d = por_acuerdo[por_acuerdo["AÑO"] == anio]
    pct = {op: 100 * d.loc[(d["OPERACION"] == op) & (d["TIPO_ACUERDO"] != "SIN_ACUERDO"), "VALOR_DOLAR"].sum()
           / d.loc[d["OPERACION"] == op, "VALOR_DOLAR"].sum() for op in ("EXPORTACION", "IMPORTACION")}
    fig.text(0.01, 0.97, f"En {anio}, el {pct['EXPORTACION']:.0f} % de lo exportado y el {pct['IMPORTACION']:.0f} % "
             "de lo importado usaron un acuerdo comercial", fontsize=14, fontweight="bold", color=t["texto"], va="top")
    fig.text(0.01, 0.905, f"Comercio de Paraguay según el acuerdo usado, {periodo}. Millones de USD. "
             "Despachos aduaneros definitivos (datos abiertos de la DNIT).",
             fontsize=10.5, color=t["texto2"], va="top")
    fig.text(0.2, 0.82, "■  Con acuerdo", color=t["con"], fontsize=10.5)
    # el rosa claro no se lee como texto: cuadrado en color, etiqueta en gris
    fig.text(0.42, 0.82, "■", color=t["sin"], fontsize=10.5)
    fig.text(0.435, 0.82, "Sin acuerdo / OMC", color=t["texto2"], fontsize=10.5)
    fig.savefig(IMG / f"acuerdos_{anio}_{modo}.png", dpi=200, facecolor=FONDO[modo])
    plt.close(fig)


def main():
    # Si existen los resúmenes por año (salidas/por_acuerdo/por_acuerdo_AAAA.csv), se grafican
    # todos; si no, el reporte de procesar_despachos.py.
    resumenes = sorted((RAIZ / "salidas" / "por_acuerdo").glob("por_acuerdo_*.csv"))
    if resumenes:
        por_acuerdo = pd.concat([pd.read_csv(r) for r in resumenes], ignore_index=True)
    else:
        por_acuerdo = pd.read_excel(REPORTE, sheet_name="Por acuerdo")
    for anio in sorted(por_acuerdo["AÑO"].unique()):
        for modo, t in TEMAS.items():
            grafico_acuerdos(por_acuerdo, anio, modo, t)
    print("Listo:", sorted(p.name for p in IMG.glob("*.png")))


if __name__ == "__main__":
    main()
