"""Funciones CRUD para la base de datos de GasPredict Ecuador.

Proporciona operaciones de lectura/escritura para todas las tablas:
- fuel_prices: Precios historicos de combustibles
- wti_daily: Precios diarios del WTI
- predictions: Historial de predicciones
- news_cache: Cache de noticias
- wti_predictions: Predicciones del WTI
"""

import logging
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import desc, func

from app.database.models import (
    FuelPrice,
    WtiDaily,
    Prediction,
    NewsCache,
    WtiPrediction,
)

logger = logging.getLogger(__name__)


# =====================================================================
# FUEL PRICES - Precios historicos de combustibles
# =====================================================================

def seed_historical_prices(db: Session):
    """Carga los datos historicos iniciales de precios si la tabla esta vacia.

    Importa los 69+ meses de datos reales desde data_pipeline.HISTORICAL_FUEL_PRICES
    y los inserta en la tabla fuel_prices. Solo ejecuta si la tabla tiene 0 registros.
    """
    count = db.query(func.count(FuelPrice.id)).scalar()
    if count > 0:
        logger.info("La tabla fuel_prices ya tiene %d registros. No se hace seed.", count)
        return

    from app.services.data_pipeline import HISTORICAL_FUEL_PRICES
    from app.config import settings

    fuel_types = ["extra", "ecopais", "super_95", "diesel"]
    records_to_insert = []

    for i, row in enumerate(HISTORICAL_FUEL_PRICES):
        date_str = row[0]
        prices = {"extra": row[1], "ecopais": row[2], "super_95": row[3], "diesel": row[4]}

        # Obtener precios del mes anterior para calcular cambio
        prev_prices = {}
        if i > 0:
            prev_row = HISTORICAL_FUEL_PRICES[i - 1]
            prev_prices = {"extra": prev_row[1], "ecopais": prev_row[2], "super_95": prev_row[3], "diesel": prev_row[4]}

        for fuel_type in fuel_types:
            price = prices[fuel_type]
            previous_price = prev_prices.get(fuel_type)
            change_pct = None
            band_status = None

            if previous_price is not None and previous_price > 0:
                change_pct = round(((price - previous_price) / previous_price) * 100, 2)

                # Determinar estado de banda
                fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
                if fuel_config.get("band_system"):
                    max_price = round(previous_price * 1.05, 3)
                    min_price = round(previous_price * 0.90, 3)
                    tolerance = 0.005
                    if price >= max_price - tolerance:
                        band_status = "TECHO"
                    elif price <= min_price + tolerance:
                        band_status = "PISO"
                    else:
                        band_status = "DENTRO"
                else:
                    band_status = "LIBRE"

            record = FuelPrice(
                date=datetime.strptime(date_str, "%Y-%m-%d").date(),
                fuel_type=fuel_type,
                price=price,
                previous_price=previous_price,
                change_percent=change_pct,
                band_status=band_status,
            )
            records_to_insert.append(record)

    db.bulk_save_objects(records_to_insert)
    db.commit()
    logger.info("Seed completado: %d registros insertados en fuel_prices.", len(records_to_insert))


def get_current_prices(db: Session) -> list:
    """Obtiene los precios mas recientes (ultimo dia 11) de todos los combustibles.

    Returns:
        Lista de dicts con fuel_type, price, previous_price, change_percent, band_status.
    """
    # Obtener la fecha mas reciente
    latest_date = db.query(func.max(FuelPrice.date)).scalar()
    if latest_date is None:
        return []

    prices = (
        db.query(FuelPrice)
        .filter(FuelPrice.date == latest_date)
        .all()
    )

    return [
        {
            "fuel_type": p.fuel_type,
            "price": p.price,
            "previous_price": p.previous_price,
            "change_percent": p.change_percent,
            "band_status": p.band_status,
            "date": p.date.isoformat(),
        }
        for p in prices
    ]


def get_historical_prices(db: Session, years: int = 6) -> list:
    """Obtiene el historico de precios de combustibles.

    Args:
        years: Cantidad de anos hacia atras a consultar.

    Returns:
        Lista de dicts agrupados por fecha con precios de los 4 combustibles.
    """
    cutoff_date = date.today() - timedelta(days=years * 365)

    prices = (
        db.query(FuelPrice)
        .filter(FuelPrice.date >= cutoff_date)
        .order_by(FuelPrice.date)
        .all()
    )

    # Agrupar por fecha
    grouped = {}
    for p in prices:
        date_key = p.date.isoformat()
        if date_key not in grouped:
            grouped[date_key] = {"date": date_key}
        grouped[date_key][p.fuel_type] = p.price

    return list(grouped.values())


def upsert_fuel_price(
    db: Session,
    price_date: date,
    fuel_type: str,
    price: float,
    previous_price: float = None,
    change_pct: float = None,
    band_status: str = None,
):
    """Inserta o actualiza un precio de combustible.

    Si ya existe un registro con la misma fecha y tipo de combustible,
    actualiza el precio y campos relacionados.
    """
    stmt = pg_insert(FuelPrice).values(
        date=price_date,
        fuel_type=fuel_type,
        price=price,
        previous_price=previous_price,
        change_percent=change_pct,
        band_status=band_status,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fuel_price_date_type",
        set_={
            "price": price,
            "previous_price": previous_price,
            "change_percent": change_pct,
            "band_status": band_status,
            "updated_at": datetime.utcnow(),
        },
    )
    db.execute(stmt)
    db.commit()


