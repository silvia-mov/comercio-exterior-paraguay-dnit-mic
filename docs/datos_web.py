"""Archivos para descargar desde la página web (docs/datos/), a partir del cruce de las cuatro fuentes.

Uso (desde la raíz del repositorio), después de python python/cruzar_fuentes.py:
    python docs/datos_web.py

Los datos espejo de UN Comtrade se publican solo como total anual (no por país ni por producto),
porque se bajan con una suscripción.
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "salidas" / "Cruce_4_fuentes.xlsx"
DESTINO = RAIZ / "docs" / "datos"
DESTINO.mkdir(parents=True, exist_ok=True)

COLUMNAS = {
    "AÑO": "AÑO", "MESES": "MESES",
    "DNIT_FOB_TOTAL": "DNIT_EXPORTADO_USD", "DNIT_FOB_CON_ACUERDO": "DNIT_CON_ACUERDO_USD",
    "DNIT_FOB_SIN_ACUERDO": "DNIT_SIN_ACUERDO_USD", "UTILIZACION_PCT": "TASA_UTILIZACION_PCT",
    "VUE_FOB": "VUE_CERTIFICADOS_USD", "BCP_FOB": "BCP_TOTAL_USD", "BCP_ELECTRICIDAD": "BCP_ELECTRICIDAD_USD",
    "BCP_SIN_ELECTRICIDAD": "BCP_SIN_ELECTRICIDAD_USD", "ESPEJO_SIN_ELECTRICIDAD": "ESPEJO_SIN_ELECTRICIDAD_USD_CIF",
}


def main():
    hojas = pd.read_excel(ORIGEN, sheet_name=None, keep_default_na=False, na_values=[""])
    anual = hojas["Por año"][[c for c in COLUMNAS if c in hojas["Por año"]]].rename(columns=COLUMNAS)
    socios = hojas["Utilización por socio"].rename(columns={
        "DNIT_FOB_TOTAL": "DNIT_EXPORTADO_USD", "DNIT_FOB_CON_ACUERDO": "DNIT_CON_ACUERDO_USD",
        "DNIT_FOB_SIN_ACUERDO": "DNIT_SIN_ACUERDO_USD", "UTILIZACION_PCT": "TASA_UTILIZACION_PCT"})
    pais = hojas["Por país"][["AÑO", "CODIGO_PAIS", "PAIS", "DNIT_FOB_TOTAL", "DNIT_FOB_CON_ACUERDO",
                              "DNIT_FOB_SIN_ACUERDO", "UTILIZACION_PCT", "VUE_FOB", "BCP_FOB",
                              "BCP_SIN_ELECTRICIDAD"]].rename(columns=COLUMNAS)
    notas = pd.DataFrame({"Nota": [
        "Exportaciones de Paraguay, 2011-2026. Valores en dólares FOB (el espejo, en CIF).",
        "TASA_UTILIZACION_PCT = exportado con acuerdo / exportado total, según los despachos de la DNIT.",
        "El año en curso tiene solo los meses indicados en MESES (los mismos en todas las fuentes).",
        "DNIT: regímenes definitivos, origen paraguayo, destino declarado en el despacho.",
        "VUE: certificados de origen (todos, con y sin preferencia), destino final.",
        "BCP: estadística oficial (SICEX), todos los regímenes, destino final; incluye electricidad (NCM 2716).",
        "Espejo: lo que los demás países declaran haber importado desde Paraguay (UN Comtrade), solo total anual.",
        "Fuentes: DNIT (datos abiertos de aduanas); VUE (origen de los datos: Ministerio de Industria y "
        "Comercio); BCP (SICEX); UN Comtrade. Elaboración propia.",
        "Método y código: https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic",
    ]})

    anual.to_csv(DESTINO / "utilizacion_por_anio.csv", index=False, encoding="utf-8-sig")
    socios.to_csv(DESTINO / "utilizacion_por_socio.csv", index=False, encoding="utf-8-sig")
    pais.to_csv(DESTINO / "exportaciones_por_pais.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(DESTINO / "Utilizacion_acuerdos_Paraguay_2011_2026.xlsx", engine="xlsxwriter") as w:
        for nombre, t in (("Por año", anual), ("Utilización por socio", socios),
                          ("Por país", pais), ("Notas", notas)):
            t.to_excel(w, sheet_name=nombre, index=False)
            w.sheets[nombre].freeze_panes(1, 0)
            w.sheets[nombre].set_column(0, len(t.columns) - 1, 18 if nombre != "Notas" else 110)
    print("Listo:", sorted(p.name for p in DESTINO.iterdir()))


if __name__ == "__main__":
    main()
