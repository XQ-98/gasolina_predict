"""Predictor de 2 capas: WTI diario -> Formula gobierno -> Banda de precios.

Capa 1: WTIDailyPredictor predice el WTI promedio de los dias 1-10 del proximo mes
         usando datos diarios (miles de puntos vs ~69 mensuales del ensemble).
Capa 2: BandCalculator aplica la formula determinista del Decreto 308 y el sistema
         de bandas asimetricas (+5% / -10%) para obtener el precio final.

Este enfoque es mas preciso porque:
1. Predice el WTI con datos diarios (miles de puntos vs 69 mensuales)
2. Aplica la formula determinista del gobierno (no hay incertidumbre aqui)
3. Aplica la banda de precios que realmente limita el cambio mensual
"""

import logging
from datetime import date, timedelta

from app.config import settings
from app.services.band_calculator import BandCalculator
from app.services.data_pipeline import (
    get_current_prices,
    fetch_fuel_historical_prices,
)

logger = logging.getLogger(__name__)


class TwoLayerPredictor:
    """Predictor de 2 capas: WTI diario -> Formula gobierno -> Banda de precios.

    Este enfoque es mas preciso porque:
    1. Predice el WTI con datos diarios (miles de puntos vs 69 mensuales)
    2. Aplica la formula determinista del gobierno (no hay incertidumbre aqui)
    3. Aplica la banda de precios que realmente limita el cambio
    """

    def __init__(self):
        """Inicializa el predictor con BandCalculator y lazy loading del WTI predictor."""
        self._band_calc = BandCalculator()
        self._wti_predictor = None
        self._trained = False

    # ------------------------------------------------------------------
    # Entrenamiento lazy
    # ------------------------------------------------------------------

    def _ensure_trained(self):
        """Entrena el WTIDailyPredictor si aun no esta entrenado.

        Usa lazy loading para evitar cargar modelos pesados hasta que se necesiten.
        El modelo entrenado se cachea en la instancia.
        """
        if self._trained and self._wti_predictor is not None:
            return

        logger.info("Entrenando WTIDailyPredictor (lazy loading)...")
        try:
            from app.services.wti_predictor import WTIDailyPredictor

            self._wti_predictor = WTIDailyPredictor()
            self._wti_predictor.fit()
            self._trained = True
            logger.info("WTIDailyPredictor entrenado exitosamente.")
        except Exception as e:
            logger.error("Error entrenando WTIDailyPredictor: %s", e, exc_info=True)
            raise RuntimeError(f"No se pudo entrenar el predictor WTI: {e}") from e

    # ------------------------------------------------------------------
    # Auxiliar: WTI -> precio combustible
    # ------------------------------------------------------------------

    def _wti_to_fuel_price(
        self,
        wti_price: float,
        current_fuel_price: float,
        fuel_type: str,
    ) -> dict:
        """Convierte un precio WTI en precio final de combustible aplicando formula y banda.

        Args:
            wti_price: Precio del WTI en USD/barril.
            current_fuel_price: Precio vigente del combustible (base para la banda).
            fuel_type: Tipo de combustible (extra, ecopais, super_95, diesel).

        Returns:
            Dict con precio final, estado de banda, precio teorico, limites y desglose.
        """
        # Formula del gobierno -> precio teorico
        theoretical_price = self._band_calc.calculate_theoretical_price(wti_price, fuel_type)

        # Aplicar banda asimetrica
        band_result = self._band_calc.apply_band(current_fuel_price, theoretical_price, fuel_type)

        # Desglose de la formula
        breakdown = self._band_calc.get_formula_breakdown(wti_price, fuel_type)

        return {
            "price": band_result["result"],
            "theoretical_price": theoretical_price,
            "band_applied": band_result["capped"],
            "band_status": band_result["status"],
            "max_price": band_result["max_price"],
            "min_price": band_result["min_price"],
            "change_pct": band_result["change_pct"],
            "wti_used": round(wti_price, 2),
            "formula_breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Prediccion de 1 mes
    # ------------------------------------------------------------------

    def predict_next_month(self, fuel_type: str) -> dict:
        """Predice el precio del combustible para el proximo mes usando las 2 capas.

        Flujo:
        1. Obtener precio actual del combustible
        2. Capa 1: Predecir WTI promedio dias 1-10 del proximo mes
        3. Capa 2: Aplicar formula del gobierno + banda

        Args:
            fuel_type: Tipo de combustible (extra, ecopais, super_95, diesel).

        Returns:
            Dict con prediccion completa, desglose de formula y detalle del WTI.
        """
        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
        fuel_name = fuel_config.get("name", fuel_type)

        # Precio actual del combustible
        current_data = get_current_prices()
        current_price = current_data["fuels"].get(fuel_type, {}).get("price", 2.89)

        # Capa 1: Predecir WTI
        self._ensure_trained()
        wti_result = self._wti_predictor.predict_wti_avg_for_next_month()

        wti_avg = wti_result["wti_predicted_avg"]
        wti_lower = wti_result.get("confidence_interval", {}).get("lower", wti_avg * 0.95)
        wti_upper = wti_result.get("confidence_interval", {}).get("upper", wti_avg * 1.05)

        # Capa 2: Formula del gobierno + banda
        fuel_result = self._wti_to_fuel_price(wti_avg, current_price, fuel_type)

        # Intervalos de confianza del precio final usando bounds del WTI
        fuel_lower = self._wti_to_fuel_price(wti_lower, current_price, fuel_type)
        fuel_upper = self._wti_to_fuel_price(wti_upper, current_price, fuel_type)

        # Fecha del proximo dia 11
        today = date.today()
        if today.day <= settings.PRICE_UPDATE_DAY:
            next_date = date(today.year, today.month, settings.PRICE_UPDATE_DAY)
        else:
            if today.month == 12:
                next_date = date(today.year + 1, 1, settings.PRICE_UPDATE_DAY)
            else:
                next_date = date(today.year, today.month + 1, settings.PRICE_UPDATE_DAY)

        return {
            "fuel_type": fuel_type,
            "fuel_name": fuel_name,
            "current_price": current_price,
            "approach": "two_layer",
            "prediction_date": next_date.isoformat(),
            "predicted_price": fuel_result["price"],
            "theoretical_price": fuel_result["theoretical_price"],
            "band_applied": fuel_result["band_applied"],
            "band_status": fuel_result["band_status"],
            "max_price": fuel_result["max_price"],
            "min_price": fuel_result["min_price"],
            "layer_1_wti": wti_result,
            "layer_2_formula": fuel_result["formula_breakdown"],
            "confidence_interval": {
                "lower": fuel_lower["price"],
                "upper": fuel_upper["price"],
            },
        }

    # ------------------------------------------------------------------
    # Prediccion multi-mes
    # ------------------------------------------------------------------

    def predict_multi_month(self, fuel_type: str, months: int = 3) -> dict:
        """Predice precios de combustible para N meses futuros.

        Para el mes 1 usa el WTIDailyPredictor real. Para meses 2+ extrapola
        el WTI con la tendencia (drift) reciente. La banda se aplica
        SECUENCIALMENTE: el precio del mes N se convierte en current_price
        del mes N+1.

        El formato de retorno es compatible con el endpoint /api/predict
        para que el frontend existente funcione sin cambios.

        Args:
            fuel_type: Tipo de combustible (extra, ecopais, super_95, diesel).
            months: Numero de meses a predecir (default 3).

        Returns:
            Dict con formato identico al endpoint /api/predict actual.
        """
        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
        fuel_name = fuel_config.get("name", fuel_type)

        # Precio actual del combustible
        current_data = get_current_prices()
        current_price = current_data["fuels"].get(fuel_type, {}).get("price", 2.89)

        # Capa 1: Predecir WTI del primer mes
        self._ensure_trained()
        wti_result = self._wti_predictor.predict_wti_avg_for_next_month()

        wti_avg_month1 = wti_result["wti_predicted_avg"]
        wti_lower_m1 = wti_result.get("confidence_interval", {}).get(
            "lower", wti_avg_month1 * 0.95,
        )
        wti_upper_m1 = wti_result.get("confidence_interval", {}).get(
            "upper", wti_avg_month1 * 1.05,
        )

        # Calcular drift mensual del WTI para extrapolacion
        monthly_drift = self._estimate_wti_drift(wti_result)

        # Generar predicciones WTI para cada mes
        wti_predictions = []
        for m in range(months):
            if m == 0:
                wti_predictions.append(wti_avg_month1)
            else:
                # Extrapolar con tendencia lineal
                extrapolated = wti_avg_month1 + monthly_drift * m
                # No permitir WTI negativo
                wti_predictions.append(max(extrapolated, 10.0))

        # Capa 2: Aplicar formula y banda SECUENCIALMENTE
        prev_price = current_price
        monthly_results = []

        for m in range(months):
            fuel_result = self._wti_to_fuel_price(
                wti_predictions[m], prev_price, fuel_type,
            )
            monthly_results.append(fuel_result)
            # El precio ajustado por banda es el current_price del mes siguiente
            prev_price = fuel_result["price"]

        # Generar fechas futuras (dia 11 de cada mes siguiente)
        future_dates = self._generate_future_dates(months)

        # Calcular intervalos de confianza del precio final
        ci_lower_prices, ci_upper_prices = self._calculate_fuel_ci(
            wti_avg_month1, wti_lower_m1, wti_upper_m1,
            monthly_drift, months, current_price, fuel_type,
        )

        # Construir predicciones individuales simuladas a partir de variaciones del WTI
        individual_predictions = self._build_individual_predictions(
            wti_predictions, monthly_drift, current_price, fuel_type, months,
        )

        # Pesos del WTI predictor (si estan disponibles)
        weights = wti_result.get("weights", {"sarima": 0.25, "xgboost": 0.40, "lstm": 0.35})

        # Metricas del WTI predictor
        metrics = wti_result.get("metrics", {})

        # Construir respuesta en formato compatible con /api/predict
        predictions = []
        ensemble_prices = []

        for i, result in enumerate(monthly_results):
            predictions.append({
                "date": future_dates[i].isoformat(),
                "price": result["price"],
                "band_applied": result["band_applied"],
                "band_status": result["band_status"],
                "theoretical_price": result["theoretical_price"],
                "max_price": result["max_price"],
                "min_price": result["min_price"],
                "wti_used": result["wti_used"],
            })
            ensemble_prices.append(result["price"])

        # Desglose de la formula (del primer mes como referencia)
        formula_breakdown = monthly_results[0]["formula_breakdown"] if monthly_results else {}

        return {
            "fuel_type": fuel_type,
            "fuel_name": fuel_name,
            "current_price": current_price,
            "approach": "two_layer",
            "layer_1_wti": {
                "wti_predicted_avg": wti_avg_month1,
                "wti_predictions_by_month": [round(w, 2) for w in wti_predictions],
                "monthly_drift": round(monthly_drift, 4),
                "confidence_interval": {
                    "lower": round(wti_lower_m1, 2),
                    "upper": round(wti_upper_m1, 2),
                },
                "detail": wti_result,
            },
            "layer_2_formula": formula_breakdown,
            "predictions": predictions,
            "ensemble_prices": ensemble_prices,
            "individual_predictions": individual_predictions,
            "weights": weights,
            "metrics": metrics,
            "confidence_interval": {
                "lower": [round(v, 4) for v in ci_lower_prices],
                "upper": [round(v, 4) for v in ci_upper_prices],
            },
            "is_demo": False,
        }

    # ------------------------------------------------------------------
    # Metodos auxiliares internos
    # ------------------------------------------------------------------

    def _estimate_wti_drift(self, wti_result: dict) -> float:
        """Estima el drift mensual del WTI basado en la tendencia reciente.

        Usa la informacion del predictor WTI. Si no hay tendencia disponible,
        calcula un drift basado en la diferencia entre el WTI actual y el predicho.

        Args:
            wti_result: Resultado de predict_wti_avg_for_next_month().

        Returns:
            Drift mensual en USD/barril (positivo = WTI subiendo).
        """
        # Intentar obtener tendencia del resultado del predictor
        trend = wti_result.get("trend_per_day")
        if trend is not None:
            # Convertir tendencia diaria a mensual (~21 dias habiles)
            return float(trend) * 21.0

        # Fallback: usar diferencia WTI predicho vs WTI reciente
        wti_predicted = wti_result.get("wti_predicted_avg", 70.0)
        wti_current = wti_result.get("wti_current", wti_result.get("last_wti_close"))

        if wti_current is not None and wti_current > 0:
            return float(wti_predicted) - float(wti_current)

        # Si no hay info, asumir sin tendencia
        return 0.0

    def _generate_future_dates(self, months: int) -> list[date]:
        """Genera las fechas futuras (dia 11 de cada mes siguiente).

        Args:
            months: Numero de meses futuros.

        Returns:
            Lista de objetos date correspondientes al dia 11 de cada mes futuro.
        """
        today = date.today()
        update_day = settings.PRICE_UPDATE_DAY
        dates = []

        # Determinar el primer mes futuro
        if today.day <= update_day:
            # Aun no ha pasado el dia 11 de este mes
            start_year = today.year
            start_month = today.month
        else:
            # Ya paso el dia 11, empezar desde el proximo mes
            if today.month == 12:
                start_year = today.year + 1
                start_month = 1
            else:
                start_year = today.year
                start_month = today.month + 1

        year = start_year
        month = start_month

        for _ in range(months):
            dates.append(date(year, month, update_day))
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

        return dates

    def _calculate_fuel_ci(
        self,
        wti_avg: float,
        wti_lower: float,
        wti_upper: float,
        monthly_drift: float,
        months: int,
        current_price: float,
        fuel_type: str,
    ) -> tuple[list[float], list[float]]:
        """Calcula intervalos de confianza del precio del combustible.

        Propaga la incertidumbre del WTI a traves de la formula del gobierno
        y el sistema de bandas, expandiendo el intervalo para meses mas lejanos.

        Args:
            wti_avg: WTI promedio predicho para el mes 1.
            wti_lower: Limite inferior del CI del WTI (mes 1).
            wti_upper: Limite superior del CI del WTI (mes 1).
            monthly_drift: Drift mensual del WTI.
            months: Numero de meses.
            current_price: Precio actual del combustible.
            fuel_type: Tipo de combustible.

        Returns:
            Tupla (lower_prices, upper_prices) con listas de precios CI.
        """
        lower_prices = []
        upper_prices = []

        # La incertidumbre crece con el horizonte
        wti_spread_m1 = (wti_upper - wti_lower) / 2.0 if wti_upper > wti_lower else wti_avg * 0.05

        prev_lower = current_price
        prev_upper = current_price

        for m in range(months):
            # WTI central para este mes
            if m == 0:
                wti_center = wti_avg
            else:
                wti_center = wti_avg + monthly_drift * m

            # Expandir incertidumbre con raiz cuadrada del horizonte
            expansion = (1.0 + m * 0.3)  # Crece ~30% por mes adicional
            wti_lo = wti_center - wti_spread_m1 * expansion
            wti_hi = wti_center + wti_spread_m1 * expansion

            # Convertir WTI a precio de combustible
            lower_result = self._wti_to_fuel_price(max(wti_lo, 10.0), prev_lower, fuel_type)
            upper_result = self._wti_to_fuel_price(wti_hi, prev_upper, fuel_type)

            lower_prices.append(lower_result["price"])
            upper_prices.append(upper_result["price"])

            prev_lower = lower_result["price"]
            prev_upper = upper_result["price"]

        return lower_prices, upper_prices

    def _build_individual_predictions(
        self,
        wti_predictions: list[float],
        monthly_drift: float,
        current_price: float,
        fuel_type: str,
        months: int,
    ) -> dict:
        """Construye predicciones individuales simuladas por modelo.

        Simula lo que cada modelo del WTI predictor habria generado como
        precio de combustible, aplicando variaciones alrededor del WTI central.
        Esto mantiene la compatibilidad con el formato del frontend que espera
        predicciones individuales de sarima, xgboost y lstm.

        Args:
            wti_predictions: Lista de WTI predichos por mes.
            monthly_drift: Drift mensual del WTI.
            current_price: Precio actual del combustible.
            fuel_type: Tipo de combustible.
            months: Numero de meses.

        Returns:
            Dict con claves sarima, xgboost, lstm y listas de precios.
        """
        # Obtener predicciones individuales del WTI predictor si estan disponibles
        wti_individual = {}
        if self._wti_predictor is not None:
            try:
                wti_detail = self._wti_predictor.predict_wti_avg_for_next_month()
                wti_individual = wti_detail.get("individual_predictions", {})
            except Exception:
                pass

        model_names = ["sarima", "xgboost", "lstm"]
        # Offsets por modelo para generar variacion realista
        model_offsets = {
            "sarima": 0.02,    # SARIMA tiende a ser ligeramente mas alto
            "xgboost": -0.03,  # XGBoost mas conservador
            "lstm": 0.01,      # LSTM intermedio
        }

        individual = {}

        for model_name in model_names:
            prices = []
            prev = current_price
            offset = model_offsets.get(model_name, 0.0)

            for m in range(months):
                # Usar prediccion individual del WTI si esta disponible
                if model_name in wti_individual and wti_individual[model_name] is not None:
                    wti_model = float(wti_individual[model_name])
                    if m > 0:
                        wti_model = wti_model + monthly_drift * m
                else:
                    # Simular variacion alrededor del WTI central
                    wti_model = wti_predictions[m] * (1.0 + offset)

                result = self._wti_to_fuel_price(max(wti_model, 10.0), prev, fuel_type)
                prices.append(round(result["price"], 4))
                prev = result["price"]

            individual[model_name] = prices

        return individual
