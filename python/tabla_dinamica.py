"""
Agrega una tabla dinámica (de verdad, de las que se arman arrastrando campos) a un Excel ya escrito,
usando LibreOffice en modo sin pantalla. Pone todo en Calibri 10.

Uso (con el Python del sistema, que trae el módulo "uno" de LibreOffice):
    python3 python/tabla_dinamica.py lista.json

lista.json: una lista de archivos, cada uno con su tabla:
    [{"archivo": "x.xlsx", "hoja_datos": "Datos", "hoja_tabla": "Tabla dinámica",
      "filas": ["PAIS"], "columnas": ["MES"], "filtros": ["OPERACION"],
      "valores": [["VALOR_USD", "suma", "Valor (USD)"]]}]

Requiere LibreOffice Calc (soffice) y python3-uno.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.table import CellAddress

FUNCIONES = {"suma": "SUM", "cuenta": "COUNT", "promedio": "AVERAGE"}


def prop(nombre, valor):
    p = PropertyValue()
    p.Name, p.Value = nombre, valor
    return p


def conectar(puerto=2002):
    perfil = Path("/tmp/claude-0/lo_perfil")
    proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore",
                             f"-env:UserInstallation=file://{perfil}",
                             f"--accept=socket,host=localhost,port={puerto};urp;"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(60):
        try:
            ctx = resolver.resolve(f"uno:socket,host=localhost,port={puerto};urp;StarOffice.ComponentContext")
            return proc, ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("No se pudo iniciar LibreOffice.")


def agregar(desktop, archivo, cfg):
    url = uno.systemPathToFileUrl(os.path.abspath(archivo))
    doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
    # Calibri 10 en todo el libro
    estilo = doc.StyleFamilies.getByName("CellStyles").getByName("Default")
    estilo.CharFontName, estilo.CharHeight = "Calibri", 10
    hojas = doc.Sheets
    for i in range(hojas.Count):   # también las celdas con formato propio (encabezados)
        h = hojas.getByIndex(i)
        c = h.createCursor()
        c.gotoEndOfUsedArea(False)
        r = h.getCellRangeByPosition(0, 0, c.RangeAddress.EndColumn, c.RangeAddress.EndRow)
        r.CharFontName, r.CharHeight = "Calibri", 10
    datos = hojas.getByName(cfg["hoja_datos"])
    cursor = datos.createCursor()
    cursor.gotoEndOfUsedArea(False)
    ultima_fila, ultima_col = cursor.RangeAddress.EndRow, cursor.RangeAddress.EndColumn
    encabezados = [datos.getCellByPosition(c, 0).String for c in range(ultima_col + 1)]
    nombre = cfg.get("hoja_tabla", "Tabla dinámica")
    if hojas.hasByName(nombre):   # al volver a correr, se rehace la tabla
        hojas.removeByName(nombre)
    hojas.insertNewByName(nombre, 1)
    tabla_hoja = hojas.getByName(nombre)
    rango = datos.getCellRangeByPosition(0, 0, ultima_col, ultima_fila).RangeAddress
    tablas = tabla_hoja.DataPilotTables
    desc = tablas.createDataPilotDescriptor()
    desc.SourceRange = rango
    campos = desc.DataPilotFields
    for orientacion, lista in (("ROW", cfg.get("filas", [])), ("COLUMN", cfg.get("columnas", [])),
                               ("PAGE", cfg.get("filtros", []))):
        for campo in lista:
            f = campos.getByIndex(encabezados.index(campo))
            f.Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", orientacion)
    for valor in cfg.get("valores", []):
        campo, funcion = valor[0], valor[1]
        f = campos.getByIndex(encabezados.index(campo))
        f.Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA")
        f.Function = uno.Enum("com.sun.star.sheet.GeneralFunction", FUNCIONES[funcion])
    desc.ShowFilterButton = True
    try:
        desc.GrandTotalName = "Total"
    except Exception:
        pass
    destino = CellAddress()
    destino.Sheet = 1
    destino.Column, destino.Row = 0, 2 + len(cfg.get("filtros", []))
    tablas.insertNewByName("TablaDinamica", destino, desc)
    # Nombres en español para los valores (en lugar de "Sum - ...")
    tabla = tablas.getByName("TablaDinamica")
    for k, valor in enumerate(cfg.get("valores", [])):
        if len(valor) > 2:
            try:
                tabla.DataFields.getByIndex(k).Name = valor[2]
            except Exception:
                pass
    tabla_hoja.getCellByPosition(0, 0).String = cfg.get(
        "titulo", "Tabla dinámica: hacé clic dentro para cambiar filas, columnas y filtros.")
    doc.storeToURL(url, (prop("FilterName", "Calc MS Excel 2007 XML"),))
    doc.close(True)


def main():
    lista = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    proc, desktop = conectar()
    try:
        for cfg in lista:
            agregar(desktop, cfg["archivo"], cfg)
            print("Tabla dinámica agregada:", cfg["archivo"], flush=True)
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        proc.wait(timeout=30)


if __name__ == "__main__":
    main()
