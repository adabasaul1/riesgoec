"""
GEOPORTAL RIESGOS NATURALES ECUADOR - main.py
Ejecutar: python main.py
"""

import logging
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg


def setup_logging():
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    logger = logging.getLogger("geoportal")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    try:
        fh = logging.FileHandler(cfg.LOG_DIR / "geoportal.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


def init_database():
    conn = sqlite3.connect(cfg.DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sismos (
            id TEXT PRIMARY KEY, fuente TEXT, lat REAL, lon REAL,
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
            nombre TEXT PRIMARY KEY, lat REAL, lon REAL,
            gvp_code TEXT, elevacion_m REAL, nivel TEXT,
            descripcion TEXT, boletin_url TEXT, color TEXT,
            fecha_update TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id TEXT PRIMARY KEY, fuente TEXT, tipo TEXT,
            nivel TEXT, nivel_original TEXT, titulo TEXT,
            descripcion TEXT, afecta_ecuador INTEGER,
            fecha_utc TEXT, fecha_ec TEXT, url TEXT,
            activa INTEGER DEFAULT 1, color TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS infraestructura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, tipo TEXT, lat REAL, lon REAL,
            ciudad TEXT, provincia TEXT, contacto TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sismos_fecha ON sismos(fecha_utc)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sismos_mag ON sismos(magnitud)")
    conn.commit()
    conn.close()
    logging.getLogger("geoportal.db").info("Base de datos inicializada.")


def job_usgs():
    try:
        from data_fetchers.usgs_fetcher import fetch_earthquakes_ecuador
        from processors.alert_engine import evaluate_sismos, dispatch_alerts
        sismos = fetch_earthquakes_ecuador(hours=48)
        alertas = evaluate_sismos(sismos)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job USGS: {e}")


def job_igepn():
    try:
        from data_fetchers.igepn_fetcher import fetch_sismos_igepn, fetch_volcanes_igepn
        from processors.alert_engine import evaluate_volcanes, dispatch_alerts
        fetch_sismos_igepn()
        volcanes = fetch_volcanes_igepn()
        alertas = evaluate_volcanes(volcanes)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job IGEPN: {e}")


def job_tsunami():
    try:
        from data_fetchers.tsunami_fetcher import fetch_tsunami_alerts
        from processors.alert_engine import evaluate_tsunami, dispatch_alerts
        alertas_raw = fetch_tsunami_alerts()
        alertas = evaluate_tsunami(alertas_raw)
        if alertas:
            dispatch_alerts(alertas)
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job Tsunami: {e}")


def job_geojson():
    try:
        from processors.geojson_builder import export_all_layers
        export_all_layers()
    except Exception as e:
        logging.getLogger("geoportal.jobs").error(f"Job GeoJSON: {e}")


def initial_fetch_all():
    logger = logging.getLogger("geoportal.init")
    logger.info("Carga inicial de datos...")
    for fn, nombre in [(job_usgs, "USGS"), (job_igepn, "IGEPN"),
                       (job_tsunami, "Tsunami"), (job_geojson, "GeoJSON")]:
        try:
            logger.info(f"  Cargando {nombre}...")
            fn()
        except Exception as e:
            logger.warning(f"  {nombre} fallo: {e}")
    logger.info("Carga inicial completada.")


def setup_scheduler():
    scheduler = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=4)},
        timezone="America/Guayaquil",
    )
    scheduler.add_job(job_usgs,    "interval", minutes=2,  id="usgs",    max_instances=1)
    scheduler.add_job(job_igepn,   "interval", minutes=5,  id="igepn",   max_instances=1)
    scheduler.add_job(job_tsunami, "interval", minutes=5,  id="tsunami", max_instances=1)
    scheduler.add_job(job_geojson, "interval", minutes=2,  id="geojson", max_instances=1)
    return scheduler


def main():
    logger = setup_logging()

    print("""
    ================================================
      GEOPORTAL RIESGOS NATURALES ECUADOR - RiesgoEC
      Iniciando servidor...
    ================================================
    """)

    logger.info("Inicializando base de datos...")
    init_database()

    logger.info("Cargando datos iniciales...")
    initial_fetch_all()

    logger.info("Iniciando scheduler...")
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info(f"Scheduler activo - {len(scheduler.get_jobs())} jobs.")

    # Puerto: usar variable PORT de Render, o 5000 por defecto local
    port = int(os.environ.get("PORT", cfg.FLASK_PORT))
    logger.info(f"Iniciando Flask en puerto {port}...")

    from webapp.app import app
    logger.info(f"Servidor disponible en http://0.0.0.0:{port}")

    try:
        # Usar threaded=True y el puerto correcto
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        logger.info("Deteniendo geoportal...")
        scheduler.shutdown(wait=False)
        sys.exit(0)


if __name__ == "__main__":
    main()