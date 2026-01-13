# candles/utils.py или strategy/utils/no_lookahead.py

from datetime import datetime
from typing import Generator, Optional
from candles.models import Candles, CandleInterval
from copy import deepcopy


def sliding_window_isolated(
        figi: str,
        interval: CandleInterval,
        start: datetime,
        stop: Optional[datetime] = None,
        window_size: int = 60,
        factor: float = 1.0
) -> Generator[Candles, None, None]:
    """
    Генератор с полной информационной изоляцией.

    1. Создаёт полный буфер: все свечи с start до stop (включительно)
    2. Создаёт изолированный объект Candles (пустой)
    3. На каждом шаге принудительно перезаписывает .candles и .last_candle
    4. Пересчитывает динамические метрики только на доступных данных
    5. yield'ит изолированный объект — будущее физически недоступно

    Args:
        figi: FIGI инструмента
        interval: CandleInterval (обычно DAY)
        start: datetime — первая свеча в тесте
        stop: datetime — последняя (по умолчанию сейчас)
        window_size: сколько свечей в окне (например 60)
        factor: для облигаций и т.д.

    Yields:
        Candles — полностью изолированный объект, знает только прошлое и настоящее
    """
    if stop is None:
        stop = datetime.utcnow()

    # 1. Полный буфер — один раз загружаем из БД
    full_candles_obj = Candles(figi=figi, interval=interval, factor=factor)
    full_candles_obj.load_candles(from_date=start, to_date=stop)

    full_list = [c for c in full_candles_obj.candles if start <= c.time <= stop]
    full_list.sort(key=lambda x: x.time)

    if len(full_list) < window_size:
        raise ValueError(f"Недостаточно свечей: {len(full_list)} < {window_size}")

    # 2. Создаём один раз изолированный объект (пустой, но с правильными полями)
    isolated = Candles(figi=figi, interval=interval, factor=factor)
    isolated.candles = []  # очищаем
    isolated.last_candle = None

    # 3. Основной цикл — скользящее окно
    for end_idx in range(window_size - 1, len(full_list)):
        window_slice = full_list[end_idx - window_size + 1: end_idx + 1]

        # Принудительно перезаписываем буфер
        isolated.candles = window_slice
        isolated.last_candle = window_slice[-1]

        # Сбрасываем все динамические метрики — они будут пересчитаны заново
        for attr in list(isolated.__dict__.keys()):
            if attr.startswith(('sma_', 'ema_', 'rsi_', 'atr_', 'bollinger_', 'stoch_', 'roc_', 'momentum_')):
                setattr(isolated, attr, [])
        # Также сбрасываем статические, если не нужны
        isolated.volatility = None
        isolated.sharpe_ratio = None
        isolated.max_drawdown = None

        yield isolated
