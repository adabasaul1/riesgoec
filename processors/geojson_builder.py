"""
╔══════════════════════════════════════════════════════════════════╗
║  processors/geojson_builder.py                                  ║
║  Genera capas GeoJSON para Leaflet desde SQLite                 ║
║                                                                  ║
║  Estándar: GeoJSON RFC 7946 — IETF                              ║
║  OGC: Simple Features Access ISO 19125                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger("geoportal.geojson")

DATA_DIR = cfg.DATA_DIR


def export_all_layers() -> None:
    """Exporta todas las capas GeoJSON al directorio estático de Flask."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    export_sismos_geojson()
    export_volcanes_geojson()
    export_alertas_geojson()
    export_infraestructura_geojson()
    logger.info("Todas las capas GeoJSON exportadas correctamente.")


def export_sismos_geojson(hours: int = 168) -> None:
    """
    Exporta capa de sismos. Por defecto últimos 7 días (168h).
    Se generan 2 archivos: sismos_24h.geojson y sismos_7d.geojson
    """
    for ventana, nombre_archivo in [(24, "sismos_24h"), (168, "sismos_7d")]:
        sismos = _query_sismos(hours=ventana)
        geojson = _build_point_featurecollection(
            items=sismos,
            props_fn=_sismo_props,
        )
        _write_geojson(geojson, f"{nombre_archivo}.geojson")
        logger.debug(f"Exportados {len(sismos)} sismos → {nombre_archivo}.geojson")


def export_volcanes_geojson() -> None:
    """Exporta capa de volcanes activos Ecuador."""
    volcanes = _query_volcanes()
    geojson  = _build_point_featurecollection(
        items=volcanes,
        props_fn=_volcán_props,
    )
    _write_geojson(geojson, "volcanes.geojson")
    logger.debug(f"Exportados {len(volcanes)} volcanes → volcanes.geojson")


def export_alertas_geojson() -> None:
    """Exporta alertas activas (tsunami, enjambres, etc.)."""
    alertas = _query_alertas_activas()
    # Las alertas no son puntos sino se muestran en el banner; exportar de todas formas
    geojson = {"type": "FeatureCollection", "features": [], "metadata": {
        "count": len(alertas),
        "has_tsunami": any(a.get("tipo") == "TSUNAMI" for a in alertas),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }}
    for a in alertas:
        geojson["features"].append({
            "type": "Feature",
            "properties": a,
            "geometry": None,  # alertas globales sin geometría puntual
        })
    _write_geojson(geojson, "alertas.geojson")


def export_infraestructura_geojson() -> None:
    """
    Exporta puntos de infraestructura crítica.
    Si hay datos de OSM en SQLite los usa; sino genera desde config.
    """
    infra = _query_infraestructura()
    if not infra:
        infra = _build_default_infrastructure()

    geojson = _build_point_featurecollection(
        items=infra,
        props_fn=lambda x: x,
    )
    _write_geojson(geojson, "infraestructura.geojson")


# ─────────────────────────────────────────────
# BUILDERS DE FEATURES
# ─────────────────────────────────────────────

def _build_point_featurecollection(items: list[dict], props_fn) -> dict:
    """Construye un FeatureCollection GeoJSON de puntos."""
    features = []
    for item in items:
        lat = item.get("lat")
        lon = item.get("lon")
        if lat is None or lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [round(lon, 6), round(lat, 6)],
            },
            "properties": props_fn(item),
        })

    return {
        "type":     "FeatureCollection",
        "features": features,
        "metadata": {
            "count":        len(features),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "crs":          "EPSG:4326",
            "source":       "RiesgoEC Geoportal",
        },
    }


def _sismo_props(s: dict) -> dict:
    """Propiedades de estilo y popup para un sismo en Leaflet."""
    return {
        "id":                  s.get("id"),
        "fuente":              s.get("fuente"),
        "magnitud":            s.get("magnitud"),
        "tipo_magnitud":       s.get("tipo_magnitud", "Mw"),
        "profundidad_km":      s.get("profundidad_km"),
        "clasificacion_prof":  s.get("clasificacion_prof", ""),
        "lugar":               s.get("lugar", "Ecuador"),
        "fecha_utc":           s.get("fecha_utc"),
        "fecha_ec":            s.get("fecha_ec"),
        "ciudad_cercana":      s.get("ciudad_cercana", ""),
        "dist_ciudad_km":      s.get("dist_ciudad_km", 0),
        "intensidad_mercalli": s.get("intensidad_mercalli", ""),
        "color":               s.get("color", "#AAAAAA"),
        "radio_mapa":          s.get("radio_mapa", 5),
        "url_detalle":         s.get("url_detalle", ""),
        "tsunami_flag":        s.get("tsunami_flag", 0),
        # Texto para compartir
        "share_text":          (
            f"Sismo M{s.get('magnitud')} a {s.get('dist_ciudad_km')}km de "
            f"{s.get('ciudad_cercana')} | {s.get('fecha_ec')} (EC) | "
            f"riesgoec.com #SismoEcuador #IGEPN"
        ),
    }