# =====================================================================
# WTI DAILY - Precios diarios del crudo WTI
# =====================================================================

def save_wti_daily(db: Session, data: list[dict]):
    """Guarda datos diarios del WTI en bulk. Ignora duplicados por fecha.

    Args:
        data: Lista de dicts con keys: date, close_price, open_price, high, low, volume.
    """
    if not data:
        return

    inserted = 0
    for row in data:
        stmt = pg_insert(WtiDaily).values(
            date=row["date"],
            close_price=row["close_price"],
            open_price=row.get("open_price"),
            high=row.get("high"),
            low=row.get("low"),
            volume=row.get("volume"),
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["date"])
        result = db.execute(stmt)
        if result.rowcount > 0:
            inserted += 1

    db.commit()
    logger.info("WTI diario: %d nuevos registros insertados de %d proporcionados.", inserted, len(data))


def get_wti_daily(db: Session, days: int = 365) -> list:
    """Obtiene los precios diarios del WTI de los ultimos N dias.

    Args:
        days: Cantidad de dias hacia atras a consultar.

    Returns:
        Lista de dicts con date, close_price, open_price, high, low, volume.
    """
    cutoff_date = date.today() - timedelta(days=days)

    records = (
        db.query(WtiDaily)
        .filter(WtiDaily.date >= cutoff_date)
        .order_by(WtiDaily.date)
        .all()
    )

    return [
        {
            "date": r.date.isoformat(),
            "close_price": r.close_price,
            "open_price": r.open_price,
            "high": r.high,
            "low": r.low,
            "volume": r.volume,
        }
        for r in records
    ]


def get_latest_wti(db: Session):
    """Obtiene el ultimo precio WTI conocido.

    Returns:
        Dict con date y close_price, o None si no hay datos.
    """
    record = (
        db.query(WtiDaily)
        .order_by(desc(WtiDaily.date))
        .first()
    )

    if record is None:
        return None

    return {
        "date": record.date.isoformat(),
        "close_price": record.close_price,
        "open_price": record.open_price,
        "high": record.high,
        "low": record.low,
    }


# =====================================================================
# PREDICTIONS - Historial de predicciones
# =====================================================================

def save_prediction(
    db: Session,
    fuel_type: str,
    approach: str,
    target_date: date,
    predicted_price: float,
    wti_predicted: float = None,
    band_status: str = None,
    model_weights: dict = None,
    confidence_lower: float = None,
    confidence_upper: float = None,
):
    """Guarda una prediccion realizada por el sistema.

    Args:
        db: Sesion de base de datos.
        fuel_type: Tipo de combustible predicho.
        approach: Enfoque usado (two_layer o ensemble).
        target_date: Dia 11 objetivo de la prediccion.
        predicted_price: Precio predicho en USD/galon.
        wti_predicted: Precio WTI predicho (opcional).
        band_status: Estado de banda aplicado (opcional).
        model_weights: Pesos del ensemble (opcional).
        confidence_lower: Limite inferior del intervalo (opcional).
        confidence_upper: Limite superior del intervalo (opcional).

    Returns:
        ID de la prediccion creada.
    """
    prediction = Prediction(
        fuel_type=fuel_type,
        approach=approach,
        target_date=target_date,
        predicted_price=predicted_price,
        wti_predicted=wti_predicted,
        band_status=band_status,
        model_weights=model_weights,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    logger.info(
        "Prediccion guardada: id=%d, %s %s -> $%.3f",
        prediction.id, fuel_type, target_date, predicted_price,
    )
    return prediction.id


def get_predictions_history(db: Session, fuel_type: str = None, limit: int = 20):
    """Obtiene el historial de predicciones realizadas.

    Args:
        fuel_type: Filtrar por tipo de combustible (opcional).
        limit: Cantidad maxima de resultados.

    Returns:
        Lista de dicts con los datos de cada prediccion.
    """
    query = db.query(Prediction).order_by(desc(Prediction.created_at))

    if fuel_type:
        query = query.filter(Prediction.fuel_type == fuel_type)

    records = query.limit(limit).all()

    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "fuel_type": r.fuel_type,
            "approach": r.approach,
            "target_date": r.target_date.isoformat() if r.target_date else None,
            "predicted_price": r.predicted_price,
            "actual_price": r.actual_price,
            "wti_predicted": r.wti_predicted,
            "wti_actual": r.wti_actual,
            "band_status": r.band_status,
            "accuracy_pct": r.accuracy_pct,
            "model_weights": r.model_weights,
            "confidence_lower": r.confidence_lower,
            "confidence_upper": r.confidence_upper,
        }
        for r in records
    ]


