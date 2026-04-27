"""
webapp/app.py - Servidor Flask corregido
Fix: API sismos historicos + capas CONALI + puerto Render
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from processors.geojson_builder import get_stats
from data_fetchers.tsunami_fetcher import is_tsunami_active

logger = logging.getLogger("geoportal.flask")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.config["SECRET_KEY"] = cfg.SECRET_KEY
CORS(app)


@app.route("/")
def index():
    return render_template("index.html", mapbox_token=cfg.MAPBOX_TOKEN)


@app.route("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://riesgoec.onrender.com/</loc><changefreq>always</changefreq><priority>1.0</priority></url>
</urlset>"""
    return app.response_class(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nAllow: /\nSitemap: https://riesgoec.onrender.com/sitemap.xml",
        mimetype="text/plain"
    )


# ─── API SISMOS — CORREGIDA ───────────────────────────────────
@app.route("/api/sismos")
def api_sismos():
    """
    Retorna sismos en formato GeoJSON.
    hours=999999 significa "todos los históricos sin límite de fecha"
    """
    hours   = int(request.args.get("hours", 24))
    min_mag = float(request.args.get("min_mag", 2.5))
    hours   = max(1, min(hours, 999999))

    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()

        # FIX: si hours >= 999999, no filtrar por fecha (traer TODO el histórico)
        if hours >= 999999:
            cur.execute("""
                SELECT * FROM sismos
                WHERE magnitud >= ?
                ORDER BY fecha_utc DESC
                LIMIT 5000
            """, (min_mag,))
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            cur.execute("""
                SELECT * FROM sismos
                WHERE fecha_utc >= ? AND magnitud >= ?
                ORDER BY fecha_utc DESC
                LIMIT 2000
            """, (cutoff, min_mag))

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        features = []
        for s in rows:
            if s.get("lat") is None or s.get("lon") is None:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [s["lon"], s["lat"]]
                },
                "properties": {k: v for k, v in s.items() if k not in ("lat", "lon")},
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
        return jsonify({"error": str(e), "features": [], "type": "FeatureCollection",
                        "metadata": {"count": 0}}), 500


# ─── API VOLCANES ─────────────────────────────────────────────
@app.route("/api/volcanes")
def api_volcanes():
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute("SELECT * FROM volcanes ORDER BY nombre")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not rows:
            rows = [
                {"nombre": k, "lat": v["lat"], "lon": v["lon"],
                 "nivel": "SIN_DATO", "color": "#888888",
                 "elevacion_m": v["elev"], "gvp_code": v["gvp"],
                 "boletin_url": cfg.IGEPN["informes"]}
                for k, v in cfg.VOLCANES_ECUADOR.items()
            ]

        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]},
                "properties": {k: val for k, val in v.items() if k not in ("lat", "lon")},
            }
            for v in rows if v.get("lat") and v.get("lon")
        ]
        return jsonify({"type": "FeatureCollection", "features": features})

    except Exception as e:
        return jsonify({"error": str(e), "features": []}), 500


# ─── API ALERTAS ──────────────────────────────────────────────
@app.route("/api/alertas")
def api_alertas():
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute("SELECT * FROM alertas WHERE activa=1 ORDER BY fecha_utc DESC LIMIT 20")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({
            "alertas":       rows,
            "tsunami_activo": is_tsunami_active(),
            "count":          len(rows),
        })
    except Exception:
        return jsonify({"alertas": [], "tsunami_activo": False, "count": 0})


# ─── API ESTADÍSTICAS ─────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    try:
        return jsonify(get_stats())
    except Exception as e:
        return jsonify({"sismos_24h": 0, "max_magnitud": 0.0, "error": str(e)})


# ─── API ¿TEMBLANDO AHORA? ────────────────────────────────────
@app.route("/api/temblando_ahora")
def api_temblando_ahora():
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
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
                f"Sí — Sismo M{top['magnitud']} a {top.get('dist_ciudad_km','?')}km de "
                f"{top.get('ciudad_cercana','Ecuador')} hace menos de 30 minutos."
            ),
            "sismos": rows,
        })
    except Exception as e:
        return jsonify({"temblando": False, "error": str(e)})


# ─── API ZONA DE RIESGO ───────────────────────────────────────
@app.route("/api/zona_riesgo")
def api_zona_riesgo():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"error": "Parámetros lat y lon requeridos"}), 400

    try:
        from geopy.distance import geodesic
    except ImportError:
        return jsonify({"error": "geopy no instalado"}), 500

    riesgo_volcanico = "BAJO"
    volcán_cercano   = None
    dist_min = float("inf")

    for nombre, datos in cfg.VOLCANES_ECUADOR.items():
        dist = geodesic((lat, lon), (datos["lat"], datos["lon"])).kilometers
        if dist < dist_min:
            dist_min = dist
            volcán_cercano = nombre

    if dist_min < 30:   riesgo_volcanico = "ALTO"
    elif dist_min < 100:riesgo_volcanico = "MEDIO"

    riesgo_sismico  = "ALTO" if (-81 <= lon <= -75 and -5 <= lat <= 2) else "MEDIO"
    riesgo_tsunami  = "ALTO" if lon < -78.5 else "BAJO"

    return jsonify({
        "lat": lat, "lon": lon,
        "riesgo_sismico":   riesgo_sismico,
        "riesgo_volcanico": riesgo_volcanico,
        "volcan_cercano":   volcán_cercano,
        "dist_volcan_km":   round(dist_min, 1),
        "riesgo_tsunami":   riesgo_tsunami,
        "recomendaciones": {
            "sismico":  "Identifica zonas seguras. Ten kit de emergencias.",
            "volcanico": f"Monitorea boletines IGEPN sobre {volcán_cercano}.",
            "tsunami":  "Conoce rutas de evacuación a zonas altas." if riesgo_tsunami == "ALTO" else "Zona interior — riesgo de tsunami bajo.",
        },
    })


# ─── API HISTÓRICO ────────────────────────────────────────────
@app.route("/api/historico")
def api_historico():
    """Sismos históricos con filtro por año y magnitud."""
    min_mag  = float(request.args.get("min_mag", 4.0))
    year_from = int(request.args.get("year_from", 1960))
    year_to   = int(request.args.get("year_to",   2025))

    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute("""
            SELECT * FROM sismos
            WHERE magnitud >= ?
              AND substr(fecha_utc, 1, 4) >= ?
              AND substr(fecha_utc, 1, 4) <= ?
            ORDER BY magnitud DESC
            LIMIT 2000
        """, (min_mag, str(year_from), str(year_to)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"sismos": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e), "sismos": [], "count": 0}), 500


# ─── ARCHIVOS ESTÁTICOS / GEOJSON ────────────────────────────
@app.route("/data/<path:filename>")
def serve_data(filename):
    """Sirve GeoJSON de CONALI y capas del mapa."""
    return send_from_directory(cfg.DATA_DIR, filename)


# ─── HEALTH CHECK ─────────────────────────────────────────────
@app.route("/api/health")
def health():
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sismos")
        count = cur.fetchone()[0]
        conn.close()
    except Exception:
        count = 0

    return jsonify({
        "status":       "ok",
        "version":      "1.0",
        "sismos_en_db": count,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    })


def run_flask():
    port = int(os.environ.get("PORT", cfg.FLASK_PORT))
    logger.info(f"Flask iniciando en puerto {port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )