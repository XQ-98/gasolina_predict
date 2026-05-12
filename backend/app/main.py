"""Punto de entrada principal de la API GasPredict Ecuador.

Prediccion de precios de combustibles en Ecuador usando modelos de ML
con el sistema de bandas de precios del Decreto Ejecutivo No. 308.
"""

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API para prediccion del precio de combustibles en Ecuador. "
        "Implementa el sistema de bandas de precios (Decreto 308) con "
        "modelos SARIMA, XGBoost y LSTM en ensemble."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


def _scheduled_price_fetch():
    """Job del scheduler: obtiene precios del dia 12 y los guarda en la BD."""
    from app.services.price_scraper import fetch_latest_prices, save_fetched_prices
    from app.database.connection import SessionLocal
    from datetime import date

    logger.info("APScheduler: iniciando obtencion automatica de precios del dia 12")
    try:
        result = fetch_latest_prices()
        if result["success"] and result["prices"]:
            db = SessionLocal()
            try:
                price_date = date.fromisoformat(result["date"])
                # Usar el dia 11 del mes como fecha de vigencia
                price_date = price_date.replace(day=11)
                save_result = save_fetched_prices(result["prices"], price_date, db)
                logger.info(
                    "APScheduler: precios guardados exitosamente. Guardados=%s, Predicciones actualizadas=%s",
                    save_result["saved"],
                    save_result["predictions_updated"],
                )
            finally:
                db.close()
        else:
            logger.warning("APScheduler: no se obtuvieron precios. Mensaje: %s", result.get("message"))
    except Exception as e:
        logger.error("APScheduler: error en obtencion automatica de precios: %s", e, exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Inicializa recursos al arrancar: NLTK, base de datos y scheduler."""
    # Descargar recursos NLTK para analisis de sentimiento
    try:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        nltk.download("punkt", quiet=True)
    except Exception:
        pass

    # Inicializar base de datos PostgreSQL
    try:
        from app.database.init_db import init_database
        init_database()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.warning(f"No se pudo conectar a la BD: {e}. Usando modo sin BD.")
        settings.DB_ENABLED = False

    # Iniciar APScheduler: obtencion automatica el dia 12 a las 8am hora Ecuador (UTC-5 = 13:00 UTC)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import asyncio

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            _scheduled_price_fetch,
            CronTrigger(day=12, hour=13, minute=0, timezone="UTC"),  # 8am Ecuador (UTC-5)
            id="fetch_prices_day12",
            name="Obtencion automatica de precios dia 12",
            replace_existing=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("APScheduler iniciado: obtencion de precios programada para el dia 12 a las 8am Ecuador")
    except Exception as e:
        logger.warning("No se pudo iniciar APScheduler: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el scheduler al cerrar la aplicacion."""
    try:
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.shutdown(wait=False)
            logger.info("APScheduler detenido")
    except Exception:
        pass


@app.get("/")
async def root():
    """Informacion general de la API."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "descripcion": "Prediccion de precios de combustibles en Ecuador",
        "docs": "/docs",
        "combustibles": list(settings.FUEL_TYPES.keys()),
        "sistema_bandas": "Decreto Ejecutivo No. 308 - Bandas asimetricas (+5% / -10%)",
    }
