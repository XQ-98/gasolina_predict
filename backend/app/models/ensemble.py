"""Modelo ensemble que combina SARIMA, XGBoost y LSTM para prediccion
de precios mensuales de combustibles en Ecuador.

Despues de generar predicciones crudas de cada modelo, aplica el sistema
de bandas asimetricas para obtener predicciones realistas (los precios
no pueden subir mas del 5% ni bajar mas del 10% por mes).
"""

import numpy as np
import pandas as pd

from app.models.sarima_model import SARIMAPredictor
from app.models.xgboost_model import XGBoostPredictor
from app.models.lstm_model import LSTMPredictor
from app.services.feature_engineering import prepare_features
from app.services.band_calculator import BandCalculator
from app.config import settings


class EnsemblePredictor:
    """Combina predicciones de SARIMA, XGBoost y LSTM con pesos adaptativos.

    Flujo:
    1. Entrenar los 3 modelos con datos mensuales historicos
    2. Ajustar pesos segun rendimiento de cada modelo
    3. Generar prediccion ensemble (promedio ponderado)
    4. Aplicar el sistema de bandas asimetricas mes a mes
    """

    def __init__(self):
        self.sarima = SARIMAPredictor()
        self.xgboost = XGBoostPredictor()
        self.lstm = LSTMPredictor()
        self.weights = {"sarima": 0.3, "xgboost": 0.4, "lstm": 0.3}
        self.is_fitted = False
        self.metrics = {}
        self._band_calc = BandCalculator()

    def fit(self, df: pd.DataFrame, fuel_type: str = "extra", target_col: str = "price"):
        """Entrena los 3 modelos y ajusta pesos segun rendimiento.

        Args:
            df: DataFrame con datos mensuales (Date, price, wti, etc.).
            fuel_type: Tipo de combustible (para referencia).
            target_col: Nombre de la columna target.
        """
        self._fuel_type = fuel_type
        df_features = prepare_features(df, fuel_type)

        # Columnas de features (excluir Date, target, y columnas no numericas)
        exclude = ["Date", target_col, "extra", "ecopais", "super_95", "diesel",
                    "wti_close", "wti_high", "wti_low", "notes"]
        feature_cols = [
            c for c in df_features.columns
            if c not in exclude
            and df_features[c].dtype in [np.float64, np.int64, np.int32, np.float32]
        ]

        X = df_features[feature_cols]
        y = df_features[target_col]
        series = df_features[target_col]

        # Entrenar SARIMA
        try:
            self.sarima.fit(series)
            self.metrics["sarima"] = self.sarima.get_metrics(series)
        except Exception as e:
            self.metrics["sarima"] = {"error": str(e), "mape": 100}

        # Entrenar XGBoost
        try:
            self.xgboost.fit(X, y)
            self.metrics["xgboost"] = self.xgboost.get_metrics(X, y)
        except Exception as e:
            self.metrics["xgboost"] = {"error": str(e), "mape": 100}

        # Entrenar LSTM
        try:
            self.lstm.fit(df_features, target_col)
            self.metrics["lstm"] = self.lstm.get_metrics(df_features, target_col)
        except Exception as e:
            self.metrics["lstm"] = {"error": str(e), "mape": 100}

        # Ajustar pesos inversamente proporcionales al MAPE
        self._adjust_weights()

        self._df_features = df_features
        self._feature_cols = feature_cols
        self._target_col = target_col
        self.is_fitted = True

        return self

    def _adjust_weights(self):
        """Ajusta los pesos del ensemble segun el rendimiento de cada modelo."""
        mapes = {}
        for model_name in ["sarima", "xgboost", "lstm"]:
            m = self.metrics.get(model_name, {})
            mapes[model_name] = m.get("mape", 100)

        # Peso inversamente proporcional al MAPE
        total_inv = sum(1 / max(m, 0.01) for m in mapes.values())
        if total_inv > 0:
            self.weights = {
                name: round((1 / max(mape, 0.01)) / total_inv, 4)
                for name, mape in mapes.items()
            }

    def predict(
        self,
        horizon_months: int,
        fuel_type: str = "extra",
        current_price: float | None = None,
    ) -> dict:
        """Genera predicciones ensemble para los proximos N meses.

        Flujo:
        1. Cada modelo genera sus predicciones crudas
        2. Se combinan con promedio ponderado
        3. Se aplica el sistema de bandas mes a mes

        Args:
            horizon_months: Numero de meses a predecir.
            fuel_type: Tipo de combustible.
            current_price: Precio actual. Si None, usa el ultimo del dataset.

        Returns:
            Dict con predicciones ajustadas por banda, intervalos de confianza,
            predicciones individuales, pesos y metricas.
        """
        if not self.is_fitted:
            raise ValueError("El ensemble no ha sido entrenado.")

        if current_price is None:
            current_price = float(self._df_features[self._target_col].iloc[-1])

        predictions = {}

        # SARIMA
        try:
            sarima_pred = self.sarima.predict(horizon_months)
            predictions["sarima"] = sarima_pred["forecast"]
        except Exception:
            predictions["sarima"] = None

        # XGBoost
        try:
            last_row = self._df_features[self._feature_cols].iloc[[-1]]
            xgb_pred = self.xgboost.predict_recursive(last_row, horizon_months)
            predictions["xgboost"] = xgb_pred
        except Exception:
            predictions["xgboost"] = None

        # LSTM
        try:
            lstm_pred = self.lstm.predict(self._df_features, horizon_months)
            predictions["lstm"] = lstm_pred
        except Exception:
            predictions["lstm"] = None

        # Ensemble ponderado (prediccion cruda sin banda)
        ensemble_raw = self._weighted_average(predictions, horizon_months)

        # Intervalos de confianza basados en la dispersion entre modelos
        lower_ci, upper_ci = self._calculate_confidence(
            predictions, ensemble_raw, horizon_months,
        )

        # Aplicar sistema de bandas mes a mes
        band_adjusted = self._apply_band_sequential(ensemble_raw, current_price, fuel_type)

        # Generar fechas futuras (dia 11 de cada mes siguiente)
        last_date = self._df_features["Date"].iloc[-1]
        future_dates = []
        current_date = last_date
        for _ in range(horizon_months):
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=11)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=11)
            future_dates.append(current_date)

        # Construir predicciones mensuales detalladas
        monthly_predictions = []
        for i, ba in enumerate(band_adjusted):
            monthly_predictions.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "price": ba["price"],
                "band_applied": ba["band_status"] in ("TECHO", "PISO"),
                "band_status": ba["band_status"],
                "theoretical_price": ba["theoretical_price"],
                "max_price": ba["max_possible"],
                "min_price": ba["min_possible"],
            })

        # Metricas formateadas
        formatted_metrics = {}
        for k, v in self.metrics.items():
            formatted_metrics[k] = {
                mk: round(float(mv), 4) if isinstance(mv, (int, float)) else mv
                for mk, mv in v.items()
            }

        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})

        return {
            "fuel_type": fuel_type,
            "fuel_name": fuel_config.get("name", fuel_type),
            "current_price": current_price,
            "predictions": monthly_predictions,
            "ensemble_prices": [ba["price"] for ba in band_adjusted],
            "individual_predictions": {
                k: [round(float(vi), 4) for vi in v]
                for k, v in predictions.items()
                if v is not None
            },
            "weights": self.weights,
            "metrics": formatted_metrics,
            "confidence_interval": {
                "lower": [round(v, 4) for v in lower_ci],
                "upper": [round(v, 4) for v in upper_ci],
            },
        }

    def _weighted_average(
        self, predictions: dict, horizon: int,
    ) -> list[float]:
        """Calcula el promedio ponderado de las predicciones disponibles."""
        result = [0.0] * horizon
        total_weight = 0.0

        for model_name, preds in predictions.items():
            if preds is None:
                continue
            w = self.weights.get(model_name, 0)
            total_weight += w
            for i in range(min(len(preds), horizon)):
                result[i] += preds[i] * w

        if total_weight > 0:
            result = [r / total_weight for r in result]

        return result

    def _apply_band_sequential(
        self,
        raw_forecast: list[float],
        current_price: float,
        fuel_type: str,
    ) -> list[dict]:
        """Aplica el sistema de bandas secuencialmente mes a mes.

        Cada mes, el precio ajustado se usa como base para el siguiente.
        Esto simula lo que realmente pasaria: aunque el modelo prediga un
        precio alto, la banda limita el cambio a +5% mensual.

        Args:
            raw_forecast: Predicciones crudas del ensemble.
            current_price: Precio actual (base para el primer mes).
            fuel_type: Tipo de combustible.

        Returns:
            Lista de dicts con precio ajustado, estado de banda y detalles.
        """
        adjusted = []
        prev_price = current_price

        for raw_price in raw_forecast:
            band_result = self._band_calc.apply_band(prev_price, raw_price, fuel_type)
            adjusted.append({
                "price": band_result["result"],
                "band_status": band_result["status"],
                "theoretical_price": round(raw_price, 3),
                "max_possible": band_result["max_price"],
                "min_possible": band_result["min_price"],
                "change_percent": band_result["change_pct"],
            })
            prev_price = band_result["result"]

        return adjusted

    def _calculate_confidence(
        self,
        predictions: dict,
        ensemble: list[float],
        horizon: int,
    ) -> tuple[list[float], list[float]]:
        """Calcula intervalos de confianza basados en la dispersion entre modelos."""
        available = [v for v in predictions.values() if v is not None]

        if len(available) < 2:
            # Si solo hay un modelo, usar +/-3% como CI (combustibles son estables)
            lower = [p * 0.97 for p in ensemble]
            upper = [p * 1.03 for p in ensemble]
            return lower, upper

        lower, upper = [], []
        for i in range(horizon):
            values = [preds[i] for preds in available if i < len(preds)]
            if values:
                std = np.std(values)
                # Minimo CI de 1% del precio
                min_ci = ensemble[i] * 0.01
                std = max(std, min_ci)
                lower.append(ensemble[i] - 1.96 * std)
                upper.append(ensemble[i] + 1.96 * std)
            else:
                lower.append(ensemble[i] * 0.97)
                upper.append(ensemble[i] * 1.03)

        return lower, upper
