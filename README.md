# 🌎 GEOPORTAL RIESGOS NATURALES ECUADOR — RiesgoEC
### Versión 1.0 | Python + Leaflet.js + Flask | Datos IGEPN · USGS · PTWC · GDACS

---

## ⚡ INICIO RÁPIDO (3 pasos)

### Paso 1 — Abrir Anaconda Prompt (o Spyder)
```bash
# Si usas entorno dedicado (recomendado):
conda create -n geoportal_ec python=3.11 -y
conda activate geoportal_ec
```

### Paso 2 — Navegar a la carpeta del proyecto
```bash
cd geoportal_riesgos_ecuador
```

### Paso 3 — Ejecutar el instalador (instala todo automáticamente)
```bash
python install_and_run.py
```

El navegador se abrirá automáticamente en **http://localhost:5000**

---

## 📂 ESTRUCTURA DEL PROYECTO

```
geoportal_riesgos_ecuador/
├── main.py                          ← Punto de entrada principal
├── config.py                        ← URLs de APIs y configuración global
├── install_and_run.py               ← Instalador automático
├── requirements.txt                 ← Dependencias Python
│
├── data_fetchers/                   ← Módulos de obtención de datos
│   ├── usgs_fetcher.py              ← USGS earthquakes API (cada 2 min)
│   ├── igepn_fetcher.py             ← IGEPN sismos + volcanes (cada 5 min)
│   └── tsunami_fetcher.py           ← PTWC + GDACS tsunamis (cada 5 min)
│
├── processors/                      ← Procesamiento y lógica
│   ├── alert_engine.py              ← Motor de alertas CAP Protocol
│   └── geojson_builder.py           ← Generador de capas GeoJSON
│
├── webapp/                          ← Servidor Flask + interfaz web
│   ├── app.py                       ← Servidor Flask + API REST
│   ├── templates/index.html         ← Geoportal HTML/Leaflet.js completo
│   └── static/data/                 ← GeoJSON cacheados (auto-generados)
│
├── logs/
│   ├── geoportal.log                ← Log del sistema
│   └── alertas.csv                  ← Registro de alertas emitidas
│
└── geoportal.db                     ← Base de datos SQLite (auto-creada)
```

---

## 🔌 FUENTES DE DATOS INTEGRADAS

| Fuente | Datos | Frecuencia | Acceso |
|--------|-------|-----------|--------|
| **IGEPN** (igepn.edu.ec) | Sismos + Volcanes Ecuador | Cada 5 min | Gratis |
| **USGS** (usgs.gov) | Sismos tiempo real | Cada 2 min | Gratis |
| **PTWC-NOAA** | Alertas tsunami Pacífico | Cada 5 min | Gratis |
| **GDACS (ONU)** | Desastres globales | Cada 15 min | Gratis |
| **SGR Ecuador** | Alertas oficiales | Cada 10 min | Gratis |
| **GVP Smithsonian** | Volcanes mundo | Cada hora | Gratis |
| **EMSC** | Sismos (validación) | Cada 5 min | Gratis |
| **OpenStreetMap** | Infraestructura | Diario | Gratis |

---

## 🗺️ FUNCIONALIDADES DEL MAPA

- **5 mapas base:** OpenStreetMap, CartoDB Oscuro, Satélite Esri, Topográfico, Positron
- **Capas temáticas:** Sismos (puntos escalados), Volcanes, Mapa de calor, Infraestructura
- **Filtros:** Período temporal (1h/6h/24h/7d/30d) y magnitud mínima
- **Búsqueda:** Por ciudad o dirección con geocodificación Nominatim
- **Popups:** Información completa de cada evento con botones de compartir
- **Barra de alertas:** Se activa automáticamente con alertas rojas/naranjas
- **Actualización:** Auto-refresh cada 30 segundos en el navegador
- **Feature viral:** Botón "¿Está temblando ahora?"

---

## 🔴 SISTEMA DE ALERTAS (CAP Protocol)

