# strategy/short_term_regime/run_training.py
from t_tech.invest import CandleInterval

from candles.time_synchronized import TimeSynchronizedContext
from strategy.short_term_regime.trainer import ShortTermRegimeTrainer, MACRO_FIGI
from candles.models import Candles
from datetime import datetime


def run_daily_training(
    stock_figies: list,
    window_days: int = 60,
    n_clusters: int = 6,
    interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY
):
    print(f"[{datetime.now()}] Запуск ежедневного обучения кластеризации режимов")

    # Загружаем все акции + макро
    all_candles = []
    for figi in stock_figies:
        c = Candles(figi=figi, interval=interval)
        c.load_candles()  # вся история
        all_candles.append(c)

    # Макро
    for name, figi in MACRO_FIGI.items():
        c = Candles(figi=figi, interval=interval)
        c.load_candles()
        all_candles.append(c)

    # Синхронизатор — используем глобальную сетку (чтобы все были на одной дате)
    sync = TimeSynchronizedContext(all_candles, master=None)

    trainer = ShortTermRegimeTrainer(
        window_days=window_days,
        n_clusters=n_clusters
    )

    # Обучение
    context = trainer.train_daily(sync.master_slave_memory_efficient(max_buffer_size=1000))
    print(trainer.predict_current(context))
    print(f"[{datetime.now()}] Обучение завершено. Модель сохранена.")


# Пример запуска
if __name__ == "__main__":
    # Твой список акций (пример)
    MY_STOCKS = ["TCS00A105XJ1", "SBER", "GAZP", "LKOH", "YNDX", ...]
    run_daily_training(MY_STOCKS, window_days=60, n_clusters=6)
