"""
╔══════════════════════════════════════════════════════════════════╗
║  GEOPORTAL RIESGOS NATURALES ECUADOR — config.py               ║
║  Configuración global, URLs de APIs y parámetros del sistema    ║
║                                                                  ║
║  INSTRUCCIONES:                                                  ║
║  1. No modificar las URLs de APIs (son endpoints oficiales)     ║
║  2. Editar solo la sección "CONFIGURACIÓN PERSONAL" más abajo   ║
║  3. Las API_KEYS opcionales mejoran la experiencia pero no son  ║
║     obligatorias para el funcionamiento básico                  ║
╚══════════════════════════════════════════════════════════════════╝

Fundamentación científica:
  - Estándares OGC WMS 1.3.0 / WFS 2.0 (Vretanos, 2010)
  - Principios FAIR para geodatos abiertos (Wilkinson et al., 2016)
  - Protocolo CAP (Common Alerting Protocol — ITU-T X.1303)
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# RUTAS DEL PROYECTO
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "webapp" / "static" / "data"
LOG_DIR  = BASE_DIR / "logs"
DB_PATH  = BASE_DIR / "geoportal.db"

# ─────────────────────────────────────────────
# SERVIDOR FLASK
# ─────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False
SECRET_KEY  = os.environ.get("SECRET_KEY", "riesgoec-secret-2026")

# ─────────────────────────────────────────────
# CONFIGURACIÓN PERSONAL (EDITAR AQUÍ)
# ─────────────────────────────────────────────
NASA_FIRMS_KEY     = os.environ.get("NASA_FIRMS_KEY", "")      # firms.modaps.eosdis.nasa.gov
MAPBOX_TOKEN       = os.environ.get("MAPBOX_TOKEN", "")        # mapbox.com (tier gratis)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # @BotFather en Telegram
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
EMAIL_ALERT_TO     = os.environ.get("EMAIL_ALERT_TO", "")      # tu@gmail.com
EMAIL_SMTP_USER    = os.environ.get("EMAIL_SMTP_USER", "")
EMAIL_SMTP_PASS    = os.environ.get("EMAIL_SMTP_PASS", "")     # contraseña de app Gmail

# ─────────────────────────────────────────────
# BBOX ECUADOR (WGS84)
# ─────────────────────────────────────────────
ECUADOR_BBOX = {
    "min_lat": -5.0,
    "max_lat":  2.0,
    "min_lon": -81.0,
    "max_lon": -75.0,
}
ECUADOR_CENTER = [-1.8312, -78.1834]  # Centro geográfico de Ecuador

# Ciudades principales para cálculo de distancias
CIUDADES_ECUADOR = {
    "Quito":       {"lat": -0.2295, "lon": -78.5243, "pop": 2700000},
    "Guayaquil":   {"lat": -2.1894, "lon": -79.8891, "pop": 3100000},
    "Cuenca":      {"lat": -2.9001, "lon": -79.0059, "pop": 636000},
    "Ambato":      {"lat": -1.2491, "lon": -78.6167, "pop": 400000},
    "Portoviejo":  {"lat": -1.0546, "lon": -80.4541, "pop": 300000},
    "Manta":       {"lat": -0.9677, "lon": -80.7089, "pop": 270000},
    "Loja":        {"lat": -3.9931, "lon": -79.2042, "pop": 215000},
    "Esmeraldas":  {"lat":  0.9592, "lon": -79.6536, "pop": 200000},
    "Riobamba":    {"lat": -1.6635, "lon": -78.6540, "pop": 196000},
    "Ibarra":      {"lat":  0.3517, "lon": -78.1220, "pop": 181000},
    "Santo Domingo": {"lat": -0.2520, "lon": -79.1720, "pop": 450000},
    "Macas":       {"lat": -2.3035, "lon": -78.1148, "pop": 22000},
}

# Volcanes activos Ecuador con coordenadas y código GVP
VOLCANES_ECUADOR = {
    "Cotopaxi":          {"lat": -0.6770, "lon": -78.4360, "gvp": "352050", "elev": 5897},
    "Tungurahua":        {"lat": -1.4670, "lon": -78.4420, "gvp": "352080", "elev": 5023},
    "Sangay":            {"lat": -2.0050, "lon": -78.3410, "gvp": "352090", "elev": 5230},
    "Guagua Pichincha":  {"lat": -0.1710, "lon": -78.5980, "gvp": "352020", "elev": 4784},
    "Reventador":        {"lat": -0.0770, "lon": -77.6560, "gvp": "352010", "elev": 3562},
    "Cayambe":           {"lat":  0.0290, "lon": -77.9860, "gvp": "352006", "elev": 5790},
    "Antisana":          {"lat": -0.4730, "lon": -78.1410, "gvp": "352040", "elev": 5758},
    "Chiles-Cerro Negro":{"lat":  0.7910, "lon": -77.9360, "gvp": "351020", "elev": 4768},
    "Cotacachi":         {"lat":  0.3520, "lon": -78.3450, "gvp": "352003", "elev": 4939},
    "Imbabura":          {"lat":  0.2600, "lon": -78.1840, "gvp": "352004", "elev": 4630},
}

# ─────────────────────────────────────────────
# APIs — NIVEL 1: ECUADOR OFICIAL
# ─────────────────────────────────────────────
IGEPN = {
    "base":          "https://www.igepn.edu.ec",
    "sismos_lista":  "https://www.igepn.edu.ec/cat-sismo-lista",
    "rss_sismos":    "https://www.igepn.edu.ec/rss-sismos",
    "volcanes":      "https://www.igepn.edu.ec/actividad-volcanica-actual",
    "informes":      "https://www.igepn.edu.ec/informes-volcanicos",
    "interval_min":  5,
}

SGR = {
    "base":        "https://www.gestionderiesgos.gob.ec",
    "alertas":     "https://www.gestionderiesgos.gob.ec/alertas/",
    "situacion":   "https://www.gestionderiesgos.gob.ec/sala-de-situacion/",
    "geoportal":   "https://geoportal.gestionderiesgos.gob.ec/",
    "interval_min": 10,
}

INAMHI = {
    "base":        "https://www.inamhi.gob.ec",
    "hidrologia":  "https://www.inamhi.gob.ec/index.php/hidrologia",
    "alertas":     "https://www.inamhi.gob.ec/index.php/alertas",
    "interval_min": 30,
}

IGM = {
    "base":    "https://www.geoportaligm.gob.ec",
    "portal":  "https://www.geoportaligm.gob.ec/portal/",
    "wms":     "https://www.geoportaligm.gob.ec/ogc/",
    "interval_min": 1440,  # 1 vez al día
}

# ─────────────────────────────────────────────
# APIs — NIVEL 2: INTERNACIONALES
# ─────────────────────────────────────────────
USGS = {
    "base":         "https://earthquake.usgs.gov/fdsnws/event/1/query",
    "min_mag":       1.5,
    "limit":         500,
    "interval_min":  2,
    "params": {
        "format":       "geojson",
        "minlatitude":  -6.0,
        "maxlatitude":   3.0,
        "minlongitude": -82.0,
        "maxlongitude": -74.0,
        "minmagnitude": 1.5,
        "limit":        500,
        "orderby":      "time",
    }
}
PTWC = {
    "rss_pac":     "https://ptwc.weather.gov/feeds/ptwc_rss_pac.xml",
    "alertas_txt": "https://ptwc.weather.gov/text/HPXTCPAC.txt",
    "interval_min": 5,
}

NOAA_TSUNAMI = {
    "alerts":      "https://tsunami.gov/events/xml/PHEBprods.xml",
    "interval_min": 5,
}

GDACS = {
    "rss":         "https://www.gdacs.org/xml/rss.xml",
    "api":         "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
    "interval_min": 15,
}

GVP = {
    "weekly":      "https://volcano.si.edu/gvp_api.cfm",
    "rss":         "https://volcano.si.edu/news/WeeklyVolcanoRSS.xml",
    "interval_min": 60,
}

EMSC = {
    "base":         "https://www.seismicportal.eu/fdsnws/event/1/query",
    "interval_min":  5,
    "params": {
        "format":       "json",
        "minlat":       ECUADOR_BBOX["min_lat"],
        "maxlat":       ECUADOR_BBOX["max_lat"],
        "minlon":       ECUADOR_BBOX["min_lon"],
        "maxlon":       ECUADOR_BBOX["max_lon"],
        "minmag":       2.5,
        "limit":        100,
        "orderby":      "time",
    }
}

OSM_OVERPASS = {
    "base":        "https://overpass-api.de/api/interpreter",
    "interval_min": 1440,
}

NASA_FIRMS = {
    "base":        "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
    "source":      "VIIRS_SNPP_NRT",
    "interval_min": 180,
}

COPERNICUS_EMS = {
    "activations": "https://emergency.copernicus.eu/mapping/list-of-activations-rapid",
    "wms":         "https://emergency.copernicus.eu/mapping/ows/wms",
    "interval_min": 60,
}

# ─────────────────────────────────────────────
# UMBRALES DE ALERTAS (CAP — ITU-T X.1303)
# ─────────────────────────────────────────────
ALERT_THRESHOLDS = {
    "red": {
        "sismo_mag":          6.0,
        "enjambre_count":     5,
        "enjambre_mag":       3.5,
        "enjambre_hours":     1,
        "volcán_nivel":       "ROJO",
        "tsunami_any":        True,
    },
    "orange": {
        "sismo_mag":          5.0,
        "volcán_nivel":       "NARANJA",
        "rio_nivel_inamhi":   3,
    },
    "yellow": {
        "sismo_mag":          4.0,
        "sismo_dist_ciudad_km": 50,
        "ciudad_min_pop":     50000,
        "volcán_nivel":       "AMARILLO",
    }
}

# ─────────────────────────────────────────────
# RETENCIÓN DE DATOS EN SQLITE
# ─────────────────────────────────────────────
RETENTION_DAYS = {
    "sismos":   90,
    "volcanes": 365,
    "alertas":  730,
    "incendios": 30,
}

# ─────────────────────────────────────────────
# HTTP HEADERS (User-Agent apropiado)
# ─────────────────────────────────────────────
HTTP_HEADERS = {
    "User-Agent": (
        "RiesgoEC-Geoportal/1.0 "
        "(Geoportal de Riesgos Naturales Ecuador; "
        "contact: geoportal@riesgoec.com; "
        "https://riesgoec.com)"
    ),
    "Accept": "application/json, application/geo+json, text/html, */*",
    "Accept-Language": "es-EC, es, en",
}
HTTP_TIMEOUT = 15  # segundos

# ─────────────────────────────────────────────
# COLORES PARA EL MAPA (Leaflet)
# ─────────────────────────────────────────────
SISMO_COLORS = {
    "M_muy_alto":  {"min": 6.0, "color": "#8B0000", "label": "M ≥ 6.0"},
    "M_alto":      {"min": 5.0, "color": "#FF0000", "label": "M 5.0-5.9"},
    "M_medio_alto":{"min": 4.0, "color": "#FF6600", "label": "M 4.0-4.9"},
    "M_medio":     {"min": 3.0, "color": "#FFCC00", "label": "M 3.0-3.9"},
    "M_bajo":      {"min": 2.5, "color": "#AAAAAA", "label": "M < 3.0"},
}

VOLCÁN_COLORS = {
    "ROJO":    "#FF0000",
    "NARANJA": "#FF6600",
    "AMARILLO":"#FFCC00",
    "VERDE":   "#00CC44",
    "SIN_DATO":"#888888",
}

ALERT_COLORS = {
    "red":    "#FF0000",
    "orange": "#FF8C00",
    "yellow": "#FFD700",
    "green":  "#00AA44",
    "none":   "#333333",
}
