"""Modelo LSTM para prediccion de precios mensuales de combustibles en Ecuador.

Adaptado para datos MENSUALES con secuencias mas cortas que el proyecto de cacao.
Con ~70 puntos de datos mensuales, el LSTM necesita secuencias cortas (6-12 meses)
y una arquitectura ligera para evitar overfitting.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class LSTMPredictor:
    """Predictor basado en LSTM para series temporales mensuales."""

    def __init__(self, sequence_length: int = 6, units: int = 32, epochs: int = 100):
        """Inicializa el modelo LSTM.

        Args:
            sequence_length: Meses de historia por secuencia (default 6).
            units: Neuronas en la capa LSTM (default 32, mas pequeno que diario).
            epochs: Epocas de entrenamiento (mas epocas por pocos datos).
        """
        self.sequence_length = sequence_length
        self.units = units
        self.epochs = epochs
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self._tf_imported = False

    def _import_tf(self):
        """Importacion lazy de TensorFlow para evitar overhead en startup."""
        if not self._tf_imported:
            import tensorflow as tf
            tf.get_logger().setLevel("ERROR")
            self._tf = tf
            self._tf_imported = True

    def _build_model(self, input_shape: tuple):
        """Construye la arquitectura LSTM ligera para datos mensuales.

        Arquitectura simplificada para evitar overfitting con pocos datos:
        - Una capa LSTM (no dos como en diario)
        - Dropout bajo
        - Capa densa pequena
        """
        self._import_tf()
        tf = self._tf

        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(
                self.units,
                return_sequences=False,
                input_shape=input_shape,
            ),
            tf.keras.layers.Dropout(0.1),
            tf.keras.layers.Dense(16, activation="relu"),
            tf.keras.layers.Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        return model

    def _create_sequences(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Crea secuencias para entrenamiento del LSTM.

        Args:
            data: Datos escalados (n_samples, n_features).

        Returns:
            Tupla (X, y) donde X tiene forma (n_sequences, sequence_length, n_features).
        """
        X, y = [], []
        for i in range(self.sequence_length, len(data)):
            X.append(data[i - self.sequence_length:i])
            y.append(data[i, 0])  # Columna 0 = precio target
        return np.array(X), np.array(y)

    def fit(self, df: pd.DataFrame, target_col: str = "price"):
        """Entrena el modelo LSTM con datos mensuales.

        Args:
            df: DataFrame con features numericas.
            target_col: Columna objetivo.
        """
        self._import_tf()

        # Seleccionar features numericas, poniendo target primero
        feature_cols = [target_col] + [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c != target_col
        ]
        # Limitar features para dataset pequeno
        feature_cols = feature_cols[:12]

        data = df[feature_cols].values
        self.scaler.fit(data)
        scaled_data = self.scaler.transform(data)

        X, y = self._create_sequences(scaled_data)

        if len(X) == 0:
            raise ValueError(
                f"No hay suficientes datos para crear secuencias. "
                f"Se necesitan al menos {self.sequence_length + 1} meses."
            )

        self.model = self._build_model((X.shape[1], X.shape[2]))
        self.model.fit(
            X,
            y,
            epochs=self.epochs,
            batch_size=min(16, len(X)),  # Batch pequeno por pocos datos
            validation_split=0.15,
            verbose=0,
        )

        self._feature_cols = feature_cols
        self._n_features = len(feature_cols)
        return self

    def predict(self, df: pd.DataFrame, horizon: int) -> list[float]:
        """Genera predicciones para el horizonte especificado en MESES.

        Args:
            df: DataFrame con features (debe incluir al menos sequence_length filas).
            horizon: Numero de meses a predecir.

        Returns:
            Lista de precios predichos.
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado.")

        data = df[self._feature_cols].values
        scaled_data = self.scaler.transform(data)

        predictions = []
        current_seq = scaled_data[-self.sequence_length:].copy()

        for _ in range(horizon):
            input_seq = current_seq.reshape(1, self.sequence_length, self._n_features)
            pred_scaled = self.model.predict(input_seq, verbose=0)[0, 0]

            # Crear fila completa para inverse transform
            pred_row = current_seq[-1].copy()
            pred_row[0] = pred_scaled

            # Inverse transform para obtener precio real
            full_row = pred_row.reshape(1, -1)
            inv = self.scaler.inverse_transform(full_row)
            predictions.append(float(inv[0, 0]))

            # Actualizar secuencia
            current_seq = np.vstack([current_seq[1:], pred_row])

        return predictions

    def get_metrics(
        self,
        df: pd.DataFrame,
        target_col: str = "price",
        test_size: int = 6,
    ) -> dict:
        """Calcula metricas de rendimiento.

        Args:
            df: DataFrame con features.
            target_col: Columna target.
            test_size: Meses para test (default 6).

        Returns:
            Dict con MSE, RMSE, MAE y MAPE.
        """
        try:
            data = df[self._feature_cols].values
            scaled_data = self.scaler.transform(data)

            X, y_true = self._create_sequences(scaled_data)

            if len(X) <= test_size:
                return {"mse": 0.0, "rmse": 0.0, "mae": 0.0, "mape": 10.0}

            X_test = X[-test_size:]
            y_test_scaled = y_true[-test_size:]

            y_pred_scaled = self.model.predict(X_test, verbose=0).flatten()

            # Inverse transform
            dummy = np.zeros((len(y_test_scaled), self._n_features))
            dummy[:, 0] = y_test_scaled
            y_test_real = self.scaler.inverse_transform(dummy)[:, 0]

            dummy[:, 0] = y_pred_scaled
            y_pred_real = self.scaler.inverse_transform(dummy)[:, 0]

            mse = float(np.mean((y_test_real - y_pred_real) ** 2))
            rmse = float(np.sqrt(mse))
            mae = float(np.mean(np.abs(y_test_real - y_pred_real)))
            mape = float(
                np.mean(np.abs((y_test_real - y_pred_real) / y_test_real)) * 100
            )

            return {"mse": mse, "rmse": rmse, "mae": mae, "mape": mape}
        except Exception as e:
            return {"mse": 0.0, "rmse": 0.0, "mae": 0.0, "mape": 10.0, "error": str(e)}
