"""
╔══════════════════════════════════════════════════════════════════╗
║  webapp/app.py                                                  ║
║  Servidor Flask — API REST + Servicio de archivos estáticos     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from processors.geojson_builder import get_stats, export_all_layers
from data_fetchers.tsunami_fetcher import is_tsunami_active, get_active_tsunami_alerts

logger = logging.getLogger("geoportal.flask")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.config["SECRET_KEY"] = cfg.SECRET_KEY
CORS(app)

# ─────────────────────────────────────────────
# RUTAS PRINCIPALES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    """Página principal del geoportal."""
    return render_template("index.html", mapbox_token=cfg.MAPBOX_TOKEN)


@app.route("/sitemap.xml")
def sitemap():
    """Sitemap SEO auto-generado."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://riesgoec.com/</loc><changefreq>always</changefreq><priority>1.0</priority></url>
  <url><loc>https://riesgoec.com/api/sismos</loc><changefreq>always</changefreq><priority>0.8</priority></url>
</urlset>"""
    return app.response_class(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nAllow: /\nSitemap: https://riesgoec.com/sitemap.xml",
        mimetype="text/plain"
    )


# ─────────────────────────────────────────────
# API REST — DATOS DEL MAPA
# ─────────────────────────────────────────────

@app.route("/api/sismos")
def api_sismos():
    """
    Retorna sismos en formato GeoJSON.
    Query params:
        hours: ventana temporal (default: 24)
        min_mag: magnitud mínima (default: 2.5)
    """
    hours   = int(request.args.get("hours", 24))
    min_mag = float(request.args.get("min_mag", 2.5))
    hours   = max(1, min(hours, 720))  # entre 1h y 30 días

    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        cur.execute("""
            SELECT * FROM sismos
            WHERE fecha_utc >= ? AND magnitud >= ?
            ORDER BY fecha_utc DESC LIMIT 500
        """, (cutoff, min_mag))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        features = []
        for s in rows:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                "properties": {k: v for k, v in s.items() if k not in ("lat","lon")},
            })

        return jsonify({
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count":    len(features),
                "hours":    hours,
                "min_mag":  min_mag,
                "generated": datetime.now(timezone.utc).isoformat(),
            }
        })
    except Exception as e:
        logger.error(f"API /sismos error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/volcanes")
def api_volcanes():
    """Retorna volcanes activos de Ecuador con nivel de alerta IGEPN."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM volcanes ORDER BY nombre")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not rows:
            # Fallback: datos base del config
            rows = [
                {**{"nombre": k, "lat": v["lat"], "lon": v["lon"],
                    "nivel": "SIN_DATO", "color": "#888888"}, **v}
                for k, v in cfg.VOLCANES_ECUADOR.items()
            ]

        features = []
        for v in rows:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]},
                "properties": {k: val for k, val in v.items() if k not in ("lat","lon")},
            })
        return jsonify({"type": "FeatureCollection", "features": features})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alertas")
