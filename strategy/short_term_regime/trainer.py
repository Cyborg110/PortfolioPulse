# strategy/short_term_regime/trainer.py

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Generator
import numpy as np
import pandas as pd
from joblib import dump, load
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans
from pathlib import Path

from candles.models import Candles

# Рабочие FIGI (IMOEX2 — как ты и сказал, он грузится стабильно)
MACRO_FIGI = {
    "IMOEX": "BBG00KDWPPW3",   # IMOEX2 — 100% работает
    "BRENT": "BBG000PGXPS4",
    "USD":   "BBG0013HGFT4",
}


class ShortTermRegimeTrainer:
    """
    Полностью соответствует твоим требованиям:
    • Явно пересчитывает метрики после загрузки
    • Никакого .close у Candles — берём только через last_candle
    • Работает с global_grid_memory_efficient (16 ГБ — ок)
    • Сохраняет модель и scaler
    """
    def __init__(
        self,
        window_days: int = 60,
        n_clusters: int = 6,
        model_path: str = "output/regime_kmeans.joblib",
        scaler_path: str = "output/regime_scaler.joblib",
    ):
        self.window_days = window_days
        self.n_clusters = n_clusters
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)

        # Создаём папку
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.scaler_path.parent.mkdir(parents=True, exist_ok=True)

        self.model = MiniBatchKMeans(
            n_clusters=n_clusters,
            batch_size=256,
            random_state=42,
            max_iter=100,
            reassignment_ratio=0.01
        )
        self.scaler = StandardScaler()
        self.is_fitted = False

    def _recalculate_metrics(self, candles):
        """Явный пересчёт всех нужных метрик"""
        if not candles.candles:
            return

        # Только то, что реально нужно
        candles.calculate_rsi(14)
        candles.calculate_sma(200)
        candles.calculate_sma(50)
        candles.calculate_atr(14)
        candles.calculate_bollinger_bands(20, 2.0)
        candles.calculate_volume_ratio(60)
        candles.calculate_atr_ratio(14, 60)

    def _build_features(self, context: Dict[str, Candles]) -> Optional[pd.DataFrame]:
        """
        Одна строка фичей для акции.
        Работает только с last_candle и атрибутами после пересчёта.
        """
        # Находим акцию (всё, что не в MACRO_FIGI)
        stock_candles = None
        stock_figi = None
        for figi, c in context.items():
            if figi not in MACRO_FIGI.values() and c and c.candles:
                stock_candles = c
                stock_figi = figi
                break
        if not stock_candles or not stock_candles.last_candle:
            return None

        # Явно пересчитываем метрики
        self._recalculate_metrics(stock_candles)

        # Макро
        imoex = context.get(MACRO_FIGI["IMOEX"])
        brent = context.get(MACRO_FIGI["BRENT"])
        usd = context.get(MACRO_FIGI["USD"])

        if not imoex or not imoex.last_candle or len(imoex.candles) < 60:
            return None

        # === Цена ===
        close_price = stock_candles.last_candle.close

        # === Индикаторы ===
        rsi = stock_candles.rsi_14[-1] if stock_candles.rsi_14 else np.nan
        sma200 = stock_candles.sma_200[-1] if stock_candles.sma_200 else np.nan
        dist_sma200 = (close_price - sma200) / sma200 * 100 if sma200 and sma200 != 0 else np.nan

        vol_ratio = stock_candles.volume_ratio_60[-1] if hasattr(stock_candles, 'volume_ratio_60') and stock_candles.volume_ratio_60 else np.nan
        atr_ratio = stock_candles.atr_ratio_14_60[-1] if hasattr(stock_candles, 'atr_ratio_14_60') and stock_candles.atr_ratio_14_60 else np.nan
        bb_pb = stock_candles.bollinger_percent_b_20_2_0[-1] if hasattr(stock_candles, 'bollinger_percent_b_20_2_0') else np.nan

        # === Относительная сила 10 дней ===
        if len(stock_candles.candles) >= 11 and len(imoex.candles) >= 11:
            price_10d_ago = stock_candles.candles[-11].close
            imoex_10d_ago = imoex.candles[-11].close
            ret_stock = np.log(close_price / price_10d_ago) if price_10d_ago != 0 else np.nan
            ret_imoex = np.log(imoex.last_candle.close / imoex_10d_ago) if imoex_10d_ago != 0 else np.nan
            rel_strength = ret_stock - ret_imoex
        else:
            rel_strength = np.nan

        # === Макро z-score ===
        def zscore_last(candles_obj, window=120):
            if not candles_obj or len(candles_obj.candles) < window:
                return np.nan
            values = [c.close for c in candles_obj.candles[-window:]]
            mean, std = np.mean(values), np.std(values)
            return (candles_obj.last_candle.close - mean) / std if std > 0 else 0.0

        brent_z = zscore_last(brent)
        usd_z = zscore_last(usd)

        row = pd.DataFrame([{
            'figi': stock_figi,
            'date': stock_candles.last_candle.time.date(),
            'rsi_14': rsi,
            'dist_sma200_pct': dist_sma200,
            'volume_ratio_60': vol_ratio,
            'atr_ratio_60': atr_ratio,
            # 'bb_percent_b': bb_pb,
            'rel_strength_10d': rel_strength,
            'brent_z': brent_z,
            'usd_z': usd_z,
        }])

        return row

    def train_daily(self, sync_generator: Generator[Dict[str, Candles], None, None]):
        features_list = []

        for context in sync_generator:
            row = self._build_features(context)
            if row is not None:
                # Убираем пропуски — только полные строки
                if not row.drop(columns=['figi', 'date']).isnull().any(axis=1).iloc[0]:
                    features_list.append(row)

        if not features_list:
            print(f"[{datetime.now()}] Нет валидных данных для обучения")
            return

        df = pd.concat(features_list, ignore_index=True)
        X = df.drop(columns=['figi', 'date'])

        if not self.is_fitted:
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            self.model.fit(X_scaled)
            self.is_fitted = True
            print(f"[{datetime.now()}] Первое обучение: {len(df)} объектов → {self.n_clusters} кластеров")
        else:
            X_scaled = self.scaler.transform(X)
            self.model.partial_fit(X_scaled)
            print(f"[{datetime.now()}] Обновление модели: +{len(df)} новых объектов")

        # Сохраняем
        dump(self.model, self.model_path)
        dump(self.scaler, self.scaler_path)
        print(f"Модель сохранена → {self.model_path}")
        return context

    def predict_current(self, context: Dict[str, Candles]) -> Dict[str, int]:
        """Предсказание кластера для текущего контекста"""
        if not self.is_fitted:
            raise RuntimeError("Модель не обучена")

        row = self._build_features(context)
        if row is None or row.drop(columns=['figi', 'date']).isnull().any(axis=1).iloc[0]:
            return {}

        X = self.scaler.transform(row.drop(columns=['figi', 'date']))
        cluster = int(self.model.predict(X)[0])
        return {row['figi'].iloc[0]: cluster}
