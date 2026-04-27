"""
╔══════════════════════════════════════════════════════════════════╗
║  data_fetchers/igepn_fetcher.py                                 ║
║  Obtiene datos sísmicos y volcánicos del IGEPN (fuente oficial) ║
║                                                                  ║
║  Fuente: Instituto Geofísico EPN — igepn.edu.ec                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger("geoportal.igepn")


# ─────────────────────────────────────────────
# SISMOS IGEPN (RSS + Scraping)
# ─────────────────────────────────────────────

def fetch_sismos_igepn() -> list[dict[str, Any]]:
    """
    Obtiene sismos recientes desde el RSS del IGEPN.
    El RSS del IGEPN es la fuente más confiable para Ecuador ya que
    incluye sismos locales que USGS puede tardar más en publicar.

    Returns:
        Lista de sismos con datos parseados del feed RSS.
    """
    logger.info("Consultando RSS IGEPN sismos...")
    sismos = []

    try:
        feed = feedparser.parse(
            cfg.IGEPN["rss_sismos"],
            request_headers={"User-Agent": cfg.HTTP_HEADERS["User-Agent"]},
        )

        if feed.bozo and not feed.entries:
            logger.warning(f"IGEPN RSS — feed con errores: {feed.bozo_exception}")
            return _scrape_sismos_igepn()

        for entry in feed.entries:
            try:
                sismo = _parse_igepn_rss_entry(entry)
                if sismo:
                    sismos.append(sismo)
            except Exception as e:
                logger.warning(f"Error parseando entrada RSS IGEPN: {e}")
                continue

        logger.info(f"IGEPN RSS: {len(sismos)} sismos obtenidos.")

    except Exception as e:
        logger.error(f"Error leyendo RSS IGEPN: {e}. Intentando scraping...")
        sismos = _scrape_sismos_igepn()

    _save_igepn_sismos(sismos)
    return sismos


def _parse_igepn_rss_entry(entry) -> dict[str, Any] | None:
    """
    Parsea una entrada del RSS IGEPN.
    El formato típico del título es:
    "Sismo de magnitud 3.5 ML a 12.3 km al NE de Quito"
    """
    title   = entry.get("title", "")
    summary = entry.get("summary", "")
    link    = entry.get("link", "")

    # Extraer magnitud del título
    mag_match = re.search(r"magnitud\s+([\d.]+)\s+(\w+)", title, re.IGNORECASE)
    mag       = float(mag_match.group(1)) if mag_match else None
    mag_type  = mag_match.group(2) if mag_match else "ML"

    if mag is None:
        return None

    # Extraer coordenadas del summary (IGEPN las incluye en el HTML del summary)
    lat, lon, depth = _extract_coords_from_summary(summary)

    # Fecha
    published = entry.get("published_parsed")
    if published:
        dt_utc = datetime(*published[:6], tzinfo=timezone.utc)
    else:
        dt_utc = datetime.now(timezone.utc)

    sismo_id = f"IGEPN-{dt_utc.strftime('%Y%m%d%H%M%S')}-{mag}"

    return {
        "id":              sismo_id,
        "fuente":          "IGEPN",
        "lat":              lat or -1.5,
        "lon":              lon or -78.5,
        "profundidad_km":   depth or 10.0,
        "magnitud":         round(mag, 1),
        "tipo_magnitud":    mag_type,
        "lugar":            title,
        "fecha_utc":        dt_utc.isoformat(),
        "fecha_ec":         (dt_utc).strftime("%d/%m/%Y %H:%M:%S"),
        "url_detalle":      link,
        "color":            _color_mag(mag),
        "radio_mapa":       max(4, (mag ** 2) * 0.8),
        "tsunami_flag":     0,
    }


def _extract_coords_from_summary(summary: str) -> tuple[float | None, float | None, float | None]:
    """Extrae latitud, longitud y profundidad del HTML del summary RSS."""
    try:
        soup = BeautifulSoup(summary, "lxml")
        text = soup.get_text()

        lat_m   = re.search(r"Latitud[:\s]+([-\d.]+)", text, re.IGNORECASE)
        lon_m   = re.search(r"Longitud[:\s]+([-\d.]+)", text, re.IGNORECASE)
        depth_m = re.search(r"Profundidad[:\s]+([\d.]+)", text, re.IGNORECASE)

        lat   = float(lat_m.group(1))   if lat_m   else None
        lon   = float(lon_m.group(1))   if lon_m   else None
        depth = float(depth_m.group(1)) if depth_m else None
        return lat, lon, depth
    except Exception:
        return None, None, None


def _scrape_sismos_igepn() -> list[dict[str, Any]]:
    """
    Fallback: scraping directo de la página de catálogo de sismos IGEPN.
    Se usa cuando el RSS falla.
    """
    logger.info("Scraping fallback igepn.edu.ec/cat-sismo-lista...")
    sismos = []
    try:
        resp = requests.get(
            cfg.IGEPN["sismos_lista"],
            headers=cfg.HTTP_HEADERS,
            timeout=cfg.HTTP_TIMEOUT,
            verify=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # La tabla de sismos suele estar en un <table> con clase específica
        tabla = soup.find("table")
        if not tabla:
            logger.warning("IGEPN scraping: no se encontró tabla de sismos.")
            return []

        filas = tabla.find_all("tr")[1:]  # saltar header
        for fila in filas[:50]:
            celdas = fila.find_all("td")
            if len(celdas) < 5:
                continue
            try:
                fecha_str = celdas[0].get_text(strip=True)
                lat_str   = celdas[1].get_text(strip=True)
                lon_str   = celdas[2].get_text(strip=True)
                prof_str  = celdas[3].get_text(strip=True)
                mag_str   = celdas[4].get_text(strip=True)

                lat   = float(lat_str.replace(",", "."))
                lon   = float(lon_str.replace(",", "."))
                depth = float(prof_str.replace(",", "."))
                mag   = float(mag_str.replace(",", "."))

                # Intentar parsear fecha ecuatoriana
                try:
                    dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
                    dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = datetime.now(timezone.utc)

                sismo_id = f"IGEPN-SCRAPE-{dt.strftime('%Y%m%d%H%M%S')}-{mag}"
                sismos.append({
                    "id":           sismo_id,
                    "fuente":       "IGEPN",
                    "lat":           lat,
                    "lon":           lon,
                    "profundidad_km": depth,
                    "magnitud":      round(mag, 1),
                    "tipo_magnitud": "ML",
                    "lugar":         "Ecuador (IGEPN)",
                    "fecha_utc":     dt.isoformat(),
                    "fecha_ec":      fecha_str,
                    "url_detalle":   cfg.IGEPN["base"],
                    "color":         _color_mag(mag),
                    "radio_mapa":    max(4, (mag ** 2) * 0.8),
                    "tsunami_flag":  0,
                })
            except (ValueError, IndexError) as e:
                logger.debug(f"Fila IGEPN no parseable: {e}")
                continue

        logger.info(f"IGEPN scraping: {len(sismos)} sismos extraídos.")
    except Exception as e:
        logger.error(f"IGEPN scraping fallido: {e}")

    return sismos


def _save_igepn_sismos(sismos: list[dict]) -> None:
    """Guarda sismos IGEPN en SQLite (misma tabla que USGS)."""
    if not sismos:
        return
    try:
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
                tsunami_flag INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        for s in sismos:
            cur.execute("""
                INSERT OR IGNORE INTO sismos
                (id, fuente, lat, lon, profundidad_km, magnitud, tipo_magnitud,
                 lugar, fecha_utc, fecha_ec, ciudad_cercana, dist_ciudad_km,
                 color, radio_mapa, url_detalle, tsunami_flag)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                s["id"], s["fuente"], s["lat"], s["lon"],
                s["profundidad_km"], s["magnitud"], s["tipo_magnitud"],
                s["lugar"], s["fecha_utc"], s["fecha_ec"],
                s.get("ciudad_cercana", ""), s.get("dist_ciudad_km", 0),
                s["color"], s["radio_mapa"], s["url_detalle"], s["tsunami_flag"],
            ))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"SQLite error guardando IGEPN sismos: {e}")


