"""Datos del buscador "Consultá un dato" de la página web (docs/datos/consulta.json).

Uso (desde la raíz del repositorio), después de python docs/datos_web.py:
    python docs/consulta_web.py

Por país y año: exportado según la DNIT (total y con acuerdo) y según el BCP (destino final, sin
electricidad), en dólares FOB. Los nombres de los países se pasan a mayúsculas y minúsculas con tildes.
"""
import json
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "docs" / "datos" / "exportaciones_por_pais.csv"
ANUAL = RAIZ / "docs" / "datos" / "utilizacion_por_anio.csv"
DESTINO = RAIZ / "docs" / "datos" / "consulta.json"

NOMBRES = {
    "ESTADOS UNIDOS DE AMERICA": "Estados Unidos", "ESPANA": "España", "PAISES BAJOS": "Países Bajos",
    "PERU": "Perú", "JAPON": "Japón", "MEXICO": "México", "CANADA": "Canadá", "BELGICA": "Bélgica",
    "TAIWAN": "Taiwán", "EMIRATOS ARABES UNIDOS": "Emiratos Árabes Unidos", "PAKISTAN": "Pakistán",
    "IRAN": "Irán", "LIBANO": "Líbano", "TURQUIA": "Turquía", "SUDAFRICA": "Sudáfrica", "HAITI": "Haití",
    "PANAMA": "Panamá", "R.DOMINICANA": "República Dominicana", "KAZAJSTAN": "Kazajistán",
    "AZERBAIJAN": "Azerbaiyán", "BOSTWANA": "Botsuana", "CAMBOYA(KAMPUCHEA)": "Camboya", "TUNEZ": "Túnez",
    "BAHREIN": "Baréin", "HUNGRIA": "Hungría", "ARGELIA": "Argelia", "AFGANISTAN": "Afganistán", "BIELORRUSIA": "Bielorrusia", "ESLOVAQUIA": "Eslovaquia", "ETIOPIA": "Etiopía",
    "GABON": "Gabón", "IRAK": "Irak", "MALDIVAS(ISLAS)": "Maldivas", "MALI": "Malí", "OMAN": "Omán",
    "TAJIKISTAN": "Tayikistán", "TURKMENISTAN": "Turkmenistán", "UZBEKISTAN": "Uzbekistán",
    "KIRGUIZISTAN": "Kirguistán", "SURINAN": "Surinam", "BUTAN": "Bután", "BENIN": "Benín",
    "CAMERUN": "Camerún", "COREA DEL SUR": "Corea del Sur", "FIDJI": "Fiyi", "REINO UNIDO": "Reino Unido",
    "REPUBLICA CHECA": "República Checa", "REPUBLICA CENTROAFRICANA": "República Centroafricana",
    "REPUBLICA DEMOCRATICA DEL CONGO": "República Democrática del Congo", "PRINCIPADO DE MONACO": "Mónaco",
    "ISLAS VIRGENES (GB)": "Islas Vírgenes Británicas", "ISLAS VIRGENES EE.UU.": "Islas Vírgenes de EE. UU.",
    "ISLAS CAIMAN": "Islas Caimán", "SEYCHELLES Y DEPENDENCIAS": "Seychelles",
    "NUEVA CALEDONIA Y DEPENDENCIAS": "Nueva Caledonia", "BOSNIA-HERZEGOVINA": "Bosnia y Herzegovina",
    "CIUDAD DEL VATICANO": "Ciudad del Vaticano", "COSTA DE MARFIL": "Costa de Marfil",
    "ANTILLAS NEERLANDESAS": "Antillas Neerlandesas", "CURACAO": "Curazao", "REUNION": "Reunión",
    "RUMANIA": "Rumania", "PAPUA NUEVA GUINEA": "Papúa Nueva Guinea", "SAN PEDRO Y MIQUELON": "San Pedro y Miquelón",
    "TAHITI": "Tahití", "HONG KONG": "Hong Kong", "SRI LANKA": "Sri Lanka", "TRINIDAD Y TOBAGO": "Trinidad y Tobago",
    "ANTIGUA Y BARBUDA": "Antigua y Barbuda", "GUINEA BISSAU": "Guinea-Bisáu", "ISLAS MARSHALL": "Islas Marshall",
}
EXCLUIR = {"PARAGUAY", "SIN DATO DE PAIS", "ZA FRCA GLOBAL", "ZA FRCA TRANSTRADE", "REGIONES POLARES"}


def nombre(n):
    if n in NOMBRES:
        return NOMBRES[n]
    return " ".join(p if p in ("y", "de", "del") else p.capitalize() for p in n.lower().split())


def main():
    d = pd.read_csv(ORIGEN, keep_default_na=False, na_values=[""])
    anual = pd.read_csv(ANUAL)
    anios = sorted(d["AÑO"].unique().tolist())
    meses = dict(zip(anual["AÑO"], anual["MESES"]))
    d = d[~d["PAIS"].isin(EXCLUIR) & (d["PAIS"].str.len() > 3)]
    total = d.groupby("CODIGO_PAIS")["DNIT_EXPORTADO_USD"].sum()
    d = d[d["CODIGO_PAIS"].isin(total[total > 0].index)]
    # Puesto de cada país como destino, por año (según la DNIT)
    d["PUESTO"] = d.groupby("AÑO")["DNIT_EXPORTADO_USD"].rank(ascending=False, method="min")

    paises = []
    for (cod, n), g in d.groupby(["CODIGO_PAIS", "PAIS"]):
        g = g.set_index("AÑO").reindex(anios)
        r = lambda col, dec=0: [None if pd.isna(v) else round(float(v), dec) for v in g[col]]
        paises.append({"c": cod, "n": nombre(n), "t": r("DNIT_EXPORTADO_USD"), "a": r("DNIT_CON_ACUERDO_USD"),
                       "b": r("BCP_SIN_ELECTRICIDAD_USD"), "p": r("PUESTO")})
    # orden alfabético sin tener en cuenta las tildes (Bélgica junto a Belice)
    paises.sort(key=lambda p: unicodedata.normalize("NFKD", p["n"]).encode("ascii", "ignore").decode().lower())
    principales = total.drop(labels=[c for c in total.index if c not in {p["c"] for p in paises}])
    datos = {
        "anios": anios,
        "parcial": {str(a): int(m) for a, m in meses.items() if m < 12},
        "principales": principales.sort_values(ascending=False).head(10).index.tolist(),
        "paises": paises,
    }
    DESTINO.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(paises)} países -> {DESTINO} ({DESTINO.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
