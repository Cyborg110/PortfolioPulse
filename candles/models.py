# /candles/models.py
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from tinkoff.invest import CandleInterval

from settings import Settings
from api_client import tinkoff_api_client
from candles.database import candles_database


class Candle:
    """
    Класс для представления одной свечи.
    """
    def __init__(self, open_: float, high: float, low: float, close: float, volume: float, time: datetime,
                 factor: float = 1):
        """
        Инициализация объекта свечи из данных кортежа из базы данных.
        :param open_: Цена открытия.
        :param high: Максимальная цена.
        :param low: Минимальная цена.
        :param close: Цена закрытия.
        :param volume: Объём торгов.
        :param time: Время свечи.
        :param factor: Множитель для конвертации цен.
        """
        self.open_ = open_ * factor
        self.high = high * factor
        self.low = low * factor
        self.close = close * factor
        self.volume = volume
        self.time = time

    def __str__(self):
        return f"Открытие: {self.open_}\t " \
               f"Мин:{self.low}\t " \
               f"Макс:{self.high}\t " \
               f"Закрытие:{self.close}\t " \
               f"Обьем:{self.volume}\t " \
               f"Дата:{self.time}"


class CandlesBase:
    """
    Базовый класс для работы с набором свечей, содержит методы сбора данных и поля для метрик.
    """

    def __init__(self, figi: str, interval: CandleInterval, factor: float=1):
        """
        Инициализация объекта свечей.
        :param figi: FIGI актива.
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :param factor: Множитель для конвертации цен.
        """
        self.figi = figi
        self.interval = interval
        self.factor = factor
        self.candles: List[Candle] = []                 # Кэш для свечей
        self.volatility: Optional[float] = None         # Кэшированная волатильность
        self.avg_volume: Optional[float] = None         # Кэшированный средний объём
        self.avg_price_volume: Optional[float] = None   # Кэшированный средний объём в валюте
        self.average_return: Optional[float] = None     # Кэшированная средняя доходность
        self.sharpe_ratio: Optional[float] = None       # Кэшированный коэффициент Шарпа
        self.max_drawdown: Optional[float] = None       # Кэшированная максимальная просадка
        self.last_candle: Optional[Candle] = None       # Последняя известная свеча
        self._load_last_candle()                        # Загружаем последнюю свечу

    def _load_last_candle(self) -> None:
        """
        Загружает последнюю доступную свечу из базы данных.
        """
        candle_data = candles_database.query_last_candle(
            figi=self.figi,
            interval=self.interval
        )
        if candle_data:
            self.last_candle = Candle(**candle_data, factor=self.factor)

    def load_candles(self, from_date: datetime = None, to_date: datetime = None) -> None:
        """
        Загружает свечи из базы данных для указанного периода, добавляя их в кэш.
        :param from_date: Начало периода.
        :param to_date: Конец периода.
        """
        if not all((from_date, to_date)):
            from_date = datetime.utcnow() - timedelta(days=Settings.Candles.DEFAULT_LOAD_DAYS[self.interval])
            to_date = datetime.utcnow()

        candle_data = candles_database.query_candles(
            figi=self.figi,
            interval=self.interval,
            from_time=from_date,
            to_time=to_date
        )
        self.candles = [Candle(**data, factor=self.factor) for data in candle_data]
        self.candles.sort(key=lambda c: c.time)

    def get_candle_by_date(self, date: datetime) -> Optional[Candle]:
        """
        Возвращает свечу, ближайшую к указанной дате, но не позднее неё.
        :param date: Дата для поиска свечи.
        :return: Объект Candle или None, если свеча не найдена.
        """
        candle_data = candles_database.query_candle_before_date(
            figi=self.figi,
            interval=self.interval,
            date=date
        )
        if candle_data:
            candle = Candle(**candle_data, factor=self.factor)
            return candle
        return None

    def drop(self) -> None:
        """
        Удаление всех свечей в базе данных.
        :return:
        """
        candles_database.drop(figi=self.figi, interval=self.interval)
        self._load_last_candle()

    async def update_candles(self, from_time: datetime = None) -> None:
        """
        Обновляет свечи в базе данных и перезагружает последнюю свечу.
        :param from_time: Начало периода для загрузки новых данных.
        """
        await candles_database.fetch_data(
            figi=self.figi,
            interval=self.interval,
            from_time=from_time
        )
        self._load_last_candle()

    def clear_buffer(self) -> None:
        """
        Очищает список свечей, не трогая рассчитанные метрики и последнюю свечу.
        """
        self.candles = []

    @property
    def price(self) -> Optional[float]:
        """
        Возвращает цену закрытия последней известной свечи.
        """
        return self.last_candle.close if self.last_candle else None

    def __iter__(self):
        return iter(self.candles)

    def __len__(self):
        return len(self.candles)

    def __bool__(self):
        return True


