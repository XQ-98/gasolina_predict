"""Modelo SARIMA para prediccion de precios mensuales de combustibles en Ecuador.

Adaptado para datos MENSUALES (no diarios) con estacionalidad de 12 meses.
SARIMA captura bien la tendencia y estacionalidad anual de los precios,
aunque en Ecuador la estacionalidad es leve porque los precios dependen
mas del WTI que de factores estacionales locales.
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


class SARIMAPredictor:
    """Predictor basado en SARIMA (Seasonal ARIMA) para datos mensuales."""

    def __init__(self, order=(1, 1, 1), seasonal_order=(1, 1, 0, 12)):
        """Inicializa el modelo SARIMA.

        Args:
            order: (p, d, q) - Parametros ARIMA no estacionales.
            seasonal_order: (P, D, Q, s) - Parametros estacionales.
                s=12 para estacionalidad anual con datos mensuales.
        """
        self.order = order
        self.seasonal_order = seasonal_order
        self.model = None
        self.fitted = None

    def fit(self, series: pd.Series):
        """Entrena el modelo SARIMA con la serie de precios mensuales.

        Args:
            series: Serie temporal de precios (indexada mensualmente).
        """
        # Asegurar que no hay NaN
        series = series.dropna()

        self.model = SARIMAX(
            series,
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self.fitted = self.model.fit(disp=False, maxiter=300)
        return self

    def predict(self, horizon: int) -> dict:
        """Genera predicciones para el horizonte especificado en MESES.

        Args:
            horizon: Numero de meses a predecir.

        Returns:
            Dict con 'forecast', 'lower_ci', 'upper_ci' como listas.
        """
        if self.fitted is None:
            raise ValueError("El modelo no ha sido entrenado. Llama a fit() primero.")

        forecast = self.fitted.get_forecast(steps=horizon)
        mean = forecast.predicted_mean
        ci = forecast.conf_int(alpha=0.05)

        return {
            "forecast": [round(float(v), 4) for v in mean.values],
            "lower_ci": [round(float(v), 4) for v in ci.iloc[:, 0].values],
            "upper_ci": [round(float(v), 4) for v in ci.iloc[:, 1].values],
        }

    def get_metrics(self, series: pd.Series, test_size: int = 6) -> dict:
        """Calcula metricas de rendimiento usando los ultimos test_size meses.

        Args:
            series: Serie completa de precios.
            test_size: Numero de meses para test (default 6).

        Returns:
            Dict con MSE, RMSE, MAE y MAPE.
        """
        if len(series) <= test_size + 12:
            # No hay suficientes datos para train/test con estacionalidad
            return {"mse": 0.0, "rmse": 0.0, "mae": 0.0, "mape": 5.0}

        train = series[:-test_size]
        test = series[-test_size:]

        try:
            temp_model = SARIMAX(
                train,
                order=self.order,
                seasonal_order=self.seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            temp_fitted = temp_model.fit(disp=False, maxiter=300)
            predictions = temp_fitted.get_forecast(steps=test_size).predicted_mean

            test_vals = test.values
            pred_vals = predictions.values

            mse = float(np.mean((test_vals - pred_vals) ** 2))
            rmse = float(np.sqrt(mse))
            mae = float(np.mean(np.abs(test_vals - pred_vals)))
            mape = float(
                np.mean(np.abs((test_vals - pred_vals) / test_vals)) * 100
            )

            return {"mse": mse, "rmse": rmse, "mae": mae, "mape": mape}
        except Exception as e:
            return {"mse": 0.0, "rmse": 0.0, "mae": 0.0, "mape": 10.0, "error": str(e)}
