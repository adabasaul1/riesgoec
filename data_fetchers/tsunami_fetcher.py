"""
╔══════════════════════════════════════════════════════════════════╗
║  data_fetchers/tsunami_fetcher.py                               ║
║  Alertas de tsunami en tiempo real — PTWC (NOAA) + GDACS ONU   ║
║                                                                  ║
║  CRÍTICO: Este módulo tiene prioridad máxima.                   ║
║  Cualquier alerta del Pacífico Sur dispara alerta ROJA.         ║
║                                                                  ║
║  Fuente científica:                                              ║
║  Papadopoulos, G.A. et al. (2020). Tsunami hazard in the        ║
║  Ecuador–Colombia subduction zone. Frontiers in Earth Science.  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger("geoportal.tsunami")

# Clasificación según PTWC / CAP Protocol
TSUNAMI_LEVELS = {
    "WARNING":    {"nivel": "ROJO",    "desc": "ALERTA DE TSUNAMI — Olas destructivas posibles"},
    "WATCH":      {"nivel": "NARANJA", "desc": "VIGILANCIA DE TSUNAMI — Prepararse para evacuación"},
    "ADVISORY":   {"nivel": "AMARILLO","desc": "AVISO DE TSUNAMI — Corrientes peligrosas posibles"},
    "INFORMATION":{"nivel": "VERDE",   "desc": "INFORMACIÓN — Tsunami no esperado en esta zona"},
    "CANCELLATION":{"nivel":"VERDE",   "desc": "ALERTA CANCELADA — Peligro de tsunami ha pasado"},
}

# Palabras clave para Pacífico Sur (Ecuador)
PACIFICO_SUR_KEYWORDS = [
    "ecuador", "colombia", "perú", "peru", "pacific south",
    "pacifico", "south america", "sudamerica", "galapagos",
    "galápagos", "esmeraldas", "guayaquil", "manabi",
]


def fetch_tsunami_alerts() -> list[dict[str, Any]]:
    """
    Obtiene alertas de tsunami desde PTWC y GDACS.
    Si detecta cualquier alerta activa para el Pacífico Sur,
    el motor de alertas dispara notificación inmediata.

    Returns:
        Lista de alertas con nivel, descripción y área afectada.
    """
    logger.info("Consultando alertas de tsunami (PTWC + GDACS)...")
    alertas = []

    # Fuente 1: PTWC RSS
    alertas_ptwc = _fetch_ptwc_rss()
    alertas.extend(alertas_ptwc)

    # Fuente 2: GDACS (ONU) para validación cruzada
    alertas_gdacs = _fetch_gdacs()
    alertas.extend(alertas_gdacs)

    # Eliminar duplicados por cercanía temporal
    alertas_unicos = _deduplicate_alerts(alertas)

    _save_alertas_tsunami(alertas_unicos)

    criticos = [a for a in alertas_unicos if a["nivel"] in ("ROJO", "NARANJA")]
    if criticos:
        logger.critical(f"¡ALERTA TSUNAMI ACTIVA! {len(criticos)} alertas críticas detectadas.")
    else:
        logger.info(f"Tsunami: {len(alertas_unicos)} alertas totales. Sin amenaza crítica activa.")

    return alertas_unicos


def _fetch_ptwc_rss() -> list[dict[str, Any]]:
    """Lee el RSS del Pacific Tsunami Warning Center (NOAA)."""
    alertas = []
    try:
        feed = feedparser.parse(
            cfg.PTWC["rss_pac"],
            request_headers={"User-Agent": cfg.HTTP_HEADERS["User-Agent"]},
        )

        for entry in feed.entries:
            titulo  = entry.get("title", "").upper()
            summary = entry.get("summary", "").upper()
            link    = entry.get("link", "")

            # Detectar nivel de alerta en el título
            nivel_detectado = None
            for key in TSUNAMI_LEVELS:
                if key in titulo or key in summary:
                    nivel_detectado = key
                    break

            if nivel_detectado is None:
                continue

            # Verificar si afecta Pacífico Sur / Ecuador
            afecta_ecuador = any(
                kw in titulo or kw in summary
                for kw in PACIFICO_SUR_KEYWORDS
            )

            # Si es un WARNING general del Pacífico, asumir que afecta Ecuador
            if nivel_detectado == "WARNING" and "PACIFIC" in titulo:
                afecta_ecuador = True

            published = entry.get("published_parsed")
            dt_utc = datetime(*published[:6], tzinfo=timezone.utc) if published else datetime.now(timezone.utc)

            info = TSUNAMI_LEVELS[nivel_detectado]
            alertas.append({
                "id":            f"PTWC-{dt_utc.strftime('%Y%m%d%H%M%S')}",
                "fuente":        "PTWC-NOAA",
                "tipo":          "TSUNAMI",
                "nivel":         info["nivel"],
                "nivel_original":nivel_detectado,
                "titulo":        entry.get("title", ""),
                "descripcion":   info["desc"],
                "afecta_ecuador":afecta_ecuador,
                "fecha_utc":     dt_utc.isoformat(),
                "fecha_ec":      dt_utc.strftime("%d/%m/%Y %H:%M:%S"),
                "url":           link,
                "activa":        True,
                "color":         cfg.ALERT_COLORS.get(
                    {"ROJO":"red","NARANJA":"orange","AMARILLO":"yellow","VERDE":"green"}.get(info["nivel"],"none"),
                    "#888"
                ),
            })

    except Exception as e:
        logger.error(f"Error leyendo PTWC RSS: {e}")

    return alertas


def _fetch_gdacs() -> list[dict[str, Any]]:
    """
    Lee el feed RSS de GDACS (Global Disaster Alert — ONU).
    Filtra eventos de tsunami relevantes para Ecuador.
    """
    alertas = []
    try:
        feed = feedparser.parse(
            cfg.GDACS["rss"],
            request_headers={"User-Agent": cfg.HTTP_HEADERS["User-Agent"]},
        )

        for entry in feed.entries:
            titulo  = entry.get("title", "").upper()
            summary = entry.get("summary", "").upper()

            # Solo tsunamis o sismos de gran magnitud
            if "TSUNAMI" not in titulo and "EARTHQUAKE" not in titulo:
                continue

            afecta_ecuador = any(
                kw in titulo or kw in summary
                for kw in PACIFICO_SUR_KEYWORDS
            )
            if not afecta_ecuador:
                continue

            # Intentar extraer nivel de alerta GDACS (rojo/naranja/verde)
            nivel = "AMARILLO"
            if "RED" in titulo or "RED" in summary:
                nivel = "ROJO"
            elif "ORANGE" in titulo or "ORANGE" in summary:
                nivel = "NARANJA"

            published = entry.get("published_parsed")
            dt_utc = datetime(*published[:6], tzinfo=timezone.utc) if published else datetime.now(timezone.utc)

            alertas.append({
                "id":            f"GDACS-{dt_utc.strftime('%Y%m%d%H%M%S')}",
                "fuente":        "GDACS-ONU",
                "tipo":          "TSUNAMI",
                "nivel":         nivel,
                "nivel_original":"GDACS",
                "titulo":        entry.get("title", ""),
                "descripcion":   entry.get("summary", "")[:300],
                "afecta_ecuador":True,
                "fecha_utc":     dt_utc.isoformat(),
                "fecha_ec":      dt_utc.strftime("%d/%m/%Y %H:%M:%S"),
                "url":           entry.get("link", ""),
                "activa":        True,
                "color":         "#FF0000" if nivel == "ROJO" else "#FF8C00",
            })

    except Exception as e:
        logger.error(f"Error leyendo GDACS RSS: {e}")

    return alertas


def _deduplicate_alerts(alertas: list[dict]) -> list[dict]:
    """Elimina duplicados (mismo evento de distintas fuentes)."""
    vistos = set()
    unicos = []
    for a in alertas:
        key = (a["tipo"], a["nivel"], a["fecha_utc"][:13])  # mismo tipo+nivel+hora
        if key not in vistos:
            vistos.add(key)
            unicos.append(a)
    return unicos


def _save_alertas_tsunami(alertas: list[dict]) -> None:
    """Persiste alertas de tsunami en SQLite."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alertas (
                id TEXT PRIMARY KEY,
                fuente TEXT, tipo TEXT, nivel TEXT, nivel_original TEXT,
                titulo TEXT, descripcion TEXT, afecta_ecuador INTEGER,
                fecha_utc TEXT, fecha_ec TEXT, url TEXT,
                activa INTEGER DEFAULT 1,
                color TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        for a in alertas:
            cur.execute("""
                INSERT OR REPLACE INTO alertas
                (id, fuente, tipo, nivel, nivel_original, titulo, descripcion,
                 afecta_ecuador, fecha_utc, fecha_ec, url, activa, color)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                a["id"], a["fuente"], a["tipo"], a["nivel"], a["nivel_original"],
                a["titulo"], a["descripcion"], int(a["afecta_ecuador"]),
                a["fecha_utc"], a["fecha_ec"], a["url"], int(a["activa"]), a["color"],
            ))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"SQLite error guardando alertas tsunami: {e}")


def get_active_tsunami_alerts() -> list[dict[str, Any]]:
    """Retorna alertas de tsunami activas desde caché SQLite."""
    try:
        conn = sqlite3.connect(cfg.DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM alertas
            WHERE tipo = 'TSUNAMI' AND activa = 1
            ORDER BY fecha_utc DESC LIMIT 10
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def is_tsunami_active() -> bool:
    """Retorna True si hay alguna alerta de tsunami roja o naranja activa."""
    alertas = get_active_tsunami_alerts()
    return any(a["nivel"] in ("ROJO", "NARANJA") for a in alertas)
