"""
╔══════════════════════════════════════════════════════════════════╗
║  subir_github.py — PUBLICAR GEOPORTAL EN INTERNET              ║
║                                                                  ║
║  ANTES DE EJECUTAR:                                             ║
║  1. Crear cuenta gratis en: https://github.com                 ║
║  2. Crear cuenta gratis en: https://render.com                 ║
║  3. Editar las variables de la seccion CONFIGURACION abajo     ║
║                                                                  ║
║  CÓMO EJECUTAR:                                                 ║
║    conda activate geoportal_ec                                  ║
║    cd C:\VARIOS\geoportal_riesgos_ecuador                       ║
║    python subir_github.py                                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

# ════════════════════════════════════════════
# CONFIGURACION — EDITAR ANTES DE EJECUTAR
# ════════════════════════════════════════════
GITHUB_USUARIO   = "adabasaul1"   
GITHUB_REPO      = "riesgoec"            # Nombre del repositorio a crear
GITHUB_EMAIL     = "adabasaul1@gmail.com"        # Tu email de GitHub
GITHUB_NOMBRE    = "Adan Saul Abarca"           # Tu nombre completo
# ════════════════════════════════════════════

class C:
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    BOLD   = '\033[1m'
    RESET  = '\033[0m'

def ok(msg):   print(f"  {C.GREEN}✓{C.RESET} {msg}")
def err(msg):  print(f"  {C.RED}✗ ERROR:{C.RESET} {msg}")
def warn(msg): print(f"  {C.YELLOW}⚠{C.RESET} {msg}")
def info(msg): print(f"  {C.BLUE}→{C.RESET} {msg}")
def titulo(msg): print(f"\n{C.BOLD}{msg}{C.RESET}")


def verificar_configuracion():
    titulo("[1/6] Verificando configuración...")
    if GITHUB_USUARIO == "TU_USUARIO_GITHUB":
        err("Debes editar el archivo subir_github.py y poner tu usuario de GitHub")
        err("Abre el archivo con el Bloc de Notas y edita las variables al inicio")
        print("\n  Ejemplo:")
        print('  GITHUB_USUARIO = "carlos_geologo"')
        print('  GITHUB_EMAIL   = "carlos@gmail.com"')
        print('  GITHUB_NOMBRE  = "Carlos Rodriguez"')
        sys.exit(1)
    ok(f"Usuario GitHub: {GITHUB_USUARIO}")
    ok(f"Repositorio:    {GITHUB_REPO}")
    ok(f"Email:          {GITHUB_EMAIL}")


def verificar_git():
    titulo("[2/6] Verificando Git instalado...")
    git_path = shutil.which("git")
    if git_path is None:
        err("Git no está instalado en tu computadora")
        print("\n  Descarga e instala Git desde: https://git-scm.com/download/win")
        print("  Después de instalar, cierra y vuelve a abrir Anaconda Prompt")
        print("  y ejecuta este script de nuevo.")
        sys.exit(1)
    result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    ok(f"Git encontrado: {result.stdout.strip()}")


def crear_gitignore():
    titulo("[3/6] Creando archivos necesarios para GitHub...")
    
    # .gitignore — archivos que NO subir
    gitignore = Path(".gitignore")
    gitignore.write_text("""# Base de datos local (se regenera en el servidor)
geoportal.db
*.db-journal

# Logs locales
logs/
*.log
*.csv

