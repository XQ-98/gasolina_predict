"""Endpoints de la API GasPredict Ecuador.

Endpoints disponibles:
- GET  /api/prices/current      - Precios actuales de los 4 combustibles
- GET  /api/prices/historical   - Historico mensual (dia 11) desde 2020
- GET  /api/wti                 - Precio WTI actual + historico diario
- POST /api/predict             - Generar prediccion con ensemble
- POST /api/band/simulate       - Simular sistema de bandas con WTI dado
- GET  /api/band/history        - Historial de cambios del dia 11
- GET  /api/analysis            - Analisis de factores
- GET  /api/news                - Noticias de combustibles Ecuador
- GET  /api/predictions/history - Historial de predicciones realizadas

Todos los endpoints tienen fallback: si la BD no esta disponible,
funcionan con data_pipeline.py como fuente de datos.
"""

import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from app.api.schemas import (
    PredictionRequest,
    BandSimulationRequest,
)
from app.config import settings
from app.services.data_pipeline import (
    fetch_fuel_historical_prices,
    get_historical_as_dicts,
    get_current_prices as get_current_prices_pipeline,
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


def _get_db_or_none():
    """Dependency injection que retorna sesion de BD o None si no esta disponible."""
    if not settings.DB_ENABLED:
        yield None
        return

    try:
        from app.database.connection import SessionLocal
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    except Exception:
        yield None


def _get_fuel_current_price(fuel_type: str, db=None) -> float:
    """Obtiene el precio vigente actual de un combustible.

    Busca primero en la BD (ultimo precio en fuel_prices),
    si no hay BD usa data_pipeline como fallback.
    """
    if db is not None:
        try:
            from app.database.models import FuelPrice
            from sqlalchemy import desc
            latest = db.query(FuelPrice).filter(
                FuelPrice.fuel_type == fuel_type
            ).order_by(desc(FuelPrice.date)).first()
            if latest:
                return float(latest.price)
        except Exception:
            pass

    data = get_current_prices_pipeline()
    return data["fuels"].get(fuel_type, {}).get("price", 2.89)


@router.get("/prices/current")
async def get_current_price(
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Retorna los precios vigentes (ultimo dia 11) de todos los combustibles.

    Primero intenta leer de la BD. Si no hay datos, usa data_pipeline como fallback.
    Calcula el cambio vs mes anterior y determina si se aplico banda.
    """
    try:
        # Intentar leer de la BD
        if db is not None:
            try:
                from app.database import crud
                db_prices = crud.get_current_prices(db)
                if db_prices:
                    next_update = _band_calc.get_next_update_date()
                    prices = []
                    for p in db_prices:
                        fuel_key = p["fuel_type"]
                        fuel_config = settings.FUEL_TYPES.get(fuel_key, {})
                        prev = p.get("previous_price") or 0
                        curr = p["price"]
                        change = curr - prev if prev else 0
                        change_pct = (change / prev * 100) if prev > 0 else 0

                        prices.append({
                            "fuel_type": fuel_key,
                            "name": fuel_config.get("name", fuel_key),
                            "price": curr,
                            "previous_price": prev,
                            "change": round(change, 3),
                            "change_pct": round(change_pct, 2),
                            "band_system": fuel_config.get("band_system", True),
                            "band_status": p.get("band_status"),
                        })

                    return {
                        "date": db_prices[0]["date"],
                        "is_demo": False,
                        "prices": prices,
                        "next_update": next_update,
                    }
            except Exception as e:
                logger.warning("Error leyendo precios de BD: %s. Usando fallback.", e)

        # Fallback: data_pipeline
        data = get_current_prices_pipeline()
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
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Retorna el historico completo de precios mensuales (dia 11).

    Primero intenta leer de la BD. Si no hay datos, usa data_pipeline.
    Incluye precios de los 4 combustibles y WTI del mismo dia.
    """
    try:
        # Intentar leer de la BD
        if db is not None:
            try:
                from app.database import crud
                db_records = crud.get_historical_prices(db, years)
                if db_records:
                    # Agregar WTI a los registros de la BD
                    try:
                        wti_df = fetch_wti_data(years)
                        import pandas as pd
                        for record in db_records:
                            record_date = pd.Timestamp(record["date"])
                            mask = wti_df["date"] <= record_date
                            if mask.any():
                                record["wti"] = round(float(wti_df.loc[mask, "wti_close"].iloc[-1]), 2)
                            else:
                                record["wti"] = None
                    except Exception:
                        for record in db_records:
                            record["wti"] = None

                    return {
                        "count": len(db_records),
                        "currency": "USD",
                        "unit": "galon",
                        "update_day": settings.PRICE_UPDATE_DAY,
                        "data": db_records,
                    }
            except Exception as e:
                logger.warning("Error leyendo historico de BD: %s. Usando fallback.", e)

        # Fallback: data_pipeline
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
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Precio WTI actual + historico diario.

    Primero busca en la BD. Si faltan datos recientes, descarga de Yahoo Finance
    y guarda en la BD. Calcula cambios a 24h, 7d y 30d.
    """
    try:
        # Mapear periodo a anos y dias
        period_map = {"3mo": 1, "6mo": 1, "1y": 1, "2y": 2, "5y": 5}
        years = period_map.get(period, 1)
        days_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
        days = days_map.get(period, 365)

        df = None

        # Intentar leer de la BD y verificar si hay datos recientes
        if db is not None:
            try:
                from app.database import crud
                db_records = crud.get_wti_daily(db, days=days)
                latest_wti = crud.get_latest_wti(db)

                # Si hay datos pero faltan recientes (mas de 2 dias), descargar nuevos
                needs_refresh = True
                if latest_wti:
                    latest_date = datetime.strptime(latest_wti["date"], "%Y-%m-%d").date()
                    days_old = (date.today() - latest_date).days
                    needs_refresh = days_old > 2

                if needs_refresh:
                    # Descargar datos frescos y guardar en BD
                    df = fetch_wti_data(years=years)
                    if not df.empty:
                        wti_records = []
                        for _, row in df.iterrows():
                            wti_records.append({
                                "date": row["date"].date() if hasattr(row["date"], "date") else row["date"],
                                "close_price": float(row["wti_close"]),
                                "open_price": float(row["wti_open"]) if "wti_open" in row and not (isinstance(row.get("wti_open"), float) and row["wti_open"] != row["wti_open"]) else None,
                                "high": float(row["wti_high"]) if "wti_high" in row and not (isinstance(row.get("wti_high"), float) and row["wti_high"] != row["wti_high"]) else None,
                                "low": float(row["wti_low"]) if "wti_low" in row and not (isinstance(row.get("wti_low"), float) and row["wti_low"] != row["wti_low"]) else None,
                                "volume": int(row["wti_volume"]) if "wti_volume" in row and not (isinstance(row.get("wti_volume"), float) and row["wti_volume"] != row["wti_volume"]) else None,
                            })
                        try:
                            crud.save_wti_daily(db, wti_records)
                        except Exception as save_err:
                            logger.warning("Error guardando WTI en BD: %s", save_err)
                elif db_records:
                    # Usar datos de la BD (estan frescos)
                    import pandas as pd
                    df = pd.DataFrame(db_records)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.rename(columns={"close_price": "wti_close"})
                    df = df.sort_values("date").reset_index(drop=True)
            except Exception as e:
                logger.warning("Error con BD para WTI: %s. Descargando directo.", e)

        # Si no tenemos datos aun, descargar directo
        if df is None or (hasattr(df, "empty") and df.empty):
            df = fetch_wti_data(years=years)

        if df.empty:
            raise HTTPException(status_code=404, detail="No se obtuvieron datos del WTI")

        latest = df.iloc[-1]
        current_price = round(float(latest["wti_close"]), 2)
        current_date = latest["date"].strftime("%Y-%m-%d") if hasattr(latest["date"], "strftime") else str(latest["date"])

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

        # Historico resumido
        step = max(1, len(df) // 200)
        history = [
            {
                "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
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
async def predict_price(
    request: PredictionRequest,
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Genera prediccion de precios de combustibles.

    Dos enfoques disponibles:
    - 'two_layer' (default): Predice WTI con datos diarios -> aplica formula gobierno -> banda.
      Mas preciso porque usa miles de datos diarios y la formula determinista.
    - 'ensemble': ML directo sobre precios mensuales (69 puntos). Menos preciso.

    Si la BD esta disponible, guarda la prediccion en el historial.
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

            # Guardar prediccion en la BD
            _save_predictions_to_db(db, result, fuel_type, "two_layer")

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

            # Guardar prediccion en la BD
            _save_predictions_to_db(db, result, fuel_type, "ensemble")

            return result

        except Exception as e:
            logger.error("Error en prediccion ensemble: %s", e, exc_info=True)

    # ===== FALLBACK A DATOS DEMO =====
    try:
        from app.services.demo_data import generate_demo_predictions
        fuel_config = settings.FUEL_TYPES.get(request.fuel_type, {})

        current_price = _get_fuel_current_price(request.fuel_type, db)

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


def _save_predictions_to_db(db: Session, result: dict, fuel_type: str, approach: str):
    """Guarda las predicciones generadas en la base de datos.

    Extrae cada prediccion mensual del resultado y la persiste.
    Si la BD no esta disponible, no hace nada.
    """
    if db is None:
        return

    try:
        from app.database import crud

        predictions = result.get("predictions", [])
        weights = result.get("weights")
        confidence = result.get("confidence_interval", {})
        confidence_lower_list = confidence.get("lower", [])
        confidence_upper_list = confidence.get("upper", [])

        # Extraer WTI predicho si existe
        wti_predicted = None
        wti_data = result.get("wti_prediction", {})
        if isinstance(wti_data, dict):
            wti_predicted = wti_data.get("predicted_avg") or wti_data.get("predicted_price")

        # Solo guardar el primer mes (proximo ajuste real).
        # Los meses 2+ son extrapolaciones especulativas sin valor de seguimiento.
        if not predictions:
            return
        pred = predictions[0]
        target_date_str = pred.get("date", "")
        if not target_date_str:
            return

        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return

        predicted_price = pred.get("price", 0)
        band_status = pred.get("band_status")
        conf_lower = confidence_lower_list[0] if confidence_lower_list else None
        conf_upper = confidence_upper_list[0] if confidence_upper_list else None

        crud.save_prediction(
            db=db,
            fuel_type=fuel_type,
            approach=approach,
            target_date=target_date,
            predicted_price=predicted_price,
            wti_predicted=wti_predicted,
            band_status=band_status,
            model_weights=weights,
            confidence_lower=conf_lower,
            confidence_upper=conf_upper,
        )
    except Exception as e:
        logger.warning("Error guardando predicciones en BD: %s", e)


@router.post("/band/simulate")
async def simulate_band(
    request: BandSimulationRequest,
    db: Session = Depends(_get_db_or_none),
) -> dict:
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

        # Obtener precio actual del combustible (BD primero, luego pipeline)
        current_price = _get_fuel_current_price(fuel_type, db)

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
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Historial de todos los cambios del dia 11.

    Primero intenta leer de la BD. Si no hay datos, usa data_pipeline.
    Recorre el historico, calcula cambios y determina si se aplico
    banda en cada mes. Incluye estadisticas globales.
    """
    try:
        if fuel_type not in settings.FUEL_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de combustible invalido: {fuel_type}",
            )

        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})

        # Intentar leer de BD
        if db is not None:
            try:
                from app.database import crud
                db_records = crud.get_historical_prices(db, years=10)
                if db_records and len(db_records) > 1:
                    # Convertir al formato que espera analyze_band_history
                    result = _band_calc.analyze_band_history(db_records, fuel_type)
                    return {
                        "fuel_type": fuel_type,
                        "fuel_name": fuel_config.get("name", fuel_type),
                        "records": result["records"],
                        "stats": result["stats"],
                    }
            except Exception as e:
                logger.warning("Error leyendo historial de bandas de BD: %s. Usando fallback.", e)

        # Fallback: data_pipeline
        prices = get_historical_as_dicts()
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
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Noticias recientes sobre combustibles en Ecuador con analisis de sentimiento.

    Primero busca en el cache de la BD. Si el cache expiro (>24h),
    obtiene noticias frescas y las guarda en la BD.
    """
    try:
        # Intentar usar cache de BD
        if db is not None:
            try:
                from app.database import crud
                cached = crud.get_cached_news(db, hours=24)
                if cached:
                    articles = cached[:max_articles]
                    summary = get_sentiment_summary(articles)
                    return {
                        "articles": articles,
                        "sentiment_summary": summary,
                    }
            except Exception as e:
                logger.warning("Error leyendo cache de noticias: %s. Obteniendo frescas.", e)

        # Obtener noticias frescas
        articles = fetch_news(max_articles=max_articles, lang="es")
        summary = get_sentiment_summary(articles)

        # Guardar en cache de BD
        if db is not None and articles:
            try:
                from app.database import crud
                crud.save_news(db, articles)
            except Exception as e:
                logger.warning("Error guardando noticias en cache: %s", e)

        return {
            "articles": articles,
            "sentiment_summary": summary,
        }
    except Exception as e:
        logger.error("Error obteniendo noticias: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/history")
async def get_predictions_history(
    fuel_type: str = Query(default=None, description="Filtrar por tipo de combustible"),
    limit: int = Query(default=20, ge=1, le=100, description="Cantidad maxima de resultados"),
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Historial de predicciones realizadas por el sistema.

    Retorna las predicciones pasadas con su precision cuando esta disponible.
    Util para mostrar el track record del modelo.
    """
    if db is None:
        return {
            "message": "Base de datos no disponible. El historial de predicciones requiere PostgreSQL.",
            "predictions": [],
            "count": 0,
        }

    try:
        from app.database import crud
        predictions = crud.get_predictions_history(db, fuel_type=fuel_type, limit=limit)

        return {
            "predictions": predictions,
            "count": len(predictions),
            "fuel_type_filter": fuel_type,
        }
    except Exception as e:
        logger.error("Error obteniendo historial de predicciones: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predictions/update-actuals")
