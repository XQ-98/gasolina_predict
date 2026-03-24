"""Feature engineering adaptado para prediccion de combustibles mensuales en Ecuador.

Features principales:
- Lags de precio: 1, 2, 3, 6, 12 meses
- Media movil del precio: 3, 6, 12 meses
- Cambio porcentual: 1, 3, 6 meses
- WTI: precio, cambio %, media movil
- Brent: precio, cambio %
- Dollar Index: valor, cambio %
- Temporal: mes del ano (sin/cos encoding), trimestre
- Band features: distancia al techo, distancia al piso, veces que toco techo
- Volatilidad WTI
- Dummies para eventos regulatorios
"""

import numpy as np
import pandas as pd

from app.config import settings


def add_price_features(df: pd.DataFrame, target_col: str = "price") -> pd.DataFrame:
    """Agrega features derivadas del precio del combustible.

    Incluye lags, medias moviles, cambios porcentuales y volatilidad.
    """
    df = df.copy()

    # Diferencia de precio mes a mes
    df["price_diff"] = df[target_col].diff()
    df["price_pct_change_1m"] = df[target_col].pct_change() * 100

    # Cambio porcentual a 3 y 6 meses
    df["price_pct_change_3m"] = df[target_col].pct_change(periods=3) * 100
    df["price_pct_change_6m"] = df[target_col].pct_change(periods=6) * 100

    # Lag features del precio (meses anteriores)
    for lag in [1, 2, 3, 6, 12]:
        if lag < len(df):
            df[f"lag_{lag}"] = df[target_col].shift(lag)

    # Media movil del precio
    for window in [3, 6, 12]:
        if window <= len(df):
            df[f"price_ma_{window}"] = df[target_col].rolling(window=window, min_periods=1).mean()
            df[f"price_ratio_ma_{window}"] = df[target_col] / df[f"price_ma_{window}"].replace(0, 1)

    # Volatilidad del precio (desviacion estandar rolling)
    if len(df) >= 6:
        df["price_volatility_6m"] = df[target_col].rolling(window=6, min_periods=3).std()
    else:
        df["price_volatility_6m"] = 0.0

    return df


def add_wti_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega features derivadas del WTI.

    El WTI es el factor principal (~65%) del precio de combustibles en Ecuador.
    """
    df = df.copy()

    if "wti_close" not in df.columns:
        return df

    # Cambio porcentual WTI
    df["wti_pct_change"] = df["wti_close"].pct_change() * 100

    # WTI del mes anterior
    df["wti_prev_month"] = df["wti_close"].shift(1)

    # Promedio WTI ultimos 3 y 6 meses
    df["wti_ma_3"] = df["wti_close"].rolling(window=3, min_periods=1).mean()
    df["wti_ma_6"] = df["wti_close"].rolling(window=6, min_periods=1).mean()
    df["wti_ma_12"] = df["wti_close"].rolling(window=12, min_periods=1).mean()

    # Tendencia WTI (pendiente de ultimos 6 meses)
    def calc_slope(series):
        if len(series.dropna()) < 3:
            return 0.0
        x = np.arange(len(series))
        valid = ~series.isna()
        if valid.sum() < 3:
            return 0.0
        coeffs = np.polyfit(x[valid], series[valid], 1)
        return coeffs[0]

    df["wti_trend"] = df["wti_close"].rolling(window=6, min_periods=3).apply(calc_slope, raw=False)

    # Volatilidad WTI
    df["wti_vol_3m"] = df["wti_close"].rolling(window=3, min_periods=2).std()

    # RSI del WTI (adaptado a datos mensuales, window=6)
    delta = df["wti_close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=6, min_periods=3).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6, min_periods=3).mean()
    rs = gain / loss.replace(0, 1e-10)
    df["wti_rsi"] = 100 - (100 / (1 + rs))
    df["wti_rsi"] = df["wti_rsi"].fillna(50)

    # Ratio precio/WTI (cuanto del precio de gasolina se explica por WTI)
    if "price" in df.columns:
        df["ratio_price_wti"] = df["price"] / df["wti_close"].replace(0, 1)

    return df


def add_brent_dollar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega features del Brent y Dollar Index."""
    df = df.copy()

    if "brent_close" in df.columns:
        df["brent_pct_change"] = df["brent_close"].pct_change() * 100
        df["brent_wti_spread"] = df.get("brent_close", 0) - df.get("wti_close", 0)

    if "dollar_index" in df.columns:
        df["dollar_pct_change"] = df["dollar_index"].pct_change() * 100
        df["dollar_ma_3"] = df["dollar_index"].rolling(window=3, min_periods=1).mean()

    return df


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega features temporales (estacionalidad mensual).

    Usa codificacion seno/coseno para capturar la ciclicidad del mes y trimestre.
    """
    df = df.copy()

    df["month"] = df["Date"].dt.month
    df["quarter"] = df["Date"].dt.quarter
    df["year"] = df["Date"].dt.year

    # Features ciclicos para capturar estacionalidad
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["quarter_sin"] = np.sin(2 * np.pi * df["quarter"] / 4)
    df["quarter_cos"] = np.cos(2 * np.pi * df["quarter"] / 4)

    return df


def add_event_dummies(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega variables dummy para eventos regulatorios importantes.

    Eventos clave:
    - Jul 2020: Inicio del sistema de bandas (Decreto 1054)
    - Jul 2022: Ajuste post-protestas
    - Nov 2023: Ajuste de precios
    - Jul 2024: Inicio de bandas asimetricas (Decreto 308)
    - Sep 2025: Eliminacion subsidio Diesel
    """
    df = df.copy()

    df["post_bandas_2020"] = (df["Date"] >= "2020-07-01").astype(int)
    df["post_protestas_2022"] = (df["Date"] >= "2022-07-01").astype(int)
    df["post_ajuste_2023"] = (df["Date"] >= "2023-11-01").astype(int)
    df["post_decreto_308"] = (df["Date"] >= "2024-07-01").astype(int)
    df["post_subsidio_diesel"] = (df["Date"] >= "2025-09-01").astype(int)

    return df


