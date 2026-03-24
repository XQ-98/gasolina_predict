"""Modelo XGBoost para prediccion de precios mensuales de combustibles en Ecuador.

XGBoost es ideal para capturar relaciones no lineales entre:
- Precio del WTI y el precio local de combustibles
- Features de banda (techo, piso, racha de cambios)
- Estacionalidad y tendencias

Adaptado para datos MENSUALES con horizonte de prediccion en meses.
"""

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error


class XGBoostPredictor:
    """Predictor basado en XGBoost para series temporales mensuales."""

    def __init__(self, params: dict | None = None):
        """Inicializa el modelo XGBoost.

        Parametros ajustados para datasets pequenos (datos mensuales ~70 filas).
        """
        self.params = params or {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.7,
            "min_child_weight": 2,
            "reg_alpha": 0.5,
            "reg_lambda": 2.0,
            "random_state": 42,
        }
        self.model = None
        self.feature_names = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        """Entrena el modelo XGBoost.

        Args:
            X: Features de entrenamiento.
            y: Variable target (precios mensuales).
        """
        self.feature_names = X.columns.tolist()
        self.model = xgb.XGBRegressor(**self.params)
        self.model.fit(
            X,
            y,
            eval_set=[(X, y)],
            verbose=False,
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Genera predicciones.

        Args:
            X: Features para prediccion.

        Returns:
            Array de predicciones.
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado.")
        return self.model.predict(X)

    def predict_recursive(
        self,
        last_features: pd.DataFrame,
        horizon: int,
        price_col_idx: int = 0,
    ) -> list[float]:
        """Prediccion recursiva multi-step para datos mensuales.

        Usa la prediccion de un mes como input para predecir el siguiente.
        Actualiza los features de lag en cada paso.

        Args:
            last_features: Ultima fila de features conocida.
            horizon: Numero de meses a predecir.
            price_col_idx: Indice de la columna de precio (no usado directamente).

        Returns:
            Lista de precios predichos para cada mes.
        """
        predictions = []
        current_features = last_features.copy()

        for _ in range(horizon):
            pred = self.model.predict(current_features)[0]
            predictions.append(float(pred))

            # Actualizar features de lag
            current_row = current_features.iloc[0].copy()
            lag_cols = [c for c in current_features.columns if c.startswith("lag_")]
            lag_cols_sorted = sorted(lag_cols, key=lambda x: int(x.split("_")[1]))

            # Desplazar lags: lag_2 <- lag_1, lag_3 <- lag_2, etc.
            for i in range(len(lag_cols_sorted) - 1, 0, -1):
                current_row[lag_cols_sorted[i]] = current_row[lag_cols_sorted[i - 1]]
            if lag_cols_sorted:
                current_row[lag_cols_sorted[0]] = pred

            # Actualizar otros features dinamicos
            if "prev_price" in current_row.index:
                current_row["prev_price"] = pred
            if "price_change_1m" in current_row.index:
                if len(predictions) >= 2:
                    current_row["price_change_1m"] = predictions[-1] - predictions[-2]
                else:
                    current_row["price_change_1m"] = 0.0

            current_features = pd.DataFrame([current_row])

        return predictions

    def get_feature_importance(self) -> dict[str, float]:
        """Retorna la importancia de cada feature.

        Returns:
            Dict ordenado de feature -> importancia.
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado.")

        importance = self.model.feature_importances_
        feature_imp = dict(zip(self.feature_names, importance.tolist()))
        return dict(sorted(feature_imp.items(), key=lambda x: x[1], reverse=True))

    def get_metrics(
        self, X: pd.DataFrame, y: pd.Series, test_size: int = 6,
    ) -> dict:
        """Calcula metricas de rendimiento con validacion temporal.

        Args:
            X: Features completas.
            y: Target completo.
            test_size: Numero de meses para test (default 6).

        Returns:
            Dict con MSE, RMSE, MAE y MAPE.
        """
        if len(X) <= test_size + 10:
            # Dataset muy pequeno, usar todo como train y reportar metricas in-sample
            predictions = self.model.predict(X)
            y_vals = y.values
        else:
            X_train, X_test = X[:-test_size], X[-test_size:]
            y_train, y_test = y[:-test_size], y[-test_size:]

            temp_model = xgb.XGBRegressor(**self.params)
            temp_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            predictions = temp_model.predict(X_test)
            y_vals = y_test.values

        mse = float(mean_squared_error(y_vals, predictions))
        rmse = float(np.sqrt(mse))
        mae = float(mean_absolute_error(y_vals, predictions))
        mape = float(np.mean(np.abs((y_vals - predictions) / y_vals)) * 100)

        return {"mse": mse, "rmse": rmse, "mae": mae, "mape": mape}