class StaticMetrics(CandlesBase):
    """
    Класс для расчёта статических метрик, выражающихся одним числом.
    Наследуется от CandlesBase, использует его поля для кэширования.
    """
    ANNUALIZATION_FACTOR = {                            # Норамлизация на год по часам и дням
        CandleInterval.CANDLE_INTERVAL_DAY: 252,
        CandleInterval.CANDLE_INTERVAL_HOUR: 2205
    }

    def calculate_volatility(self) -> float:
        """
        Рассчитывает волатильность доходности и сохраняет в self.volatility.
        :return: Волатильность (% годовых).
        """
        if len(self.candles) < 2:
            self.volatility = 0.0
            return 0.0

        closes = [candle.close for candle in self.candles]
        returns = [np.log((closes[i] / closes[i - 1]) if closes[i - 1] != 0 else 100) for i in range(1, len(closes))]
        self.volatility = np.std(returns) * np.sqrt(self.ANNUALIZATION_FACTOR[self.interval])
        return self.volatility

    def calculate_average_volume(self):
        """
        Рассчитывает средний объем и сохраняет в self.avg_volume
        :return:
        """
        if len(self.candles) < 2:
            self.avg_volume = 0.0
            return 0.0

        self.avg_volume = np.mean([c.volume for c in self.candles])
        return self.avg_volume

    def calculate_average_price_volume(self):
        """
        Рассчитывает средний объем в валюте и сохраняет в self.avg_price_volume
        :return:
        """
        if len(self.candles) < 2:
            self.avg_volume = 0.0
            return 0.0

        self.avg_price_volume = np.mean([c.volume * c.close for c in self.candles])
        return self.avg_price_volume

    def calculate_average_return(self) -> float:
        """
        Рассчитывает среднюю доходность и сохраняет в self.average_return.
        :return: Средняя доходность (% годовых).
        """
        if len(self.candles) < 2:
            self.average_return = 0.0
            return 0.0

        closes = [candle.close for candle in self.candles]
        returns = [np.log((closes[i] / closes[i - 1]) if closes[i - 1] != 0 else 100) for i in range(1, len(closes))]
        self.average_return = np.mean(returns) * self.ANNUALIZATION_FACTOR[self.interval]
        return float(self.average_return)

    def calculate_sharpe_ratio(self) -> float:
        """
        Рассчитывает коэффициент Шарпа и сохраняет в self.sharpe_ratio.
        :return: Коэффициент Шарпа.
        """
        if self.volatility is None:
            self.calculate_volatility()
        if self.average_return is None:
            self.calculate_average_return()

        if self.volatility == 0:
            self.sharpe_ratio = 0.0
            return 0.0

        self.sharpe_ratio = (self.average_return - Settings.Candles.RISK_FREE_RATE) / self.volatility
        return self.sharpe_ratio

    def calculate_max_drawdown(self) -> float:
        """
        Рассчитывает максимальную просадку и сохраняет в self.max_drawdown.
        :return: Максимальная просадка (%).
        """
        closes = [candle.close for candle in self.candles if candle.close != 0]
        if not closes:
            self.max_drawdown = 0.0
            return 0.0

        peak = closes[0]
        max_dd = 0.0
        for price in closes:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
        self.max_drawdown = max_dd * 100
        return self.max_drawdown


