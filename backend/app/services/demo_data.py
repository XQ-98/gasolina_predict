"""Generador de datos de demostracion para GasPredict Ecuador.

Se usa como fallback cuando no hay conexion a Yahoo Finance.
Genera datos simulados del WTI, Brent y Dollar Index basados en rangos
historicos reales. Tambien genera predicciones demo respetando el sistema de bandas.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate_wti_prices(years: int = 6) -> pd.DataFrame:
    """Genera precios simulados del WTI con patrones realistas.

    Rango tipico del WTI 2020-2026:
    - 2020: $20-$45 (crisis COVID)
    - 2021: $50-$80 (recuperacion)
    - 2022: $75-$120 (guerra Ucrania)
    - 2023: $65-$90 (estabilizacion)
    - 2024-2026: $65-$85 (rango moderado)

    Args:
        years: Anos de historia a generar.

    Returns:
        DataFrame con columnas: date, wti_close, wti_open, wti_high, wti_low, wti_volume
    """
    np.random.seed(42)

    end = datetime.now()
    start = end - timedelta(days=years * 365)
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)
    t = np.linspace(0, 1, n)

    # Construir curva base del WTI segun fases historicas
    end_year = 2026.22
    start_year = end_year - years
    price = np.zeros(n)

    for i in range(n):
        year = start_year + (end_year - start_year) * t[i]

        if year < 2020.3:
            base = 55 + 5 * np.sin(2 * np.pi * (year - 2020) * 4)
        elif year < 2020.5:
            # COVID crash
            progress = (year - 2020.3) / 0.2
            base = 55 - 30 * progress
        elif year < 2021.0:
            # Recuperacion
            progress = (year - 2020.5) / 0.5
            base = 25 + 30 * progress
        elif year < 2022.0:
            # Subida fuerte
            progress = (year - 2021.0)
            base = 55 + 30 * progress + 5 * np.sin(2 * np.pi * year * 3)
        elif year < 2022.5:
            # Pico por guerra Ucrania
            base = 95 + 15 * np.sin(2 * np.pi * (year - 2022) * 6)
        elif year < 2023.0:
            # Bajada post-pico
            progress = (year - 2022.5) / 0.5
            base = 95 - 15 * progress
        elif year < 2024.0:
            # Estabilizacion
            base = 78 + 8 * np.sin(2 * np.pi * (year - 2023) * 4)
        elif year < 2025.0:
            base = 75 + 6 * np.sin(2 * np.pi * (year - 2024) * 3)
        else:
            base = 72 + 5 * np.sin(2 * np.pi * (year - 2025) * 4)

        price[i] = base

    # Ruido diario
    noise = np.cumsum(np.random.normal(0, 0.3, n))
    noise = noise - noise.mean()
    price = price + noise
    price = np.clip(price, 18, 125)

    daily_vol = np.abs(np.random.normal(0, 0.012, n))
    df = pd.DataFrame({
        "date": dates[:n],
        "wti_open": price * (1 + np.random.normal(0, 0.003, n)),
        "wti_high": price * (1 + daily_vol),
        "wti_low": price * (1 - daily_vol),
        "wti_close": price,
        "wti_volume": np.random.randint(100000, 500000, n),
    })

    return df.sort_values("date").reset_index(drop=True)


def generate_brent_prices(years: int = 6) -> pd.DataFrame:
    """Genera datos simulados del Brent (tipicamente $3-5 mas que WTI).

    Args:
        years: Anos de historia a generar.

    Returns:
        DataFrame con columnas: date, brent_close
    """
    wti = generate_wti_prices(years)
    np.random.seed(99)

    brent_premium = 3.5 + np.random.normal(0, 0.5, len(wti))
    df = pd.DataFrame({
        "date": wti["date"],
        "brent_close": wti["wti_close"] + brent_premium,
    })

    return df


def generate_dollar_index(years: int = 6) -> pd.DataFrame:
    """Genera datos simulados del Dollar Index (rango 90-110).

    Args:
        years: Anos de historia a generar.

    Returns:
        DataFrame con columnas: date, dollar_index
    """
    np.random.seed(456)

    end = datetime.now()
    start = end - timedelta(days=years * 365)
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)
    t = np.linspace(0, 1, n)

    # Dollar Index oscila entre 90-110
    base = 100 + 5 * np.sin(2 * np.pi * t * 2)
    noise = np.cumsum(np.random.normal(0, 0.1, n))
    noise = noise - noise.mean()
    values = base + noise
    values = np.clip(values, 88, 115)

    return pd.DataFrame({
        "date": dates[:n],
        "dollar_index": values,
    })


def generate_demo_predictions(
    fuel_type: str,
    current_price: float,
    months: int = 3,
    band_system: bool = True,
) -> list[dict]:
    """Genera predicciones demo respetando el sistema de bandas.

    Simula predicciones realistas que respetan las reglas de las bandas
    asimetricas (+5% techo, -10% piso).

    Args:
        fuel_type: Tipo de combustible.
        current_price: Precio actual.
        months: Meses a predecir.
        band_system: Si el combustible esta sujeto al sistema de bandas.

    Returns:
        Lista de dicts con fecha, precio y estado de banda por mes.
    """
    np.random.seed(123)
    predictions = []
    prev_price = current_price
    base_date = datetime.now()

    for m in range(1, months + 1):
        # Generar cambio porcentual aleatorio realista
        # La mayoria de meses el cambio es pequeno (+/- 2%)
        raw_change_pct = np.random.normal(0.01, 0.025)
        theoretical = prev_price * (1 + raw_change_pct)

        if band_system:
            max_price = prev_price * 1.05
            min_price = prev_price * 0.90

            if theoretical > max_price:
                final_price = max_price
                status = "TECHO"
                capped = True
            elif theoretical < min_price:
                final_price = min_price
                status = "PISO"
                capped = True
            else:
                final_price = theoretical
                status = "DENTRO"
                capped = False
        else:
            final_price = theoretical
            max_price = None
            min_price = None
            status = "LIBRE"
            capped = False

        # Calcular fecha del proximo dia 11
        if base_date.month + m > 12:
            year = base_date.year + (base_date.month + m - 1) // 12
            month = (base_date.month + m - 1) % 12 + 1
        else:
            year = base_date.year
            month = base_date.month + m
        pred_date = datetime(year, month, 11)

        predictions.append({
            "date": pred_date.strftime("%Y-%m-%d"),
            "price": round(final_price, 3),
            "band_applied": capped,
            "band_status": status,
            "theoretical_price": round(theoretical, 3),
            "max_price": round(max_price, 3) if max_price else None,
            "min_price": round(min_price, 3) if min_price else None,
        })

        prev_price = final_price

    return predictions
