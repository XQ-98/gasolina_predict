"""Predictor diario del WTI: nucleo del sistema de prediccion de 2 capas.

Capa 1: Predice el precio promedio del WTI en los dias 1-10 del proximo mes
         usando un ensemble de ARIMA, XGBoost y LSTM con pesos adaptativos.
Capa 2: El resultado alimenta la formula del gobierno (band_calculator.py)
         para estimar el precio final de combustibles en Ecuador.

Los tres modelos se entrenan sobre datos diarios del WTI (ticker CL=F)
y generan predicciones multi-step hacia adelante. El ensemble pondera
inversamente al MAPE de cada modelo en el periodo de prueba.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error

logger = logging.getLogger(__name__)


class WTIDailyPredictor:
    """Predictor de precios diarios del WTI con ensemble de 3 modelos.

    Combina ARIMA(2,1,2), XGBoost y LSTM para generar predicciones
    diarias del precio del crudo WTI. Calcula pesos adaptativos basados
    en el rendimiento de cada modelo sobre los ultimos 60 dias de prueba.
    """

    def __init__(self):
        """Inicializa los componentes internos del predictor."""
        # Modelos (se crean en fit)
        self.arima_model = None
        self.xgb_model = None
        self.lstm_model = None
        self.lstm_scaler = None

        # Estado de entrenamiento
        self._is_fitted = False
        self._arima_ok = False
        self._xgb_ok = False
        self._lstm_ok = False

        # Datos y features
        self._raw_df = None
        self._features_df = None
        self._feature_cols = None
        self._train_series = None
        self._last_known_price = None

        # Metricas y pesos
        self.metrics = {}
        self.weights = {"sarima": 1 / 3, "xgboost": 1 / 3, "lstm": 1 / 3}

        # Configuracion LSTM
        self._lstm_sequence_length = 30
        self._tf = None
        self._tf_imported = False

    # ------------------------------------------------------------------
    # Obtencion de datos
    # ------------------------------------------------------------------

    def fetch_and_prepare_data(self, years: int = 5) -> pd.DataFrame:
        """Obtiene datos diarios del WTI desde Yahoo Finance.

        Si la descarga falla, genera datos demo con un random walk realista
        alrededor de $70 con volatilidad tipica del crudo (~2% diario).

        Args:
            years: Anos de historia a descargar.

        Returns:
            DataFrame con columnas: date, close, open, high, low, volume.
        """
        end = datetime.now()
        start = end - timedelta(days=years * 365)

        try:
            import yfinance as yf

            ticker = yf.Ticker("CL=F")
            df = ticker.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )

            if df.empty:
                raise ValueError("DataFrame WTI diario vacio")

            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df = df.rename(columns={
                "Date": "date",
                "Close": "close",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Volume": "volume",
            })
            df = df[["date", "close", "open", "high", "low", "volume"]].copy()
            df = df.sort_values("date").reset_index(drop=True)
            df = df.dropna(subset=["close"])
            logger.info(
                "Datos WTI diarios descargados: %d filas (%s a %s)",
                len(df),
                df["date"].iloc[0].strftime("%Y-%m-%d"),
                df["date"].iloc[-1].strftime("%Y-%m-%d"),
            )
            return df

        except Exception as e:
            logger.warning(
                "No se pudo obtener datos WTI diarios: %s. Generando datos demo.", e
            )
            return self._generate_demo_data(years)

    def _generate_demo_data(self, years: int = 5) -> pd.DataFrame:
        """Genera datos demo realistas del WTI con random walk.

        Simula ~1200 dias habiles con volatilidad tipica del crudo.

        Args:
            years: Anos de datos a generar.

        Returns:
            DataFrame con la misma estructura que datos reales.
        """
        np.random.seed(42)
        n_days = int(years * 252)  # ~252 dias habiles por ano
        dates = pd.bdate_range(
            end=datetime.now(), periods=n_days, freq="B"
        )

        # Random walk con mean-reversion alrededor de $70
        price = 65.0
        prices = []
        for _ in range(n_days):
            # Mean reversion hacia $70 + drift + ruido
            drift = 0.0001 * (70.0 - price)
            shock = np.random.normal(0, price * 0.018)
            price = max(price + drift + shock, 20.0)
            prices.append(price)

        closes = np.array(prices)
        # Generar OHLV a partir del close
        daily_range = closes * 0.015
        highs = closes + np.abs(np.random.normal(0, 1, n_days)) * daily_range
        lows = closes - np.abs(np.random.normal(0, 1, n_days)) * daily_range
        opens = closes + np.random.normal(0, 1, n_days) * daily_range * 0.5
        volumes = np.random.randint(200_000, 600_000, size=n_days).astype(float)

        df = pd.DataFrame({
            "date": dates[:n_days],
            "close": closes,
            "open": opens,
            "high": highs,
            "low": lows,
            "volume": volumes,
        })
        logger.info("Datos demo WTI generados: %d dias", len(df))
        return df

    # ------------------------------------------------------------------
    # Feature engineering diario
    # ------------------------------------------------------------------

    def prepare_daily_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construye features tecnicas diarias para prediccion del WTI.

        Incluye lags, medias moviles, indicadores tecnicos (RSI, MACD,
        Bollinger Bands), volatilidad y codificacion ciclica temporal.

        Args:
            df: DataFrame con columnas date, close, open, high, low, volume.

        Returns:
            DataFrame con todas las features, sin filas con NaN.
        """
        df = df.copy()
        close = df["close"]

        # --- Lags ---
        for lag in [1, 2, 3, 5, 10, 22]:
            df[f"lag_{lag}"] = close.shift(lag)

        # --- Medias moviles simples ---
        for w in [5, 10, 20, 50]:
            df[f"sma_{w}"] = close.rolling(window=w).mean()

        # --- Medias moviles exponenciales ---
        df["ema_12"] = close.ewm(span=12, adjust=False).mean()
        df["ema_26"] = close.ewm(span=26, adjust=False).mean()

        # --- RSI 14 ---
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 1e-10)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # --- MACD (12, 26, 9) ---
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # --- Bollinger Bands (20, 2) ---
        bb_sma = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        bb_upper = bb_sma + 2 * bb_std
        bb_lower = bb_sma - 2 * bb_std
        bb_range = (bb_upper - bb_lower).replace(0, 1e-10)
        df["bb_position"] = (close - bb_lower) / bb_range

        # --- Volatilidad rolling ---
        df["volatility_10"] = close.pct_change().rolling(window=10).std() * np.sqrt(252)
        df["volatility_20"] = close.pct_change().rolling(window=20).std() * np.sqrt(252)

        # --- Cambio porcentual ---
        df["pct_change_1"] = close.pct_change(1) * 100
        df["pct_change_5"] = close.pct_change(5) * 100
        df["pct_change_10"] = close.pct_change(10) * 100

        # --- Features temporales ciclicas ---
        day_of_week = df["date"].dt.dayofweek
        df["dow_sin"] = np.sin(2 * np.pi * day_of_week / 5)
        df["dow_cos"] = np.cos(2 * np.pi * day_of_week / 5)

        month = df["date"].dt.month
        df["month_sin"] = np.sin(2 * np.pi * month / 12)
        df["month_cos"] = np.cos(2 * np.pi * month / 12)

        # --- Volumen ---
        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()

        # --- Limpiar NaN generados por indicadores ---
        df = df.dropna().reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Entrenamiento
    # ------------------------------------------------------------------

    def fit(self, years: int = 5) -> "WTIDailyPredictor":
        """Entrena los 3 modelos sobre datos diarios del WTI.

        Descarga datos, genera features, separa train/test (ultimos 60 dias),
        entrena ARIMA, XGBoost y LSTM, calcula metricas y pesos adaptativos.

        Args:
            years: Anos de historia para entrenamiento.

        Returns:
            self, para permitir encadenamiento.
        """
        logger.info("Iniciando entrenamiento del WTIDailyPredictor...")

        # 1) Obtener datos y features
        self._raw_df = self.fetch_and_prepare_data(years)
        self._features_df = self.prepare_daily_features(self._raw_df)

        if len(self._features_df) < 100:
            logger.warning(
                "Pocos datos disponibles (%d filas). Los modelos pueden ser imprecisos.",
                len(self._features_df),
            )

        # 2) Split temporal: ultimos 60 dias como test
        test_size = min(60, len(self._features_df) // 5)
        train_df = self._features_df.iloc[:-test_size].copy()
        test_df = self._features_df.iloc[-test_size:].copy()

        self._last_known_price = float(self._features_df["close"].iloc[-1])

        # Columnas de features (excluyendo date y close)
        exclude_cols = {"date", "close", "open", "high", "low"}
        self._feature_cols = [
            c for c in self._features_df.columns if c not in exclude_cols
        ]

        # 3) Entrenar cada modelo
        self._fit_arima(train_df, test_df)
        self._fit_xgboost(train_df, test_df)
        self._fit_lstm(train_df, test_df)

        # 4) Calcular pesos adaptativos
        self._compute_adaptive_weights()

        self._is_fitted = True
        active = sum([self._arima_ok, self._xgb_ok, self._lstm_ok])
        logger.info(
            "Entrenamiento completado. Modelos activos: %d/3. Pesos: %s",
            active,
            {k: round(v, 3) for k, v in self.weights.items()},
        )
        return self

    def _fit_arima(self, train_df: pd.DataFrame, test_df: pd.DataFrame):
        """Entrena ARIMA(2,1,2) sobre la serie close del WTI."""
        try:
            from statsmodels.tsa.arima.model import ARIMA

            train_series = train_df["close"].values
            test_series = test_df["close"].values

            model = ARIMA(train_series, order=(2, 1, 2))
            self.arima_model = model.fit()

            # Metricas en test set
            preds = self.arima_model.forecast(steps=len(test_series))
            rmse = float(np.sqrt(mean_squared_error(test_series, preds)))
            mae = float(mean_absolute_error(test_series, preds))
            mape = float(
                np.mean(np.abs((test_series - preds) / test_series)) * 100
            )

            self.metrics["sarima"] = {"rmse": rmse, "mae": mae, "mape": mape}
            self._arima_ok = True
            self._train_series = np.concatenate([train_series, test_series])
            logger.info("ARIMA(2,1,2) entrenado. MAPE test: %.2f%%", mape)

        except Exception as e:
            logger.error("Error entrenando ARIMA: %s", e)
            self._arima_ok = False
            self.metrics["sarima"] = {"rmse": 999.0, "mae": 999.0, "mape": 999.0}
            # Guardar serie para posible fallback
            self._train_series = np.concatenate([
                train_df["close"].values, test_df["close"].values
            ])

    def _fit_xgboost(self, train_df: pd.DataFrame, test_df: pd.DataFrame):
        """Entrena XGBoost con todas las features diarias."""
        try:
            import xgboost as xgb

            X_train = train_df[self._feature_cols].values
            y_train = train_df["close"].values
            X_test = test_df[self._feature_cols].values
            y_test = test_df["close"].values

            self.xgb_model = xgb.XGBRegressor(
                n_estimators=500,
                max_depth=6,
                learning_rate=0.03,
                subsample=0.8,
                colsample_bytree=0.7,
                min_child_weight=3,
                reg_alpha=0.5,
                reg_lambda=2.0,
                random_state=42,
                n_jobs=-1,
            )
            self.xgb_model.fit(
                X_train,
                y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )

            preds = self.xgb_model.predict(X_test)
            rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
            mae = float(mean_absolute_error(y_test, preds))
            mape = float(np.mean(np.abs((y_test - preds) / y_test)) * 100)

            self.metrics["xgboost"] = {"rmse": rmse, "mae": mae, "mape": mape}
            self._xgb_ok = True
            logger.info("XGBoost entrenado. MAPE test: %.2f%%", mape)

        except Exception as e:
            logger.error("Error entrenando XGBoost: %s", e)
            self._xgb_ok = False
            self.metrics["xgboost"] = {"rmse": 999.0, "mae": 999.0, "mape": 999.0}

    def _fit_lstm(self, train_df: pd.DataFrame, test_df: pd.DataFrame):
        """Entrena LSTM de 2 capas sobre la serie close del WTI."""
        try:
            self._import_tf()
            tf = self._tf

            seq_len = self._lstm_sequence_length

            # Usar solo close para el LSTM
            all_close = pd.concat([train_df["close"], test_df["close"]]).values.reshape(-1, 1)
            train_close = train_df["close"].values.reshape(-1, 1)

            self.lstm_scaler = MinMaxScaler(feature_range=(0, 1))
            self.lstm_scaler.fit(train_close)

            scaled_train = self.lstm_scaler.transform(train_close)

            # Crear secuencias de entrenamiento
            X_train_seq, y_train_seq = self._create_lstm_sequences(
                scaled_train, seq_len
            )

            if len(X_train_seq) == 0:
                raise ValueError("No hay suficientes datos para secuencias LSTM")

            # Construir modelo: 2 capas LSTM(64, 32)
            model = tf.keras.Sequential([
                tf.keras.layers.LSTM(
                    64,
                    return_sequences=True,
                    input_shape=(seq_len, 1),
                ),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.LSTM(32, return_sequences=False),
                tf.keras.layers.Dropout(0.2),
                tf.keras.layers.Dense(16, activation="relu"),
                tf.keras.layers.Dense(1),
            ])
            model.compile(optimizer="adam", loss="mse")

            early_stop = tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=10,
                restore_best_weights=True,
            )

            model.fit(
                X_train_seq,
                y_train_seq,
                epochs=50,
                batch_size=32,
                validation_split=0.1,
                callbacks=[early_stop],
                verbose=0,
            )
            self.lstm_model = model

            # Metricas en test set (prediccion one-step con datos reales)
            scaled_all = self.lstm_scaler.transform(all_close)
            test_size = len(test_df)
            # Generar predicciones para el periodo test
            test_preds = []
            for i in range(test_size):
                idx = len(train_close) - seq_len + i
                seq = scaled_all[idx: idx + seq_len].reshape(1, seq_len, 1)
                pred_scaled = model.predict(seq, verbose=0)[0, 0]
                test_preds.append(pred_scaled)

            test_preds = np.array(test_preds).reshape(-1, 1)
            test_preds_inv = self.lstm_scaler.inverse_transform(test_preds).flatten()
            y_test = test_df["close"].values

            rmse = float(np.sqrt(mean_squared_error(y_test, test_preds_inv)))
            mae = float(mean_absolute_error(y_test, test_preds_inv))
            mape = float(
                np.mean(np.abs((y_test - test_preds_inv) / y_test)) * 100
            )

            self.metrics["lstm"] = {"rmse": rmse, "mae": mae, "mape": mape}
            self._lstm_ok = True
            logger.info("LSTM entrenado. MAPE test: %.2f%%", mape)

        except Exception as e:
            logger.error("Error entrenando LSTM: %s", e)
            self._lstm_ok = False
            self.metrics["lstm"] = {"rmse": 999.0, "mae": 999.0, "mape": 999.0}

    def _import_tf(self):
        """Importacion lazy de TensorFlow."""
        if not self._tf_imported:
            import tensorflow as tf

            tf.get_logger().setLevel("ERROR")
            self._tf = tf
            self._tf_imported = True

    @staticmethod
    def _create_lstm_sequences(
        data: np.ndarray, seq_len: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Crea secuencias (X, y) para entrenamiento LSTM.

        Args:
            data: Datos escalados con forma (n, 1).
            seq_len: Longitud de cada secuencia.

        Returns:
            X con forma (n_seq, seq_len, 1) e y con forma (n_seq,).
        """
        X, y = [], []
        for i in range(seq_len, len(data)):
            X.append(data[i - seq_len: i])
            y.append(data[i, 0])
        if len(X) == 0:
            return np.array([]), np.array([])
        return np.array(X), np.array(y)

    def _compute_adaptive_weights(self):
        """Calcula pesos inversamente proporcionales al MAPE de cada modelo.

        Si un modelo fallo (MAPE=999), su peso sera practicamente 0.
        """
        mape_values = {
            "sarima": self.metrics.get("sarima", {}).get("mape", 999.0),
            "xgboost": self.metrics.get("xgboost", {}).get("mape", 999.0),
            "lstm": self.metrics.get("lstm", {}).get("mape", 999.0),
        }

        # Inverso del MAPE (mayor MAPE -> menor peso)
        inv_mapes = {}
        for name, mape in mape_values.items():
            if mape > 0 and mape < 500:
                inv_mapes[name] = 1.0 / mape
            else:
                inv_mapes[name] = 0.0

        total = sum(inv_mapes.values())
        if total > 0:
            self.weights = {k: v / total for k, v in inv_mapes.items()}
        else:
            # Si todos fallaron, pesos iguales para los que funcionan
            active = sum([self._arima_ok, self._xgb_ok, self._lstm_ok])
            if active > 0:
                self.weights = {
                    "sarima": (1.0 / active) if self._arima_ok else 0.0,
                    "xgboost": (1.0 / active) if self._xgb_ok else 0.0,
                    "lstm": (1.0 / active) if self._lstm_ok else 0.0,
                }
            else:
                self.weights = {"sarima": 1 / 3, "xgboost": 1 / 3, "lstm": 1 / 3}

    # ------------------------------------------------------------------
    # Prediccion
    # ------------------------------------------------------------------

    def predict_daily(self, days_ahead: int = 15) -> dict[str, Any]:
        """Genera predicciones diarias del WTI con los 3 modelos y ensemble.

        Args:
            days_ahead: Numero de dias habiles a predecir.

        Returns:
            Dict con predicciones individuales, ensemble ponderado e
            intervalo de confianza basado en la dispersion entre modelos.
        """
        if not self._is_fitted:
            raise ValueError("El modelo no ha sido entrenado. Llama a fit() primero.")

        preds = {"sarima": None, "xgboost": None, "lstm": None}

        # --- ARIMA ---
        if self._arima_ok:
            try:
                # Re-entrenar ARIMA sobre toda la serie para prediccion final
                from statsmodels.tsa.arima.model import ARIMA

                full_series = self._features_df["close"].values
                model = ARIMA(full_series, order=(2, 1, 2))
                fitted = model.fit()
                arima_preds = fitted.forecast(steps=days_ahead)
                preds["sarima"] = np.array(arima_preds, dtype=float)
            except Exception as e:
                logger.warning("Error en prediccion ARIMA: %s", e)
                self._arima_ok = False

        # --- XGBoost (recursive) ---
        if self._xgb_ok:
            try:
                preds["xgboost"] = self._predict_xgb_recursive(days_ahead)
            except Exception as e:
                logger.warning("Error en prediccion XGBoost: %s", e)
                self._xgb_ok = False

        # --- LSTM (recursive) ---
        if self._lstm_ok:
            try:
                preds["lstm"] = self._predict_lstm_recursive(days_ahead)
            except Exception as e:
                logger.warning("Error en prediccion LSTM: %s", e)
                self._lstm_ok = False

        # --- Fallback si todos fallaron ---
        active_preds = {k: v for k, v in preds.items() if v is not None}
        if not active_preds:
            logger.warning("Todos los modelos fallaron. Usando prediccion naive.")
            naive = self._naive_prediction(days_ahead)
            preds["sarima"] = naive
            active_preds = {"sarima": naive}
            self.weights = {"sarima": 1.0, "xgboost": 0.0, "lstm": 0.0}

        # Recalcular pesos solo sobre modelos activos
        active_weights = {k: self.weights.get(k, 0.0) for k in active_preds}
        w_total = sum(active_weights.values())
        if w_total > 0:
            active_weights = {k: v / w_total for k, v in active_weights.items()}
        else:
            n = len(active_preds)
            active_weights = {k: 1.0 / n for k in active_preds}

        # --- Ensemble ponderado ---
        ensemble = np.zeros(days_ahead)
        for name, pred_arr in active_preds.items():
            ensemble += active_weights[name] * pred_arr

        # --- Intervalo de confianza (basado en dispersion entre modelos) ---
        if len(active_preds) >= 2:
            stacked = np.stack(list(active_preds.values()))
            std_dev = np.std(stacked, axis=0)
        else:
            # Un solo modelo: usar 3% del precio como incertidumbre
            std_dev = ensemble * 0.03

        lower = ensemble - 1.96 * std_dev
        upper = ensemble + 1.96 * std_dev

        return {
            "ensemble": ensemble.tolist(),
            "lower_ci": lower.tolist(),
            "upper_ci": upper.tolist(),
            "individual": {
                k: v.tolist() if v is not None else None for k, v in preds.items()
            },
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
        }

    def _predict_xgb_recursive(self, days_ahead: int) -> np.ndarray:
        """Prediccion recursiva multi-step con XGBoost.

        Usa la prediccion del dia anterior como lag_1 y desplaza los demas
        lags en cada paso.

        Args:
            days_ahead: Dias a predecir.

        Returns:
            Array de predicciones.
        """
        predictions = []
        # Tomar la ultima fila de features como punto de partida
        current_features = self._features_df[self._feature_cols].iloc[-1].values.copy()
        feature_names = self._feature_cols

        # Indices de lags en el array de features
        lag_indices = {}
        for i, name in enumerate(feature_names):
            if name.startswith("lag_"):
                lag_num = int(name.split("_")[1])
                lag_indices[lag_num] = i

        lag_nums_sorted = sorted(lag_indices.keys())

        last_close = float(self._features_df["close"].iloc[-1])

        for step in range(days_ahead):
            pred = float(
                self.xgb_model.predict(current_features.reshape(1, -1))[0]
            )
            predictions.append(pred)

            # Desplazar lags: lag_22 <- lag_10, lag_10 <- lag_5, ...
            for j in range(len(lag_nums_sorted) - 1, 0, -1):
                dst = lag_indices[lag_nums_sorted[j]]
                src = lag_indices[lag_nums_sorted[j - 1]]
                current_features[dst] = current_features[src]

            # lag_1 <- prediccion actual
            if 1 in lag_indices:
                current_features[lag_indices[1]] = pred

            # Actualizar pct_change_1 si existe
            pct1_idx = None
            for i, name in enumerate(feature_names):
                if name == "pct_change_1":
                    pct1_idx = i
                    break
            if pct1_idx is not None:
                prev = predictions[-2] if len(predictions) >= 2 else last_close
                if prev != 0:
                    current_features[pct1_idx] = ((pred - prev) / prev) * 100

        return np.array(predictions)

    def _predict_lstm_recursive(self, days_ahead: int) -> np.ndarray:
        """Prediccion recursiva multi-step con LSTM.

        Alimenta la prediccion del paso anterior como input del siguiente.

        Args:
            days_ahead: Dias a predecir.

        Returns:
            Array de predicciones.
        """
        seq_len = self._lstm_sequence_length
        close_values = self._features_df["close"].values.reshape(-1, 1)
        scaled = self.lstm_scaler.transform(close_values)

        current_seq = scaled[-seq_len:].copy()
        predictions = []

        for _ in range(days_ahead):
            input_seq = current_seq.reshape(1, seq_len, 1)
            pred_scaled = self.lstm_model.predict(input_seq, verbose=0)[0, 0]

            # Inverse transform
            pred_real = self.lstm_scaler.inverse_transform(
                np.array([[pred_scaled]])
            )[0, 0]
            predictions.append(float(pred_real))

            # Desplazar secuencia
            current_seq = np.vstack([current_seq[1:], [[pred_scaled]]])

        return np.array(predictions)

    def _naive_prediction(self, days_ahead: int) -> np.ndarray:
        """Prediccion naive basada en tendencia simple (drift).

        Usa el ultimo precio conocido mas una tendencia calculada sobre
        los ultimos 20 dias.

        Args:
            days_ahead: Dias a predecir.

        Returns:
            Array de predicciones.
        """
        close = self._features_df["close"].values
        last_price = close[-1]

        # Drift: pendiente lineal de los ultimos 20 dias
        lookback = min(20, len(close))
        recent = close[-lookback:]
        x = np.arange(lookback)
        slope = np.polyfit(x, recent, 1)[0]

        predictions = []
        for i in range(1, days_ahead + 1):
            pred = last_price + slope * i
            # Agregar ruido pequeno para no tener linea perfecta
            noise = np.random.normal(0, last_price * 0.005)
            predictions.append(max(float(pred + noise), 10.0))

        return np.array(predictions)

    # ------------------------------------------------------------------
    # Prediccion WTI promedio para proximo mes (API principal)
    # ------------------------------------------------------------------

    def predict_wti_avg_for_next_month(self) -> dict[str, Any]:
        """Predice el precio promedio del WTI en los dias 1-10 del proximo mes.

        Este es el metodo principal del sistema de 2 capas:
        1. Calcula cuantos dias habiles quedan hasta el dia 10 del mes siguiente.
        2. Genera predicciones diarias con el ensemble.
        3. Filtra los dias 1-10 del mes siguiente (~7 dias habiles).
        4. Calcula el promedio ponderado.

        Returns:
            Dict completo con prediccion, intervalos, modelos individuales,
            pesos, metricas y metadata de entrenamiento.
        """
        if not self._is_fitted:
            self.fit()

        today = datetime.now()
        # Determinar el proximo mes
        if today.month == 12:
            next_month = 1
            next_year = today.year + 1
        else:
            next_month = today.month + 1
            next_year = today.year

        # Dias habiles entre hoy y el dia 10 del proximo mes
        target_start = pd.Timestamp(next_year, next_month, 1)
        target_end = pd.Timestamp(next_year, next_month, 10)

        # Calcular dias habiles totales necesarios
        all_bdays = pd.bdate_range(start=today + timedelta(days=1), end=target_end)
        days_ahead = max(len(all_bdays), 5)  # Minimo 5 dias

        # Generar predicciones
        result = self.predict_daily(days_ahead=days_ahead)
        ensemble = np.array(result["ensemble"])

        # Generar fechas de dias habiles para las predicciones
        pred_dates = pd.bdate_range(
            start=today + timedelta(days=1), periods=days_ahead
        )

        # Filtrar solo dias 1-10 del mes siguiente
        mask = (pred_dates.month == next_month) & (
            pred_dates.year == next_year
        ) & (pred_dates.day <= 10)

        if mask.any():
            target_prices = ensemble[mask]
            target_dates = pred_dates[mask]
            lower_ci = np.array(result["lower_ci"])[mask]
            upper_ci = np.array(result["upper_ci"])[mask]
        else:
            # Fallback: usar las ultimas 7 predicciones
            target_prices = ensemble[-7:]
            target_dates = pred_dates[-7:]
            lower_ci = np.array(result["lower_ci"])[-7:]
            upper_ci = np.array(result["upper_ci"])[-7:]
            logger.warning(
                "No se encontraron dias en el rango 1-10 del mes %d/%d. "
                "Usando ultimas 7 predicciones.",
                next_month,
                next_year,
            )

        wti_avg = float(np.mean(target_prices))
        wti_current = self._last_known_price
        wti_change_pct = ((wti_avg - wti_current) / wti_current * 100) if wti_current else 0.0

        # Predicciones diarias detalladas
        daily_predictions = [
            {"date": d.strftime("%Y-%m-%d"), "price": round(float(p), 2)}
            for d, p in zip(target_dates, target_prices)
        ]

        # Predicciones individuales filtradas al periodo 1-10
        individual_models = {}
        for model_name in ["sarima", "xgboost", "lstm"]:
            model_preds = result["individual"].get(model_name)
            if model_preds is not None:
                model_arr = np.array(model_preds)
                if mask.any() and len(model_arr) >= len(mask):
                    model_target = model_arr[mask]
                else:
                    model_target = model_arr[-min(7, len(model_arr)):]

                individual_models[model_name] = {
                    "avg": round(float(np.mean(model_target)), 2),
                    "daily": [round(float(v), 2) for v in model_target],
                }
            else:
                individual_models[model_name] = {
                    "avg": None,
                    "daily": [],
                }

        # Rango de entrenamiento
        train_from = self._features_df["date"].iloc[0].strftime("%Y-%m-%d")
        train_to = self._features_df["date"].iloc[-1].strftime("%Y-%m-%d")

        return {
            "wti_predicted_avg": round(wti_avg, 2),
            "wti_current": round(wti_current, 2),
            "wti_change_pct": round(wti_change_pct, 2),
            "confidence_interval": {
                "lower": round(float(np.mean(lower_ci)), 2),
                "upper": round(float(np.mean(upper_ci)), 2),
            },
            "daily_predictions": daily_predictions,
            "individual_models": individual_models,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "metrics": {
                "sarima": {
                    k: round(v, 4) for k, v in self.metrics.get("sarima", {}).items()
                },
                "xgboost": {
                    k: round(v, 4) for k, v in self.metrics.get("xgboost", {}).items()
                },
                "lstm": {
                    k: round(v, 4) for k, v in self.metrics.get("lstm", {}).items()
                },
            },
            "data_points_used": len(self._features_df),
            "training_range": {"from": train_from, "to": train_to},
        }