class DynamicMetrics(CandlesBase):
    """
    Динамические (скользящие) индикаторы.
    Все методы возвращают список значений одинаковой длины с self.candles.
    Значения до первого расчётного индекса — None.
    Кэшируются как атрибуты: sma_20, rsi_14, ema_50 и т.д.
    """

    def calculate_sma(self, period: int = 20) -> List[Optional[float]]:
        """Simple Moving Average"""
        if len(self.candles) < period:
            setattr(self, f"sma_{period}", [])
            return []

        closes = [c.close for c in self.candles]
        sma = [None] * (period - 1)
        for i in range(period - 1, len(closes)):
            window = closes[i - period + 1:i + 1]
            sma.append(sum(window) / period)
        setattr(self, f"sma_{period}", sma)
        return sma

    def calculate_ema(self, period: int = 20) -> List[Optional[float]]:
        """Exponential Moving Average"""
        if len(self.candles) < period:
            setattr(self, f"ema_{period}", [])
            return []

        closes = [c.close for c in self.candles]
        k = 2 / (period + 1)
        ema = [None] * period
        ema[period - 1] = sum(closes[:period]) / period  # начальное значение — SMA

        for i in range(period, len(closes)):
            ema.append(closes[i] * k + ema[i - 1] * (1 - k))
        setattr(self, f"ema_{period}", ema)
        return ema

    def calculate_rsi(self, period: int = 14) -> List[Optional[float]]:
        """Relative Strength Index"""
        if len(self.candles) < period + 1:
            setattr(self, f"rsi_{period}", [])
            return []

        closes = [c.close for c in self.candles]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        gains = [d if d > 0 else 0 for d in deltas]
        losses = [abs(d) if d < 0 else 0 for d in deltas]

        rsi = [None] * period

        # Первое значение — простое среднее
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

        # Дальше — сглаженное
        for i in range(period, len(deltas)):
            current_gain = gains[i]
            current_loss = losses[i]
            avg_gain = (avg_gain * (period - 1) + current_gain) / period
            avg_loss = (avg_loss * (period - 1) + current_loss) / period
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))

        setattr(self, f"rsi_{period}", rsi)
        return rsi

    def calculate_atr(self, period: int = 14) -> List[Optional[float]]:
        """Average True Range"""
        if len(self.candles) < period + 1:
            setattr(self, f"atr_{period}", [])
            return []

        tr_list = []
        for i in range(1, len(self.candles)):
            high = self.candles[i].high
            low = self.candles[i].low
            prev_close = self.candles[i - 1].close
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)

        atr = [None] * period
        # Первое значение — простое среднее
        atr.append(sum(tr_list[:period]) / period)

        # Дальше — сглаженное
        for i in range(period, len(tr_list)):
            atr.append((atr[-1] * (period - 1) + tr_list[i]) / period)

        setattr(self, f"atr_{period}", atr)
        return atr

    def calculate_momentum(self, period: int = 10) -> List[Optional[float]]:
        """Momentum: close_t - close_{t-period}"""
        if len(self.candles) < period + 1:
            setattr(self, f"momentum_{period}", [])
            return []

        closes = [c.close for c in self.candles]
        mom = [None] * period
        for i in range(period, len(closes)):
            mom.append(closes[i] - closes[i - period])
        setattr(self, f"momentum_{period}", mom)
        return mom

    def calculate_macd(self,
                       fast_period: int = 12,
                       slow_period: int = 26,
                       signal_period: int = 9) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        MACD: (macd_line, signal_line, histogram)
        """
        if len(self.candles) < slow_period + signal_period:
            setattr(self, f"macd_{fast_period}_{slow_period}_{signal_period}", ([], [], []))
            return [], [], []

        ema_fast = self.calculate_ema(fast_period)
        ema_slow = self.calculate_ema(slow_period)

        macd_line = [None if (f is None or s is None) else f - s
                     for f, s in zip(ema_fast, ema_slow)]

        # Signal line — EMA от macd_line
        signal_line = [None] * (slow_period + signal_period - 1)
        valid_macd = [x for x in macd_line if x is not None]
        if len(valid_macd) >= signal_period:
            k = 2 / (signal_period + 1)
            signal = sum(valid_macd[:signal_period]) / signal_period
            signal_line.extend([None] * (len(macd_line) - len(valid_macd)))
            for i in range(len(valid_macd) - signal_period, len(valid_macd)):
                signal = valid_macd[i] * k + signal * (1 - k)
                signal_line.append(signal)
        else:
            signal_line = [None] * len(macd_line)

        histogram = [None if (m is None or s is None) else m - s
                     for m, s in zip(macd_line, signal_line)]

        key = f"macd_{fast_period}_{slow_period}_{signal_period}"
        setattr(self, key, (macd_line, signal_line, histogram))
        return macd_line, signal_line, histogram

    def calculate_volume_ratio(self, window: int = 60) -> List[float]:
        """Текущий объём / средний объём за window дней (уже отношение → не нормируем)"""
        volumes = [c.volume for c in self.candles]
        ratio = [None] * (window - 1)
        for i in range(window - 1, len(volumes)):
            avg = np.mean(volumes[i - window + 1:i + 1])
            ratio.append(volumes[i] / avg if avg > 0 else 0.0)
        setattr(self, f"volume_ratio_{window}", ratio)
        return ratio

    # candles/models.py — заменяй полностью

    def calculate_atr_ratio(self, atr_period: int = 14, ratio_window: int = 60):
        """
        Считает ATR ratio БЕЗОПАСНО.
        Игнорирует None, работает только с float.
        """
        atr_attr = f"atr_{atr_period}"

        # Если ATR ещё не посчитан ATR — считаем
        if not hasattr(self, atr_attr) or not getattr(self, atr_attr):
            self.calculate_atr(period=atr_period)

        atr_series = getattr(self, atr_attr)
        if not atr_series:
            setattr(self, f"atr_ratio_{atr_period}_{ratio_window}", [])
            return

        # Отрезаем начальные None (их всегда atr_period штук)
        # и оставляем только валидные значения
        valid_atr = []
        for val in atr_series:
            if val is not None and val > 0:
                valid_atr.append(val)
            # Если ещё не накопилось — просто ждём
            # (не добавляем None в valid_atr!)

        if len(valid_atr) < ratio_window:
            setattr(self, f"atr_ratio_{atr_period}_{ratio_window}", [])
            return

        # Теперь считаем ratio только по чистым значениям
        ratio = []
        for i in range(ratio_window - 1, len(valid_atr)):
            window = valid_atr[i - ratio_window + 1: i + 1]
            avg = sum(window) / ratio_window  # sum и деление — только float
            current = valid_atr[i]
            ratio.append(current / avg if avg > 0 else 1.0)

        # Сохраняем
        setattr(self, f"atr_ratio_{atr_period}_{ratio_window}", ratio)

    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2.0):
        """
        Bollinger Bands: upper, middle (SMA), lower и %B.
        Сохраняет как атрибуты:
            bollinger_upper_{period}_{std_dev}
            bollinger_middle_{period}_{std_dev}
            bollinger_lower_{period}_{std_dev}
            bollinger_percent_b_{period}_{std_dev}
        """
        if len(self.candles) < period:
            key = f"bollinger_{period}_{std_dev}"
            setattr(self, f"{key}_upper", [])
            setattr(self, f"{key}_middle", [])
            setattr(self, f"{key}_lower", [])
            setattr(self, f"{key}_percent_b", [])
            return

        if not hasattr(self, f"sma_{period}"):
            self.calculate_sma(period)

        closes = [c.close for c in self.candles]
        sma = getattr(self, f"sma_{period}")

        upper = []
        lower = []
        percent_b = []

        for i in range(len(closes)):
            if i < period - 1 or sma[i] is None:
                upper.append(None)
                lower.append(None)
                percent_b.append(None)
                continue

            window = closes[i - period + 1:i + 1]
            std = np.std(window, ddof=1)
            middle = sma[i]

            up = middle + std_dev * std
            low = middle - std_dev * std

            # %B = (цена − нижняя полоса) / (верхняя − нижняя)
            pb = (closes[i] - low) / (up - low) if (up - low) != 0 else None

            upper.append(up)
            lower.append(low)
            percent_b.append(pb)

        key = f"bollinger_{period}_{std_dev}"
        setattr(self, f"{key}_upper", upper)
        setattr(self, f"{key}_middle", sma)  # middle == SMA
        setattr(self, f"{key}_lower", lower)
        setattr(self, f"{key}_percent_b", percent_b)

    def calculate_stochastic(self, k_period: int = 14, d_period: int = 3):
        """
        Stochastic Oscillator.
        Сохраняет:
            stoch_k_{k_period}
            stoch_d_{k_period}_{d_period}  (SMA от %K)
        """
        if len(self.candles) < k_period:
            setattr(self, f"stoch_k_{k_period}", [])
            setattr(self, f"stoch_d_{k_period}_{d_period}", [])
            return

        highs = [c.high for c in self.candles]
        lows = [c.low for c in self.candles]
        closes = [c.close for c in self.candles]

        k_line = []
        for i in range(len(self.candles)):
            if i < k_period - 1:
                k_line.append(None)
                continue
            window_high = max(highs[i - k_period + 1:i + 1])
            window_low = min(lows[i - k_period + 1:i + 1])
            denominator = window_high - window_low
            k_val = 100 * (closes[i] - window_low) / denominator if denominator != 0 else 50.0
            k_line.append(k_val)

        # %D — простая скользящая от %K
        d_line = [None] * (k_period - 1)
        for i in range(k_period - 1, len(k_line)):
            if None in k_line[i - d_period + 1:i + 1]:
                d_line.append(None)
            else:
                d_line.append(sum(k_line[i - d_period + 1:i + 1]) / d_period)

        setattr(self, f"stoch_k_{k_period}", k_line)
        setattr(self, f"stoch_d_{k_period}_{d_period}", d_line)

    def calculate_roc(self, period: int = 12) -> List[Optional[float]]:
        """
        Rate of Change: ((close_t / close_{t-period}) - 1) * 100
        Кэшируется как roc_{period}
        """
        if len(self.candles) < period + 1:
            setattr(self, f"roc_{period}", [])
            return []

        closes = [c.close for c in self.candles]
        roc = [None] * period

        for i in range(period, len(closes)):
            if closes[i - period] == 0:
                roc.append(None)
            else:
                roc.append((closes[i] / closes[i - period] - 1) * 100)

        setattr(self, f"roc_{period}", roc)
        return roc


class Candles(StaticMetrics, DynamicMetrics):
    """
    Класс для работы с набором свечей, наследуется от StaticMetrics и DynamicMetrics.
    Содержит метод для массового расчёта статичных метрик.
    """
    def calculate_static(self, use_buffer: bool = False) -> None:
        """
        Запускает расчёт всех статичных метрик и сохраняет их в поля объекта.
        :param use_buffer: Если True, использует self.candles, иначе загружает из БД за фиксированный период.
        """
        if not use_buffer:
            self.load_candles()
        self.calculate_volatility()
        self.calculate_average_return()
        self.calculate_average_volume()
        self.calculate_average_price_volume()
        self.calculate_sharpe_ratio()
        self.calculate_max_drawdown()
        self.calculate_atr(period=14)
        if not use_buffer:
            self.clear_buffer()

    def calculate_dynamic(self, use_buffer: bool = False) -> None:
        """Расчёт стандартного набора: SMA20/50/200, EMA12/26, RSI14, ATR14, Momentum10, MACD"""
        if not use_buffer:
            self.load_candles()
        self.calculate_sma(20)
        self.calculate_sma(50)
        self.calculate_sma(200)
        self.calculate_ema(12)
        self.calculate_ema(26)
        self.calculate_rsi(14)
        self.calculate_atr(14)
        self.calculate_momentum(10)
        self.calculate_macd(12, 26, 9)
        if not use_buffer:
            self.clear_buffer()

    def _reset_and_recalculate(self):
        """Внутренний метод для быстрого сброса метрик (только для fast-режима)"""
        for attr in list(self.__dict__.keys()):
            if attr.startswith(('sma_', 'ema_', 'rsi_', 'atr_', 'volume_ratio', 'atr_ratio')):
                setattr(self, attr, [])

    def __str__(self):
        width = 25
        return (
            f"Candles                {self.interval.name}\n"
            f"\t{'Волатильность:':<{width}}{self.volatility:>10.4f}\n"
            f"\t{'Средний объём:':<{width}}{self.avg_volume:>10.2f}\n"
            f"\t{'Средний денежный объём:':<{width}}{self.avg_price_volume:>10.2f}\n"
            f"\t{'Средняя доходность:':<{width}}{self.average_return:>10.4f}\n"
            f"\t{'Шарп:':<{width}}{self.sharpe_ratio:>10.4f}\n"
            f"\t{'Макс. просадка:':<{width}}{self.max_drawdown:>10.4f}\n"
            f"\t{'ATR_14:':<{width}}{getattr(self, 'atr_14', 'N/A'):>10}"
        )


class MultiTimeframeCandles:
    """
    Класс для управления свечами с часовым и дневным интервалами.
    """
    SUPPORTED_INTERVALS = [
        CandleInterval.CANDLE_INTERVAL_DAY,
        CandleInterval.CANDLE_INTERVAL_HOUR
    ]

    def __init__(self, figi: str, factor: float = 1):
        """
        Инициализация объекта с созданием свечей для часового и дневного интервалов.
        :param factor: Множитель для конвертации цен.
        :param figi: FIGI актива.
        """
        self.figi = figi
        self.candles: Dict[CandleInterval, Candles] = {
            CandleInterval.CANDLE_INTERVAL_HOUR: Candles(self.figi, CandleInterval.CANDLE_INTERVAL_HOUR, factor),
            CandleInterval.CANDLE_INTERVAL_DAY: Candles(self.figi, CandleInterval.CANDLE_INTERVAL_DAY, factor)
        }

    def calculate_static(self, use_buffer: bool = False) -> None:
        """
        Рассчитывает статичные метрики для часового и дневного интервалов.
        :param use_buffer: Если True, использует свечи из self.candles каждого объекта Candles,
                           иначе загружает из БД за фиксированный период.
        :return: None
        """
        for interval, candles in self.candles.items():
            candles.calculate_static(use_buffer=use_buffer)

    async def update_candles(self, from_time: [datetime, None] = None, sleep: float = 0) -> None:
        """
        Рассчитывает волатильность для часового и дневного интервалов.
        :param from_time: Дата, с которой записываем данные при пустой БД
        :param sleep: Сон между интервалами
        :return: None
        """
        for interval, candles in self.candles.items():
            await candles.update_candles(from_time=from_time)
            await asyncio.sleep(sleep)

    def drop(self):
        """
        Удаление БД свечек для всех интервалов.
        :return:
        """
        for interval, candles in self.candles.items():
            candles.drop()

    def __str__(self):
        metrics = [
            ("Волатильность", lambda c: f"{c.volatility:.4f}"),
            ("Средний объём", lambda c: f"{c.avg_volume:.2f}"),
            ("Средняя доходность", lambda c: f"{c.average_return:.4f}"),
            ("Шарп", lambda c: f"{c.sharpe_ratio:.4f}"),
            ("Макс. просадка", lambda c: f"{c.max_drawdown:.4f}"),
            ("ATR_14", lambda c: getattr(c, 'atr_14', 'N/A')),
        ]

        intervals = list(self.candles.keys())
        width_name = 22
        width_val = 12

        # Заголовок
        header = "MultiTimeframeCandles\n"
        header += "\t" + " " * width_name + "".join([f"{str(iv):>{width_val}}" for iv in intervals]) + "\n"

        # Строки метрик
        lines = []
        for name, getter in metrics:
            values = [getter(self.candles[iv]) for iv in intervals]
            line = f"\t{name:<{width_name}}" + "".join([f"{val:>{width_val}}" for val in values])
            lines.append(line)

        return header + "\n".join(lines)

    def __getitem__(self, interval: CandleInterval) -> Candles:
        """
        Возвращает объект Candles для заданного интервала.
        :param interval: Интервал свечей (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :return: Объект Candles.
        :raises KeyError: Если интервал не поддерживается.
        """
        if interval not in self.SUPPORTED_INTERVALS:
            raise KeyError(f"Неподдерживаемый интервал: {interval}")
        return self.candles[interval]

    def __getattr__(self, item):
        """
        При запросе атрибутов класса Candles возвращает атрибут из часовых свечек.
        :param item:
        :return:
        """
        return getattr(self.candles[CandleInterval.CANDLE_INTERVAL_DAY], item)
