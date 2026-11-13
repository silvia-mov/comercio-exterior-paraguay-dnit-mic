"""
Arma los Excel para descargar desde la página: uno por año y por fuente, en Calibri 10,
con tres hojas:
    Datos            la tabla completa del año
    Tabla dinámica   una tabla dinámica de verdad, lista para mover filas, columnas y filtros
    Notas            fuente, qué es cada columna y cómo citar

Fuentes (carpeta docs/descargas/<fuente>/):
    dnit/DNIT_<año>.xlsx  despachos de la DNIT resumidos por producto (NCM 8 dígitos), país y
                          acuerdo (los datos completos no entran en Excel: superan el millón de filas)
    bcp/BCP_<año>.xlsx    exportaciones del SICEX del BCP por mes, producto y país
    vue/VUE_<año>.xlsx    los 12 archivos mensuales de la VUE unidos (sin cambiar los valores)

Además agrega la hoja "Tabla dinámica" a los dos Excel de resultados de docs/datos/.
Correr DESPUÉS de docs/datos_web.py y python/productos_acuerdos.py (que rehacen esos Excel).

Uso (desde la raíz del repositorio):
    python python/excel_descargas.py                 # todo
    python python/excel_descargas.py --fuentes bcp vue --anios 2024 2025

La tabla dinámica la arma python/tabla_dinamica.py con LibreOffice (requiere soffice y python3-uno
del sistema); este programa lo llama al final con /usr/bin/python3.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leer_bcp  # noqa: E402
import leer_vue  # noqa: E402
from productos_acuerdos import descripcion_legible  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "descargas"
ANIOS = range(2011, 2027)
AYUDA = ("Hoja 'Tabla dinámica': hacé clic dentro de la tabla para elegir otras filas, columnas o "
         "filtros (en Excel aparece el panel 'Campos de tabla dinámica').")


def escribir(destino, datos, notas):
    """Hoja Datos + hoja Notas, todo en Calibri 10, con filtros y la primera fila fija."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="xlsxwriter") as w:
        libro = w.book
        libro.formats[0].set_font_name("Calibri")
        libro.formats[0].set_font_size(10)
        negrita = libro.add_format({"bold": True, "font_name": "Calibri", "font_size": 10, "bg_color": "#FEC9D7"})
        texto = libro.add_format({"font_name": "Calibri", "font_size": 10})
        datos.to_excel(w, sheet_name="Datos", index=False, header=False, startrow=1)
        hoja = w.sheets["Datos"]
        for c, nombre in enumerate(datos.columns):
            hoja.write(0, c, nombre, negrita)
            ancho = 60 if nombre.startswith("DESCRIPCION") else max(10, min(40, len(str(nombre)) + 4))
            hoja.set_column(c, c, ancho, texto)
        hoja.freeze_panes(1, 0)
        hoja.autofilter(0, 0, len(datos), len(datos.columns) - 1)
        notas_hoja = libro.add_worksheet("Notas")
        notas_hoja.set_column(0, 0, 120, texto)
        for i, linea in enumerate(notas + ["", AYUDA]):
            notas_hoja.write(i, 0, linea, negrita if i == 0 else texto)


# --- DNIT: resumen por producto, país y acuerdo -------------------------------------------------
def nombres_paises():
    p = pd.read_csv(RAIZ / "config" / "paises_dnit.csv", dtype=str, keep_default_na=False)
    return p.drop_duplicates("codigo_dnit").set_index("codigo_dnit")["pais_dnit"]


