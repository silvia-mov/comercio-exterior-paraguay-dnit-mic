"""
Descarga de los archivos mensuales de la DNIT (despachos "Nivel Item", CSV)
==========================================================================

Herramienta APARTE del procesamiento: solo baja los archivos a una carpeta.
Después se corre procesar_despachos.py como siempre.

Fuentes, en este orden (se puede elegir con --fuente):
  1. dnit   : el portal de Datos Abiertos de la DNIT
              (https://datosabiertos.aduana.gov.py), que publica desde enero de 1997.
  2. github : la copia de respaldo en las releases de este repositorio
              (una release por año: datos-2021, datos-2022, ...), por si el portal
              de la DNIT no responde o cambia de dirección.

Uso:
    python python/descargar_dnit.py --anios 2021
    python python/descargar_dnit.py --anios 2019-2021 --meses enero,febrero
    python python/descargar_dnit.py --anios 2021 --fuente github
    python python/descargar_dnit.py --listar            # muestra qué años y meses hay en la DNIT

Los archivos que ya están en la carpeta (con el mismo tamaño) no se vuelven a bajar.
Solo usa la biblioteca estándar de Python (no hay que instalar nada).
"""

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

CARPETA_DESTINO = "datos_dnit"

PORTAL_DNIT = "https://datosabiertos.aduana.gov.py"
LISTA_ARCHIVOS_DNIT = PORTAL_DNIT + "/ddaa/mainctrl/listaArchivos"
# Releases de respaldo: https://github.com/<REPO_GITHUB>/releases/tag/datos-<año>
REPO_GITHUB = "silvia-mov/comercio-exterior-paraguay-dnit-mic"

# ==============================================================================

RAIZ_REPO = Path(__file__).resolve().parent.parent
MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
         "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
CABECERAS = {"User-Agent": "comercio-exterior-paraguay-dnit-mic (descarga de datos abiertos)"}


def leer_anios(texto):
    """'2021' -> [2021]; '2019-2021' -> [2019, 2020, 2021]; '2019,2021' -> [2019, 2021]."""
    anios = []
    for parte in texto.replace(" ", "").split(","):
        if "-" in parte:
            a, b = (int(x) for x in parte.split("-"))
            anios += list(range(min(a, b), max(a, b) + 1))
        elif parte:
            anios.append(int(parte))
    return sorted(set(anios))


def leer_meses(texto):
    if not texto or texto.strip().upper() == "TODOS":
        return MESES
    elegidos = []
    for p in texto.upper().replace(" ", "").split(","):
        if p.isdigit() and 1 <= int(p) <= 12:
            elegidos.append(MESES[int(p) - 1])
        elif p in ("SETIEMBRE", "SEP", "SET"):
            elegidos.append("SEPTIEMBRE")
        elif p in MESES:
            elegidos.append(p)
        else:
            sys.exit(f"Mes no reconocido: {p}")
    return [m for m in MESES if m in elegidos]


def abrir(url, metodo="GET", timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS, method=metodo),
                                  timeout=timeout)


def lista_dnit():
    """Lista de archivos que publica el portal: {(año, MES): tamaño en bytes o None}."""
    with abrir(LISTA_ARCHIVOS_DNIT) as r:
        archivos = json.load(r)
    disponibles = {}
    for a in archivos:
        _, anio, mes = (a.get("separatePath") or [None, None, None])[:3]
        if a.get("ext") == "csv" and a.get("fileName", "").endswith("_Nivel_Item"):
            disponibles[(int(anio), mes)] = PORTAL_DNIT + "/" + a["directory"] + a["fileName"] + ".csv"
    return disponibles


def tamano_remoto(url):
    try:
        with abrir(url, metodo="HEAD", timeout=30) as r:
            n = r.headers.get("Content-Length")
            return int(n) if n else None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def bajar(url, destino, intentos=3):
    """Descarga a un archivo temporal y lo renombra al terminar (no deja archivos a medias).
    Reintenta si la conexión se corta (el portal de la DNIT a veces es lento)."""
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    for intento in range(1, intentos + 1):
        try:
            with abrir(url, timeout=300) as r, open(temporal, "wb") as f:
                shutil.copyfileobj(r, f, length=1024 * 1024)
            esperado = r.headers.get("Content-Length")
            if esperado and int(esperado) != temporal.stat().st_size:
                raise OSError(f"archivo incompleto ({temporal.stat().st_size} de {esperado} bytes)")
            temporal.replace(destino)
            return
        except urllib.error.HTTPError:
            temporal.unlink(missing_ok=True)
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            temporal.unlink(missing_ok=True)
            if intento == intentos:
                raise
            print(f"  se cortó la descarga ({e}); reintento {intento + 1} de {intentos} ...", flush=True)