def update_prediction_actual(
    db: Session,
    prediction_id: int,
    actual_price: float,
    wti_actual: float = None,
):
    """Actualiza una prediccion con el precio real cuando se conoce.

    Calcula automaticamente la precision porcentual.

    Args:
        prediction_id: ID de la prediccion a actualizar.
        actual_price: Precio real observado.
        wti_actual: Precio WTI real (opcional).
    """
    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if prediction is None:
        logger.warning("Prediccion id=%d no encontrada para actualizar.", prediction_id)
        return

    prediction.actual_price = actual_price
    if wti_actual is not None:
        prediction.wti_actual = wti_actual

    # Calcular precision
    if prediction.predicted_price > 0 and actual_price > 0:
        error_pct = abs(prediction.predicted_price - actual_price) / actual_price * 100
        prediction.accuracy_pct = round(100 - error_pct, 2)

    db.commit()
    logger.info(
        "Prediccion id=%d actualizada: real=$%.3f, precision=%.1f%%",
        prediction_id, actual_price, prediction.accuracy_pct or 0,
    )


# =====================================================================
# NEWS CACHE - Cache de noticias
# =====================================================================

def save_news(db: Session, articles: list[dict]):
    """Guarda noticias en el cache. Ignora URLs duplicadas.

    Args:
        articles: Lista de dicts con title, source, url, published, sentiment, etc.
    """
    if not articles:
        return

    inserted = 0
    for article in articles:
        url = article.get("url", "")
        if not url:
            continue

        # Verificar si ya existe
        existing = db.query(NewsCache).filter(NewsCache.url == url).first()
        if existing:
            continue

        # Extraer datos de sentimiento
        sentiment_data = article.get("sentiment", {})
        sentiment_label = sentiment_data.get("label", "neutro") if isinstance(sentiment_data, dict) else "neutro"
        sentiment_score = sentiment_data.get("score", 0.0) if isinstance(sentiment_data, dict) else 0.0

        # Parsear fecha de publicacion
        published_date = None
        published_str = article.get("published", "")
        if published_str:
            try:
                published_date = datetime.fromisoformat(published_str)
            except (ValueError, TypeError):
                pass

        news = NewsCache(
            title=article.get("title", "")[:500],
            source=article.get("source", "")[:200] if article.get("source") else None,
            url=url[:1000],
            published_date=published_date,
            sentiment=sentiment_label,
            sentiment_score=sentiment_score,
            summary=article.get("description", ""),
        )
        db.add(news)
        inserted += 1

    db.commit()
    logger.info("Noticias: %d nuevas guardadas en cache de %d proporcionadas.", inserted, len(articles))


def get_cached_news(db: Session, hours: int = 24) -> list:
    """Obtiene noticias del cache si tienen menos de N horas.

    Args:
        hours: Cantidad de horas maxima de antiguedad del cache.

    Returns:
        Lista de dicts con datos de noticias, o lista vacia si el cache expiro.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # Verificar si hay noticias recientes
    recent_count = (
        db.query(func.count(NewsCache.id))
        .filter(NewsCache.fetched_at >= cutoff)
        .scalar()
    )

    if recent_count == 0:
        return []

    records = (
        db.query(NewsCache)
        .filter(NewsCache.fetched_at >= cutoff)
        .order_by(desc(NewsCache.published_date))
        .limit(50)
        .all()
    )

    return [
        {
            "title": r.title,
            "description": r.summary or "",
            "source": r.source or "",
            "url": r.url,
            "published": r.published_date.isoformat() if r.published_date else "",
            "published_relative": "",
            "sentiment": {
                "score": r.sentiment_score or 0.0,
                "label": r.sentiment,
                "impact": (
                    "alcista" if r.sentiment == "positivo"
                    else "bajista" if r.sentiment == "negativo"
                    else "neutral"
                ),
                "confidence": round(abs(r.sentiment_score or 0.0), 2),
            },
        }
        for r in records
    ]


# =====================================================================
# WTI PREDICTIONS - Predicciones del WTI (Capa 1)
# =====================================================================

def save_wti_prediction(
    db: Session,
    target_month: date,
    predicted_avg: float,
    confidence_lower: float = None,
    confidence_upper: float = None,
    sarima: float = None,
    xgboost: float = None,
    lstm: float = None,
    weights: dict = None,
):
    """Guarda una prediccion del WTI generada por la Capa 1.

    Args:
        db: Sesion de base de datos.
        target_month: Primer dia del mes objetivo.
        predicted_avg: Precio promedio predicho en USD/barril.
        confidence_lower: Limite inferior del intervalo.
        confidence_upper: Limite superior del intervalo.
        sarima: Prediccion individual del modelo SARIMA.
        xgboost: Prediccion individual del modelo XGBoost.
        lstm: Prediccion individual del modelo LSTM.
        weights: Pesos del ensemble usados.

    Returns:
        ID de la prediccion creada.
    """
    prediction = WtiPrediction(
        target_month=target_month,
        predicted_avg=predicted_avg,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        sarima_prediction=sarima,
        xgboost_prediction=xgboost,
        lstm_prediction=lstm,
        weights=weights,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    logger.info(
        "Prediccion WTI guardada: id=%d, mes=%s, avg=$%.2f",
        prediction.id, target_month, predicted_avg,
    )
    return prediction.id
