# GasPredict Ecuador

**Prediccion Inteligente de Precios de Combustibles en Ecuador**

Sistema de prediccion que utiliza Machine Learning y la formula oficial del gobierno ecuatoriano (Decreto Ejecutivo No. 308) para estimar los precios de gasolina y diesel que se publican el dia 11 de cada mes.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.18-orange?logo=tensorflow)
![XGBoost](https://img.shields.io/badge/XGBoost-2.1-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)

---

## Que hace este proyecto

En Ecuador, los precios de los combustibles (Extra, EcoPais, Diesel) se actualizan el **dia 11 de cada mes** mediante un sistema de bandas de precios regulado por el gobierno. Este sistema:

- Calcula un precio teorico basado en el costo de importacion del petroleo (WTI)
- Limita la subida a un maximo de **+5% mensual** (techo)
- Limita la bajada a un maximo de **-10% mensual** (piso)
- La gasolina Super 95 tiene precio libre (no esta regulada por bandas)

**GasPredict Ecuador** predice estos precios usando un enfoque de **2 capas**:

### Capa 1: Prediccion del WTI con datos diarios
- Entrena 3 modelos ML (SARIMA, XGBoost, LSTM) con **miles de datos diarios** del precio del petroleo WTI
- Predice el WTI promedio para los dias 1-10 del proximo mes
- Calcula un ensemble ponderado segun el desempeno de cada modelo

### Capa 2: Formula del Gobierno + Banda de precios
- Toma el WTI predicho y aplica la **formula exacta del Decreto 308**:
  - Costo de importacion (CIF) basado en el WTI
  - Costos de transporte y almacenamiento
  - Margen de EP Petroecuador
  - Costo de capital (tasa 10.78%)
  - IVA (15%)
  - Margen de comercializacion
- Aplica la **banda de precios**: techo +5% / piso -10% sobre el precio del mes anterior
- Resultado: precio estimado para el proximo dia 11

Este enfoque es mas preciso que predecir el precio del combustible directamente, porque separa la parte incierta (precio del petroleo) de la parte determinista (formula del gobierno).

---

## Combustibles cubiertos

| Combustible | Octanaje | Sistema de bandas | Precio actual (Mar 2026) |
|------------|----------|-------------------|--------------------------|
| Extra | RON 87 | Si (+5% / -10%) | $2.89/galon |
| EcoPais | RON 87 + etanol | Si (+5% / -10%) | $2.89/galon |
| Super 95 | RON 95 | No (precio libre) | $3.41/galon |
| Diesel Premium | - | Si (+5% / -10%) | $2.828/galon |

---

## Arquitectura

```
                    FRONTEND (Next.js 14 + React 18)
                              |
                         REST API
                              |
                    BACKEND (FastAPI + Python)
                         |         |
                    PostgreSQL   Yahoo Finance
                    (Docker)     (WTI en vivo)
                         |
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
  +---Ensemble----+                    +-----Precio Final----+
      ponderado                              dia 11
```

---

## Funcionalidades

### Dashboard
- **Cuenta regresiva** al proximo dia 11 con barra de progreso
- **Mini prediccion** para Extra, EcoPais y Diesel con probabilidad de subida/bajada
- **Panel expandible**: al hacer clic en un combustible muestra:
  - Explicacion en lenguaje natural de por que sube o baja
  - Paso 1: Prediccion del WTI (actual, predicho, IC 95%, pesos de modelos)
  - Paso 2: Desglose de la formula (CIF, transporte, margenes, IVA 15%)
  - Paso 3: Aplicacion de la banda con visualizacion grafica
- **Precios actuales** de los 4 combustibles con cambio vs mes anterior
- **Tracker del WTI** en tiempo real con sparkline y cambios 24h/7d/30d
- **Grafico historico** de todos los combustibles desde julio 2020
- **Noticias** de combustibles Ecuador con analisis de sentimiento
- **Tooltips educativos** en siglas tecnicas (WTI, CIF, IC, SARIMA, etc.)

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
- Tabla con todos los cambios del dia 11 desde julio 2020 (69 meses)
- Conteo de subidas vs bajadas
- Grafico de barras con cambios mensuales
- Filtro por tipo de combustible

### Base de datos (PostgreSQL)
- **Persistencia completa** de todos los datos en PostgreSQL 16 (Docker)
- **5 tablas**: precios historicos, WTI diario, predicciones, noticias, predicciones WTI
- **Seed automatico**: al iniciar, carga 69 meses de datos reales (276 registros)
- **Cache inteligente**: noticias se cachean por 24h, WTI diario se acumula
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
| **yfinance** | Datos del WTI desde Yahoo Finance |
| **NLTK** | Analisis de sentimiento de noticias |
| **Pandas/NumPy** | Procesamiento de datos |

### Frontend
| Tecnologia | Uso |
|-----------|-----|
| **Next.js 14** | Framework React con SSR |
| **TypeScript** | Tipado estatico |
| **Tailwind CSS** | Estilos utilitarios |
| **Plotly.js** | Graficos interactivos |
| **Lucide React** | Iconos |
| **date-fns** | Manejo de fechas |

### Infraestructura
| Tecnologia | Uso |
|-----------|-----|
| **Docker Compose** | Orquestacion de contenedores |
| **PostgreSQL 16** | Base de datos en contenedor (puerto 5436) |

---

## Estructura del proyecto

```
Prediccion_Gas/
├── README.md
├── .gitignore
├── docker-compose.yml                      # PostgreSQL 16 en Docker
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                         # FastAPI entry point
│       ├── config.py                       # Configuracion (tickers, bandas, formula, BD)
│       ├── api/
│       │   ├── routes.py                   # 9 endpoints REST
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
│       │   ├── wti_predictor.py            # Prediccion WTI diaria (Capa 1)
│       │   ├── two_layer_predictor.py      # Orquestador 2 capas
│       │   ├── band_calculator.py          # Formula Decreto 308 + bandas
│       │   ├── data_pipeline.py            # Datos historicos + Yahoo Finance
│       │   ├── feature_engineering.py      # Features tecnicas
│       │   ├── explainability.py           # Analisis de factores
│       │   ├── news_service.py             # Noticias + sentimiento
│       │   └── demo_data.py                # Datos de respaldo (fallback sin BD)
│       └── data/
└── frontend/
    ├── package.json
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx                    # Dashboard principal (4 pestanas)
        │   └── globals.css
        ├── components/
        │   ├── NextUpdateCountdown.tsx     # Cuenta regresiva + mini prediccion
        │   ├── FuelPriceCards.tsx           # Tarjetas de precios actuales
        │   ├── WtiTracker.tsx              # Seguimiento del WTI
        │   ├── HistoricalChart.tsx          # Grafico historico
        │   ├── PredictionChart.tsx          # Grafico de prediccion
        │   ├── PredictionSummary.tsx        # Resumen + detalle 2 capas
        │   ├── BandSimulator.tsx            # Simulador de bandas
        │   ├── BandHistory.tsx              # Historial dia 11
        │   ├── AnalysisPanel.tsx            # Analisis de factores
        │   ├── ModelComparison.tsx          # Comparacion de modelos
        │   ├── ModelMetrics.tsx             # Metricas
        │   ├── NewsPanel.tsx                # Noticias
        │   └── Sigla.tsx                    # Tooltips educativos
        └── lib/
            ├── api.ts                      # Cliente API con normalizacion
            └── types.d.ts                  # Tipos TypeScript
```

---

## Base de datos

### Esquema (PostgreSQL 16)

| Tabla | Descripcion | Registros iniciales |
|-------|-------------|---------------------|
| `fuel_prices` | Precios historicos mensuales (dia 11) por combustible | 276 (69 meses x 4 combustibles) |
| `wti_daily` | Precios diarios del WTI (se acumula automaticamente) | Se llena al consultar /api/wti |
| `predictions` | Historial de predicciones con precision calculable | Se llena al hacer predicciones |
| `news_cache` | Cache de noticias con sentimiento (expira en 24h) | Se llena al consultar /api/news |
| `wti_predictions` | Predicciones del WTI (Capa 1) | Se llena con predicciones two_layer |

### Diagrama de relaciones

```
fuel_prices (276 registros seed)
├── date + fuel_type (UNIQUE)
├── price, previous_price, change_percent
└── band_status (TECHO | PISO | DENTRO | LIBRE)

wti_daily (se acumula)
├── date (UNIQUE)
└── close_price, open, high, low, volume

predictions (historial)
├── fuel_type, approach, target_date
├── predicted_price, actual_price (se llena despues)
├── wti_predicted, wti_actual
├── accuracy_pct (calculable)
└── model_weights (JSON), confidence bounds

news_cache (cache 24h)
├── url (UNIQUE)
├── title, source, sentiment, score
└── fetched_at (para control de expiracion)

wti_predictions (Capa 1)
├── target_month
├── predicted_avg, actual_avg
├── sarima/xgboost/lstm predictions
└── weights (JSON), accuracy_pct
```

### Modo sin base de datos

Si PostgreSQL no esta disponible (contenedor detenido, sin Docker), el sistema **sigue funcionando** automaticamente:
- Los precios historicos se leen de `data_pipeline.py` (datos hardcodeados)
- El WTI se descarga directo de Yahoo Finance
- Las predicciones se calculan pero no se persisten
- Las noticias se obtienen en cada request sin cache

---

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/prices/current` | Precios vigentes de los 4 combustibles |
| GET | `/api/prices/historical` | Historico mensual (dia 11) desde 2020 |
| GET | `/api/wti` | Precio WTI actual + historico diario |
| POST | `/api/predict` | Prediccion (two_layer o ensemble) |
| POST | `/api/band/simulate` | Simular sistema de bandas con WTI dado |
| GET | `/api/band/history` | Historial de cambios del dia 11 |
| GET | `/api/analysis` | Analisis de factores que afectan el precio |
| GET | `/api/news` | Noticias de combustibles + sentimiento |
| GET | `/api/predictions/history` | Historial de predicciones pasadas y su precision |

### Ejemplo de prediccion

```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"fuel_type": "extra", "months": 3, "approach": "two_layer"}'
```

Respuesta incluye:
- `layer_1_wti`: WTI predicho, IC 95%, modelos individuales, pesos, metricas
- `layer_2_formula`: Desglose de la formula (CIF, transporte, margenes, IVA)
- `predictions`: Precio final con banda aplicada por mes
- `confidence_interval`: Limites inferior y superior

### Ejemplo de historial de predicciones

```bash
curl http://localhost:8000/api/predictions/history?fuel_type=extra&limit=10
```

Retorna predicciones pasadas con `predicted_price`, `actual_price` (si ya paso el dia 11) y `accuracy_pct`.

---

## Instalacion y ejecucion

### Requisitos previos
- **Python** 3.10+
- **Node.js** 18+
- **Docker** y **Docker Compose** (para PostgreSQL)

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/xavierquiroz1998/gasolina_predict.git
cd gasolina_predict
```

