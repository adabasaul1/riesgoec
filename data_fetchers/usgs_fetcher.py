"""
╔══════════════════════════════════════════════════════════════════╗
║  data_fetchers/usgs_fetcher.py  — VERSIÓN CORREGIDA             ║
║  Obtiene sismos en tiempo real desde la API USGS FDSN           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from geopy.distance import geodesic

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger("geoportal.usgs")

# URL directa con todos los parámetros de Ecuador hardcodeados para evitar bugs
USGS_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&minlatitude=-6.0"
    "&maxlatitude=3.0"
    "&minlongitude=-82.0"
    "&maxlongitude=-74.0"
    "&minmagnitude=1.5"
    "&limit=500"
    "&orderby=time"
)


def _color_mag(mag: float) -> str:
    if mag >= 6.0:   return "#8B0000"
    elif mag >= 5.0: return "#FF0000"
    elif mag >= 4.0: return "#FF6600"
    elif mag >= 3.0: return "#FFCC00"
    else:            return "#AAAAAA"


def _radio_mag(mag: float) -> float:
    return max(4, (mag ** 2) * 0.8)


def _classify_depth(d: float) -> str:
    if d < 35:    return "Superficial (<35 km)"
    elif d < 70:  return "Intermedio (35–70 km)"
    elif d < 300: return "Profundo (70–300 km)"
    else:         return "Muy profundo (>300 km)"


def _mercalli(mag: float, depth: float) -> str:
    m = mag - depth / 100.0
    if m >= 6.5:   return "X–XII (Extremo)"
    elif m >= 5.5: return "VIII–IX (Severo)"
    elif m >= 4.5: return "VI–VII (Fuerte)"
    elif m >= 3.5: return "IV–V (Moderado)"
    elif m >= 2.5: return "II–III (Débil)"
    else:          return "I (Imperceptible)"


def _nearest_city(lat: float, lon: float) -> dict:
    min_dist = float("inf")
    nearest  = {"nombre": "Ecuador", "dist_km": 0}
    for nombre, datos in cfg.CIUDADES_ECUADOR.items():
        d = geodesic((lat, lon), (datos["lat"], datos["lon"])).kilometers
        if d < min_dist:
            min_dist = d
            nearest  = {"nombre": nombre, "dist_km": round(d, 1)}
    return nearest


def fetch_earthquakes_ecuador(hours: int = 48) -> list[dict[str, Any]]:
    """
    Obtiene sismos de Ecuador desde USGS.
    Usa URL directa para evitar problemas de parámetros.
    """
    end_time   = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    url = (
        USGS_URL
        + f"&starttime={start_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        + f"&endtime={end_time.strftime('%Y-%m-%dT%H:%M:%S')}"
    )

    logger.info(f"Consultando USGS — últimas {hours}h — URL: {url[:120]}...")

    try:
        resp = requests.get(url, timeout=20, verify=True,
                            headers={"User-Agent": cfg.HTTP_HEADERS["User-Agent"]})
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        logger.error("USGS timeout — usando caché")
        return _load_cache(hours)
    except Exception as e:
        logger.error(f"USGS error: {e} — usando caché")
        return _load_cache(hours)

    features = data.get("features", [])
    logger.info(f"USGS retornó {len(features)} sismos.")

    sismos = []
    for f in features:
        try:
            p     = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [None, None, None])
            lon, lat, depth = coords[0], coords[1], (coords[2] or 0.0)
            mag      = p.get("mag") or 0.0
            time_ms  = p.get("time", 0)
            usgs_id  = f.get("id", "")

            if lat is None or lon is None:
                continue

            dt_utc = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
            dt_ec  = dt_utc - timedelta(hours=5)
            ciudad = _nearest_city(lat, lon)

            sismos.append({
                "id":                 usgs_id,
                "fuente":             "USGS",
                "lat":                round(lat, 4),
                "lon":                round(lon, 4),
                "profundidad_km":     round(depth, 1),
                "magnitud":           round(mag, 1),
                "tipo_magnitud":      p.get("magType", "Mw"),
                "lugar":              p.get("place", "Ecuador"),
                "fecha_utc":          dt_utc.isoformat(),
                "fecha_ec":           dt_ec.strftime("%d/%m/%Y %H:%M:%S"),
                "ciudad_cercana":     ciudad["nombre"],
                "dist_ciudad_km":     ciudad["dist_km"],
                "clasificacion_prof": _classify_depth(depth),
                "intensidad_mercalli":_mercalli(mag, depth),
                "color":              _color_mag(mag),
                "radio_mapa":         _radio_mag(mag),
                "url_detalle":        p.get("url", ""),
                "tsunami_flag":       int(p.get("tsunami", 0)),
            })
        except Exception as e:
            logger.warning(f"Error procesando sismo {f.get('id','')}: {e}")

    _save_cache(sismos)
    logger.info(f"Guardados {len(sismos)} sismos en SQLite.")
    return sismos


def _save_cache(sismos: list[dict]) -> None:
    if not sismos:
        return
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        cur  = conn.cursor()
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
        for s in sismos:
            cur.execute("""
                INSERT OR REPLACE INTO sismos
                (id,fuente,lat,lon,profundidad_km,magnitud,tipo_magnitud,
                 lugar,fecha_utc,fecha_ec,ciudad_cercana,dist_ciudad_km,
                 clasificacion_prof,intensidad_mercalli,color,radio_mapa,
                 url_detalle,tsunami_flag)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                s["id"],s["fuente"],s["lat"],s["lon"],s["profundidad_km"],
                s["magnitud"],s["tipo_magnitud"],s["lugar"],s["fecha_utc"],
                s["fecha_ec"],s["ciudad_cercana"],s["dist_ciudad_km"],
                s["clasificacion_prof"],s["intensidad_mercalli"],s["color"],
                s["radio_mapa"],s["url_detalle"],s["tsunami_flag"],
            ))
        # Limpiar más de 90 días
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        cur.execute("DELETE FROM sismos WHERE fecha_utc < ?", (cutoff,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")


def _load_cache(hours: int = 48) -> list[dict]:
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur.execute("SELECT * FROM sismos WHERE fecha_utc >= ? ORDER BY fecha_utc DESC", (cutoff,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        logger.info(f"Caché: {len(rows)} sismos")
        return rows
    except:
        return []


def get_recent_sismos_for_map(hours: int = 24) -> list[dict[str, Any]]:
    return fetch_earthquakes_ecuador(hours=hours)