# Datos GeoJSON cacheados (se regeneran)
webapp/static/data/*.geojson

# Python
__pycache__/
*.py[cod]
*.pyo
.env
*.egg-info/
dist/
build/

# Anaconda
.conda/
envs/

# Windows
Thumbs.db
desktop.ini
""", encoding="utf-8")
    ok(".gitignore creado")

    # Procfile para Render.com
    procfile = Path("Procfile")
    procfile.write_text("web: python main.py\n", encoding="utf-8")
    ok("Procfile creado (necesario para Render.com)")

    # runtime.txt para especificar versión de Python
    runtime = Path("runtime.txt")
    runtime.write_text("python-3.11.0\n", encoding="utf-8")
    ok("runtime.txt creado")

    # render.yaml — configuración automática de Render
    render_yaml = Path("render.yaml")
    render_yaml.write_text(f"""services:
  - type: web
    name: {GITHUB_REPO}
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
""", encoding="utf-8")
    ok("render.yaml creado (despliegue automático en Render)")

    # README actualizado con el link público
    readme_extra = f"""
## 🌐 Ver en línea

Una vez desplegado en Render.com, el geoportal estará disponible en:
**https://{GITHUB_REPO}.onrender.com**

Cualquier persona en Ecuador (o el mundo) puede acceder desde su navegador,
sin necesidad de instalar nada.
"""
    readme_path = Path("README.md")
    if readme_path.exists():
        contenido = readme_path.read_text(encoding="utf-8")
        if "Ver en línea" not in contenido:
            readme_path.write_text(contenido + readme_extra, encoding="utf-8")
    ok("README.md actualizado")


def configurar_git_local():
    titulo("[4/6] Configurando Git e inicializando repositorio...")
    
    # Configurar identidad Git
    subprocess.run(["git", "config", "user.email", GITHUB_EMAIL], check=True)
    subprocess.run(["git", "config", "user.name",  GITHUB_NOMBRE], check=True)
    ok(f"Identidad Git configurada: {GITHUB_NOMBRE} <{GITHUB_EMAIL}>")

    # Inicializar repositorio si no existe
    git_dir = Path(".git")
    if not git_dir.exists():
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "branch", "-M", "main"], check=True)
        ok("Repositorio Git inicializado")
    else:
        ok("Repositorio Git ya existía")

    # Crear carpetas vacías necesarias con .gitkeep
    for carpeta in ["logs", "webapp/static/data", "webapp/static/img"]:
        p = Path(carpeta)
        p.mkdir(parents=True, exist_ok=True)
        gitkeep = p / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")

    # Agregar todos los archivos
    subprocess.run(["git", "add", "."], check=True)
    
    # Verificar si hay cambios para commitear
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    
    if result.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", "RiesgoEC v1.0 - Geoportal Riesgos Naturales Ecuador"],
            check=True
        )
        ok("Commit creado con todos los archivos del proyecto")
    else:
        ok("No hay cambios nuevos para commitear")


def subir_a_github():
    titulo("[5/6] Subiendo a GitHub...")
    
    repo_url = f"https://github.com/{GITHUB_USUARIO}/{GITHUB_REPO}.git"
    
    # Verificar si ya existe el remote
    result = subprocess.run(
        ["git", "remote", "-v"],
        capture_output=True, text=True
    )
    
    if "origin" in result.stdout:
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
        info("Remote 'origin' actualizado")
    else:
        subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
        info("Remote 'origin' añadido")

    print(f"""
  {C.YELLOW}IMPORTANTE — Pasos manuales necesarios:{C.RESET}
  
  1. Ve a: {C.BLUE}https://github.com/new{C.RESET}
  2. Repository name: {C.BOLD}{GITHUB_REPO}{C.RESET}
  3. Visibility: {C.BOLD}Public{C.RESET}
  4. NO marques "Add README" ni ninguna opción extra
  5. Clic en {C.BOLD}"Create repository"{C.RESET}
  
  Luego presiona ENTER aquí para continuar con el push...
""")
    input("  Presiona ENTER cuando hayas creado el repositorio en GitHub...")
    
    # Push al repositorio
    info("Subiendo archivos a GitHub (puede tardar 1-2 minutos)...")
    result = subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        ok(f"Código subido exitosamente a GitHub")
        ok(f"URL del repositorio: https://github.com/{GITHUB_USUARIO}/{GITHUB_REPO}")
    else:
        # Git puede pedir autenticación
        print(f"\n  {C.YELLOW}Git necesita autenticación. Sigue estos pasos:{C.RESET}")
        print(f"""
  Para autenticarte en GitHub desde la línea de comandos:
  
  1. Ve a: https://github.com/settings/tokens/new
  2. Note (nombre): geoportal-ec
  3. Expiration: No expiration
  4. Selecciona: repo (marcar todo el grupo)
  5. Clic "Generate token"
  6. COPIA el token (empieza con ghp_...)
  
  Luego ejecuta en Anaconda Prompt:
  
  {C.BOLD}git push -u origin main{C.RESET}
  
  Cuando pida usuario: pon tu usuario de GitHub
  Cuando pida contraseña: pega el TOKEN (no tu contraseña)
""")
        print(f"  Error original: {result.stderr[:300]}")


def mostrar_instrucciones_render():
    titulo("[6/6] Instrucciones para publicar en Render.com (GRATIS)...")
    
    print(f"""
  {C.GREEN}╔═══════════════════════════════════════════════════════════════╗
  ║   ULTIMO PASO — PUBLICAR EN INTERNET CON RENDER.COM          ║
  ╚═══════════════════════════════════════════════════════════════╝{C.RESET}

  Con esto, CUALQUIER persona en Ecuador podrá ver el geoportal
  desde su celular o computadora, SIN que tú tengas que tener
  nada ejecutando.

  {C.BOLD}Pasos:{C.RESET}

  1. Ve a: {C.BLUE}https://render.com{C.RESET}
  
  2. Clic en {C.BOLD}"Get Started for Free"{C.RESET}
     → Sign up with GitHub (usa tu cuenta de GitHub)

  3. En el dashboard, clic en {C.BOLD}"New +" → "Web Service"{C.RESET}

  4. Conecta tu repositorio: {C.BOLD}{GITHUB_REPO}{C.RESET}
     → Clic en "Connect"

  5. Configuración del servicio:
     ┌─────────────────────────────────────────────────┐
     │ Name:          {GITHUB_REPO:<33} │
     │ Region:        Oregon (US West)                 │
     │ Branch:        main                             │
     │ Build Command: pip install -r requirements.txt  │
     │ Start Command: python main.py                   │
     │ Plan:          Free                             │
     └─────────────────────────────────────────────────┘

  6. Clic en {C.BOLD}"Create Web Service"{C.RESET}

  7. Espera 3-5 minutos mientras Render instala todo.

  8. Tu geoportal estará disponible en:
     {C.GREEN}{C.BOLD}https://{GITHUB_REPO}.onrender.com{C.RESET}

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {C.YELLOW}NOTA PLAN GRATUITO:{C.RESET}
  El servidor se "duerme" si nadie lo visita en 15 min.
  El primer visitante espera ~30 segundos para que despierte.
  Para mantenerlo siempre activo: plan $7/mes en Render.
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {C.BOLD}Para actualizar el geoportal en el futuro:{C.RESET}
  
    conda activate geoportal_ec
    cd C:\\VARIOS\\geoportal_riesgos_ecuador
    git add .
    git commit -m "Actualización"
    git push
  
  Render detecta el push y redespliega automáticamente.
""")


def main():
    print(f"""
{C.BOLD}{C.BLUE}
  ╔════════════════════════════════════════════════════════════╗
  ║   PUBLICAR RIESGOEC EN INTERNET — GitHub + Render.com     ║
  ║   Para que cualquier persona en Ecuador pueda verlo        ║
  ╚════════════════════════════════════════════════════════════╝
{C.RESET}""")

    # Verificar que estamos en la carpeta correcta
    if not Path("main.py").exists():
        err("Este script debe ejecutarse desde la carpeta del geoportal")
        err("Ejecuta: cd C:\\VARIOS\\geoportal_riesgos_ecuador")
        err("Luego:   python subir_github.py")
        sys.exit(1)

    verificar_configuracion()
    verificar_git()
    crear_gitignore()
    configurar_git_local()
    subir_a_github()
    mostrar_instrucciones_render()

    print(f"\n{C.GREEN}{C.BOLD}  ¡Proceso completado! Tu geoportal estará en internet en minutos.{C.RESET}\n")


if __name__ == "__main__":
    main()