def desde_github(anio, mes, destino):
    """Prueba el CSV y, si no está, un .zip con el CSV adentro."""
    nombre = f"{anio}_{mes}_Nivel_Item"
    base = f"https://github.com/{REPO_GITHUB}/releases/download/datos-{anio}/"
    try:
        bajar(base + nombre + ".csv", destino)
        return True
    except urllib.error.HTTPError:
        pass
    try:
        zip_destino = destino.with_suffix(".zip")
        bajar(base + nombre + ".zip", zip_destino)
        with zipfile.ZipFile(zip_destino) as z:
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
            with z.open(csvs[0]) as src, open(destino, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        zip_destino.unlink()
        return True
    except (urllib.error.HTTPError, zipfile.BadZipFile, IndexError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Descarga los CSV mensuales 'Nivel Item' de la DNIT")
    parser.add_argument("--anios", help="años, p. ej. 2021 o 2019-2021")
    parser.add_argument("--meses", default="todos", help="meses, p. ej. todos o enero,febrero")
    parser.add_argument("--fuente", choices=["auto", "dnit", "github"], default="auto",
                        help="auto = DNIT y, si falla, el respaldo de GitHub (por defecto)")
    parser.add_argument("--destino", default=CARPETA_DESTINO, help="carpeta donde guardar los archivos")
    parser.add_argument("--listar", action="store_true", help="solo mostrar qué hay en el portal de la DNIT")
    args = parser.parse_args()

    disponibles = {}
    if args.fuente in ("auto", "dnit") or args.listar:
        try:
            disponibles = lista_dnit()
            print(f"Portal DNIT: {len(disponibles)} meses disponibles.")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"AVISO: no se pudo leer la lista del portal de la DNIT ({e}).")
            if args.fuente == "dnit":
                sys.exit(1)

    if args.listar:
        for anio in sorted({a for a, _ in disponibles}):
            meses = [m for m in MESES if (anio, m) in disponibles]
            print(f"  {anio}: {len(meses)} meses ({meses[0].title()} a {meses[-1].title()})")
        return
    if not args.anios:
        sys.exit("Indique los años con --anios (p. ej. --anios 2021), o use --listar.")

    carpeta = Path(args.destino)
    if not carpeta.is_absolute():
        carpeta = RAIZ_REPO / carpeta
    carpeta.mkdir(parents=True, exist_ok=True)

    resumen = {"bajados": 0, "ya estaban": 0, "no encontrados": []}
    for anio in leer_anios(args.anios):
        for mes in leer_meses(args.meses):
            destino = carpeta / str(anio) / f"{anio}_{mes}_Nivel_Item.csv"
            destino.parent.mkdir(exist_ok=True)
            url = disponibles.get((anio, mes))

            if destino.exists():
                remoto = tamano_remoto(url) if url else None
                if remoto is None or remoto == destino.stat().st_size:
                    print(f"{anio} {mes}: ya está")
                    resumen["ya estaban"] += 1
                    continue

            ok = False
            if url and args.fuente in ("auto", "dnit"):
                print(f"{anio} {mes}: bajando de la DNIT ...", flush=True)
                try:
                    bajar(url, destino)
                    ok = True
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    print(f"  falló la DNIT ({e})")
            if not ok and args.fuente in ("auto", "github"):
                print(f"{anio} {mes}: bajando del respaldo en GitHub ...", flush=True)
                ok = desde_github(anio, mes, destino)
            if ok:
                print(f"  {destino.stat().st_size / 1e6:,.0f} MB -> {destino.relative_to(RAIZ_REPO) if destino.is_relative_to(RAIZ_REPO) else destino}")
                resumen["bajados"] += 1
            else:
                print("  no está disponible en ninguna fuente")
                resumen["no encontrados"].append(f"{anio} {mes}")

    print(f"\nListo: {resumen['bajados']} bajados, {resumen['ya estaban']} ya estaban.")
    if resumen["no encontrados"]:
        print("No encontrados:", ", ".join(resumen["no encontrados"]))


if __name__ == "__main__":
    main()