def _volcán_props(v: dict) -> dict:
    """Propiedades de estilo y popup para un volcán en Leaflet."""
    return {
        "nombre":       v.get("nombre"),
        "gvp_code":     v.get("gvp_code"),
        "elevacion_m":  v.get("elevacion_m"),
        "nivel":        v.get("nivel", "SIN_DATO"),
        "descripcion":  v.get("descripcion", ""),
        "boletin_url":  v.get("boletin_url", ""),
        "color":        v.get("color", "#888888"),
        "fecha_update": v.get("fecha_update", ""),
        "fuente":       "IGEPN",
    }


def _build_default_infrastructure() -> list[dict]:
    """Lista básica de infraestructura crítica cuando OSM no está disponible."""
    return [
        {"nombre": "Hospital Eugenio Espejo", "tipo": "hospital",  "lat": -0.2039, "lon": -78.4935, "ciudad": "Quito"},
        {"nombre": "Hospital Abel Gilbert",   "tipo": "hospital",  "lat": -2.1521, "lon": -79.9007, "ciudad": "Guayaquil"},
        {"nombre": "Albergue SGR Norte",      "tipo": "albergue",  "lat": -0.1500, "lon": -78.4800, "ciudad": "Quito"},
        {"nombre": "Estación IGEPN Quito",    "tipo": "estacion",  "lat": -0.2295, "lon": -78.5243, "ciudad": "Quito"},
        {"nombre": "ECU911 Nacional",         "tipo": "emergencia","lat": -0.2270, "lon": -78.5130, "ciudad": "Quito"},
    ]


# ─────────────────────────────────────────────
# QUERIES SQLITE
# ─────────────────────────────────────────────

def _query_sismos(hours: int = 24) -> list[dict]:
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur.execute(
            "SELECT * FROM sismos WHERE fecha_utc >= ? ORDER BY fecha_utc DESC LIMIT 500",
            (cutoff,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def _query_volcanes() -> list[dict]:
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM volcanes ORDER BY nombre")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows if rows else list(cfg.VOLCANES_ECUADOR.values())
    except sqlite3.Error:
        return []


def _query_alertas_activas() -> list[dict]:
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM alertas WHERE activa = 1 ORDER BY fecha_utc DESC LIMIT 20"
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def _query_infraestructura() -> list[dict]:
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute("SELECT * FROM infraestructura LIMIT 500")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def _write_geojson(data: dict, filename: str) -> None:
    """Escribe el GeoJSON en el directorio estático con encoding UTF-8."""
    path = DATA_DIR / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
    except OSError as e:
        logger.error(f"Error escribiendo {filename}: {e}")


def get_stats() -> dict[str, Any]:
    """Retorna estadísticas para el panel derecho del geoportal."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        cur  = conn.cursor()

        # Sismos últimas 24h
        cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cur.execute("SELECT COUNT(*), MAX(magnitud) FROM sismos WHERE fecha_utc >= ?", (cutoff_24h,))
        row = cur.fetchone()
        count_24h = row[0] or 0
        max_mag   = row[1] or 0.0

        # Sismos por hora (últimas 24h para el gráfico)
        cur.execute("""
            SELECT strftime('%H', fecha_utc) as hora, COUNT(*) as cnt
            FROM sismos WHERE fecha_utc >= ?
            GROUP BY hora ORDER BY hora
        """, (cutoff_24h,))
        sismos_por_hora = {r[0]: r[1] for r in cur.fetchall()}

        # Volcán con mayor nivel de alerta
        cur.execute("""
            SELECT nombre, nivel FROM volcanes
            WHERE nivel IN ('ROJO','NARANJA','AMARILLO')
            ORDER BY CASE nivel
                WHEN 'ROJO'    THEN 1
                WHEN 'NARANJA' THEN 2
                WHEN 'AMARILLO'THEN 3
            END LIMIT 1
        """)
        volcán_activo = cur.fetchone()

        # Alertas tsunami activas
        cur.execute(
            "SELECT COUNT(*) FROM alertas WHERE tipo='TSUNAMI' AND activa=1 AND nivel='ROJO'"
        )
        tsunami_activo = cur.fetchone()[0] > 0

        conn.close()
        return {
            "sismos_24h":    count_24h,
            "max_magnitud":  round(max_mag, 1),
            "sismos_x_hora": sismos_por_hora,
            "volcán_activo": {"nombre": volcán_activo[0], "nivel": volcán_activo[1]} if volcán_activo else None,
            "tsunami_activo":tsunami_activo,
            "ultima_update": datetime.now(timezone.utc).isoformat(),
        }
    except sqlite3.Error as e:
        logger.error(f"Error calculando estadísticas: {e}")
        return {"sismos_24h": 0, "max_magnitud": 0.0, "ultima_update": "N/D"}