| Nivel | Condición | Acción |
|-------|-----------|--------|
| 🔴 ROJO | Sismo M≥6.0 / Tsunami activo / Volcán ROJO / Enjambre ≥5 sismos/h | Notificación OS + Telegram + Email |
| 🟠 NARANJA | Sismo M 5.0-5.9 / Volcán NARANJA / Río nivel 3 | Notificación OS + Log CSV |
| 🟡 AMARILLO | Sismo M 4.0+ cerca ciudad grande / Volcán AMARILLO | Log CSV |

---

## ⚙️ CONFIGURACIÓN OPCIONAL

Editar `config.py` para agregar:

```python
# Alertas por Telegram (gratis — @BotFather)
TELEGRAM_BOT_TOKEN = "1234567:ABCdef..."
TELEGRAM_CHAT_ID   = "-1001234567890"

# Alertas por email (Gmail)
EMAIL_ALERT_TO   = "tu@gmail.com"
EMAIL_SMTP_USER  = "remitente@gmail.com"
EMAIL_SMTP_PASS  = "contraseña-de-app"

# NASA FIRMS (incendios — registro gratis)
NASA_FIRMS_KEY = "tu-api-key"
```

---

## 🌐 API REST DISPONIBLE

```
GET /api/sismos?hours=24&min_mag=2.5     → GeoJSON sismos
GET /api/volcanes                         → GeoJSON volcanes
GET /api/alertas                          → Alertas activas
GET /api/stats                            → Estadísticas panel
GET /api/temblando_ahora                  → ¿Está temblando?
GET /api/zona_riesgo?lat=-0.22&lon=-78.5  → Riesgo por coordenada
GET /api/health                           → Estado del servidor
```

---

## 📡 DESPLIEGUE EN LA NUBE (Render.com — gratis)

Para hacer el geoportal público en internet:

```bash
# 1. Subir código a GitHub
git init && git add . && git commit -m "RiesgoEC v1.0"
git remote add origin https://github.com/tu-usuario/riesgoec.git
git push -u origin main

# 2. En render.com:
#    → New Web Service → conectar repositorio GitHub
#    → Build Command: pip install -r requirements.txt
#    → Start Command: python main.py
#    → Plan: Free
#    → Domain: riesgoec.onrender.com (gratis) o dominio propio
```

---

## 📚 FUNDAMENTACIÓN CIENTÍFICA

1. **Zhao et al. (2021)** — WebGIS real-time monitoring. *NHESS* Q1, IF:4.58
2. **Pittore et al. (2022)** — Dynamic exposure assessment. *Earthquake Spectra* Q1
3. **Figueiredo & Martina (2016)** — Open data for risk. *NHESS* Q1
4. **Wieland et al. (2023)** — Multi-hazard WebGIS. *ISPRS IJGI* Q2
5. **Papadopoulos et al. (2020)** — Tsunami Ecuador. *Frontiers Earth Science* Q2
6. **Protocolo CAP** (ITU-T X.1303) — Sistema de alertas
7. **OGC Standards** WMS 1.3.0 / WFS 2.0 / GeoJSON RFC 7946
8. **Principios FAIR** (Wilkinson et al. 2016, *Scientific Data*)

---

## 🛠️ SOLUCIÓN DE PROBLEMAS

**El mapa no carga:**
```bash
# Verificar que Flask está corriendo:
# En la consola debe aparecer: "Running on http://0.0.0.0:5000"
```

**Error de importación de módulos:**
```bash
conda activate geoportal_ec
pip install -r requirements.txt --upgrade
```

**No hay datos en el mapa:**
```bash
# Verificar conexión a internet y ejecutar:
python -c "from data_fetchers.usgs_fetcher import fetch_earthquakes_ecuador; print(len(fetch_earthquakes_ecuador()))"
```

**Puerto 5000 ocupado:**
```bash
# Editar config.py:
FLASK_PORT = 5001  # o cualquier otro puerto libre
```

---

*Geoportal desarrollado para Ecuador — Geología · SIG · Gestión de Riesgos*
*Licencia MIT — Libre uso académico y profesional*
*Datos de fuentes oficiales: IGEPN, USGS, NOAA, ONU*

## 🌐 Ver en línea

Una vez desplegado en Render.com, el geoportal estará disponible en:
**https://riesgoec.onrender.com**

Cualquier persona en Ecuador (o el mundo) puede acceder desde su navegador,
sin necesidad de instalar nada.
