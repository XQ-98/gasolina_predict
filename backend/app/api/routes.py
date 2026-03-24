"""Endpoints de la API GasPredict Ecuador.

Endpoints disponibles:
- GET  /api/prices/current   - Precios actuales de los 4 combustibles
- GET  /api/prices/historical - Historico mensual (dia 11) desde 2020
- GET  /api/wti              - Precio WTI actual + historico diario
- POST /api/predict          - Generar prediccion con ensemble
- POST /api/band/simulate    - Simular sistema de bandas con WTI dado
- GET  /api/band/history     - Historial de cambios del dia 11
- GET  /api/analysis         - Analisis de factores
- GET  /api/news             - Noticias de combustibles Ecuador
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    PredictionRequest,
    BandSimulationRequest,
)
from app.config import settings
from app.services.data_pipeline import (
    fetch_fuel_historical_prices,
    get_historical_as_dicts,
    get_current_prices,
    fetch_wti_data,
    build_master_dataset,
    is_using_demo_data,
)
from app.services.band_calculator import BandCalculator
from app.services.explainability import analyze_price_factors
from app.services.news_service import fetch_news, get_sentiment_summary
from app.models.ensemble import EnsemblePredictor

logger = logging.getLogger(__name__)

router = APIRouter()

# Instancia del calculador de bandas
_band_calc = BandCalculator()

# Cache del modelo entrenado
_cached_ensemble: EnsemblePredictor | None = None
_cached_fuel_type: str | None = None


@router.get("/prices/current")
async def get_current_price() -> dict:
    """Retorna los precios vigentes (ultimo dia 11) de todos los combustibles.

    Calcula el cambio vs mes anterior y determina si se aplico banda.
    """
    try:
        data = get_current_prices()
        next_update = _band_calc.get_next_update_date()

        prices = []
        for fuel_key, fuel_data in data["fuels"].items():
            fuel_config = settings.FUEL_TYPES.get(fuel_key, {})

            # Determinar si se aplico banda
            prev = fuel_data["previous_price"]
            curr = fuel_data["price"]
            if fuel_config.get("band_system") and prev > 0:
                max_p = prev * 1.05
                min_p = prev * 0.90
                if curr >= max_p - 0.005:
                    band_status = "TECHO"
                elif curr <= min_p + 0.005:
                    band_status = "PISO"
                else:
                    band_status = "DENTRO"
            elif not fuel_config.get("band_system"):
                band_status = "LIBRE"
            else:
                band_status = None

            prices.append({
                "fuel_type": fuel_key,
                "name": fuel_data["name"],
                "price": fuel_data["price"],
                "previous_price": fuel_data["previous_price"],
                "change": fuel_data["change"],
                "change_pct": fuel_data["change_pct"],
                "band_system": fuel_config.get("band_system", True),
                "band_status": band_status,
            })

        return {
            "date": data["date"],
            "is_demo": False,
            "prices": prices,
            "next_update": next_update,
        }
    except Exception as e:
        logger.error("Error obteniendo precios actuales: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prices/historical")
async def get_historical_prices(
    years: int = Query(default=6, ge=1, le=10, description="Anos de historia"),
) -> dict:
    """Retorna el historico completo de precios mensuales (dia 11).

    Incluye precios de los 4 combustibles y WTI del mismo dia.
    """
    try:
        fuel_df = fetch_fuel_historical_prices()

        # Agregar WTI
        try:
            wti_df = fetch_wti_data(years)
            wti_values = []
            for fuel_date in fuel_df["date"]:
                mask = wti_df["date"] <= fuel_date
                if mask.any():
                    wti_values.append(round(float(wti_df.loc[mask, "wti_close"].iloc[-1]), 2))
                else:
                    wti_values.append(None)
            fuel_df["wti"] = wti_values
        except Exception:
            fuel_df["wti"] = None

        records = []
        for _, row in fuel_df.iterrows():
            records.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "extra": round(float(row["extra"]), 3),
                "ecopais": round(float(row["ecopais"]), 3),
                "super_95": round(float(row["super_95"]), 3),
                "diesel": round(float(row["diesel"]), 3),
                "wti": round(float(row["wti"]), 2) if row.get("wti") is not None and not (isinstance(row.get("wti"), float) and row["wti"] != row["wti"]) else None,
            })

        return {
            "count": len(records),
            "currency": "USD",
            "unit": "galon",
            "update_day": settings.PRICE_UPDATE_DAY,
            "data": records,
        }
    except Exception as e:
        logger.error("Error obteniendo historico: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wti")
async def get_wti_data(
    period: str = Query(default="1y", description="Periodo: 3mo, 6mo, 1y, 2y, 5y"),
) -> dict:
    """Precio WTI actual + historico diario.

    Calcula cambios a 24h, 7d y 30d.
    """
    try:
        # Mapear periodo a anos
        period_map = {"3mo": 1, "6mo": 1, "1y": 1, "2y": 2, "5y": 5}
        years = period_map.get(period, 1)
        df = fetch_wti_data(years=years)

        if df.empty:
            raise HTTPException(status_code=404, detail="No se obtuvieron datos del WTI")

        latest = df.iloc[-1]
        current_price = round(float(latest["wti_close"]), 2)
        current_date = latest["date"].strftime("%Y-%m-%d")

        # Calcular cambios
        changes = {}

        if len(df) >= 2:
            prev = df.iloc[-2]
            change_24h = current_price - float(prev["wti_close"])
            changes["change_24h"] = round(change_24h, 2)
            changes["change_24h_pct"] = round((change_24h / float(prev["wti_close"])) * 100, 2) if float(prev["wti_close"]) > 0 else 0

        if len(df) >= 5:
            prev_7d = df.iloc[-5]
            change_7d = current_price - float(prev_7d["wti_close"])
            changes["change_7d"] = round(change_7d, 2)
            changes["change_7d_pct"] = round((change_7d / float(prev_7d["wti_close"])) * 100, 2) if float(prev_7d["wti_close"]) > 0 else 0

        if len(df) >= 22:
            prev_30d = df.iloc[-22]
            change_30d = current_price - float(prev_30d["wti_close"])
            changes["change_30d"] = round(change_30d, 2)
            changes["change_30d_pct"] = round((change_30d / float(prev_30d["wti_close"])) * 100, 2) if float(prev_30d["wti_close"]) > 0 else 0

        # Historico resumido (cada 5 dias para no enviar demasiados datos)
        step = max(1, len(df) // 200)
        history = [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "price": round(float(row["wti_close"]), 2),
            }
            for _, row in df.iloc[::step].iterrows()
        ]

        return {
            "current_price": current_price,
            "date": current_date,
            "changes": changes,
            "is_demo": is_using_demo_data(),
            "historical": history,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error obteniendo WTI: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_price(request: PredictionRequest) -> dict:
    """Genera prediccion de precios de combustibles.

    Dos enfoques disponibles:
    - 'two_layer' (default): Predice WTI con datos diarios -> aplica formula gobierno -> banda.
      Mas preciso porque usa miles de datos diarios y la formula determinista.
    - 'ensemble': ML directo sobre precios mensuales (69 puntos). Menos preciso.
    """
    global _cached_ensemble, _cached_fuel_type

    fuel_type = request.fuel_type
    if fuel_type not in settings.FUEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de combustible invalido: {fuel_type}. "
                   f"Opciones: {list(settings.FUEL_TYPES.keys())}",
        )

    approach = getattr(request, "approach", "two_layer")

    # ===== ENFOQUE 2 CAPAS (default, mas preciso) =====
    if approach == "two_layer":
        try:
            from app.services.two_layer_predictor import TwoLayerPredictor

            predictor = TwoLayerPredictor()
            result = predictor.predict_multi_month(fuel_type, request.months)
            result["approach"] = "two_layer"
            logger.info("Prediccion 2 capas exitosa para %s", fuel_type)
            return result

        except Exception as e:
            logger.error(
                "Error en prediccion 2 capas para %s: %s", fuel_type, e, exc_info=True
            )
            # Fallthrough al ensemble como respaldo
            approach = "ensemble"

    # ===== ENFOQUE ENSEMBLE DIRECTO =====
    if approach == "ensemble":
        try:
            df = build_master_dataset(fuel_type)
            logger.info("Dataset construido: %d registros para %s", len(df), fuel_type)

            ensemble = EnsemblePredictor()
            ensemble.fit(df, fuel_type)
            _cached_ensemble = ensemble
            _cached_fuel_type = fuel_type

            result = ensemble.predict(request.months, fuel_type)
            result["approach"] = "ensemble"
            result["is_demo"] = is_using_demo_data()
            return result

        except Exception as e:
            logger.error("Error en prediccion ensemble: %s", e, exc_info=True)

    # ===== FALLBACK A DATOS DEMO =====
    try:
        from app.services.demo_data import generate_demo_predictions
        fuel_config = settings.FUEL_TYPES.get(request.fuel_type, {})

        data = get_current_prices()
        current_price = data["fuels"].get(request.fuel_type, {}).get("price", 2.89)

        demo_preds = generate_demo_predictions(
            fuel_type=request.fuel_type,
            current_price=current_price,
            months=request.months,
            band_system=fuel_config.get("band_system", True),
        )

        return {
            "fuel_type": request.fuel_type,
            "fuel_name": fuel_config.get("name", request.fuel_type),
            "current_price": current_price,
            "approach": "demo",
            "predictions": demo_preds,
            "ensemble_prices": [p["price"] for p in demo_preds],
            "individual_predictions": {"sarima": None, "xgboost": None, "lstm": None},
            "weights": {"sarima": 0.3, "xgboost": 0.4, "lstm": 0.3},
            "metrics": {},
            "confidence_interval": {
                "lower": [p["price"] * 0.97 for p in demo_preds],
                "upper": [p["price"] * 1.03 for p in demo_preds],
            },
            "is_demo": True,
        }
    except Exception as fallback_error:
        logger.error("Error en fallback demo: %s", fallback_error)
        raise HTTPException(status_code=500, detail="Error generando prediccion")


@router.post("/band/simulate")
async def simulate_band(request: BandSimulationRequest) -> dict:
    """Simula el sistema de bandas dado un precio WTI.

    Calcula el precio teorico basado en la formula del gobierno,
    aplica la banda y retorna el desglose completo.
    """
    try:
        fuel_type = request.fuel_type
        if fuel_type not in settings.FUEL_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de combustible invalido: {fuel_type}",
            )

        # Obtener precio actual del combustible
        data = get_current_prices()
        current_price = data["fuels"].get(fuel_type, {}).get("price", 2.89)

        result = _band_calc.simulate(
            wti_price=request.wti_price,
            current_price=current_price,
            fuel_type=fuel_type,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en simulacion de bandas: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/band/history")
async def get_band_history(
    fuel_type: str = Query(default="extra", description="Tipo de combustible"),
) -> dict:
    """Historial de todos los cambios del dia 11.

    Recorre el historico, calcula cambios y determina si se aplico
    banda en cada mes. Incluye estadisticas globales.
    """
    try:
        if fuel_type not in settings.FUEL_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de combustible invalido: {fuel_type}",
            )

        prices = get_historical_as_dicts()
        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})

        result = _band_calc.analyze_band_history(prices, fuel_type)

        return {
            "fuel_type": fuel_type,
            "fuel_name": fuel_config.get("name", fuel_type),
            "records": result["records"],
            "stats": result["stats"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error obteniendo historial de bandas: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def get_analysis(
    fuel_type: str = Query(default="extra", description="Tipo de combustible"),
) -> dict:
    """Analisis de factores que influyen en el precio actual.

    Examina WTI, bandas, tendencia, estacionalidad y eventos regulatorios.
    """
    try:
        if fuel_type not in settings.FUEL_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de combustible invalido: {fuel_type}",
            )

        df = build_master_dataset(fuel_type)
        analysis = analyze_price_factors(df, fuel_type)

        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])

        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en analisis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news")
async def get_news(
    max_articles: int = Query(default=15, ge=1, le=50),
) -> dict:
    """Noticias recientes sobre combustibles en Ecuador con analisis de sentimiento.

    Busca noticias RSS de Google News, El Universo, El Comercio, Primicias.
    """
    try:
        articles = fetch_news(max_articles=max_articles, lang="es")
        summary = get_sentiment_summary(articles)

        return {
            "articles": articles,
            "sentiment_summary": summary,
        }
    except Exception as e:
        logger.error("Error obteniendo noticias: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