async def update_prediction_actuals(
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Actualiza predicciones pasadas con los precios reales.

    Busca predicciones cuya target_date ya paso y que no tienen actual_price,
    luego busca el precio real en la tabla fuel_prices y calcula la precision.
    """
    if db is None:
        return {"message": "Base de datos no disponible.", "updated": 0}

    try:
        from app.database.models import Prediction, FuelPrice
        from sqlalchemy import and_

        today = date.today()
        pending = db.query(Prediction).filter(
            and_(
                Prediction.actual_price.is_(None),
                Prediction.target_date <= today,
            )
        ).all()

        updated = 0
        for pred in pending:
            real = db.query(FuelPrice).filter(
                and_(
                    FuelPrice.date == pred.target_date,
                    FuelPrice.fuel_type == pred.fuel_type,
                )
            ).first()

            if real:
                pred.actual_price = real.price
                if pred.predicted_price > 0 and real.price > 0:
                    error_pct = abs(pred.predicted_price - real.price) / real.price * 100
                    pred.accuracy_pct = round(100 - error_pct, 2)
                updated += 1

        if updated > 0:
            db.commit()

        return {"updated": updated, "pending": len(pending) - updated}
    except Exception as e:
        logger.error("Error actualizando actuals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/scorecard")
async def get_predictions_scorecard(
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Scorecard completo: predicciones agrupadas por fecha con comparativa.

    Para cada target_date muestra los combustibles predichos,
    precio real (si disponible), precision y estadisticas globales.
    """
    if db is None:
        return {"message": "Base de datos no disponible.", "dates": [], "stats": {}}

    try:
        from app.database.models import Prediction, FuelPrice
        from sqlalchemy import and_

        records = db.query(Prediction).order_by(
            Prediction.target_date.desc(), Prediction.fuel_type
        ).all()

        # Cargar el precio vigente antes de cada target_date
        # Para predicciones verificadas: es el precio del mes anterior al target
        # Para predicciones futuras: es el ultimo precio conocido (el actual vigente)
        prev_prices_cache = {}
        for r in records:
            td = r.target_date
            ft = r.fuel_type
            key = (td, ft)
            if key not in prev_prices_cache:
                # Buscar el precio mas reciente ANTERIOR al target_date
                prev_fp = db.query(FuelPrice).filter(
                    and_(
                        FuelPrice.fuel_type == ft,
                        FuelPrice.date < td,
                    )
                ).order_by(FuelPrice.date.desc()).first()
                prev_prices_cache[key] = prev_fp.price if prev_fp else None

        dates_map = {}
        total_with_actual = 0
        total_correct = 0
        total_accuracy_sum = 0.0

        for r in records:
            td = r.target_date.isoformat() if r.target_date else "unknown"
            if td not in dates_map:
                dates_map[td] = {"target_date": td, "fuels": []}

            is_correct = None
            if r.actual_price and r.accuracy_pct is not None:
                total_with_actual += 1
                total_accuracy_sum += r.accuracy_pct
                is_correct = r.accuracy_pct >= 98.0
                if is_correct:
                    total_correct += 1

            prev_price = prev_prices_cache.get((r.target_date, r.fuel_type))

            dates_map[td]["fuels"].append({
                "fuel_type": r.fuel_type,
                "previous_price": prev_price,
                "predicted_price": r.predicted_price,
                "actual_price": r.actual_price,
                "accuracy_pct": r.accuracy_pct,
                "band_status": r.band_status,
                "wti_predicted": r.wti_predicted,
                "is_correct": is_correct,
                "predicted_at": r.created_at.isoformat() if r.created_at else None,
            })

        dates_list = list(dates_map.values())
        avg_accuracy = round(total_accuracy_sum / total_with_actual, 2) if total_with_actual > 0 else None
        hit_rate = round(total_correct / total_with_actual * 100, 1) if total_with_actual > 0 else None

        stats = {
            "total_predictions": len(records),
            "total_with_actual": total_with_actual,
            "total_pending": len(records) - total_with_actual,
            "total_correct": total_correct,
            "avg_accuracy_pct": avg_accuracy,
            "hit_rate_pct": hit_rate,
        }

        return {"dates": dates_list, "stats": stats}
    except Exception as e:
        logger.error("Error generando scorecard: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/check-prices")
async def check_new_prices(
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Verifica si ya salieron los precios del dia 11 y actualiza automaticamente.

    Este endpoint:
    1. Determina cual es el ultimo dia 11 (actual o pasado)
    2. Revisa si ya hay precios en fuel_prices para esa fecha
    3. Si NO hay, intenta buscarlos via scraping de fuentes publicas
    4. Si encuentra precios nuevos, los inserta y actualiza las predicciones
    """
    today = date.today()
    day_11 = date(today.year, today.month, 11)

    # Si estamos antes del 11, el ultimo dia 11 es del mes pasado
    if today < day_11:
        if today.month == 1:
            target = date(today.year - 1, 12, 11)
        else:
            target = date(today.year, today.month - 1, 11)
    else:
        target = day_11

    result = {
        "target_date": target.isoformat(),
        "today": today.isoformat(),
        "status": "unknown",
        "prices_found": False,
        "predictions_updated": 0,
        "prices": [],
    }

    if db is None:
        result["status"] = "db_unavailable"
        return result

    try:
        from app.database.models import FuelPrice, Prediction
        from sqlalchemy import and_

        # Verificar si ya existen precios para esta fecha
        existing = db.query(FuelPrice).filter(FuelPrice.date == target).all()

        if existing:
            result["status"] = "already_available"
            result["prices_found"] = True
            result["prices"] = [
                {
                    "fuel_type": r.fuel_type,
                    "price": r.price,
                    "previous_price": r.previous_price,
                    "change_pct": r.change_percent,
                    "band_status": r.band_status,
                }
                for r in existing
            ]

            # Verificar si hay predicciones sin actualizar
            pending = db.query(Prediction).filter(
                and_(
                    Prediction.target_date == target,
                    Prediction.actual_price.is_(None),
                )
            ).all()

            if pending:
                for pred in pending:
                    real = next((r for r in existing if r.fuel_type == pred.fuel_type), None)
                    if real:
                        pred.actual_price = real.price
                        if pred.predicted_price > 0 and real.price > 0:
                            error = abs(pred.predicted_price - real.price) / real.price * 100
                            pred.accuracy_pct = round(100 - error, 2)
                        result["predictions_updated"] += 1

                if result["predictions_updated"] > 0:
                    db.commit()
                    result["status"] = "predictions_updated"

            return result

        # No hay precios aun — verificar si ya deberian haber salido
        if today >= target:
            result["status"] = "awaiting_prices"
            result["message"] = (
                f"Los precios del {target.isoformat()} aun no estan registrados. "
                f"Puedes ingresarlos manualmente via POST /api/prices/register"
            )
        else:
            result["status"] = "future_date"
            result["message"] = f"El proximo ajuste es el {target.isoformat()}"

        return result

    except Exception as e:
        logger.error("Error verificando precios: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prices/register")
async def register_new_prices(
    prices: dict,
    db: Session = Depends(_get_db_or_none),
) -> dict:
    """Registra manualmente los precios nuevos del dia 11.

    Body: {"date": "2026-04-11", "extra": 3.024, "ecopais": 3.024, "super_95": 4.57, "diesel": 2.962}

    Automaticamente:
    - Calcula cambio porcentual vs mes anterior
    - Determina si se aplico banda
    - Actualiza predicciones pendientes con precision
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    try:
        from app.database.models import FuelPrice, Prediction
        from sqlalchemy import and_

        price_date = date.fromisoformat(prices.get("date", date.today().isoformat()))

        fuel_types = ["extra", "ecopais", "super_95", "diesel"]
        registered = []

        for ft in fuel_types:
            if ft not in prices:
                continue

            new_price = float(prices[ft])

            # Buscar precio anterior
            prev = db.query(FuelPrice).filter(
                and_(
                    FuelPrice.fuel_type == ft,
                    FuelPrice.date < price_date,
                )
            ).order_by(FuelPrice.date.desc()).first()

            prev_price = prev.price if prev else None
            change_pct = None
            band_status = None

            if prev_price and prev_price > 0:
                change_pct = round((new_price - prev_price) / prev_price * 100, 2)
                fuel_cfg = settings.FUEL_TYPES.get(ft, {})
                if fuel_cfg.get("band_system"):
                    if change_pct >= 4.9:
                        band_status = "TECHO"
                    elif change_pct <= -9.9:
                        band_status = "PISO"
                    else:
                        band_status = "DENTRO"
                else:
                    band_status = "LIBRE"

            # Upsert
            existing = db.query(FuelPrice).filter(
                and_(FuelPrice.date == price_date, FuelPrice.fuel_type == ft)
            ).first()

            if existing:
                existing.price = new_price
                existing.previous_price = prev_price
                existing.change_percent = change_pct
                existing.band_status = band_status
            else:
                db.add(FuelPrice(
                    date=price_date,
                    fuel_type=ft,
                    price=new_price,
                    previous_price=prev_price,
                    change_percent=change_pct,
                    band_status=band_status,
                ))

            registered.append({
                "fuel_type": ft,
                "price": new_price,
                "previous_price": prev_price,
                "change_pct": change_pct,
                "band_status": band_status,
            })

        db.commit()

        # Actualizar predicciones pendientes
        predictions_updated = 0
        pending = db.query(Prediction).filter(
            and_(
                Prediction.target_date == price_date,
                Prediction.actual_price.is_(None),
            )
        ).all()

        for pred in pending:
            actual = next((r for r in registered if r["fuel_type"] == pred.fuel_type), None)
            if actual:
                pred.actual_price = actual["price"]
                if pred.predicted_price > 0 and actual["price"] > 0:
                    error = abs(pred.predicted_price - actual["price"]) / actual["price"] * 100
                    pred.accuracy_pct = round(100 - error, 2)
                predictions_updated += 1

        if predictions_updated > 0:
            db.commit()

        return {
            "date": price_date.isoformat(),
            "registered": registered,
            "predictions_updated": predictions_updated,
        }
    except Exception as e:
        logger.error("Error registrando precios: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
