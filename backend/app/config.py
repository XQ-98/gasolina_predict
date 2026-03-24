"""Configuracion central de la aplicacion GasPredict Ecuador."""

from pydantic import BaseModel


class Settings(BaseModel):
    """Configuracion de la aplicacion."""

    APP_NAME: str = "GasPredict Ecuador"
    APP_VERSION: str = "1.0.0"

    # Tickers de Yahoo Finance
    WTI_TICKER: str = "CL=F"              # Crudo WTI
    BRENT_TICKER: str = "BZ=F"            # Crudo Brent
    NATURAL_GAS_TICKER: str = "NG=F"      # Gas Natural (referencia)
    DOLLAR_INDEX_TICKER: str = "DX-Y.NYB"  # Indice del Dolar

    # Tipos de combustible ecuatorianos
    FUEL_TYPES: dict = {
        "extra": {
            "name": "Extra (RON 87)",
            "band_system": True,
            "max_increase": 0.05,   # +5% mensual maximo
            "max_decrease": -0.10,  # -10% mensual maximo
        },
        "ecopais": {
            "name": "Ecopais",
            "band_system": True,
            "max_increase": 0.05,
            "max_decrease": -0.10,
        },
        "super_95": {
            "name": "Super 95",
            "band_system": False,  # Precio libre, no esta en el sistema de bandas
            "max_increase": None,
            "max_decrease": None,
        },
        "diesel": {
            "name": "Diesel Premium",
            "band_system": True,
            "max_increase": 0.05,
            "max_decrease": -0.10,
        },
    }

    # Factores de la formula de precio del gobierno
    # Precio final = Precio en Terminal (con IVA) + Margen de Comercializacion (con IVA)
    IMPORT_COST_WEIGHT: float = 0.45       # Peso del costo de importacion sobre WTI
    TRANSPORT_COST: float = 0.12           # $/galon transporte
    STORAGE_COST: float = 0.05             # $/galon almacenamiento
    PETROECUADOR_MARGIN: float = 0.08      # $/galon margen EP Petroecuador
    COMMERCIAL_MARGIN: float = 0.128       # $/galon margen comercializacion
    CAPITAL_COST_RATE: float = 0.1078      # Tasa costo de capital
    IVA_RATE: float = 0.15                 # 15% IVA Ecuador

    # Factor de conversion WTI ($/barril) a $/galon base
    # 1 barril = 42 galones, pero el rendimiento en gasolina es ~45-50%
    WTI_TO_GALLON_FACTOR: float = 0.022    # Factor empirico para estimar costo/galon

    # Factores de ajuste por tipo de combustible (refinacion, octanaje, etc.)
    FUEL_REFINING_FACTOR: dict = {
        "extra": 1.00,       # Base
        "ecopais": 1.00,     # Similar a Extra (mezcla con etanol)
        "super_95": 1.25,    # Mayor octanaje, mas caro de refinar
        "diesel": 0.90,      # Menor costo de refinacion que gasolina
    }

    # Correlacion empirica WTI -> precio local
    WTI_CORRELATION: dict = {
        "extra": 0.72,
        "ecopais": 0.72,
        "super_95": 0.85,
        "diesel": 0.68,
    }

    # Parametros del sistema de bandas (Decreto 308)
    BAND_CEILING: float = 0.05    # +5% maximo mensual
    BAND_FLOOR: float = -0.10     # -10% maximo mensual
    PRICE_UPDATE_DAY: int = 11    # Dia del mes en que se actualizan precios

    # Datos
    DEFAULT_HISTORY_YEARS: int = 6          # Desde 2020
    DEFAULT_PREDICTION_MONTHS: int = 3
    BAND_START_DATE: str = "2020-07-01"     # Inicio del sistema de bandas

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]


settings = Settings()