### Paso 2: Levantar PostgreSQL con Docker

```bash
docker compose up -d
```

Esto crea un contenedor `gaspredict_db` con:
- **Puerto**: 5436 (host) -> 5432 (contenedor)
- **Base de datos**: gaspredict
- **Usuario**: gaspredict
- **Password**: gaspredict2026
- **Volumen persistente**: los datos sobreviven reinicios del contenedor

Verificar que esta listo:
```bash
docker exec gaspredict_db pg_isready -U gaspredict -d gaspredict
# Debe mostrar: accepting connections
```

### Paso 3: Instalar y ejecutar el backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Al iniciar, el backend automaticamente:
1. Crea las 5 tablas en PostgreSQL
2. Carga los 276 registros de precios historicos (seed)
3. Descarga recursos NLTK para analisis de sentimiento

Verificar:
```bash
# API funcionando
curl http://localhost:8000/

# Documentacion interactiva
# Abrir http://localhost:8000/docs

# Verificar datos en BD
docker exec gaspredict_db psql -U gaspredict -d gaspredict \
  -c "SELECT count(*) FROM fuel_prices;"
# Debe mostrar: 276
```

### Paso 4: Instalar y ejecutar el frontend

```bash
cd frontend
npm install
npm run build
npm run start -- -p 3001
```

