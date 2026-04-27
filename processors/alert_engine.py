"""
╔══════════════════════════════════════════════════════════════════╗
║  processors/alert_engine.py                                     ║
║  Motor de alertas automáticas — CAP Protocol (ITU-T X.1303)    ║
║                                                                  ║
║  Niveles: ROJO (crítico) → NARANJA (alto) → AMARILLO (medio)   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import csv
import logging
import platform
import smtplib
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger("geoportal.alertas")

# Archivo CSV de log de alertas
ALERT_LOG_PATH = cfg.BASE_DIR / "logs" / "alertas.csv"


def evaluate_sismos(sismos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Evalúa la lista de sismos recientes y genera alertas según umbrales CAP.

    Args:
        sismos: Lista de sismos de las últimas horas.

    Returns:
        Lista de alertas generadas (pueden ser 0 si todo está normal).
    """
    alertas_generadas = []
    th = cfg.ALERT_THRESHOLDS

    for sismo in sismos:
        mag   = sismo.get("magnitud", 0)
        nivel = None
        motivo = ""

        # ALERTA ROJA — M ≥ 6.0
        if mag >= th["red"]["sismo_mag"]:
            nivel  = "red"
            motivo = f"Sismo M{mag} — CRÍTICO"

        # ALERTA NARANJA — M 5.0-5.9
        elif mag >= th["orange"]["sismo_mag"]:
            nivel  = "orange"
            motivo = f"Sismo M{mag} — ALTO"

        # ALERTA AMARILLA — M 4.0+ cerca de ciudad grande
        elif mag >= th["yellow"]["sismo_mag"]:
            dist   = sismo.get("dist_ciudad_km", 999)
            ciudad = sismo.get("ciudad_cercana", "")
            pop    = cfg.CIUDADES_ECUADOR.get(ciudad, {}).get("pop", 0)
            if dist <= th["yellow"]["sismo_dist_ciudad_km"] and pop >= th["yellow"]["ciudad_min_pop"]:
                nivel  = "yellow"
                motivo = f"Sismo M{mag} a {dist}km de {ciudad}"

        # Sismo con flag de tsunami (USGS lo marca)
        if sismo.get("tsunami_flag", 0) == 1 and mag >= 6.0:
            nivel  = "red"
            motivo = f"Sismo M{mag} CON POTENCIAL DE TSUNAMI"

        if nivel:
            alerta = _build_alert(
                tipo="SISMO",
                nivel=nivel,
                motivo=motivo,
                datos=sismo,
            )
            alertas_generadas.append(alerta)

    # Detectar enjambre sísmico (≥5 sismos M≥3.5 en 1h en misma zona)
    enjambre = _detect_swarm(sismos)
    if enjambre:
        alertas_generadas.append(enjambre)

    return alertas_generadas


