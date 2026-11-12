"""
Descarga el comercio mensual de Paraguay desde la API de UN Comtrade.

Los datos de Paraguay en Comtrade son los que envía el Banco Central del Paraguay (BCP):
incluyen la electricidad (Itaipú, Yacyretá y ANDE) y, en las exportaciones, el destino
final según el certificado de origen. Sirven para cruzar con la DNIT y la VUE.

Necesita una clave de suscripción de UN Comtrade (https://comtradeplus.un.org):
    export COMTRADE_KEY="su-clave"           (Linux / Mac)
    set COMTRADE_KEY=su-clave                (Windows, cmd)

Uso (desde la raíz del repositorio):
    python python/descargar_comtrade.py --anios 2011-2026
    python python/descargar_comtrade.py --anios 2021 --nivel AG6 --flujos X

Guarda un CSV por año en datos_comtrade/<año>/Comtrade_PRY_<año>_<nivel>.csv con:
    PERIODO, AÑO, MES, FLUJO (X exportación / M importación), PAIS_CODIGO_ISO2,
    PAIS_CODIGO_ISO3, PAIS, PARTIDA (código SA), VALOR_DOLAR (FOB en exportaciones,
    CIF en importaciones), FOB_DOLAR, CIF_DOLAR, PESO_NETO_KG, CLASIFICACION (versión del SA)

OJO
- Las condiciones de UN Comtrade limitan republicar datos bajados con una suscripción:
  los CSV quedan en su computadora (datos_comtrade/ no se sube a GitHub).
- Comtrade guarda la última versión que envió Paraguay. El BCP considera preliminares
  los dos últimos años, así que esos meses pueden cambiar. El archivo de cada año
  guarda la fecha de descarga y la fecha de publicación de cada mes en Comtrade.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "datos_comtrade"
API = "https://comtradeapi.un.org/data/v1"
REFERENCIA_PAISES = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
PARAGUAY = 600


def pedir(url, clave, intentos=4):
    """GET con la clave en el encabezado; reintenta si la API pide esperar."""
    req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": clave})
    for intento in range(1, intentos + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and intento < intentos:
                espera = 10 * intento
                print(f"  la API respondió {e.code}; espero {espera} s y reintento ...")
                time.sleep(espera)
                continue
            if e.code in (401, 403):
                raise SystemExit("La API rechazó la clave (error %d). Revise COMTRADE_KEY." % e.code)
            raise


def leer_rango_anios(texto):
    anios = set()
    for parte in texto.split(","):
        if "-" in parte:
            a, b = parte.split("-")
            anios.update(range(int(a), int(b) + 1))
        else:
            anios.add(int(parte))
    return sorted(anios)


def paises():
    with urllib.request.urlopen(REFERENCIA_PAISES, timeout=120) as r:
        datos = json.load(r)["results"]
    return {p["PartnerCode"]: p for p in datos}


def disponibles(clave):
    """Meses publicados para Paraguay: {AAAAMM: (versión del SA, fecha de publicación)}."""
    d = pedir(f"{API}/getDA/C/M/HS?reporterCode={PARAGUAY}", clave)["data"]
    return {int(x["period"]): (x["classificationCode"], x["lastReleased"][:10]) for x in d}


def bajar_anio(anio, meses, nivel, flujos, clave, ref):
    parametros = {
        "reporterCode": PARAGUAY,
        "period": ",".join(str(m) for m in meses),
        "flowCode": ",".join(flujos),
        "cmdCode": nivel,
        "partner2Code": 0,     # sin desagregar por segundo socio
        "customsCode": "C00",  # todos los regímenes
        "motCode": 0,          # todos los medios de transporte
        "includeDesc": "true",
    }
    d = pedir(f"{API}/get/C/M/HS?" + urllib.parse.urlencode(parametros), clave)
    if d.get("error"):
        raise SystemExit(f"Error de la API: {d['error']}")
    filas = []
    for x in d["data"]:
        if x["partnerCode"] == 0:   # "Mundo" = suma de todos los socios: se omite
            continue
        p = ref.get(x["partnerCode"], {})
        es_imp = x["flowCode"] == "M"
        filas.append({
            "PERIODO": x["period"],
            "AÑO": int(str(x["period"])[:4]),
            "MES": int(str(x["period"])[4:]),
            "FLUJO": x["flowCode"],
            "PAIS_CODIGO_ISO2": p.get("PartnerCodeIsoAlpha2", ""),
            "PAIS_CODIGO_ISO3": p.get("PartnerCodeIsoAlpha3", ""),
            "PAIS": p.get("PartnerDesc", x.get("partnerDesc", "")).strip(),
            "PARTIDA": x["cmdCode"],
            "VALOR_DOLAR": x["cifvalue"] if es_imp and x.get("cifvalue") else x["primaryValue"],
            "FOB_DOLAR": x.get("fobvalue") or "",
            "CIF_DOLAR": x.get("cifvalue") or "",
            "PESO_NETO_KG": x.get("netWgt") or "",
            "CLASIFICACION": x.get("classificationCode", ""),
        })
    return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anios", default="2011-2026", help="por ejemplo 2021 o 2011-2026")
    ap.add_argument("--nivel", default="AG4", choices=["AG2", "AG4", "AG6"],
                    help="dígitos del SA: AG2 capítulo, AG4 partida, AG6 subpartida")
    ap.add_argument("--flujos", default="X,M", help="X exportaciones, M importaciones")
    ap.add_argument("--destino", default=str(DESTINO))
    args = ap.parse_args()

    clave = os.environ.get("COMTRADE_KEY")
    if not clave:
        sys.exit("Falta la clave: defina la variable de entorno COMTRADE_KEY (ver al comienzo del archivo).")
    flujos = [f.strip().upper() for f in args.flujos.split(",")]
    hoy = date.today().isoformat()

    ref = paises()
    publicados = disponibles(clave)
    for anio in leer_rango_anios(args.anios):
        meses = sorted(p for p in publicados if p // 100 == anio)
        if not meses:
            print(f"{anio}: Comtrade todavía no tiene meses publicados para Paraguay")
            continue
        print(f"{anio}: bajando {len(meses)} meses ({nivel_txt(args.nivel)}) ...")
        filas = bajar_anio(anio, meses, args.nivel, flujos, clave, ref)
        carpeta = Path(args.destino) / str(anio)
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"Comtrade_PRY_{anio}_{args.nivel}.csv"
        with open(archivo, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        # registro de cuándo se bajó y qué versión publicó Comtrade (los datos recientes cambian)
        with open(carpeta / "descarga.txt", "w", encoding="utf-8") as f:
            f.write(f"Fuente: UN Comtrade (datos informados por Paraguay)\nFecha de descarga: {hoy}\n")
            f.write("Mes\tSA\tPublicado en Comtrade\n")
            for m in meses:
                f.write(f"{m}\t{publicados[m][0]}\t{publicados[m][1]}\n")
        tot = {fl: sum(r["VALOR_DOLAR"] for r in filas if r["FLUJO"] == fl) / 1e6 for fl in flujos}
        print("   " + ", ".join(f"{fl}: USD {v:,.1f} M" for fl, v in tot.items()) + f"  -> {archivo}")
        time.sleep(1)


def nivel_txt(nivel):
    return {"AG2": "capítulos", "AG4": "partidas", "AG6": "subpartidas"}[nivel]


if __name__ == "__main__":
    main()
