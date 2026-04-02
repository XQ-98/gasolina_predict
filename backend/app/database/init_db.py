"""Inicializacion de la base de datos de GasPredict Ecuador.

Crea todas las tablas definidas en los modelos SQLAlchemy y carga
los datos historicos iniciales de precios de combustibles.
"""

import logging

from app.database.connection import Base, engine, SessionLocal
from app.database.crud import seed_historical_prices

logger = logging.getLogger(__name__)


def init_database():
    """Crea todas las tablas y carga datos iniciales.

    1. Ejecuta CREATE TABLE IF NOT EXISTS para todos los modelos.
    2. Carga los datos historicos de precios si la tabla fuel_prices esta vacia.

    Esta funcion es segura para ejecutar multiples veces (idempotente).
    """
    # Importar modelos para que Base los registre
    import app.database.models  # noqa: F401

    # Crear tablas
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas de base de datos creadas/verificadas correctamente.")

    # Cargar datos historicos
    db = SessionLocal()
    try:
        seed_historical_prices(db)
    finally:
        db.close()
