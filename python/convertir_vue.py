"""
Copias en Excel (.xlsx) de los archivos de la VUE que no son Excel normales
==========================================================================

Algunos archivos de la VUE se llaman .xls pero por dentro son otra cosa (ver
datos_vue/LEEME.md). Este programa deja, AL LADO de cada original, una copia que abre en
Excel sin avisos, con el sufijo "_convertido":

    datos_vue/2023/Exportaciones_categoria_Pais_2023_02.xls             <- original (sin tocar)
    datos_vue/2023/Exportaciones_categoria_Pais_2023_02_convertido.xlsx <- copia en Excel

- Los valores no se modifican: solo cambia el formato del archivo.
- La hoja "Origen" de cada copia indica el archivo original, su enlace y, si el original
  la trae, la fecha de ejecución del informe (condición de reutilización del MIC).
- Los originales no se tocan.

Uso:
    python python/convertir_vue.py
"""
import email
import re
import shutil
from pathlib import Path

import pandas as pd

from leer_vue import formato, leer

RAIZ_REPO = Path(__file__).resolve().parent.parent
CARPETA = RAIZ_REPO / "datos_vue"
URL_VUE = "https://www.vue.gov.py/comercio-exterior/{anio}/origen-categoria-pais/{nombre}"
NOTA = ("Copia en formato Excel del archivo original de la VUE, sin modificar los valores. "
        "Origen de los datos: Ministerio de Industria y Comercio.")


def fecha_ejecucion(ruta):
    """Fecha de ejecución que traen algunos informes de 2011, si existe."""
    mensaje = email.message_from_bytes(ruta.read_bytes())
    for parte in mensaje.walk():
        if parte.get_content_type() == "text/html":
            texto = parte.get_payload(decode=True).decode(parte.get_content_charset() or "windows-1252",
                                                          errors="replace")
            m = re.search(r"Fecha de ejecuci\S*n:?\s*(\d{1,2}/\d{1,2}/\d{4})", re.sub("<[^>]+>", " ", texto))
            if m:
                return m.group(1)
    return ""


def main():
    hechos = []
    for ruta in sorted(CARPETA.rglob("Exportaciones_*")):
        if "_convertido" in ruta.stem or ruta.suffix.lower() == ".csv":
            continue
        fmt = formato(ruta)
        if fmt == "xls":
            continue                                     # ya es un Excel normal
        anio = ruta.parent.name
        destino = ruta.with_name(ruta.stem + "_convertido.xlsx")
        if fmt == "xlsx":
            shutil.copyfile(ruta, destino)               # mismo archivo, extensión correcta
        else:
            datos = leer(ruta).drop(columns=["ARCHIVO", "FORMATO"])
            datos = datos.dropna(axis=1, how="all")      # 2011 no trae capítulo
            origen = pd.DataFrame({
                "Campo": ["Archivo original", "Enlace", "Formato del original", "Fecha de ejecución",
                          "Nota"],
                "Valor": [ruta.name, URL_VUE.format(anio=anio, nombre=ruta.name), fmt,
                          fecha_ejecucion(ruta) if fmt == "mhtml" else "", NOTA],
            })
            with pd.ExcelWriter(destino, engine="openpyxl") as w:
                datos.to_excel(w, sheet_name="Datos", index=False)
                origen.to_excel(w, sheet_name="Origen", index=False)
        hechos.append(f"{ruta.name} ({fmt}) -> {destino.name}")
    print(f"{len(hechos)} copias en Excel:")
    print("\n".join("  " + h for h in hechos))


if __name__ == "__main__":
    main()
