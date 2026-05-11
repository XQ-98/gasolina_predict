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
    # Calibrado con datos reales: Marzo 2026 WTI~$70 -> Extra=$2.89, Super=$3.41, Diesel=$2.828
    IMPORT_COST_WEIGHT: float = 1.00       # Peso del costo de importacion (incluido en WTI_TO_GALLON_FACTOR)
    TRANSPORT_COST: float = 0.12           # $/galon transporte
    STORAGE_COST: float = 0.05             # $/galon almacenamiento
    PETROECUADOR_MARGIN: float = 0.08      # $/galon margen EP Petroecuador
    COMMERCIAL_MARGIN: float = 0.128       # $/galon margen comercializacion
    CAPITAL_COST_RATE: float = 0.1078      # Tasa costo de capital (10.78% - D.E. 83)
    IVA_RATE: float = 0.15                 # 15% IVA Ecuador (desde abril 2024)

    # Factor de conversion WTI ($/barril) a $/galon base (CALIBRADO)
    # Calibrado inversamente: WTI=$70 -> import cost ~$1.90/galon -> Extra teorico $2.89
    # Anteriormente era 0.022*0.45=0.0099 (incorrecto, daba precios irreales)
    WTI_TO_GALLON_FACTOR: float = 0.0272   # Factor calibrado con datos reales 2024-2026

    # Factores de ajuste por tipo de combustible (CALIBRADOS con precios reales)
    FUEL_REFINING_FACTOR: dict = {
        "extra": 1.000,      # Base (RON 87) - calibrado a $2.89 con WTI=$70
        "ecopais": 1.000,    # Mismo precio que Extra (mezcla con etanol)
        "super_95": 1.214,   # Mayor octanaje (RON 95) - calibrado a $3.41 con WTI=$70
        "diesel": 0.974,     # Calibrado a $2.828 con WTI=$70 (post-eliminacion subsidio)
    }

    # Modelo HIBRIDO para Super 95 (precio libre, no usa formula del Decreto 308)
    # Regresion multiple calibrada con 34 meses de datos reales (jun-2023 a abr-2026)
    # Super = WTI_COEFF*WTI + TIME_COEFF*(meses_desde_jun2023) + INTERCEPT
    # MAPE=3.6% sobre ultimos 12 meses (mejor que lineal simple MAPE=7%)
    SUPER_95_WTI_COEFF: float = 0.016108    # impacto del WTI en precio
    SUPER_95_TIME_COEFF: float = 0.036084   # tendencia mensual estructural
    SUPER_95_INTERCEPT: float = 2.0587      # constante
    SUPER_95_BASE_MONTH: int = 34           # abr-2026 = mes 34 desde jun-2023
    # Coeficientes legacy (no usados)
    SUPER_95_SLOPE: float = 0.03314
    SUPER_95_COEFF_A: float = 0.0
    SUPER_95_COEFF_B: float = 0.0
    SUPER_95_COEFF_C: float = 0.0

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

    # Base de datos PostgreSQL
    DATABASE_URL: str = "postgresql://gaspredict:gaspredict2026@localhost:5436/gaspredict"
    DB_ENABLED: bool = True  # Se pone False automaticamente si no hay conexion


settings = Settings()