Abrir **http://localhost:3001** en el navegador.

### Resumen de servicios

| Servicio | URL | Puerto |
|----------|-----|--------|
| Frontend (Next.js) | http://localhost:3001 | 3001 |
| Backend (FastAPI) | http://localhost:8000 | 8000 |
| API Docs (Swagger) | http://localhost:8000/docs | 8000 |
| PostgreSQL | localhost:5436 | 5436 |

### Detener servicios

```bash
# Detener frontend y backend: Ctrl+C en sus terminales

# Detener PostgreSQL (datos se conservan)
docker compose stop

# Eliminar contenedor y volumen (BORRA datos)
docker compose down -v
```

---

## Ejecucion sin Docker (modo sin BD)

Si no tienes Docker instalado, el sistema funciona igualmente:

```bash
# Backend (sin PostgreSQL, usa datos en memoria)
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run build
npm run start -- -p 3001
```

El backend detecta automaticamente que PostgreSQL no esta disponible y usa los datos historicos hardcodeados en `data_pipeline.py`. Las predicciones funcionan igual, pero no se persisten entre reinicios.

---

## Datos historicos incluidos

El sistema incluye **69 meses de datos reales** de precios de combustibles en Ecuador (julio 2020 - marzo 2026), incluyendo:

- Precios mensuales de Extra, EcoPais, Super 95 y Diesel
- Hitos clave:
  - Jul 2020: Inicio del sistema de bandas (Decreto 1054)
  - Jun 2024: Eliminacion del subsidio a Extra/EcoPais (Decreto 308)
  - Sep 2025: Eliminacion del subsidio al diesel (Decreto 126)
  - Dic 2025: Diesel entra al sistema de bandas (Decreto 242)

---

## Marco regulatorio

Este proyecto implementa la logica del **Decreto Ejecutivo No. 308** (junio 2024) que establece:

1. **Banda asimetrica**: techo +5% / piso -10% mensual
2. **Calculo el dia 10**: EP Petroecuador calcula basado en costos de importacion
3. **Vigencia dia 11**: nuevos precios desde las 00:00 del dia 11
4. **Super 95 excluida**: tiene precio libre de mercado
5. **Formula de precio**:
   ```
   Precio = Terminal(CIF + transporte + almacenamiento + margen EP
            + costo capital) * (1 + IVA 15%) + margen comercial * (1 + IVA 15%)
   ```

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
