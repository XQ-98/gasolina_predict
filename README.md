# GasPredict Ecuador

**Prediccion Inteligente de Precios de Combustibles en Ecuador**

Sistema de prediccion que utiliza Machine Learning y la formula oficial del gobierno ecuatoriano (Decreto Ejecutivo No. 308) para estimar los precios de gasolina y diesel. EP Petroecuador publica los nuevos precios la noche del **dia 11** de cada mes y entran en **vigencia desde el dia 12**.

![Version](https://img.shields.io/badge/version-1.1.0-brightgreen)
![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.18-orange?logo=tensorflow)
![XGBoost](https://img.shields.io/badge/XGBoost-2.1-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)

---

## Que hace este proyecto

En Ecuador, los precios de los combustibles (Extra, EcoPais, Diesel) se actualizan mensualmente mediante un sistema de bandas de precios regulado por el gobierno. Este sistema:

- Calcula un precio teorico basado en el costo de importacion del petroleo (WTI)
- Limita la subida a un maximo de **+5% mensual** (techo)
- Limita la bajada a un maximo de **-10% mensual** (piso)
- La gasolina Super 95 tiene precio libre (no esta regulada por bandas)

**GasPredict Ecuador** predice estos precios usando un enfoque de **2 capas**:

### Capa 1: Prediccion del WTI con datos diarios
- Entrena 3 modelos ML (SARIMA, XGBoost, LSTM) con datos diarios del precio del petroleo WTI
- Predice el WTI promedio para los dias 1-10 del proximo mes
- Si el WTI predicho diverge mas del 5% del precio actual, aplica un **blend 80/20** (80% precio actual + 20% modelo) para anclar la prediccion a la realidad
- Calcula un ensemble ponderado segun el desempeno de cada modelo
- Fallback automatico: si Yahoo Finance no esta disponible (Docker), usa los datos diarios de la BD local

### Capa 2: Formula del Gobierno + Banda de precios
- Toma el WTI predicho y aplica la **formula exacta del Decreto 308**:
  - Costo de importacion (CIF) basado en el WTI
  - Costos de transporte y almacenamiento
  - Margen de EP Petroecuador
  - Costo de capital (tasa 10.78%)
  - IVA (15%)
  - Margen de comercializacion
- Aplica la **banda de precios**: techo +5% / piso -10% sobre el precio del mes anterior
- Resultado: precio estimado vigente desde el proximo dia 12

---

## Ciclo mensual de precios

| Dia | Evento |
|-----|--------|
| 1-10 | EP Petroecuador calcula costos de importacion basados en el WTI del periodo |
| 11 (noche) | EP Petroecuador **publica** los nuevos precios |
| 12 | Los nuevos precios **entran en vigencia** en todas las gasolineras |

---

## Combustibles cubiertos

| Combustible | Octanaje | Sistema de bandas | Precio vigente (Jun 2026) |
|------------|----------|-------------------|--------------------------|
| Extra | RON 87 | Si (+5% / -10%) | $3.312/galon |
| EcoPais | RON 87 + etanol | Si (+5% / -10%) | $3.312/galon |
| Super 95 | RON 95 | No (precio libre) | $5.700/galon |
| Diesel Premium | - | Si (+5% / -10%) | $3.251/galon |

---

## Arquitectura

```
                    FRONTEND (Next.js 14 + React 18)
                              |
                         REST API
                              |
                    BACKEND (FastAPI + Python)
                         |         |
                    PostgreSQL   Scraper de noticias
                    (Docker)     (El Universo, Expreso,
                         |        El Comercio, Primicias)
          +-------------------+-------------------+
          |                                       |
    CAPA 1: WTI                          CAPA 2: FORMULA
    Prediccion diaria                    Decreto 308
          |                                       |
  +-------+-------+                    +----------+----------+
  |       |       |                    |                     |
SARIMA  XGBoost  LSTM               Formula              Banda
(diario) (diario) (diario)         del gobierno        +5% / -10%
  |       |       |                    |                     |
  +---Ensemble----+    Blend 80/20     +-----Precio Final----+
      ponderado   <--  si diverge >5%        vigente dia 12
```

---

## Funcionalidades

### Dashboard
- **Cuenta regresiva** al proximo dia 12 (vigencia) con nota del dia 11 (publicacion)
- **Mini prediccion** para Extra, EcoPais, Super 95 y Diesel con probabilidad de subida/bajada
- **Panel expandible**: al hacer clic en un combustible muestra:
  - Explicacion en lenguaje natural de por que sube o baja
  - Paso 1: Prediccion del WTI (actual, predicho, IC 95%, pesos de modelos)
  - Paso 2: Desglose de la formula (CIF, transporte, margenes, IVA 15%)
  - Paso 3: Aplicacion de la banda con visualizacion grafica
- **Precios actuales** de los 4 combustibles con cambio vs mes anterior
- **Tracker del WTI** en tiempo real con sparkline y cambios 24h/7d/30d
- **Boton "Obtener Precios"**: scraping automatico de noticias de combustibles
- **Grafico historico** de todos los combustibles desde julio 2020
- **Noticias** de combustibles Ecuador con analisis de sentimiento
- **Tooltips educativos** en siglas tecnicas (WTI, CIF, IC, SARIMA, etc.)
- **Badge de version** visible en el header (v1.1.0)

### Prediccion avanzada
- Selector de combustible y horizonte (1-12 meses)
- **2 enfoques**: Two-Layer (mas preciso) o Ensemble directo
- Grafico de prediccion con intervalos de confianza
- **Comparacion interactiva** de modelos (activar/desactivar SARIMA, XGBoost, LSTM)
- Metricas detalladas: RMSE, MAE, MAPE por modelo
- Pesos adaptativos del ensemble
- Detalle de las 2 capas (WTI predicho + formula + banda)

### Simulador de bandas
- Slider para variar el precio del WTI ($40-$130)
- Visualizacion en tiempo real del efecto en el precio
- Desglose completo de la formula paso a paso
- Grafico con piso, techo y precio resultante
- Indicador visual de si se topa con el techo o el piso

### Historial de bandas
- Tabla con todos los cambios desde julio 2020
- Conteo de subidas vs bajadas
- Grafico de barras con cambios mensuales
- Filtro por tipo de combustible

### Base de datos (PostgreSQL)
- **Persistencia completa** en PostgreSQL 16 (Docker)
- **5 tablas**: precios historicos, WTI diario, predicciones, noticias, predicciones WTI
- **1,413 registros WTI diarios** (2021-2026) incluyendo datos historicos sinteticos calibrados con promedios reales EIA
- **Cache inteligente**: predicciones se cachean 2 horas en localStorage (no por dia)
- **Historial de predicciones**: cada prediccion se guarda con su precision calculable
- **Graceful fallback**: si PostgreSQL no esta disponible, el sistema funciona sin BD

---

## Tecnologias

### Backend
| Tecnologia | Uso |
|-----------|-----|
| **FastAPI** | Framework web (API REST) |
| **PostgreSQL 16** | Base de datos relacional (Docker) |
| **SQLAlchemy 2.0** | ORM para Python |
| **SARIMA** (statsmodels) | Modelo de series temporales |
| **XGBoost** | Gradient boosting con features tecnicas |
| **TensorFlow/Keras** | LSTM para secuencias temporales |
| **yfinance** | Datos del WTI desde Yahoo Finance (con fallback a BD) |
| **APScheduler** | Obtencion automatica de precios el dia 12 a las 8am Ecuador |
| **BeautifulSoup** | Scraping de noticias de combustibles |
| **NLTK** | Analisis de sentimiento de noticias |
| **Pandas/NumPy** | Procesamiento de datos |

### Frontend
| Tecnologia | Uso |
|-----------|-----|
| **Next.js 14** | Framework React con SSR (output: standalone para Docker) |
| **TypeScript** | Tipado estatico |
| **Tailwind CSS** | Estilos utilitarios |
| **Plotly.js** | Graficos interactivos |
| **Lucide React** | Iconos |
| **date-fns** | Manejo de fechas |

### Infraestructura
| Tecnologia | Uso |
|-----------|-----|
| **Docker Compose** | Orquestacion de 3 contenedores |
| **PostgreSQL 16** | Base de datos (puerto 5436) |
| **Python 3.11 slim** | Contenedor backend (puerto 8001) |
| **Node 20 slim** | Contenedor frontend standalone (puerto 3001) |

---

## Estructura del proyecto

```
Prediccion_Gas/
├── README.md
├── .gitignore
├── docker-compose.yml                      # 3 servicios: postgres + backend + frontend
├── backups/                                # Respaldos de la BD (.dump y .sql)
├── backend/
│   ├── Dockerfile                          # Multi-etapa: pip split para evitar OOM
│   ├── requirements.txt
│   └── app/
│       ├── main.py                         # FastAPI + APScheduler (dia 12, 8am Ecuador)
│       ├── config.py                       # PRICE_UPDATE_DAY=11, PRICE_EFFECTIVE_DAY=12
│       ├── api/
│       │   ├── routes.py                   # Endpoints REST + /api/prices/fetch
│       │   └── schemas.py                  # Modelos Pydantic
│       ├── database/
│       │   ├── connection.py               # Engine SQLAlchemy + SessionLocal
│       │   ├── models.py                   # 5 tablas (SQLAlchemy ORM)
│       │   ├── crud.py                     # Operaciones CRUD completas
│       │   └── init_db.py                  # Inicializacion + seed de datos
│       ├── models/
│       │   ├── ensemble.py                 # Ensemble de 3 modelos (mensual)
│       │   ├── sarima_model.py             # SARIMA mensual
│       │   ├── xgboost_model.py            # XGBoost mensual
│       │   └── lstm_model.py               # LSTM mensual
│       ├── services/
│       │   ├── wti_predictor.py            # Prediccion WTI diaria (Capa 1) + fallback BD
│       │   ├── two_layer_predictor.py      # Orquestador 2 capas + blend 80/20
│       │   ├── band_calculator.py          # Formula Decreto 308 + bandas + dia 12
│       │   ├── price_scraper.py            # Scraping de noticias (4 fuentes)
│       │   ├── data_pipeline.py            # Datos historicos + Yahoo Finance
│       │   ├── feature_engineering.py      # Features tecnicas
│       │   ├── explainability.py           # Analisis de factores
│       │   ├── news_service.py             # Noticias + sentimiento
│       │   └── demo_data.py                # Datos de respaldo (fallback sin BD)
│       └── data/
└── frontend/
    ├── Dockerfile                          # Multi-etapa: builder + runner standalone
    ├── next.config.js                      # output: standalone
    ├── package.json
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx                    # Dashboard principal + badge version
        │   └── globals.css
        ├── components/
        │   ├── NextUpdateCountdown.tsx     # Cuenta regresiva al dia 12 + mini prediccion
        │   ├── FuelPriceCards.tsx          # Tarjetas de precios actuales
        │   ├── WtiTracker.tsx             # Seguimiento del WTI
        │   ├── HistoricalChart.tsx         # Grafico historico
        │   ├── PredictionChart.tsx         # Grafico de prediccion
        │   ├── PredictionSummary.tsx       # Resumen + detalle 2 capas
        │   ├── BandSimulator.tsx           # Simulador de bandas
        │   ├── BandHistory.tsx             # Historial ajustes
        │   ├── AnalysisPanel.tsx           # Analisis de factores
        │   ├── ModelComparison.tsx         # Comparacion de modelos
        │   ├── ModelMetrics.tsx            # Metricas
        │   ├── NewsPanel.tsx               # Noticias
        │   └── Sigla.tsx                   # Tooltips educativos
        └── lib/
            ├── api.ts                      # Cliente API + fetchAppInfo()
            └── types.d.ts                  # Tipos TypeScript
```

---

## Base de datos

### Esquema (PostgreSQL 16)

| Tabla | Descripcion | Registros |
|-------|-------------|-----------|
| `fuel_prices` | Precios historicos mensuales (dia 11) por combustible | ~280+ registros (Jul 2020 - presente) |
| `wti_daily` | Precios diarios del WTI | ~1,413 registros (Ene 2021 - Jun 2026) |
| `predictions` | Historial de predicciones con precision calculable | Crece con cada prediccion |
| `news_cache` | Cache de noticias con sentimiento (expira en 24h) | Se llena al consultar /api/news |
| `wti_predictions` | Predicciones del WTI (Capa 1) | Se llena con predicciones two_layer |

### Respaldo de la base de datos

Los respaldos se guardan en la carpeta `backups/`:

```bash
# Crear respaldo (formato comprimido)
docker exec gaspredict-postgres pg_dump -U gaspredict -d gaspredict -F c \
  -f /var/lib/postgresql/data/backup.dump
docker cp gaspredict-postgres:/var/lib/postgresql/data/backup.dump backups/

# Restaurar desde respaldo
docker exec -i gaspredict-postgres pg_restore -U gaspredict -d gaspredict \
  backups/gaspredict_backup_YYYYMMDD_HHMMSS.dump
```

---

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/` | Info de la app + version actual |
| GET | `/api/prices/current` | Precios vigentes de los 4 combustibles |
| GET | `/api/prices/historical` | Historico mensual desde 2020 |
| GET | `/api/prices/fetch` | Scraping automatico de precios desde noticias |
| POST | `/api/prices/register` | Registrar precios manualmente |
| GET | `/api/wti` | Precio WTI actual + historico diario |
| POST | `/api/predict` | Prediccion (two_layer o ensemble) |
| POST | `/api/band/simulate` | Simular sistema de bandas con WTI dado |
| GET | `/api/band/history` | Historial de cambios |
| GET | `/api/analysis` | Analisis de factores que afectan el precio |
| GET | `/api/news` | Noticias de combustibles + sentimiento |
| GET | `/api/predictions/history` | Historial de predicciones y su precision |

### Ejemplo de prediccion

```bash
curl -X POST http://localhost:8001/api/predict \
  -H "Content-Type: application/json" \
  -d '{"fuel_type": "extra", "months": 3, "approach": "two_layer"}'
```

Respuesta incluye:
- `layer_1_wti`: WTI predicho, IC 95%, modelos individuales, pesos, metricas, blend aplicado
- `layer_2_formula`: Desglose de la formula (CIF, transporte, margenes, IVA)
- `predictions`: Precio final con banda aplicada por mes
- `confidence_interval`: Limites inferior y superior

---

## Instalacion con Docker (recomendado)

### Requisitos previos
- **Docker Desktop** con Docker Compose

### Levantar los 3 servicios

```bash
git clone https://github.com/XQ-98/gasolina_predict.git
cd gasolina_predict
docker compose up -d
```

Esto levanta automaticamente:

| Servicio | URL | Puerto |
|----------|-----|--------|
| Frontend (Next.js) | http://localhost:3001 | 3001 |
| Backend (FastAPI) | http://localhost:8001 | 8001 |
| API Docs (Swagger) | http://localhost:8001/docs | 8001 |
| PostgreSQL | localhost:5436 | 5436 |

Al iniciar, el backend automaticamente:
1. Crea las 5 tablas en PostgreSQL
2. Carga los datos historicos de precios (seed)
3. Descarga recursos NLTK para analisis de sentimiento
4. Programa la obtencion automatica de precios para el dia 12 a las 8am (hora Ecuador)

### Detener servicios

```bash
# Detener (datos se conservan)
docker compose stop

# Eliminar contenedores y volumenes (BORRA datos)
docker compose down -v
```

---

## Instalacion sin Docker

### Requisitos
- **Python** 3.11+
- **Node.js** 20+
- **PostgreSQL** 16 (opcional, funciona sin BD)

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001

# Frontend (en otra terminal)
cd frontend
npm install
npm run build
npm run start -- -p 3001
```

---

## Datos historicos incluidos

El sistema incluye datos reales de precios de combustibles en Ecuador desde **julio 2020** hasta la fecha, incluyendo:

- Precios mensuales de Extra, EcoPais, Super 95 y Diesel
- **1,413 registros diarios de WTI** (enero 2021 - junio 2026)
- Hitos clave:
  - Jul 2020: Inicio del sistema de bandas (Decreto 1054)
  - Jun 2024: Eliminacion del subsidio a Extra/EcoPais (Decreto 308)
  - Sep 2025: Eliminacion del subsidio al diesel (Decreto 126)
  - Dic 2025: Diesel entra al sistema de bandas (Decreto 242)
  - Jun 2026: Acuerdo de paz EE.UU.-Iran, reapertura Estrecho de Ormuz, WTI cae a ~$80

---

## Marco regulatorio

Este proyecto implementa la logica del **Decreto Ejecutivo No. 308** (junio 2024) que establece:

1. **Banda asimetrica**: techo +5% / piso -10% mensual
2. **Calculo dias 1-10**: EP Petroecuador calcula basado en costos de importacion del periodo
3. **Publicacion dia 11** (noche): EP Petroecuador publica los nuevos precios
4. **Vigencia dia 12**: nuevos precios rigen en todas las gasolineras del pais
5. **Super 95 excluida**: tiene precio libre de mercado
6. **Formula de precio**:
   ```
   Precio = Terminal(CIF + transporte + almacenamiento + margen EP
            + costo capital) * (1 + IVA 15%) + margen comercial * (1 + IVA 15%)
   ```

---

## Control de versiones y ramas

| Rama | Proposito | Politica |
|------|-----------|----------|
| `main` | Produccion estable | Solo merge via PR con aprobacion del propietario |
| `develop` | Desarrollo activo | Push libre, merge a main requiere PR aprobado |

---

## Glosario de siglas

| Sigla | Significado |
|-------|------------|
| **WTI** | West Texas Intermediate - precio de referencia del petroleo crudo en EE.UU. |
| **CIF** | Cost, Insurance and Freight - costo de importacion puesto en puerto ecuatoriano |
| **IC** | Intervalo de Confianza - rango donde se espera que caiga el precio real (95%) |
| **SARIMA** | Seasonal ARIMA - modelo estadistico de series temporales con estacionalidad |
| **LSTM** | Long Short-Term Memory - red neuronal para secuencias temporales |
| **MAPE** | Mean Absolute Percentage Error - error porcentual promedio del modelo |
| **RMSE** | Root Mean Square Error - raiz del error cuadratico medio |
| **MAE** | Mean Absolute Error - error absoluto promedio |
| **IVA** | Impuesto al Valor Agregado - 15% en Ecuador (desde abril 2024) |
| **EP** | Empresa Publica (Petroecuador) |
| **RON** | Research Octane Number - medida del octanaje de la gasolina |

---

## Autor

Desarrollado por **Xavier Quiroz** como proyecto de portafolio de Data Science y Machine Learning.

---

## Licencia

MIT License
