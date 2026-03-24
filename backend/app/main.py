"""Punto de entrada principal de la API GasPredict Ecuador.

Prediccion de precios de combustibles en Ecuador usando modelos de ML
con el sistema de bandas de precios del Decreto Ejecutivo No. 308.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

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


@app.on_event("startup")
async def startup_event():
    """Descarga recursos de NLTK necesarios para analisis de sentimiento."""
    try:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        nltk.download("punkt", quiet=True)
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
