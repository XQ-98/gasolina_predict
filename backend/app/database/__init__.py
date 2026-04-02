"""Modulo de base de datos para GasPredict Ecuador.

Proporciona conexion a PostgreSQL, modelos SQLAlchemy y funciones CRUD.
Si la base de datos no esta disponible, el sistema funciona sin ella.
"""

from app.database.connection import engine, SessionLocal, Base, get_db
from app.database.models import (
    FuelPrice,
    WtiDaily,
    Prediction,
    NewsCache,
    WtiPrediction,
)

__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "FuelPrice",
    "WtiDaily",
    "Prediction",
    "NewsCache",
    "WtiPrediction",
]