def evaluate_volcanes(volcanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evalúa niveles de alerta volcánica del IGEPN."""
    alertas = []
    for v in volcanes:
        nivel_igepn = v.get("nivel", "SIN_DATO")
        nivel_alerta = None

        if nivel_igepn == "ROJO":
            nivel_alerta = "red"
        elif nivel_igepn == "NARANJA":
            nivel_alerta = "orange"
        elif nivel_igepn == "AMARILLO":
            nivel_alerta = "yellow"

        if nivel_alerta:
            alertas.append(_build_alert(
                tipo="VOLCÁN",
                nivel=nivel_alerta,
                motivo=f"Volcán {v['nombre']} en nivel {nivel_igepn}",
                datos=v,
            ))
    return alertas


def evaluate_tsunami(tsunami_alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evalúa alertas de tsunami — máxima prioridad."""
    alertas = []
    for t in tsunami_alerts:
        if t.get("afecta_ecuador") and t.get("nivel") in ("ROJO", "NARANJA"):
            alertas.append(_build_alert(
                tipo="TSUNAMI",
                nivel="red",
                motivo=f"ALERTA DE TSUNAMI — {t.get('titulo', '')}",
                datos=t,
            ))
    return alertas


def _detect_swarm(sismos: list[dict]) -> dict | None:
    """
    Detecta enjambres sísmicos: ≥5 sismos M≥3.5 en 1h dentro de 50km.
    Metodología: Zaliapin & Ben-Zion (2013) — Journal of Geophysical Research.
    """
    th = cfg.ALERT_THRESHOLDS["red"]
    min_mag    = th["enjambre_mag"]
    min_count  = th["enjambre_count"]
    time_hours = th["enjambre_hours"]

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=time_hours)).isoformat()
    candidatos = [
        s for s in sismos
        if s.get("magnitud", 0) >= min_mag and s.get("fecha_utc", "") >= cutoff
    ]

    if len(candidatos) < min_count:
        return None

    # Agrupar por zona aproximada (grid 0.5°)
    zonas: dict[tuple, list] = defaultdict(list)
    for s in candidatos:
        grid_lat = round(s["lat"] / 0.5) * 0.5
        grid_lon = round(s["lon"] / 0.5) * 0.5
        zonas[(grid_lat, grid_lon)].append(s)

    for zona, eventos in zonas.items():
        if len(eventos) >= min_count:
            mags = [e["magnitud"] for e in eventos]
            return _build_alert(
                tipo="ENJAMBRE",
                nivel="red",
                motivo=(
                    f"Enjambre sísmico: {len(eventos)} sismos M≥{min_mag} "
                    f"en última hora en zona {zona[0]:.2f}°N, {zona[1]:.2f}°E"
                ),
                datos={"lat": zona[0], "lon": zona[1], "magnitud": max(mags)},
            )
    return None


def _build_alert(tipo: str, nivel: str, motivo: str, datos: dict) -> dict:
    """Construye un objeto de alerta estándar (CAP-like)."""
    ahora = datetime.now(timezone.utc)
    return {
        "id":       f"ALERT-{tipo}-{ahora.strftime('%Y%m%d%H%M%S')}",
        "tipo":     tipo,
        "nivel":    nivel,
        "motivo":   motivo,
        "datos":    datos,
        "fecha_utc":ahora.isoformat(),
        "color":    cfg.ALERT_COLORS.get(nivel, "#333333"),
    }


# ─────────────────────────────────────────────
# ACCIONES DE NOTIFICACIÓN
# ─────────────────────────────────────────────

def dispatch_alerts(alertas: list[dict]) -> None:
    """
    Ejecuta todas las acciones de notificación para cada alerta generada.
    """
    for alerta in alertas:
        _log_alert_csv(alerta)
        _notify_os(alerta)
        _send_telegram(alerta)
        _send_email(alerta)
        logger.warning(
            f"ALERTA {alerta['nivel'].upper()} — {alerta['tipo']}: {alerta['motivo']}"
        )


def _notify_os(alerta: dict) -> None:
    """Notificación push del sistema operativo (Windows/macOS/Linux)."""
    try:
        from plyer import notification
        icons = {"red": "critical", "orange": "warning", "yellow": "info"}
        notification.notify(
            title=f"🚨 RiesgoEC — {alerta['tipo']} {alerta['nivel'].upper()}",
            message=alerta["motivo"][:256],
            app_name="RiesgoEC Geoportal",
            timeout=15,
        )
    except ImportError:
        logger.debug("plyer no instalado — notificación OS omitida.")
    except Exception as e:
        logger.debug(f"Notificación OS falló: {e}")


