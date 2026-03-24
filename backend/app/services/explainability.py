"""Motor de explicabilidad: analiza factores que influyen en el precio de combustibles.

Genera explicaciones en espanol sobre por que el precio sube o baja,
considerando el WTI, sistema de bandas, tendencias y eventos regulatorios.
"""

import numpy as np
import pandas as pd

from app.config import settings
from app.services.band_calculator import BandCalculator


band_calc = BandCalculator()


def analyze_price_factors(df: pd.DataFrame, fuel_type: str = "extra") -> dict:
    """Analiza los factores que influyen en el precio actual del combustible.

    Examina WTI, estado de bandas, tendencia, estacionalidad y eventos regulatorios
    para generar una explicacion completa.

    Args:
        df: DataFrame maestro con precios y WTI.
        fuel_type: Tipo de combustible a analizar.

    Returns:
        Diccionario con analisis completo de factores.
    """
    if len(df) < 3:
        return {"error": "No hay suficientes datos para el analisis."}

    fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
    fuel_name = fuel_config.get("name", fuel_type)

    current = df.iloc[-1]
    prev = df.iloc[-2]
    current_price = float(current["price"])
    prev_price = float(prev["price"])
    price_change = current_price - prev_price
    price_change_pct = (price_change / prev_price) * 100 if prev_price > 0 else 0

    factors = []

    # 1. Impacto del WTI (factor principal ~65%)
    wti_price = None
    wti_change_30d_pct = None
    if "wti_close" in df.columns:
        wti_current = float(current.get("wti_close", 0))
        wti_prev = float(prev.get("wti_close", 0))
        wti_change = wti_current - wti_prev
        wti_change_pct = (wti_change / wti_prev * 100) if wti_prev > 0 else 0
        wti_price = wti_current
        wti_change_30d_pct = round(wti_change_pct, 2)

        if len(df) >= 6:
            corr = df["price"].corr(df["wti_close"])
        else:
            corr = settings.WTI_CORRELATION.get(fuel_type, 0.7)

        wti_impact = "positivo" if wti_change > 0 else "negativo"
        factors.append({
            "factor": "Precio del WTI",
            "value": round(wti_current, 2),
            "impact": wti_impact,
            "weight": 0.65,
            "description": (
                f"El WTI {'subio' if wti_change > 0 else 'bajo'} "
                f"${abs(wti_change):.2f}/barril ({abs(wti_change_pct):.1f}%). "
                f"El petroleo es el factor principal (~65% del precio). "
                f"Correlacion historica: {corr:.2f}."
            ),
        })

    # 2. Estado del sistema de bandas (Decreto 308)
    has_band = fuel_config.get("band_system", True)
    band_analysis = {
        "has_band": has_band,
        "ceiling": settings.BAND_CEILING,
        "floor": settings.BAND_FLOOR,
        "next_update": band_calc.get_next_update_date(),
    }

    if has_band:
        max_price = prev_price * (1 + settings.BAND_CEILING)
        min_price = prev_price * (1 + settings.BAND_FLOOR)

        if current_price >= max_price * 0.98:
            band_desc = (
                f"El precio toco el TECHO de la banda (+5%). "
                f"Sin la banda, el precio seria mayor. "
                f"Maximo permitido: ${max_price:.3f}."
            )
            band_impact = "negativo"
        elif current_price <= min_price * 1.02:
            band_desc = (
                f"El precio toco el PISO de la banda (-10%). "
                f"Sin la banda, el precio seria menor. "
                f"Minimo permitido: ${min_price:.3f}."
            )
            band_impact = "positivo"
        else:
            band_desc = (
                f"El precio esta DENTRO de la banda. "
                f"Rango permitido: ${min_price:.3f} - ${max_price:.3f}."
            )
            band_impact = "neutral"

        factors.append({
            "factor": "Sistema de Bandas (Decreto 308)",
            "value": round(current_price, 3),
            "impact": band_impact,
            "weight": 0.20,
            "description": band_desc,
        })

    # 3. Tendencia acumulada (ultimos 6 meses)
    if len(df) >= 6:
        prices_6m = df["price"].tail(6)
        trend_pct = ((prices_6m.iloc[-1] - prices_6m.iloc[0]) / prices_6m.iloc[0]) * 100
        trend_dir = "alcista" if trend_pct > 0 else "bajista"
        factors.append({
            "factor": "Tendencia (6 meses)",
            "value": f"{trend_pct:+.1f}%",
            "impact": "positivo" if trend_pct > 1 else ("negativo" if trend_pct < -1 else "neutral"),
            "weight": 0.10,
            "description": (
                f"El {fuel_name} acumula una tendencia {trend_dir} de "
                f"{abs(trend_pct):.1f}% en los ultimos 6 meses."
            ),
        })

    # 4. Estacionalidad
    month = current["Date"].month if hasattr(current["Date"], "month") else pd.to_datetime(current["Date"]).month
    month_names = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    high_demand = month in [12, 1, 2, 7, 8]
    factors.append({
        "factor": "Estacionalidad",
        "value": month_names.get(month, str(month)),
        "impact": "positivo" if high_demand else "neutral",
        "weight": 0.05,
        "description": (
            f"Mes de {month_names.get(month, str(month))}. "
            + ("Temporada de alta demanda (vacaciones/feriados)." if high_demand
               else "Demanda tipica para este periodo del anio.")
        ),
    })

    # 5. Dollar Index
    if "dollar_index" in df.columns:
        dollar_current = float(current.get("dollar_index", 0))
        dollar_prev = float(prev.get("dollar_index", 0))
        if dollar_prev > 0 and dollar_current > 0:
            dollar_change_pct = ((dollar_current - dollar_prev) / dollar_prev) * 100
            if abs(dollar_change_pct) > 0.5:
                factors.append({
                    "factor": "Indice del Dolar",
                    "value": round(dollar_current, 2),
                    "impact": "negativo" if dollar_change_pct > 0 else "positivo",
                    "weight": 0.05,
                    "description": (
                        f"El indice del dolar {'subio' if dollar_change_pct > 0 else 'bajo'} "
                        f"{abs(dollar_change_pct):.1f}%. Un dolar mas fuerte tiende a "
                        f"{'encarecer' if dollar_change_pct > 0 else 'abaratar'} los costos de importacion."
                    ),
                })

    # 6. Eventos regulatorios recientes
    date_val = pd.to_datetime(current["Date"])
    if date_val >= pd.Timestamp("2025-09-01") and fuel_type == "diesel":
        factors.append({
            "factor": "Reforma Diesel (Sep 2025)",
            "value": "Activa",
            "impact": "negativo",
            "weight": 0.15,
            "description": (
                "La eliminacion del subsidio al diesel (septiembre 2025) "
                "produjo un incremento significativo en el precio."
            ),
        })
    elif date_val >= pd.Timestamp("2024-07-01"):
        factors.append({
            "factor": "Decreto 308 (Jul 2024)",
            "value": "Activo",
            "impact": "neutral",
            "weight": 0.10,
            "description": (
                "El Decreto 308 establecio bandas asimetricas: "
                "techo +5%/mes, piso -10%/mes. Esto limita la volatilidad."
            ),
        })

    # Resumen
    direction = "subio" if price_change > 0 else "bajo"
    summary = (
        f"El {fuel_name} {direction} ${abs(price_change):.3f} "
        f"({abs(price_change_pct):.1f}%) respecto al mes anterior. "
        f"Se identificaron {len(factors)} factores relevantes."
    )

    current_prices = {}
    for fuel in ["extra", "ecopais", "super_95", "diesel"]:
        if fuel in current.index:
            current_prices[fuel] = round(float(current[fuel]), 3)

    return {
        "current_prices": current_prices,
        "wti_price": wti_price,
        "wti_change_30d_pct": wti_change_30d_pct,
        "band_analysis": band_analysis,
        "factors": factors,
        "summary": summary,
    }
