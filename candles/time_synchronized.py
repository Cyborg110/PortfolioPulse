# strategy/utils/time_sync.py

from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Generator
from candles.models import Candles
import bisect


class TimeSynchronizedContext:
    """
    Синхронизатор Candles-объектов.
    • Никаких мутаций внутри Candles – только в этом классе.
    • Никаких deepcopy.
    • Полный контроль памяти через параметр `max_buffer_size`.
    • Пересчёт метрик делается только в твоём коде (синхронизатор НЕ пересчитывает ничего).
    • Используется только уже существующий метод Candles.load_candles(from_date, to_date).
    """

    def __init__(
        self,
        candles_list: List[Candles],
        master: Optional[Candles] = None,
    ):
        self.all_candles = {c.figi: c for c in candles_list}
        self.master = master or candles_list[0]

    # ------------------------------------------------------------------ #
    # 1. Master-Slave режим
    # ------------------------------------------------------------------ #

    def master_slave_memory_efficient(self, max_buffer_size: int = 500) -> Generator[Dict[str, Candles], None, None]:
        """
        Экономия памяти – на каждом шаге подгружаем ровно нужный диапазон.
        param: max_buffer_size: сколько свечей держать в буфере
        """
        master = self.master

        # Полный список дат мастера (один раз)
        master_dates = [c.time for c in master.candles]
        master_dates.sort()

        for ref_candle in master.candles:
            current_date = ref_candle.time

            context: Dict[str, Candles] = {}

            for figi, candles_obj in self.all_candles.items():
                # Считаем, с какой даты нам нужны свечи
                start_date = current_date - timedelta(days=max_buffer_size * 2)  # запас

                candles_obj.load_candles(from_date=start_date, to_date=current_date)

                # Оставляем только нужное количество свечей (контроль памяти)
                if len(candles_obj.candles) > max_buffer_size:
                    candles_obj.candles = candles_obj.candles[-max_buffer_size:]

                candles_obj.last_candle = candles_obj.candles[-1] if candles_obj.candles else None

                context[figi] = candles_obj

            yield context

    def master_slave_fast(self, max_buffer_size: int = 2000) -> Generator[Dict[str, Candles], None, None]:
        """
        Всё в RAM – максимальная скорость.
        Загружаем один раз всю историю и потом только обрезаем срез.
        """
        # один раз загружаем всё
        full_buffers: Dict[str, List] = {}
        for figi, c in self.all_candles.items():
            c.load_candles()  # без параметров – вся история
            buf = c.candles[:]
            buf.sort(key=lambda x: x.time)
            full_buffers[figi] = buf[:max_buffer_size]  # сразу ограничиваем

        master_buf = full_buffers[self.master.figi]

        for ref_candle in master_buf:
            current_date = ref_candle.time

            context: Dict[str, Candles] = {}

            for figi, buffer in full_buffers.items():
                # находим последнюю доступную свечу на current_date
                idx = bisect.bisect_right([c.time for c in buffer], current_date) - 1
                if idx < 0:
                    context[figi] = None
                    continue

                # создаём изолированный объект (без deepcopy!)
                iso = Candles(figi=figi, interval=buffer[0].interval)
                iso.candles = buffer[: idx + 1]                 # просто срез списка
                iso.last_candle = buffer[idx]

                context[figi] = iso

            yield context

    # ------------------------------------------------------------------ #
    # 2. Global Grid режим (общая временная сетка)
    # ------------------------------------------------------------------ #

    def global_grid_memory_efficient(self, max_buffer_size: int = 500) -> Generator[Dict[str, Candles], None, None]:
        """Экономия памяти – подгружаем диапазон на каждой новой дате сетки."""
        # собираем уникальные даты из всех инструментов
        all_dates = set()
        for c in self.all_candles.values():
            for candle in c.candles:
                all_dates.add(candle.time.date())
        dates = sorted(all_dates)

        for d in dates:
            current_date = datetime.combine(d, datetime.min.time())

            context: Dict[str, Candles] = {}
            start_date = current_date - timedelta(days=max_buffer_size * 2)

            for figi, candles_obj in self.all_candles.items():
                candles_obj.load_candles(from_date=start_date, to_date=current_date)

                if len(candles_obj.candles) > max_buffer_size:
                    candles_obj.candles = candles_obj.candles[-max_buffer_size:]

                candles_obj.last_candle = candles_obj.candles[-1] if candles_obj.candles else None
                context[figi] = candles_obj

            yield context

    def global_grid_fast(self, max_buffer_size: int = 2000) -> Generator[Dict[str, Candles], None, None]:
        """Всё в RAM – самая быстрая версия для глобальной сетки."""
        full_buffers: Dict[str, List] = {}
        for figi, c in self.all_candles.items():
            c.load_candles()
            buf = sorted(c.candles, key=lambda x: x.time)
            full_buffers[figi] = buf[-max_buffer_size:]  # сразу ограничиваем

        all_dates = set()
        for buf in full_buffers.values():
            all_dates.update(c.time.date() for c in buf)
        dates = sorted(all_dates)

        for d in dates:
            current_date = datetime.combine(d, datetime.min.time())
            context: Dict[str, Candles] = {}

            for figi, buffer in full_buffers.items():
                idx = bisect.bisect_right([c.time for c in buffer], current_date) - 1
                if idx < 0:
                    context[figi] = None
                    continue

                iso = Candles(figi=figi, interval=buffer[0].interval)
                iso.candles = buffer[: idx + 1]
                iso.last_candle = buffer[idx]
                context[figi] = iso

            yield context
            