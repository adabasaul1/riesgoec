import requests, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

def descargar_historico_render():
    conn = sqlite3.connect(cfg.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM sismos")
        count = cur.fetchone()[0]
    except:
        count = 0
    conn.close()

    if count >= 100:
        print(f"BD ya tiene {count} sismos - OK")
        return

    print("Descargando datos historicos USGS para Render...")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365*5)
    url = (
        "https://earthquake.usgs.gov/fdsnws/event/1/query"
        f"?format=geojson&minlatitude=-6&maxlatitude=3"
        f"&minlongitude=-82&maxlongitude=-74&minmagnitude=4.0"
        f"&starttime={start.strftime('%Y-%m-%d')}"
        f"&endtime={end.strftime('%Y-%m-%d')}&limit=5000&orderby=time"
    )
    r = requests.get(url, timeout=60)
    feats = r.json().get("features", [])

    conn = sqlite3.connect(cfg.DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sismos (
        id TEXT PRIMARY KEY, fuente TEXT, lat REAL, lon REAL,
        profundidad_km REAL, magnitud REAL, tipo_magnitud TEXT,
        lugar TEXT, fecha_utc TEXT, fecha_ec TEXT,
        ciudad_cercana TEXT, dist_ciudad_km REAL,
        clasificacion_prof TEXT, intensidad_mercalli TEXT,
        color TEXT, radio_mapa REAL, url_detalle TEXT,
        tsunami_flag INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime("now"))
    )""")

    count = 0
    for f in feats:
        p = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [None,None,0])
        if not coords[0]: continue
        dt = datetime.fromtimestamp((p.get("time",0))/1000, tz=timezone.utc)
        mag = p.get("mag") or 0
        c2 = "#FF6600" if mag>=4 else "#FFCC00"
        if mag>=7: c2="#4a0000"
        elif mag>=6: c2="#8B0000"
        elif mag>=5: c2="#FF0000"
        try:
            cur.execute("""INSERT OR IGNORE INTO sismos
                (id,fuente,lat,lon,profundidad_km,magnitud,tipo_magnitud,
                lugar,fecha_utc,fecha_ec,color,radio_mapa,url_detalle,tsunami_flag)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f.get("id",""),"USGS",round(coords[1],4),round(coords[0],4),
                round(coords[2] or 0,1),round(mag,1),p.get("magType","Mw"),
                p.get("place","Ecuador"),dt.isoformat(),
                (dt-timedelta(hours=5)).strftime("%d/%m/%Y %H:%M:%S"),
                c2,max(4,mag*mag*0.7),p.get("url",""),int(p.get("tsunami",0))))
            count+=1
        except: pass
    conn.commit()
    conn.close()
    print(f"Descargados {count} sismos")

if __name__ == "__main__":
    descargar_historico_render()
