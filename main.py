"""
╔══════════════════════════════════════════════════════════════════╗
║  main.py — GEOPORTAL RIESGOS NATURALES ECUADOR                  ║
║  Punto de entrada principal                                      ║
║                                                                  ║
║  CÓMO EJECUTAR:                                                  ║
║    En Spyder:        Abrir y presionar F5                       ║
║    En Anaconda Prompt: python main.py                           ║
║    En terminal:       python main.py                            ║
║                                                                  ║
║  El geoportal abrirá automáticamente en: http://localhost:5000  ║
╚══════════════════════════════════════════════════════════════════╝

Fundamentación científica:
  - Zhao et al. (2021) WebGIS real-time monitoring. NHESS Q1, IF:4.58
  - Pittore et al. (2022) Dynamic exposure assessment. Earthquake Spectra Q1
  - Protocolo CAP (ITU-T X.1303) para sistema de alertas
  - Principios FAIR para geodatos (Wilkinson et al. 2016, Scientific Data)
"""

import logging
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

# ─── Agregar raíz del proyecto al path ───
sys.path.insert(0, str(Path(__file__).parent))

import config as cfg

# ─────────────────────────────────────────────
# CONFIGURACIÓN DEL LOGGING
# ─────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """Configura logging con colores en consola y archivo rotativo."""
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Formato legible en español
    fmt_consola = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    fmt_archivo  = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"

    logger = logging.getLogger("geoportal")
    logger.setLevel(logging.DEBUG)

    # Handler consola
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt_consola, datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    # Handler archivo
    fh = logging.FileHandler(
        cfg.LOG_DIR / "geoportal.log",
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt_archivo, datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

    return logger


# ─────────────────────────────────────────────
# INICIALIZACIÓN DE LA BASE DE DATOS
# ─────────────────────────────────────────────

def init_database() -> None:
    """Crea las tablas SQLite si no existen."""
    conn = sqlite3.connect(cfg.DB_PATH)
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sismos (
            id TEXT PRIMARY KEY,
            fuente TEXT, lat REAL, lon REAL,
            profundidad_km REAL, magnitud REAL, tipo_magnitud TEXT,
            lugar TEXT, fecha_utc TEXT, fecha_ec TEXT,
            ciudad_cercana TEXT, dist_ciudad_km REAL,
            clasificacion_prof TEXT, intensidad_mercalli TEXT,
            color TEXT, radio_mapa REAL, url_detalle TEXT,
            tsunami_flag INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS volcanes (
            nombre TEXT PRIMARY KEY,
            lat REAL, lon REAL, gvp_code TEXT, elevacion_m REAL,
            nivel TEXT, descripcion TEXT, boletin_url TEXT,
            color TEXT, fecha_update TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id TEXT PRIMARY KEY,
            fuente TEXT, tipo TEXT, nivel TEXT, nivel_original TEXT,
            titulo TEXT, descripcion TEXT, afecta_ecuador INTEGER,
            fecha_utc TEXT, fecha_ec TEXT, url TEXT,
            activa INTEGER DEFAULT 1, color TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS infraestructura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, tipo TEXT, lat REAL, lon REAL, ciudad TEXT,
            provincia TEXT, contacto TEXT
        )
    """)

    # Índices para consultas frecuentes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sismos_fecha ON sismos(fecha_utc)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sismos_mag ON sismos(magnitud)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alertas_activas ON alertas(activa, tipo)")

    conn.commit()
    conn.close()
    logging.getLogger("geoportal.db").info("Base de datos inicializada correctamente.")


# ─────────────────────────────────────────────
# TAREAS PROGRAMADAS (FETCHERS)
# ─────────────────────────────────────────────

def job_usgs():
    """Job: Obtener sismos desde USGS (cada 2 minutos)."""
    try:
        from data_fetchers.usgs_fetcher import fetch_earthquakes_ecuador
        sismos = fetch_earthquakes_ecuador(hours=48)
        _evaluar_alertas_sismos(sismos)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job USGS falló: {e}")


def job_igepn():
    """Job: Obtener sismos y volcanes desde IGEPN (cada 5 minutos)."""
    try:
        from data_fetchers.igepn_fetcher import fetch_sismos_igepn, fetch_volcanes_igepn
        fetch_sismos_igepn()
        volcanes = fetch_volcanes_igepn()
        _evaluar_alertas_volcanes(volcanes)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job IGEPN falló: {e}")


def job_tsunami():
    """Job: Alertas de tsunami PTWC + GDACS (cada 5 minutos — CRÍTICO)."""
    try:
        from data_fetchers.tsunami_fetcher import fetch_tsunami_alerts
        from processors.alert_engine import evaluate_tsunami, dispatch_alerts
        alertas_raw = fetch_tsunami_alerts()
        alertas     = evaluate_tsunami(alertas_raw)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job Tsunami falló: {e}")


def job_geojson():
    """Job: Exportar capas GeoJSON para el mapa (cada 2 minutos)."""
    try:
        from processors.geojson_builder import export_all_layers
        export_all_layers()
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job GeoJSON falló: {e}")


def _evaluar_alertas_sismos(sismos):
    """Evalúa sismos y dispara alertas si corresponde."""
    try:
        from processors.alert_engine import evaluate_sismos, dispatch_alerts
        alertas = evaluate_sismos(sismos)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Evaluación alertas sismos falló: {e}")


def _evaluar_alertas_volcanes(volcanes):
    """Evalúa volcanes y dispara alertas si corresponde."""
    try:
        from processors.alert_engine import evaluate_volcanes, dispatch_alerts
        alertas = evaluate_volcanes(volcanes)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Evaluación alertas volcanes falló: {e}")


def initial_fetch_all():
    """Ejecuta todos los fetchers una vez al inicio para poblar la BD."""
    logger = logging.getLogger("geoportal.init")
    logger.info("Carga inicial de datos...")

    for job_fn, nombre in [
        (job_usgs,    "USGS sismos"),
        (job_igepn,   "IGEPN sismos/volcanes"),
        (job_tsunami, "Tsunami PTWC"),
        (job_geojson, "GeoJSON export"),
    ]:
        try:
            logger.info(f"  → Cargando {nombre}...")
            job_fn()
        except Exception as e:
            logger.warning(f"  ✗ {nombre} falló en carga inicial: {e} (continuando...)")

    logger.info("Carga inicial completada.")


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

def setup_scheduler() -> BackgroundScheduler:
    """Configura APScheduler con todos los jobs periódicos."""
    executors = {"default": ThreadPoolExecutor(max_workers=4)}
    scheduler = BackgroundScheduler(
        executors=executors,
        timezone="America/Guayaquil",  # UTC-5 Ecuador
    )

    # Sismos USGS — cada 2 minutos (más rápido)
    scheduler.add_job(job_usgs, "interval", minutes=2,
                      id="usgs", name="USGS Earthquakes", max_instances=1)

    # IGEPN — cada 5 minutos
    scheduler.add_job(job_igepn, "interval", minutes=5,
                      id="igepn", name="IGEPN Ecuador", max_instances=1)

    # Tsunami — cada 5 minutos (CRÍTICO)
    scheduler.add_job(job_tsunami, "interval", minutes=5,
                      id="tsunami", name="Tsunami PTWC", max_instances=1)

    # Exportar GeoJSON — cada 2 minutos
    scheduler.add_job(job_geojson, "interval", minutes=2,
                      id="geojson", name="GeoJSON Export", max_instances=1)

    return scheduler


# ─────────────────────────────────────────────
# SERVIDOR FLASK
# ─────────────────────────────────────────────

def run_flask():
    """Inicia Flask en hilo daemon."""
    from webapp.app import run_flask as _run
    _run()


# ─────────────────────────────────────────────
# BANNER DE INICIO
# ─────────────────────────────────────────────

def print_banner(logger):
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      🌎 GEOPORTAL RIESGOS NATURALES ECUADOR — RiesgoEC      ║
║         Versión 1.0 | Desarrollado en Python + Leaflet.js   ║
║                                                              ║
║  Fuentes de datos:                                           ║
║    • IGEPN (Instituto Geofísico EPN)                        ║
║    • USGS Earthquake Hazards Program                        ║
║    • PTWC Pacific Tsunami Warning Center (NOAA)             ║
║    • GDACS (ONU) | SGR Ecuador | INAMHI                     ║
║                                                              ║
║  Iniciando en: http://localhost:{cfg.FLASK_PORT}                     ║
║  Inicializando a las: {datetime.now().strftime('%H:%M:%S')} hora local         ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info("Geoportal Ecuador iniciando...")


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA PRINCIPAL
# ─────────────────────────────────────────────

def main():
    logger = setup_logging()
    print_banner(logger)

    # 1. Base de datos
    logger.info("Inicializando base de datos SQLite...")
    init_database()

    # 2. Carga inicial de datos
    initial_fetch_all()

    # 3. Scheduler de actualización automática
    logger.info("Iniciando scheduler de actualización automática...")
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info(f"Scheduler activo — {len(scheduler.get_jobs())} jobs programados.")

    # 4. Flask en hilo separado
    logger.info("Iniciando servidor web Flask...")
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)
    flask_thread.start()

    # 5. En la nube no se abre navegador
    url = f"http://localhost:{cfg.FLASK_PORT}"
    logger.info(f"Geoportal disponible en: {url}")

    # 6. Mantener el proceso vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Deteniendo geoportal...")
        scheduler.shutdown(wait=False)
        logger.info("Geoportal detenido. ¡Hasta pronto!")
        sys.exit(0)


if __name__ == "__main__":
    main()