def dnit(anio):
    origen = RAIZ / "salidas" / "productos" / f"productos_{anio}.csv"
    if not origen.exists():
        return None
    d = pd.read_csv(origen, dtype={"NCM": str, "CODIGO_PAIS": str}, keep_default_na=False, na_values=[""])
    desc = pd.read_csv(RAIZ / "salidas" / "productos" / f"descripciones_ncm_{anio}.csv", dtype=str)
    desc = desc.drop_duplicates("NCM").set_index("NCM")["DESCRIPCION_COMPLETA"].map(descripcion_legible)
    filas = len(d)
    d["PAIS"] = d["CODIGO_PAIS"].map(nombres_paises()).fillna(d["CODIGO_PAIS"])
    d["PARTIDA"] = d["NCM"].str[:4]
    d["DESCRIPCION"] = d["NCM"].map(desc)
    meses = int(d["MESES"].max())
    d = d[["AÑO", "OPERACION", "NCM", "PARTIDA", "DESCRIPCION", "CODIGO_PAIS", "PAIS",
           "TIPO_ACUERDO", "ACUERDO_CONSOLIDADO", "VALOR_USD", "PESO_NETO_KG"]]
    assert len(d) == filas
    notas = [f"Comercio exterior de Paraguay {anio} por producto, país y acuerdo (DNIT)",
             f"Meses incluidos: {meses}." + (" Año incompleto." if meses < 12 else ""),
             "Fuente: Dirección Nacional de Ingresos Tributarios (DNIT), datos abiertos de aduana "
             "(despachos a nivel ítem). Elaboración propia.",
             "Una fila por año, operación (exportación o importación), código NCM de 8 dígitos, país y acuerdo.",
             "Los despachos completos no entran en una hoja de Excel (superan 1.048.576 filas); por eso se suman "
             "los despachos con el mismo producto, país y acuerdo.",
             "VALOR_USD: valor FOB en dólares (exportaciones) o valor declarado (importaciones), como lo publica la DNIT.",
             "PESO_NETO_KG: peso neto en kilos.",
             "TIPO_ACUERDO y ACUERDO_CONSOLIDADO: preferencia arancelaria declarada en el despacho. 'OMC' y "
             "'Sin acuerdo' pagan el arancel general.",
             "PAIS: destino (exportación) u origen (importación) según la DNIT.",
             "Código y explicación: https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic"]
    tabla = {"hoja_datos": "Datos", "filas": ["ACUERDO_CONSOLIDADO"], "columnas": ["OPERACION"],
             "filtros": ["PAIS", "PARTIDA"], "valores": [["VALOR_USD", "suma", "Valor (USD)"]]}
    return d, notas, tabla


# --- BCP: SICEX mensual a 8 dígitos ----------------------------------------------------------------
def bcp(anio):
    if not (RAIZ / "datos_bcp" / str(anio)).exists():
        return None
    d = leer_bcp.leer([anio]).sort_values(["MES", "NCM", "PAIS"])
    d["ELECTRICIDAD"] = d["ELECTRICIDAD"].map({True: "SI", False: "NO"})
    meses = int(d["MES"].max())
    notas = [f"Exportaciones de Paraguay {anio} por mes, producto y país (BCP, SICEX)",
             f"Meses incluidos: {meses}." + (" Año incompleto." if meses < 12 else ""),
             "Fuente: Banco Central del Paraguay (BCP), Sistema de Información de Comercio Exterior (SICEX). "
             "Datos preliminares durante los 2 años siguientes.",
             "Es el mismo archivo del SICEX pasado a una fila por mes, código NCM de 8 dígitos y país (sin "
             "cambiar los valores; se quitan las filas en cero).",
             "FOB_DOLAR: valor FOB en dólares. KILOS_NETOS: peso neto.",
             "ELECTRICIDAD: SI para la NCM 2716 (energía eléctrica de Itaipú y Yacyretá), que no pasa por la aduana.",
             "CODIGO_PAIS: código de país de la DNIT, para cruzar con los otros archivos.",
             "Código y explicación: https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic"]
    tabla = {"hoja_datos": "Datos", "filas": ["PAIS"], "columnas": ["MES"],
             "filtros": ["ELECTRICIDAD", "PARTIDA"], "valores": [["FOB_DOLAR", "suma", "FOB (USD)"]]}
    return d, notas, tabla


