"""Modelos SQLAlchemy para GasPredict Ecuador.

Define las tablas de la base de datos:
- fuel_prices: Precios historicos mensuales de combustibles (dia 11)
- wti_daily: Precios diarios del crudo WTI
- predictions: Historial de predicciones realizadas por el sistema
- news_cache: Cache de noticias con analisis de sentimiento
- wti_predictions: Predicciones del WTI (Capa 1 del sistema de 2 capas)
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    Date,
    DateTime,
    BigInteger,
    JSON,
    UniqueConstraint,
)

from app.database.connection import Base


class FuelPrice(Base):
    """Precios historicos mensuales de combustibles (actualizados el dia 11)."""

    __tablename__ = "fuel_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, comment="Dia 11 del mes correspondiente")
    fuel_type = Column(String(20), nullable=False, comment="extra, ecopais, super_95, diesel")
    price = Column(Float, nullable=False, comment="Precio en USD/galon")
    previous_price = Column(Float, nullable=True, comment="Precio del mes anterior")
    change_percent = Column(Float, nullable=True, comment="Porcentaje de cambio vs mes anterior")
    band_status = Column(String(10), nullable=True, comment="TECHO, PISO, DENTRO, LIBRE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "fuel_type", name="uq_fuel_price_date_type"),
    )

    def __repr__(self):
        return f"<FuelPrice {self.fuel_type} {self.date}: ${self.price}>"


class WtiDaily(Base):
    """Precios diarios del crudo WTI desde Yahoo Finance."""

    __tablename__ = "wti_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False, comment="Fecha del registro")
    close_price = Column(Float, nullable=False, comment="Precio de cierre USD/barril")
    open_price = Column(Float, nullable=True, comment="Precio de apertura")
    high = Column(Float, nullable=True, comment="Precio maximo del dia")
    low = Column(Float, nullable=True, comment="Precio minimo del dia")
    volume = Column(BigInteger, nullable=True, comment="Volumen de transacciones")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WtiDaily {self.date}: ${self.close_price}>"


class Prediction(Base):
    """Historial de predicciones realizadas por el sistema."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, comment="Cuando se genero la prediccion")
    fuel_type = Column(String(20), nullable=False, comment="Tipo de combustible predicho")
    approach = Column(String(20), nullable=False, comment="two_layer o ensemble")
    target_date = Column(Date, nullable=False, comment="Dia 11 objetivo de la prediccion")
    predicted_price = Column(Float, nullable=False, comment="Precio predicho USD/galon")
    actual_price = Column(Float, nullable=True, comment="Precio real (se llena cuando llega el dia 11)")
    wti_predicted = Column(Float, nullable=True, comment="WTI predicho para ese periodo")
    wti_actual = Column(Float, nullable=True, comment="WTI real (se llena despues)")
    band_status = Column(String(10), nullable=True, comment="Estado de banda aplicado")
    accuracy_pct = Column(Float, nullable=True, comment="Precision porcentual (se calcula despues)")
    model_weights = Column(JSON, nullable=True, comment="Pesos del ensemble usados")
    confidence_lower = Column(Float, nullable=True, comment="Limite inferior intervalo de confianza")
    confidence_upper = Column(Float, nullable=True, comment="Limite superior intervalo de confianza")

    def __repr__(self):
        return f"<Prediction {self.fuel_type} -> {self.target_date}: ${self.predicted_price}>"


class NewsCache(Base):
    """Cache de noticias sobre combustibles con analisis de sentimiento."""

    __tablename__ = "news_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="Titulo de la noticia")
    source = Column(String(200), nullable=True, comment="Fuente de la noticia")
    url = Column(String(1000), unique=True, nullable=False, comment="URL unica de la noticia")
    published_date = Column(DateTime, nullable=True, comment="Fecha de publicacion")
    sentiment = Column(String(20), nullable=False, comment="positivo, negativo, neutro")
    sentiment_score = Column(Float, nullable=True, comment="Score numerico del sentimiento")
    summary = Column(Text, nullable=True, comment="Resumen o descripcion de la noticia")
    fetched_at = Column(DateTime, default=datetime.utcnow, comment="Cuando se obtuvo la noticia")

    def __repr__(self):
        return f"<NewsCache '{self.title[:40]}...' ({self.sentiment})>"


class WtiPrediction(Base):
    """Predicciones del WTI generadas por la Capa 1 del sistema de 2 capas."""

    __tablename__ = "wti_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, comment="Cuando se genero la prediccion")
    target_month = Column(Date, nullable=False, comment="Primer dia del mes objetivo")
    predicted_avg = Column(Float, nullable=False, comment="Precio promedio predicho USD/barril")
    actual_avg = Column(Float, nullable=True, comment="Precio promedio real (se llena despues)")
    confidence_lower = Column(Float, nullable=True, comment="Limite inferior del intervalo")
    confidence_upper = Column(Float, nullable=True, comment="Limite superior del intervalo")
    sarima_prediction = Column(Float, nullable=True, comment="Prediccion individual SARIMA")
    xgboost_prediction = Column(Float, nullable=True, comment="Prediccion individual XGBoost")
    lstm_prediction = Column(Float, nullable=True, comment="Prediccion individual LSTM")
    weights = Column(JSON, nullable=True, comment="Pesos del ensemble")
    accuracy_pct = Column(Float, nullable=True, comment="Precision porcentual (se calcula despues)")

    def __repr__(self):
        return f"<WtiPrediction {self.target_month}: ${self.predicted_avg}>"