def api_alertas():
    """Retorna alertas activas (tsunami, volcanes, enjambres)."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM alertas WHERE activa=1 ORDER BY fecha_utc DESC LIMIT 20")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({
            "alertas":       rows,
            "tsunami_activo":is_tsunami_active(),
            "count":         len(rows),
        })
    except Exception as e:
        return jsonify({"alertas": [], "tsunami_activo": False, "count": 0})


@app.route("/api/stats")
def api_stats():
    """Estadísticas para el panel derecho del geoportal."""
    return jsonify(get_stats())


@app.route("/api/temblando_ahora")
def api_temblando_ahora():
    """
    Feature viral: ¿Está temblando ahora?
    Consulta sismos de los últimos 30 minutos.
    Query params: lat, lon (opcionales — para personalizar respuesta)
    """
    lat_user = request.args.get("lat", type=float)
    lon_user = request.args.get("lon", type=float)

    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        cur.execute("""
            SELECT * FROM sismos WHERE fecha_utc >= ?
            ORDER BY magnitud DESC LIMIT 5
        """, (cutoff,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not rows:
            return jsonify({
                "temblando": False,
                "mensaje":   "No hay sismos registrados en los últimos 30 minutos en Ecuador.",
                "sismos":    [],
            })

        top = rows[0]
        return jsonify({
            "temblando": True,
            "mensaje": (
                f"Sí — Sismo M{top['magnitud']} a {top['dist_ciudad_km']}km de "
                f"{top['ciudad_cercana']} hace menos de 30 minutos."
            ),
            "sismos": rows,
        })
    except Exception as e:
        return jsonify({"temblando": False, "error": str(e)})


@app.route("/api/zona_riesgo")
def api_zona_riesgo():
    """
    Calcula el nivel de riesgo para una coordenada dada.
    Query params: lat, lon
    """
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"error": "Parámetros lat y lon requeridos"}), 400

    # Calcular distancias a volcanes
    riesgo_volcanico = "BAJO"
    volcán_cercano   = None
    dist_min_volcán  = float("inf")
    for nombre, datos in cfg.VOLCANES_ECUADOR.items():
        from geopy.distance import geodesic
        dist = geodesic((lat, lon), (datos["lat"], datos["lon"])).kilometers
        if dist < dist_min_volcán:
            dist_min_volcán = dist
            volcán_cercano  = nombre
    if dist_min_volcán < 30:
        riesgo_volcanico = "ALTO"
    elif dist_min_volcán < 100:
        riesgo_volcanico = "MEDIO"

    # Riesgo sísmico (simplificado — basado en sismicidad histórica de zona)
    # Ecuador tiene alta sismicidad en toda su extensión
    riesgo_sísmico = "ALTO" if (-81 <= lon <= -75 and -5 <= lat <= 2) else "MEDIO"

    # Riesgo de tsunami (solo costa: lon < -78)
    riesgo_tsunami = "ALTO" if lon < -78.5 else "BAJO"

    return jsonify({
        "lat": lat,
        "lon": lon,
        "riesgo_sísmico":   riesgo_sísmico,
        "riesgo_volcánico": riesgo_volcanico,
        "volcán_cercano":   volcán_cercano,
        "dist_volcán_km":   round(dist_min_volcán, 1),
        "riesgo_tsunami":   riesgo_tsunami,
        "recomendaciones": {
            "sismico":  "Identifica zonas seguras en tu hogar. Kit de emergencias.",
            "volcánico":f"Monitorea boletines IGEPN sobre {volcán_cercano}.",
            "tsunami":  "Conoce las rutas de evacuación hacia zonas altas." if riesgo_tsunami == "ALTO" else "Zona interior — riesgo de tsunami bajo.",
        },
    })


@app.route("/api/historico")
def api_historico():
    """
    Sismos históricos Ecuador desde USGS (desde el año solicitado).
    Query params: year (default: 2000), min_mag (default: 4.0)
    """
    min_mag = float(request.args.get("min_mag", 4.0))
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM sismos
            WHERE magnitud >= ?
            ORDER BY magnitud DESC LIMIT 200
        """, (min_mag,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"sismos": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e), "sismos": []}), 500


# ─────────────────────────────────────────────
# ARCHIVOS GEOJSON ESTÁTICOS
# ─────────────────────────────────────────────

@app.route("/data/<path:filename>")
def serve_data(filename):
    """Sirve archivos GeoJSON cacheados desde el directorio de datos."""
    return send_from_directory(cfg.DATA_DIR, filename)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.route("/api/health")
def health():
    """Health check del servidor."""
    return jsonify({
        "status": "ok",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def run_flask():
    """Inicia el servidor Flask."""
    app.run(
        host=cfg.FLASK_HOST,
        port=cfg.FLASK_PORT,
        debug=False,
        use_reloader=False,  # Reloader interfiere con APScheduler en threads
    )
