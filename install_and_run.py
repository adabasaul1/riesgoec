"""
╔══════════════════════════════════════════════════════════════════╗
║  install_and_run.py — INSTALADOR AUTOMÁTICO                     ║
║                                                                  ║
║  CÓMO USAR:                                                      ║
║    En Anaconda Prompt:  python install_and_run.py               ║
║    En Spyder:           Abrir y presionar F5                    ║
║                                                                  ║
║  Este script:                                                    ║
║    1. Verifica Python 3.9+                                      ║
║    2. Instala dependencias automáticamente                      ║
║    3. Verifica conectividad a APIs                              ║
║    4. Crea estructura de carpetas                               ║
║    5. Lanza el geoportal                                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import subprocess
import sys
import os
import time
from pathlib import Path


# ─── Colores ANSI para consola ───
class C:
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    BOLD   = '\033[1m'
    RESET  = '\033[0m'

def ok(msg):   print(f"  {C.GREEN}✓{C.RESET} {msg}")
def err(msg):  print(f"  {C.RED}✗{C.RESET} {msg}")
def warn(msg): print(f"  {C.YELLOW}⚠{C.RESET} {msg}")
def info(msg): print(f"  {C.BLUE}→{C.RESET} {msg}")


def check_python_version():
    print(f"\n{C.BOLD}[1/5] Verificando versión de Python...{C.RESET}")
    major, minor = sys.version_info[:2]
    v = f"{major}.{minor}"
    if major < 3 or (major == 3 and minor < 9):
        err(f"Python {v} detectado. Se requiere Python 3.9+")
        print("    Descarga Anaconda desde: https://www.anaconda.com/download")
        sys.exit(1)
    ok(f"Python {v} detectado ✓")


def install_dependencies():
    print(f"\n{C.BOLD}[2/5] Instalando dependencias...{C.RESET}")
    req_file = Path(__file__).parent / "requirements.txt"

    if not req_file.exists():
        err(f"No se encontró requirements.txt en {req_file}")
        sys.exit(1)

    # Primero actualizar pip
    info("Actualizando pip...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
        check=False
    )

    # Instalar con pip
    info("Instalando paquetes desde requirements.txt...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q", "--no-warn-script-location"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        warn("Algunos paquetes fallaron. Intentando instalar individualmente...")
        with open(req_file, "r") as f:
            packages = [
                line.strip().split("#")[0].strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
        failed = []
        for pkg in packages:
            if not pkg:
                continue
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q", "--no-warn-script-location"],
                capture_output=True
            )
            if r.returncode != 0:
                failed.append(pkg)
                warn(f"No se pudo instalar: {pkg}")
            else:
                ok(f"Instalado: {pkg.split('==')[0]}")

        if failed:
            warn(f"Paquetes no instalados: {', '.join(failed)}")
            warn("El geoportal puede funcionar con funcionalidad reducida.")
        else:
            ok("Todas las dependencias instaladas correctamente.")
    else:
        ok("Todas las dependencias instaladas correctamente.")


def create_folder_structure():
    print(f"\n{C.BOLD}[3/5] Creando estructura de carpetas...{C.RESET}")
    base = Path(__file__).parent
    dirs = [
        base / "data_fetchers",
        base / "processors",
        base / "webapp" / "templates",
        base / "webapp" / "static" / "css",
        base / "webapp" / "static" / "js",
        base / "webapp" / "static" / "data",
        base / "webapp" / "static" / "img",
        base / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # __init__.py para módulos Python
    for pkg in [base / "data_fetchers", base / "processors"]:
        init = pkg / "__init__.py"
        if not init.exists():
            init.write_text('"""Módulos del geoportal."""\n')

    ok("Estructura de carpetas creada.")


def check_api_connectivity():
    print(f"\n{C.BOLD}[4/5] Verificando conectividad a APIs...{C.RESET}")
    try:
        import requests
    except ImportError:
        warn("requests no instalado — saltando verificación de APIs.")
        return

    apis = [
        ("USGS Earthquakes",  "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=1"),
        ("IGEPN Ecuador",     "https://www.igepn.edu.ec"),
        ("PTWC Tsunami",      "https://ptwc.weather.gov"),
        ("GDACS ONU",         "https://www.gdacs.org/xml/rss.xml"),
        ("OpenStreetMap",     "https://www.openstreetmap.org"),
    ]

    headers = {"User-Agent": "RiesgoEC-Installer/1.0"}
    for nombre, url in apis:
        try:
            resp = requests.get(url, timeout=8, headers=headers)
            if resp.status_code < 400:
                ok(f"{nombre} — {resp.status_code} OK")
            else:
                warn(f"{nombre} — HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            err(f"{nombre} — Sin conexión (verificar internet)")
        except requests.exceptions.Timeout:
            warn(f"{nombre} — Timeout (puede funcionar más lento)")
        except Exception as e:
            warn(f"{nombre} — {e}")


def launch_geoportal():
    print(f"\n{C.BOLD}[5/5] Lanzando geoportal...{C.RESET}")
    main_py = Path(__file__).parent / "main.py"

    if not main_py.exists():
        err(f"No se encontró main.py en {main_py}")
        print("\n  Asegúrate de haber descargado todos los archivos del geoportal.")
        sys.exit(1)

    ok(f"Ejecutando: {main_py}")
    print(f"\n{C.BOLD}{C.GREEN}")
    print("  ════════════════════════════════════════════════════")
    print("     GEOPORTAL RIESGOS ECUADOR — INICIANDO")
    print("     URL: http://localhost:5000")
    print("     Presiona Ctrl+C para detener")
    print("  ════════════════════════════════════════════════════")
    print(C.RESET)
    time.sleep(1)

    os.chdir(str(Path(__file__).parent))
    subprocess.run([sys.executable, str(main_py)], check=True)


def main():
    print(f"\n{C.BOLD}{C.BLUE}")
    print("  ╔════════════════════════════════════════════════════╗")
    print("  ║   INSTALADOR — GEOPORTAL RIESGOS ECUADOR          ║")
    print("  ║   RiesgoEC v1.0 | Python + Leaflet.js + Flask     ║")
    print("  ╚════════════════════════════════════════════════════╝")
    print(C.RESET)

    check_python_version()
    install_dependencies()
    create_folder_structure()
    check_api_connectivity()
    launch_geoportal()


if __name__ == "__main__":
    main()
