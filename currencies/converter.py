# currencies/converter.py
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime
import bisect

from candles.models import Candles, CandleInterval, MultiTimeframeCandles


# ============================================================================= #
# CURRENCY_FIGI_MAP — только рабочие валюты
# ============================================================================= #
CURRENCY_FIGI_MAP: Dict[str, str] = {
    'eur': 'BBG0013HJJ31',
    'usd': 'BBG0013HGFT4',
    'cny': 'BBG0013HRTL0',
    'try': 'BBG0013J12N1',
    'hkd': 'BBG0013HSW87',
    'sek': 'BBG000B9XRY4',
    'kzt': 'BBG0013HG026',
    'uzs': 'BBG0013HQ310',
    'byn': 'BBG00D87WQY7',
    'amd': 'BBG0013J7V24',
    'kgs': 'BBG0013J7Y00',
    'tjs': 'BBG0013J11P1',
}


class CurrencyConvert:
    def __init__(self, figi: str | None, iso_name: str):
        self.figi = figi
        self.iso_name = iso_name.upper()
        self.is_supported = figi is not None
        self.candles = MultiTimeframeCandles(figi=figi, factor=1) if figi else None

    # --------------------------------------------------------------------- #
    # Все методы — безопасные
    # --------------------------------------------------------------------- #
    def _check(self):
        if not self.is_supported:
            return False
        return True

    def value_to(self, value: float | list[float], date: datetime = None) -> float | list[float]:
        if not self._check():
            return value
        candle = self.candles.get_candle_by_date(date)
        if not candle:
            return value
        rate = candle.close
        return [v * rate for v in value] if isinstance(value, list) else value * rate

    def value_from(self, value: float | list[float], date: datetime = None) -> float | list[float]:
        if not self._check():
            return value
        candle = self.candles.get_candle_by_date(date)
        if not candle or candle.close == 0:
            return value
        rate = candle.close
        return [v / rate for v in value] if isinstance(value, list) else value / rate

    def candles_to(self, candles: Candles) -> None:
        if not self._check() or not candles.candles:
            return
        try:
            for c in candles.candles:
                factor = self._find_rate_in_buffer(c.time, candles.interval)
                c.open_ *= factor
                c.high *= factor
                c.low *= factor
                c.close *= factor
            candles.currency = "rub"
            candles.calculate_static(use_buffer=True)
        except:
            pass  # если буфер пуст — пропускаем

    def candles_from(self, candles: Candles) -> None:
        if not self._check() or not candles.candles:
            return
        try:
            for c in candles.candles:
                factor = self._find_rate_in_buffer(c.time, candles.interval)
                if factor == 0:
                    continue
                c.open_ /= factor
                c.high /= factor
                c.low /= factor
                c.close /= factor
            candles.currency = self.iso_name
            candles.calculate_static(use_buffer=True)
        except:
            pass

    def payments_to(self, payments_obj: Any) -> None:
        if not self._check() or not payments_obj.payments:
            return
        try:
            for p in payments_obj.payments:
                factor = self._find_rate_in_buffer(p.payment_date, CandleInterval.CANDLE_INTERVAL_DAY)
                p.amount *= factor
        except:
            pass

    def payments_from(self, payments_obj: Any) -> None:
        if not self._check() or not payments_obj.payments:
            return
        try:
            for p in payments_obj.payments:
                factor = self._find_rate_in_buffer(p.payment_date, CandleInterval.CANDLE_INTERVAL_DAY)
                if factor == 0:
                    continue
                p.amount /= factor
        except:
            pass

    def _find_rate_in_buffer(self, target_date: datetime, interval: CandleInterval) -> float:
        if not self.candles:
            return 1.0
        timeframe = self.candles[interval]
        buffer = timeframe.candles
        if not buffer:
            return 1.0
        dates = [c.time for c in buffer]
        idx = bisect.bisect_left(dates, target_date)
        if idx < len(dates) and dates[idx] == target_date:
            return buffer[idx].close
        if idx == 0:
            return buffer[0].open
        return buffer[idx - 1].close


# ============================================================================= #
# Converter — безопасный доступ
# ============================================================================= #
class Converter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache: dict[str, CurrencyConvert] = {}
        return cls._instance

    def _get(self, iso_name: str) -> CurrencyConvert:
        iso_name = iso_name.lower()
        if iso_name in self._cache:
            return self._cache[iso_name]

        figi = CURRENCY_FIGI_MAP.get(iso_name)
        obj = CurrencyConvert(figi=figi, iso_name=iso_name)
        self._cache[iso_name] = obj
        return obj

    def __getattr__(self, name: str) -> CurrencyConvert:
        return self._get(name)

    def __getitem__(self, item):
        return self._get(item)

    def convert(self, obj: Any, from_iso: str, to_iso: str) -> Any:
        from_iso = from_iso.lower()
        to_iso = to_iso.lower()

        if from_iso != "rub":
            getattr(self, from_iso).candles_to(obj) if isinstance(obj, Candles) else getattr(self, from_iso).payments_to(obj)
        if to_iso != "rub":
            getattr(self, to_iso).candles_from(obj) if isinstance(obj, Candles) else getattr(self, to_iso).payments_from(obj)
        return obj

    async def update_candles(self, sleep: float = 0.0):
        for iso in CURRENCY_FIGI_MAP:
            self._get(iso)
        for currency in self._cache.values():
            if currency.is_supported:
                await currency.candles.update_candles(sleep=sleep)
        self._cache.clear()  # очистка кэша после обновления


# ============================================================================= #
# Глобальный экземпляр
# ============================================================================= #
converter = Converter()
