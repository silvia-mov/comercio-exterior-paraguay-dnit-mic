"""Gráficos del cruce de las cuatro fuentes (salidas/cruce_4_fuentes_*.csv).

Uso (desde la raíz del repositorio), después de python python/cruzar_fuentes.py:
    python docs/figuras_cruce.py

Genera en docs/img/, en versión clara y oscura:
  utilizacion_anual   exportaciones con y sin acuerdo y tasa de utilización (DNIT)
  fuentes             las cuatro fuentes comparadas (sin electricidad)
  utilizacion_socios  tasa de utilización por país socio
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["axes.facecolor"] = "none"  # el panel toma el fondo de la figura
import matplotlib.ticker
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
IMG = RAIZ / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

# Fondo propio (no transparente): GitHub elige la versión clara u oscura según la computadora.
FONDO = {"light": "#ffffff", "dark": "#0d1117"}
TEMAS = {
    "light": dict(texto="#1d1a1c", texto2="#5c5459", grilla="#ece6e8", eje="#c9bfc3",
                  verde="#39b89a", verde2="#1f7f68", rosa="#ff5883", rosa_claro="#fec9d7", menta="#79d3be"),
    "dark": dict(texto="#f5eef1", texto2="#bfb3b8", grilla="#2a2427", eje="#4a4044",
                 verde="#39b89a", verde2="#79d3be", rosa="#ff91ad", rosa_claro="#6b3a4a", menta="#b9eee1"),
}


TILDES = {"Mexico": "México", "Peru": "Perú", "Japon": "Japón", "Canada": "Canadá",
          "Estados Unidos De America": "Estados Unidos"}


DIEZ = ["Cero", "Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve", "Diez"]


def miles(x, _pos=None):
    return f"{x:,.0f}".replace(",", ".")


def estilo(ax, t, grilla="y"):
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(t["eje"])
    ax.tick_params(colors=t["texto2"], labelsize=9.5, length=0)
    ax.grid(axis=grilla, color=t["grilla"], linewidth=0.8)
    ax.set_axisbelow(True)


def titulo(fig, t, texto, sub):
    """Título = la conclusión; subtítulo = qué se mide (en hasta dos líneas para que no se corte)."""
    import textwrap
    fig.text(0.01, 0.975, texto, ha="left", va="top", fontsize=14, fontweight="bold", color=t["texto"])
    fig.text(0.01, 0.91, "\n".join(textwrap.wrap(sub, 135)), ha="left", va="top", fontsize=10.5,
             color=t["texto2"], linespacing=1.4)


def leyenda(fig, t, x, y, items):
    """items: (texto, color, marca). La etiqueta va en gris para que se lea con colores claros."""
    for texto, color, marca in items:
        fig.text(x, y, marca, color=color, fontsize=11, va="center")
        fig.text(x + 0.018, y, texto, color=t["texto2"], fontsize=10, va="center")
        x += 0.03 + len(texto) * 0.0082


def guardar(fig, nombre, modo):
    fig.savefig(IMG / f"{nombre}_{modo}.png", dpi=200, facecolor=FONDO[modo])
    plt.close(fig)


def etiqueta_anio(a, meses):
    return f"{a}*" if meses < 12 else str(a)


def main():
    anual = pd.read_csv(RAIZ / "salidas" / "cruce_4_fuentes_por_anio.csv")
    socios = pd.read_csv(RAIZ / "salidas" / "cruce_4_fuentes_utilizacion_socios.csv",
                         keep_default_na=False, na_values=[""])  # "NA" = Namibia, no vacío
    anios = anual["AÑO"].tolist()
    etiquetas = [etiqueta_anio(a, m) for a, m in zip(anual["AÑO"], anual["MESES"])]
    parcial = anual.loc[anual["MESES"] < 12]
    nota_parcial = (f"* {int(parcial['AÑO'].iloc[0])}: enero a "
                    f"{['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre'][int(parcial['MESES'].iloc[0])]}."
                    if len(parcial) else "")

    for modo, t in TEMAS.items():
        # ------------------------------------------------ 1. Utilización anual
        fig, ax = plt.subplots(figsize=(10, 4.8))
        fig.subplots_adjust(left=0.07, right=0.93, top=0.7, bottom=0.12)
        con = anual["DNIT_FOB_CON_ACUERDO"] / 1e6
        sin = anual["DNIT_FOB_SIN_ACUERDO"] / 1e6
        ax.bar(anios, con, color=t["verde"], width=0.72)
        ax.bar(anios, sin, bottom=con, color=t["rosa_claro"], width=0.72)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(miles))
        ax.set_xticks(anios, etiquetas)
        estilo(ax, t)
        ax2 = ax.twinx()
        ax2.plot(anios, anual["UTILIZACION_PCT"], color=t["rosa"], linewidth=2.5, marker="o", markersize=5)
        for a, v in zip(anios, anual["UTILIZACION_PCT"]):
            ax2.text(a, v + 3, f"{v:.0f}".replace(".", ","), ha="center", fontsize=8.5, color=t["rosa"])
        ax2.set_ylim(0, 100)
        ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _p: f"{x:.0f} %"))
        for lado in ("top", "left", "bottom", "right"):
            ax2.spines[lado].set_visible(False)
        ax2.tick_params(colors=t["texto2"], labelsize=9.5, length=0)
        u = anual["UTILIZACION_PCT"]
        titulo(fig, t, f"{DIEZ[round(u.iloc[-1] / 10)]} de cada diez dólares exportados usan un acuerdo comercial "
               f"(en {anios[0]}, {DIEZ[round(u.iloc[0] / 10)].lower()})",
               "Exportaciones de Paraguay con y sin preferencia, millones de USD FOB (barras), y % con acuerdo "
               "(línea). Despachos de la DNIT.")
        leyenda(fig, t, 0.07, 0.77, [("Con acuerdo", t["verde"], "■"), ("Sin acuerdo", t["rosa_claro"], "■"),
                                     ("% con acuerdo (eje derecho)", t["rosa"], "●")])
        if nota_parcial:
            fig.text(0.07, 0.02, nota_parcial, fontsize=8.5, color=t["texto2"])
        guardar(fig, "utilizacion_anual", modo)

        # ------------------------------------------------ 2. Cuatro fuentes
        fig, ax = plt.subplots(figsize=(10, 4.8))
        fig.subplots_adjust(left=0.07, right=0.97, top=0.7, bottom=0.12)
        series = [
            ("BCP (oficial)", anual["BCP_SIN_ELECTRICIDAD"], t["texto"], "-"),
            ("DNIT (despachos)", anual["DNIT_FOB_TOTAL"], t["verde"], "-"),
            ("VUE (certificados)", anual["VUE_FOB"], t["rosa"], "-"),
            ("Espejo (lo que declaran los socios)", anual["ESPEJO_SIN_ELECTRICIDAD"], t["menta"], (0, (4, 2))),
        ]
        for _, s, c, ls in series:
            ax.plot(anios, s / 1e6, color=c, linewidth=2.3, linestyle=ls, marker="o", markersize=4)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(miles))
        ax.set_xticks(anios, etiquetas)
        estilo(ax, t)
        r = (anual["DNIT_FOB_TOTAL"] / anual["BCP_SIN_ELECTRICIDAD"] * 100)
        titulo(fig, t, "Cuatro fuentes distintas cuentan casi lo mismo: los datos abiertos de aduanas son confiables",
               f"Exportaciones de Paraguay, millones de USD, sin electricidad. La DNIT queda entre el {int(r.min())} % y "
               f"el {int(-(-r.max() // 1))} % del dato oficial del BCP. El espejo está en CIF.")
        leyenda(fig, t, 0.07, 0.77, [(n, c, "●") for n, _, c, _ in series])
        nota = "En 2022 los archivos de la VUE tienen valores atípicos (octubre y noviembre)."
        if nota_parcial:
            nota += " " + nota_parcial + " El espejo de ese año todavía no existe."
        fig.text(0.07, 0.02, nota, fontsize=8.5, color=t["texto2"])
        guardar(fig, "fuentes", modo)

        # ------------------------------------------------ 3. Utilización por socio
        principales = (socios.groupby(["CODIGO_PAIS", "PAIS"])["DNIT_FOB_CON_ACUERDO"].sum()
                       .sort_values(ascending=False).head(6).reset_index())
        fig, axes = plt.subplots(2, 3, figsize=(10, 5.6), sharex=True, sharey=True)
        fig.subplots_adjust(left=0.07, right=0.98, top=0.77, bottom=0.1, hspace=0.42, wspace=0.12)
        for ax, (_, p) in zip(axes.flat, principales.iterrows()):
            d = socios[socios["CODIGO_PAIS"] == p["CODIGO_PAIS"]].set_index("AÑO").reindex(anios)
            ax.fill_between(anios, d["UTILIZACION_PCT"], color=t["verde"], alpha=0.18, linewidth=0)
            ax.plot(anios, d["UTILIZACION_PCT"], color=t["verde2"], linewidth=2.2)
            ultimo = d["UTILIZACION_PCT"].dropna()
            if len(ultimo):
                ax.text(1.0, 1.02, f"{int(ultimo.index[-1])}: {ultimo.iloc[-1]:.0f} %", ha="right", va="bottom",
                        transform=ax.transAxes, fontsize=9.5, color=t["verde2"], fontweight="bold")
            nombre = p["PAIS"].title()
            ax.set_title(TILDES.get(nombre, nombre), loc="left", fontsize=11, color=t["texto"])
            ax.set_ylim(0, 105)
            ax.set_yticks([0, 50, 100], ["0 %", "50 %", "100 %"])
            ax.set_xticks([anios[0], anios[len(anios) // 2], anios[-1]])
            estilo(ax, t)
        ult = {p["PAIS"]: socios[(socios["CODIGO_PAIS"] == p["CODIGO_PAIS"])].sort_values("AÑO")["UTILIZACION_PCT"].iloc[-1]
               for _, p in principales.iterrows()}
        orden = sorted(ult, key=ult.get, reverse=True)
        nom = lambda x: TILDES.get(x.title(), x.title())
        titulo(fig, t, f"Con {nom(orden[0])} y {nom(orden[1])}, más del {int(ult[orden[1]] // 5 * 5)} % usa el acuerdo; "
               f"con {nom(orden[-1])}, solo el {ult[orden[-1]]:.0f} %",
               "Tasa de utilización: % de lo exportado a cada país que usó una preferencia arancelaria. Los 6 socios "
               f"con más exportaciones con acuerdo (DNIT), último año: {anios[-1]}.")
        if nota_parcial:
            fig.text(0.07, 0.01, nota_parcial, fontsize=8.5, color=t["texto2"])
        guardar(fig, "utilizacion_socios", modo)

    print("Listo:", sorted(p.name for p in IMG.glob("*.png")))


if __name__ == "__main__":
    main()