def _log_alert_csv(alerta: dict) -> None:
    """Guarda la alerta en el CSV de log."""
    try:
        ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not ALERT_LOG_PATH.exists()
        with open(ALERT_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id","tipo","nivel","motivo","fecha_utc","color"])
            if nuevo:
                writer.writeheader()
            writer.writerow({
                "id":      alerta["id"],
                "tipo":    alerta["tipo"],
                "nivel":   alerta["nivel"],
                "motivo":  alerta["motivo"],
                "fecha_utc":alerta["fecha_utc"],
                "color":   alerta["color"],
            })
    except Exception as e:
        logger.error(f"Error guardando alerta en CSV: {e}")


def _send_telegram(alerta: dict) -> None:
    """Envía mensaje al bot de Telegram si está configurado."""
    token   = cfg.TELEGRAM_BOT_TOKEN
    chat_id = cfg.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return
    emojis = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}
    emoji  = emojis.get(alerta["nivel"], "⚪")
    texto  = (
        f"{emoji} *ALERTA {alerta['nivel'].upper()} — RiesgoEC*\n"
        f"*{alerta['tipo']}:* {alerta['motivo']}\n"
        f"🕐 {alerta['fecha_utc'][:19]} UTC\n"
        f"🗺️ Ver mapa: http://localhost:5000"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=10,
        )
        logger.info(f"Telegram alert enviada: {alerta['id']}")
    except Exception as e:
        logger.debug(f"Telegram error: {e}")


def _send_email(alerta: dict) -> None:
    """Envía email de alerta via SMTP (Gmail) si está configurado."""
    if not cfg.EMAIL_ALERT_TO or not cfg.EMAIL_SMTP_USER:
        return
    try:
        asunto = f"[RiesgoEC] ALERTA {alerta['nivel'].upper()} — {alerta['tipo']}"
        cuerpo = (
            f"ALERTA GEOPORTAL ECUADOR\n\n"
            f"Tipo: {alerta['tipo']}\n"
            f"Nivel: {alerta['nivel'].upper()}\n"
            f"Detalle: {alerta['motivo']}\n"
            f"Fecha/Hora UTC: {alerta['fecha_utc']}\n\n"
            f"Ver mapa en tiempo real: http://localhost:5000\n\n"
            f"— Sistema RiesgoEC Geoportal"
        )
        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = asunto
        msg["From"]    = cfg.EMAIL_SMTP_USER
        msg["To"]      = cfg.EMAIL_ALERT_TO

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(cfg.EMAIL_SMTP_USER, cfg.EMAIL_SMTP_PASS)
            servidor.sendmail(cfg.EMAIL_SMTP_USER, cfg.EMAIL_ALERT_TO, msg.as_string())
        logger.info(f"Email alerta enviado a {cfg.EMAIL_ALERT_TO}")
    except Exception as e:
        logger.debug(f"Email error: {e}")


def generate_share_text(sismo: dict) -> dict[str, str]:
    """
    Genera textos pre-formateados para compartir en redes sociales.

    Returns:
        Diccionario con texto para Twitter, WhatsApp y la URL del mapa.
    """
    mag    = sismo.get("magnitud", "?")
    ciudad = sismo.get("ciudad_cercana", "Ecuador")
    dist   = sismo.get("dist_ciudad_km", "?")
    fecha  = sismo.get("fecha_ec", "")
    prof   = sismo.get("profundidad_km", "?")
    url    = "https://riesgoec.com"  # dominio de producción

    twitter = (
        f"🌎 Sismo M{mag} detectado a {dist}km de {ciudad} "
        f"| Prof: {prof}km | {fecha} (EC)\n"
        f"Ver mapa en tiempo real: {url}\n"
        f"#SismoEcuador #IGEPN #RiesgoEC"
    )
    whatsapp = (
        f"*🚨 Sismo Ecuador*\n"
        f"Magnitud: M{mag}\n"
        f"Cercanía: {dist}km de {ciudad}\n"
        f"Profundidad: {prof}km\n"
        f"Hora (EC): {fecha}\n"
        f"Mapa en vivo: {url}"
    )
    return {
        "twitter":  twitter,
        "whatsapp": whatsapp,
        "url_mapa": url,
    }
