"""Schemas Pydantic para la API GasPredict Ecuador."""

from pydantic import BaseModel, Field


# -- Precios actuales --

class FuelPrice(BaseModel):
    """Precio de un tipo de combustible."""
    fuel_type: str
    name: str
    price: float
    previous_price: float
    change: float
    change_pct: float
    band_system: bool
    band_status: str | None = None  # TECHO, PISO, DENTRO, N/A


class FuelPriceResponse(BaseModel):
    """Respuesta con precios actuales de todos los combustibles."""
    date: str
    is_demo: bool = False
    prices: list[FuelPrice]


# -- Historico --

class HistoricalRecord(BaseModel):
    """Registro historico de un mes (dia 11)."""
    date: str
    extra: float
    ecopais: float
    super_95: float
    diesel: float
    wti: float | None = None


class HistoricalPriceResponse(BaseModel):
    """Respuesta con precios historicos mensuales."""
    count: int
    data: list[HistoricalRecord]


# -- WTI --

class WtiChange(BaseModel):
    """Cambios del WTI en diferentes periodos."""
    change_24h: float | None = None
    change_24h_pct: float | None = None
    change_7d: float | None = None
    change_7d_pct: float | None = None
    change_30d: float | None = None
    change_30d_pct: float | None = None


class WtiDailyRecord(BaseModel):
    """Registro diario del WTI."""
    date: str
    price: float


class WtiDataResponse(BaseModel):
    """Respuesta con datos del WTI."""
    current_price: float
    date: str
    changes: WtiChange
    is_demo: bool = False
    historical: list[WtiDailyRecord]


# -- Prediccion --

class PredictionRequest(BaseModel):
    """Solicitud de prediccion."""
    fuel_type: str = Field(
        default="extra",
        description="Tipo de combustible: extra, ecopais, super_95, diesel",
    )
    months: int = Field(
        default=3, ge=1, le=12,
        description="Meses a predecir (1-12)",
    )
    approach: str = Field(
        default="two_layer",
        description="Enfoque: 'two_layer' (WTI diario + formula, mas preciso) o 'ensemble' (ML directo sobre precios mensuales)",
    )


class ConfidenceInterval(BaseModel):
    """Intervalo de confianza."""
    lower: list[float]
    upper: list[float]


class ModelMetrics(BaseModel):
    """Metricas de rendimiento de un modelo."""
    mse: float | None = None
    rmse: float | None = None
    mae: float | None = None
    mape: float | None = None
    error: str | None = None


class MonthlyPrediction(BaseModel):
    """Prediccion de un mes individual."""
    date: str
    price: float
    band_applied: bool
    band_status: str  # TECHO, PISO, DENTRO, LIBRE
    theoretical_price: float
    max_price: float | None = None
    min_price: float | None = None


class ModelPredictions(BaseModel):
    """Predicciones individuales de cada modelo."""
    sarima: list[float] | None = None
    xgboost: list[float] | None = None
    lstm: list[float] | None = None


class PredictionResponse(BaseModel):
    """Respuesta completa de prediccion."""
    fuel_type: str
    fuel_name: str
    current_price: float
    predictions: list[MonthlyPrediction]
    ensemble_prices: list[float]
    individual_predictions: ModelPredictions
    weights: dict[str, float]
    metrics: dict[str, ModelMetrics]
    confidence_interval: ConfidenceInterval
    is_demo: bool = False


# -- Simulacion de bandas --

class BandSimulationRequest(BaseModel):
    """Solicitud de simulacion de bandas."""
    wti_price: float = Field(
        description="Precio del WTI en USD/barril",
        ge=10.0, le=200.0,
    )
    fuel_type: str = Field(
        default="extra",
        description="Tipo de combustible",
    )


class FormulaBreakdown(BaseModel):
    """Desglose paso a paso de la formula de precio."""
    wti_price_barrel: float
    import_cost_gallon: float
    refining_adjustment: float
    transport_cost: float
    storage_cost: float
    petroecuador_margin: float
    capital_cost: float
    subtotal_before_iva: float
    iva_amount: float
    terminal_price_with_iva: float
    commercial_margin: float
    commercial_margin_iva: float
    theoretical_price: float


class BandSimulationResponse(BaseModel):
    """Respuesta de simulacion de bandas."""
    fuel_type: str
    fuel_name: str
    current_price: float
    wti_input: float
    theoretical_price: float
    max_price: float | None = None
    min_price: float | None = None
    final_price: float
    band_status: str  # TECHO, PISO, DENTRO, LIBRE
    band_applied: bool
    difference_vs_current: float
    difference_pct: float
    formula_breakdown: FormulaBreakdown


# -- Historial de bandas --

class BandChangeRecord(BaseModel):
    """Registro de cambio mensual en el dia 11."""
    date: str
    fuel_type: str
    price: float
    previous_price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    band_status: str | None = None  # TECHO, PISO, DENTRO


class BandHistoryStats(BaseModel):
    """Estadisticas del historial de bandas."""
    total_months: int
    increases: int
    decreases: int
    no_change: int
    times_ceiling_hit: int
    times_floor_hit: int
    max_price: float
    min_price: float
    avg_monthly_change_pct: float


class BandHistoryResponse(BaseModel):
    """Respuesta con historial de bandas."""
    fuel_type: str
    fuel_name: str
    records: list[BandChangeRecord]
    stats: BandHistoryStats


# -- Analisis --

class AnalysisFactor(BaseModel):
    """Factor que afecta el precio."""
    factor: str
    value: float | str | None = None
    impact: str  # positivo, negativo, neutral
    description: str
    weight: float | None = None


class AnalysisResponse(BaseModel):
    """Respuesta del analisis de factores."""
    current_prices: dict[str, float]
    wti_price: float | None = None
    wti_change_30d_pct: float | None = None
    band_analysis: dict
    factors: list[AnalysisFactor]
    summary: str


# -- Noticias --

class NewsSentiment(BaseModel):
    """Sentimiento de una noticia."""
    score: float
    label: str  # positivo, negativo, neutro
    impact: str  # alcista, bajista, neutral
    confidence: float


class NewsArticle(BaseModel):
    """Articulo de noticias."""
    title: str
    description: str
    source: str
    url: str
    published: str
    published_relative: str
    sentiment: NewsSentiment


class SentimentSummary(BaseModel):
    """Resumen del sentimiento de noticias."""
    overall_score: float
    overall_label: str
    signal: str
    distribution: dict[str, int]
    total_articles: int
    summary: str


class NewsResponse(BaseModel):
    """Respuesta con noticias y sentimiento."""
    articles: list[NewsArticle]
    sentiment_summary: SentimentSummary