# --- VUE: los 12 meses en un solo archivo ----------------------------------------------------------
def vue(anio):
    carpeta = RAIZ / "datos_vue" / str(anio)
    if not carpeta.exists():
        return None
    por_mes = {}
    for p in sorted(carpeta.glob("Exportaciones_*")):
        if not p.is_file() or "_convertido" in p.stem:
            continue
        mes = int(re.search(r"_(\d{4})_\|?(\d{2})", p.name).group(2))
        actual = por_mes.get(mes)
        if actual is None or (actual.suffix.lower() == ".csv" and p.suffix.lower() != ".csv"):
            por_mes[mes] = p
    partes = []
    for mes, p in sorted(por_mes.items()):
        t = leer_vue.leer(p)
        t.insert(0, "MES", mes)
        t.insert(0, "AÑO", anio)
        partes.append(t)
    d = pd.concat(partes, ignore_index=True)
    d = d[[c for c in ["AÑO", "MES", "ANOMES", "CAPITULO", "CATEGORIA", "PAISDESTINO", "FOBDOLAR",
                       "TONELADA", "ARCHIVO"] if c in d.columns]]
    notas = [f"Exportaciones de Paraguay {anio} con certificado de origen (VUE)",
             f"Meses incluidos: {len(por_mes)} ({', '.join(str(m) for m in sorted(por_mes))})."
             + (" Año incompleto." if len(por_mes) < 12 else ""),
             "Origen de los datos: Ministerio de Industria y Comercio (MIC), Ventanilla Única de Exportación (VUE).",
             "Son los archivos mensuales publicados, uno debajo del otro, sin cambiar ningún valor. La columna "
             "ARCHIVO indica de qué archivo viene cada fila; los originales están en la carpeta datos_vue/.",
             "Este archivo no es una publicación oficial del Ministerio ni cuenta con su aval.",
             "FOBDOLAR: valor FOB en dólares. TONELADA: peso en toneladas. CAPITULO: partida de 4 dígitos "
             "(cuando el archivo la trae).",
             "Código y explicación: https://github.com/silvia-mov/comercio-exterior-paraguay-dnit-mic"]
    tabla = {"hoja_datos": "Datos", "filas": ["PAISDESTINO"], "columnas": ["MES"],
             "filtros": ["CATEGORIA"], "valores": [["FOBDOLAR", "suma", "FOB (USD)"]]}
    return d, notas, tabla


def etiquetas_en_espanol(archivo):
    """LibreOffice escribe algunas etiquetas de la tabla dinámica en inglés; se pasan al español."""
    cambios = {"xl/sharedStrings.xml": [('<t xml:space="preserve">Filter</t>', '<t xml:space="preserve">Filtros</t>'),
                                        ('<t xml:space="preserve">- all -</t>', '<t xml:space="preserve">(Todos)</t>')],
               "xl/pivotTables/pivotTable1.xml": [('dataCaption="Values"', 'dataCaption="Valores"')]}
    temporal = Path(str(archivo) + ".tmp")
    with zipfile.ZipFile(archivo) as zin, zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            contenido = zin.read(item.filename)
            for viejo, nuevo in cambios.get(item.filename, []):
                contenido = contenido.replace(viejo.encode(), nuevo.encode())
            zout.writestr(item, contenido)
    shutil.move(temporal, archivo)


FUENTES = {"dnit": ("DNIT", dnit), "bcp": ("BCP", bcp), "vue": ("VUE", vue)}

# Tablas dinámicas que se agregan a los Excel de resultados de docs/datos/
RESULTADOS = [
    {"archivo": "docs/datos/Utilizacion_acuerdos_Paraguay_2011_2026.xlsx", "hoja_datos": "Por país",
     "filas": ["PAIS"], "columnas": [], "filtros": ["AÑO"],
     "valores": [["DNIT_EXPORTADO_USD", "suma", "Exportado (USD)"],
                 ["DNIT_CON_ACUERDO_USD", "suma", "Con acuerdo (USD)"]]},
    {"archivo": "docs/datos/Productos_acuerdos_Paraguay_2011_2026.xlsx", "hoja_datos": "Todos 4 dígitos",
     "filas": ["PRODUCTO"], "columnas": ["AÑO"], "filtros": ["OPERACION"],
     "valores": [["TOTAL_USD", "suma", "Total (USD)"]]},
]


def main():
    parser = argparse.ArgumentParser(description="Excel por año con tabla dinámica")
    parser.add_argument("--fuentes", nargs="+", default=list(FUENTES) + ["resultados"])
    parser.add_argument("--anios", nargs="+", type=int, default=list(ANIOS))
    args = parser.parse_args()

    lista = []
    for clave in args.fuentes:
        if clave == "resultados":
            lista += [dict(r, archivo=str(RAIZ / r["archivo"])) for r in RESULTADOS]
            continue
        nombre, funcion = FUENTES[clave]
        for anio in args.anios:
            r = funcion(anio)
            if r is None:
                continue
            datos, notas, tabla = r
            assert len(datos) < 1_048_575, f"{nombre} {anio}: demasiadas filas para Excel"
            destino = SALIDA / clave / f"{nombre}_{anio}.xlsx"
            escribir(destino, datos, notas)
            lista.append(dict(tabla, archivo=str(destino)))
            print(f"{destino.relative_to(RAIZ)}: {len(datos):,} filas", flush=True)

    config = SALIDA / "_tablas.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        subprocess.run(["/usr/bin/python3", str(RAIZ / "python" / "tabla_dinamica.py"), str(config)], check=True)
    finally:
        config.unlink()
    for t in lista:
        etiquetas_en_espanol(t["archivo"])


if __name__ == "__main__":
    main()