def add_band_features(df: pd.DataFrame, target_col: str = "price") -> pd.DataFrame:
    """Agrega features del estado del sistema de bandas.

    Incluye distancia al techo/piso, indicadores de proximidad y racha
    de subidas/bajadas consecutivas.
    """
    df = df.copy()

    pct_change = df[target_col].pct_change()

    # Distancia al techo (+5%) y piso (-10%) del mes anterior
    df["distance_to_ceiling"] = 0.05 - pct_change
    df["distance_to_floor"] = pct_change - (-0.10)

    # Indicador de proximidad al techo/piso
    df["near_ceiling"] = (pct_change >= 0.04).astype(int)
    df["near_floor"] = (pct_change <= -0.08).astype(int)

    # Del mes anterior
    df["prev_near_ceiling"] = df["near_ceiling"].shift(1).fillna(0).astype(int)
    df["prev_near_floor"] = df["near_floor"].shift(1).fillna(0).astype(int)

    # Veces que toco techo en los ultimos 6 meses
    df["ceiling_hits_6m"] = df["near_ceiling"].rolling(window=6, min_periods=1).sum()
    df["floor_hits_6m"] = df["near_floor"].rolling(window=6, min_periods=1).sum()

    # Meses consecutivos subiendo/bajando
    changes = df[target_col].diff()
    consecutive_up = []
    consecutive_down = []
    up_count = 0
    down_count = 0

    for i in range(len(df)):
        if i == 0 or pd.isna(changes.iloc[i]):
            up_count = 0
            down_count = 0
        elif changes.iloc[i] > 0.001:
            up_count += 1
            down_count = 0
        elif changes.iloc[i] < -0.001:
            down_count += 1
            up_count = 0
        else:
            up_count = 0
            down_count = 0

        consecutive_up.append(up_count)
        consecutive_down.append(down_count)

    df["consecutive_up"] = consecutive_up
    df["consecutive_down"] = consecutive_down

    return df


def prepare_features(df: pd.DataFrame, fuel_type: str = "extra") -> pd.DataFrame:
    """Pipeline completo de feature engineering para combustibles mensuales.

    Aplica todas las transformaciones de features en orden y limpia NaN.

    Args:
        df: DataFrame con Date, price, wti_close, etc.
        fuel_type: Tipo de combustible (para referencia, no se usa directamente aqui).

    Returns:
        DataFrame con todos los features generados, sin NaN.
    """
    target_col = "price"

    df = add_price_features(df, target_col)
    df = add_wti_features(df)
    df = add_brent_dollar_features(df)
    df = add_temporal_features(df)
    df = add_event_dummies(df)
    df = add_band_features(df, target_col)

    # Eliminar primeras filas con NaN generados por lags e indicadores
    min_required = 3
    df = df.iloc[min_required:].reset_index(drop=True)

    # Rellenar NaN restantes
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].bfill().ffill().fillna(0)

    return df