# ─────────────────────────────────────────────
# VOLCANES IGEPN
# ─────────────────────────────────────────────

def fetch_volcanes_igepn() -> list[dict[str, Any]]:
    """
    Obtiene el nivel de actividad actual de volcanes desde el IGEPN.

    Returns:
        Lista de volcanes con nivel de alerta actual, descripción y
        URL del último boletín.
    """
    logger.info("Consultando IGEPN — actividad volcánica...")
    volcanes = []

    try:
        resp = requests.get(
            cfg.IGEPN["volcanes"],
            headers=cfg.HTTP_HEADERS,
            timeout=cfg.HTTP_TIMEOUT,
            verify=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Buscar bloques de información por volcán
        # IGEPN usa tarjetas/divs con el nombre y nivel de cada volcán
        volcanes_encontrados = _parse_volcanes_page(soup)
        if volcanes_encontrados:
            volcanes = volcanes_encontrados
        else:
            # Fallback: usar datos base del config con nivel desconocido
            volcanes = _build_default_volcanes()

    except requests.exceptions.RequestException as e:
        logger.error(f"Error consultando IGEPN volcanes: {e}")
        volcanes = _build_default_volcanes()

    _save_volcanes(volcanes)
    logger.info(f"Volcanes procesados: {len(volcanes)}")
    return volcanes


def _parse_volcanes_page(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Parsea la página de actividad volcánica del IGEPN."""
    volcanes = []
    niveles_validos = {"ROJO", "NARANJA", "AMARILLO", "VERDE"}

    # Buscar cualquier elemento que contenga nombres de volcanes conocidos
    texto_completo = soup.get_text().upper()

    for nombre, datos in cfg.VOLCANES_ECUADOR.items():
        nivel = "SIN_DATO"
        descripcion = ""
        boletin_url = cfg.IGEPN["informes"]

        # Buscar nivel de alerta cerca del nombre del volcán en el texto
        patron = re.search(
            rf"{nombre.upper()}.*?(ROJO|NARANJA|AMARILLO|VERDE)",
            texto_completo,
            re.DOTALL,
        )
        if patron:
            nivel = patron.group(1)

        # Buscar URL del boletín más reciente para este volcán
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"].lower()
            if nombre.lower().replace(" ", "-") in href and "boletin" in href:
                boletin_url = href if href.startswith("http") else cfg.IGEPN["base"] + href
                break

        volcanes.append({
            "nombre":       nombre,
            "lat":          datos["lat"],
            "lon":          datos["lon"],
            "gvp_code":     datos["gvp"],
            "elevacion_m":  datos["elev"],
            "nivel":        nivel,
            "descripcion":  descripcion,
            "boletin_url":  boletin_url,
            "color":        cfg.VOLCÁN_COLORS.get(nivel, "#888888"),
            "fecha_update": datetime.now(timezone.utc).isoformat(),
        })

    return volcanes


def _build_default_volcanes() -> list[dict[str, Any]]:
    """Construye lista base de volcanes cuando el IGEPN no responde."""
    return [
        {
            "nombre":       nombre,
            "lat":          datos["lat"],
            "lon":          datos["lon"],
            "gvp_code":     datos["gvp"],
            "elevacion_m":  datos["elev"],
            "nivel":        "SIN_DATO",
            "descripcion":  "Datos no disponibles — verificar igepn.edu.ec",
            "boletin_url":  cfg.IGEPN["informes"],
            "color":        "#888888",
            "fecha_update": datetime.now(timezone.utc).isoformat(),
        }
        for nombre, datos in cfg.VOLCANES_ECUADOR.items()
    ]


def _save_volcanes(volcanes: list[dict]) -> None:
    """Persiste datos de volcanes en SQLite."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS volcanes (
                nombre TEXT PRIMARY KEY,
                lat REAL, lon REAL, gvp_code TEXT, elevacion_m REAL,
                nivel TEXT, descripcion TEXT, boletin_url TEXT,
                color TEXT, fecha_update TEXT
            )
        """)
        for v in volcanes:
            cur.execute("""
                INSERT OR REPLACE INTO volcanes
                (nombre, lat, lon, gvp_code, elevacion_m, nivel,
                 descripcion, boletin_url, color, fecha_update)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                v["nombre"], v["lat"], v["lon"], v["gvp_code"],
                v["elevacion_m"], v["nivel"], v["descripcion"],
                v["boletin_url"], v["color"], v["fecha_update"],
            ))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"SQLite error guardando volcanes: {e}")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _color_mag(mag: float) -> str:
    if mag >= 6.0:   return "#8B0000"
    elif mag >= 5.0: return "#FF0000"
    elif mag >= 4.0: return "#FF6600"
    elif mag >= 3.0: return "#FFCC00"
    else:            return "#AAAAAA"
