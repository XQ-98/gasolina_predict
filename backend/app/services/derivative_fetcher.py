"""Obtencion del precio de derivados refinados para la formula del Decreto 308.

El gobierno ecuatoriano NO usa el WTI crudo como referencia directa.
Usa el indicador Platts USGC (Costa del Golfo de EE.UU.) para:
  - Gasolina Extra/EcoPais: Platts USGC UNL 87 (gasolina 87 octanos)
  - Diesel: Platts USGC ULSD (Ultra Low Sulfur Diesel)

Aproximacion via futuros publicos (Yahoo Finance):
  - RB=F  -> RBOB Gasoline Futures ($/galon) ~ Platts USGC UNL 87
  - HO=F  -> Heating Oil / ULSD Futures ($/galon) ~ Platts USGC ULSD

Formula del Decreto 308 (simplificada):
  PPIn = PM_USGC_ajustado + Flete_USGC_Ecuador + Seguro(0.05%) + CK(10.78%) + Tarifa_ARCH
  donde PM_USGC = promedio de los ultimos 20 registros disponibles de Platts USGC

Nota: El precio CIF resultante ya esta en $/galon, NO hay que convertir desde $/barril.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Costos logisticos USGC -> Ecuador (Decreto 308, actualizado Aug 2025)
FLETE_USD_GAL = 0.085        # Flete tanker clean USGC -> Ecuador 38kt (promedio 20 registros)
SEGURO_RATE = 0.0005         # 0.05% sobre (PM + flete)
CAPITAL_COST_RATE = 0.1078   # 10.78% costo de capital ponderado (D.E. 83)
TARIFA_ARCH_GAL = 0.012      # Tarifa uso infraestructura hidrocarburifera
COMERCIAL_MARGIN_GAL = 0.128 # Margen de comercializacion con IVA
IVA_RATE = 0.15              # IVA 15% Ecuador

# Ajuste de calidad octanaje: Extra/EcoPais usan mezcla con etanol
# El indicador RBOB base es 84-85 octanos; Extra requiere ~87 RON
OCTANE_QUALITY_FACTOR = {
    "extra": 1.000,
    "ecopais": 0.998,   # ligeramente menor por contenido de etanol
    "diesel": 1.000,
}


def fetch_derivative_prices(days: int = 60) -> dict:
    """Obtiene precios recientes de RBOB (gasolina) y ULSD (diesel) de Yahoo Finance.

    Retorna el promedio de los ultimos 20 registros disponibles,
    replicando la metodologia del promedio Platts USGC del Decreto 308.

    Returns:
        Dict con:
          - rbob_avg_20: promedio 20 dias RBOB en $/galon
          - ulsd_avg_20: promedio 20 dias ULSD en $/galon
          - rbob_current: ultimo precio RBOB disponible
          - ulsd_current: ultimo precio ULSD disponible
          - source: "yfinance" | "fallback"
          - data_points: numero de registros usados
    """
    try:
        import yfinance as yf

        end = datetime.now()
        start = end - timedelta(days=days)

        rbob = yf.Ticker("RB=F").history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )
        ulsd = yf.Ticker("HO=F").history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )

        if rbob.empty or ulsd.empty:
            raise ValueError("DataFrames de derivados vacios")

        rbob_closes = rbob["Close"].dropna().values[-20:]
        ulsd_closes = ulsd["Close"].dropna().values[-20:]

        if len(rbob_closes) < 5 or len(ulsd_closes) < 5:
            raise ValueError(f"Pocos datos: RBOB={len(rbob_closes)}, ULSD={len(ulsd_closes)}")

        rbob_avg = float(np.mean(rbob_closes))
        ulsd_avg = float(np.mean(ulsd_closes))

        logger.info(
            "Derivados descargados — RBOB avg20: $%.4f/gal | ULSD avg20: $%.4f/gal (%d registros)",
            rbob_avg, ulsd_avg, min(len(rbob_closes), len(ulsd_closes)),
        )

        return {
            "rbob_avg_20": round(rbob_avg, 4),
            "ulsd_avg_20": round(ulsd_avg, 4),
            "rbob_current": round(float(rbob_closes[-1]), 4),
            "ulsd_current": round(float(ulsd_closes[-1]), 4),
            "source": "yfinance",
            "data_points": min(len(rbob_closes), len(ulsd_closes)),
        }

    except Exception as e:
        logger.warning("No se pudo obtener derivados de Yahoo Finance: %s. Usando fallback.", e)
        return _fallback_derivative_prices()


def _fallback_derivative_prices() -> dict:
    """Fallback: estima RBOB/ULSD desde el WTI de la BD local.

    Relaciones historicas empiricas (2024-2026):
      RBOB ~ WTI/42 * 1.18  (crack spread gasolina ~$0.35-0.45/gal sobre WTI/42)
      ULSD ~ WTI/42 * 1.22  (crack spread diesel  ~$0.40-0.55/gal sobre WTI/42)
    """
    wti_price = _get_wti_from_db()
    if wti_price is None:
        # Ultimo recurso: usar valores calibrados a junio 2026
        logger.warning("Sin WTI en BD, usando precios Platts de referencia jun-2026")
        return {
            "rbob_avg_20": 3.02,
            "ulsd_avg_20": 2.98,
            "rbob_current": 3.02,
            "ulsd_current": 2.98,
            "source": "hardcoded_jun2026",
            "data_points": 0,
        }

    rbob_est = round((wti_price / 42) * 1.18, 4)
    ulsd_est = round((wti_price / 42) * 1.22, 4)

    logger.info(
        "Derivados estimados desde WTI=$%.2f — RBOB est: $%.4f | ULSD est: $%.4f",
        wti_price, rbob_est, ulsd_est,
    )

    return {
        "rbob_avg_20": rbob_est,
        "ulsd_avg_20": ulsd_est,
        "rbob_current": rbob_est,
        "ulsd_current": ulsd_est,
        "source": "estimated_from_wti",
        "data_points": 1,
    }


def _get_wti_from_db() -> Optional[float]:
    """Lee el ultimo precio WTI de la BD local."""
    try:
        from app.config import settings as cfg
        if not cfg.DB_ENABLED:
            return None
        from app.database.connection import SessionLocal
        from app.database import crud
        db = SessionLocal()
        try:
            records = crud.get_wti_daily(db, days=10)
            if records:
                return float(records[-1]["close_price"])
        finally:
            db.close()
    except Exception as e:
        logger.debug("No se pudo leer WTI de BD: %s", e)
    return None


def calculate_cif_from_derivative(pm_usgc: float, fuel_type: str) -> float:
    """Calcula el precio CIF Ecuador desde el marcador Platts USGC.

    Implementa la formula del Decreto 308:
      PPIn = PM_ajustado + Flete + Seguro + CK + Tarifa

    Args:
        pm_usgc: Precio marcador Platts USGC en $/galon (RBOB o ULSD).
        fuel_type: Tipo de combustible para ajuste de calidad.

    Returns:
        Precio CIF en terminal ecuatoriano ($/galon), antes de IVA y margenes.
    """
    # Ajuste de calidad por octanaje
    quality_factor = OCTANE_QUALITY_FACTOR.get(fuel_type, 1.0)
    pm_adjusted = pm_usgc * quality_factor

    # Flete USGC -> Ecuador
    flete = FLETE_USD_GAL

    # Seguro: 0.05% sobre (PM + flete)
    seguro = (pm_adjusted + flete) * SEGURO_RATE

    # Subtotal CIF (precio puesto en terminal Ecuador)
    cif = pm_adjusted + flete + seguro

    # Costo de capital (10.78% anual sobre CIF)
    capital_cost = cif * CAPITAL_COST_RATE

    # Tarifa infraestructura ARCH
    tarifa = TARIFA_ARCH_GAL

    # Precio en terminal antes de IVA
    terminal_pre_iva = cif + capital_cost + tarifa

    return round(terminal_pre_iva, 4)


def calculate_final_price_from_derivative(pm_usgc: float, fuel_type: str) -> float:
    """Calcula el precio final al consumidor desde el marcador Platts USGC.

    Aplica la formula completa del Decreto 308 incluyendo IVA y margen
    de comercializacion.

    Args:
        pm_usgc: Precio marcador Platts USGC en $/galon.
        fuel_type: Tipo de combustible.

    Returns:
        Precio teorico final al consumidor ($/galon).
    """
    terminal_pre_iva = calculate_cif_from_derivative(pm_usgc, fuel_type)

    # IVA sobre precio terminal
    iva = terminal_pre_iva * IVA_RATE
    terminal_con_iva = terminal_pre_iva + iva

    # Margen de comercializacion (ya incluye IVA en la constante)
    precio_final = terminal_con_iva + COMERCIAL_MARGIN_GAL

    return round(max(precio_final, 0.50), 3)


def get_derivative_based_theoretical_price(fuel_type: str) -> dict:
    """Obtiene el precio teorico usando derivados refinados (indicador real del gobierno).

    Flujo completo:
      1. Descarga RBOB/ULSD de Yahoo Finance (promedio 20 registros)
      2. Aplica formula Decreto 308: PM_USGC + flete + seguro + CK + tarifa + IVA + margen
      3. Retorna precio teorico y todos los componentes

    Args:
        fuel_type: extra, ecopais, diesel, super_95

    Returns:
        Dict con precio_teorico, componentes de formula, fuente del dato.
    """
    deriv = fetch_derivative_prices()

    # Seleccionar marcador segun tipo de combustible
    if fuel_type in ("extra", "ecopais", "super_95"):
        pm_usgc = deriv["rbob_avg_20"]
        pm_current = deriv["rbob_current"]
        marker_name = "RBOB USGC (gasolina 87)"
        ticker = "RB=F"
    else:  # diesel
        pm_usgc = deriv["ulsd_avg_20"]
        pm_current = deriv["ulsd_current"]
        marker_name = "ULSD USGC (diesel)"
        ticker = "HO=F"

    quality_factor = OCTANE_QUALITY_FACTOR.get(fuel_type, 1.0)
    pm_adjusted = pm_usgc * quality_factor
    flete = FLETE_USD_GAL
    seguro = (pm_adjusted + flete) * SEGURO_RATE
    cif = pm_adjusted + flete + seguro
    capital_cost = cif * CAPITAL_COST_RATE
    tarifa = TARIFA_ARCH_GAL
    terminal_pre_iva = cif + capital_cost + tarifa
    iva = terminal_pre_iva * IVA_RATE
    terminal_con_iva = terminal_pre_iva + iva
    precio_final = round(max(terminal_con_iva + COMERCIAL_MARGIN_GAL, 0.50), 3)

    return {
        "theoretical_price": precio_final,
        "marker": marker_name,
        "ticker": ticker,
        "source": deriv["source"],
        "data_points": deriv["data_points"],
        "pm_usgc_avg20": round(pm_usgc, 4),
        "pm_usgc_current": round(pm_current, 4),
        "breakdown": {
            "pm_usgc_avg20": round(pm_usgc, 4),
            "quality_adjustment": round(quality_factor, 4),
            "pm_adjusted": round(pm_adjusted, 4),
            "flete_usgc_ecuador": round(flete, 4),
            "seguro": round(seguro, 4),
            "cif_terminal": round(cif, 4),
            "capital_cost_10_78pct": round(capital_cost, 4),
            "tarifa_arch": round(tarifa, 4),
            "terminal_pre_iva": round(terminal_pre_iva, 4),
            "iva_15pct": round(iva, 4),
            "terminal_con_iva": round(terminal_con_iva, 4),
            "margen_comercializacion": COMERCIAL_MARGIN_GAL,
            "precio_final_teorico": precio_final,
        },
    }
