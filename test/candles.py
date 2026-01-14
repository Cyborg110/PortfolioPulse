# /test/candles.py
import asyncio

from datetime import datetime, timedelta
from t_tech.invest import CandleInterval
from typing import List, Tuple
from stocks.models import Stock, Stocks
from bonds.models import Bond, Bonds
from currencies.models import Currencies


def test_static_metrics():
    """
    Тестирует статические метрики для дневного и часового интервалов.
    Вызывает calculate_static и выводит значения метрик для Sber.
    """
    # Создаём объект Stock для Сбербанка
    stock = Stock("Sber")

    # Интервалы для тестирования
    intervals = [CandleInterval.CANDLE_INTERVAL_DAY, CandleInterval.CANDLE_INTERVAL_HOUR]

    # Проходим по обоим интервалам
    for interval in intervals:
        print(f"\n=== Тестирование статических метрик для интервала: {interval.name} ===")
        candles = stock.candles[interval]

        # Вызываем расчёт всех статичных метрик
        candles.calculate_static(use_buffer=False)

        # Выводим кэшированные значения
        print(f"Волатильность: {candles.volatility:.4f}")
        print(f"Средняя годовая доходность: {candles.average_return:.4f}%")
        print(f"Коэффициент Шарпа: {candles.sharpe_ratio:.4f}")
        print(f"Максимальная просадка: {candles.max_drawdown:.4f}%")
        print(f"ATR (период 14): {candles.atr_14:.4f}")


async def get_candle_by_date():
    # Проверка запроса свечи по дате
    stock = Stock("Sber")
    await stock.candles.update_candles()
    candle = stock.candles[CandleInterval.CANDLE_INTERVAL_DAY].get_candle_by_date(
        datetime.strptime("12-12-2024 15:00:00", "%d-%m-%Y %H:%M:%S")
    )
    print(candle)


async def calculate_volatility():
    # Расчет волатильности по всем валютам и металлам
    currencies = Currencies({"ticker": "SLVRUB_TOM"})
    for currency in currencies:
        print(currency.ticker, currency.figi,)
        await currency.candles.update_candles(from_time=currency.first_1day_candle_date)

        print(currency.candles.calculate_volatility())


async def update_candles():
    stocks = Currencies()
    await stocks.update_candles(1)


def sorted_by_static_metrics():
    interval = CandleInterval.CANDLE_INTERVAL_DAY
    stocks = Stocks(filters={"currency": "rub"})

    for stock in stocks:
        stock.candles[interval].calculate_static()

    stocks.sort(key=lambda x: x.candles[interval].volatility)
    print("Волатильность\n", [(stock.ticker, stock.candles[interval].volatility) for stock in stocks][-5:])

    stocks.sort(key=lambda x: x.candles[interval].average_return)
    print("Средняя дневная доходность\n", [(stock.ticker, stock.candles[interval].average_return) for stock in stocks][-5:])

    stocks.sort(key=lambda x: x.candles[interval].sharpe_ratio)
    print("Коэффициент Шарпа\n", [(stock.ticker, stock.candles[interval].sharpe_ratio) for stock in stocks][-5:])

    stocks.sort(key=lambda x: x.candles[interval].atr_14)
    print("atr_14\n", [(stock.ticker, stock.candles[interval].atr_14) for stock in stocks][-5:])

    stocks.sort(key=lambda x: x.candles[interval].max_drawdown, reverse=True)
    print("Максимальная просадка\n", [(stock.ticker, stock.candles[interval].max_drawdown) for stock in stocks][-5:])


def find_best_stocks(top_n: int = 3) -> List[Tuple[str, float, dict]]:
    """
    Находит топ-N акций по совокупной оценке статических метрик на дневном интервале.
    :param top_n: Количество лучших акций для вывода (по умолчанию 3).
    :return: Список кортежей (ticker, score, metrics_dict) для топ-N акций.
    """
    # Инициализируем Stocks с фильтром по валюте RUB
    stocks = Stocks(filters={"currency": "rub"})
    interval = CandleInterval.CANDLE_INTERVAL_DAY

    # Вычисляем метрики для всех акций
    for stock in stocks:
        stock.candles[interval].calculate_static(use_candles=False)

    # Собираем метрики для каждой акции
    stock_metrics = []
    for stock in stocks:
        candles = stock.candles[interval]
        metrics = {
            "volatility": candles.volatility or 0.0,
            "average_return": candles.average_return or 0.0,
            "sharpe_ratio": candles.sharpe_ratio or 0.0,
            "max_drawdown": candles.max_drawdown or 0.0,
            "atr_14": candles.atr_14 or 0.0,
        }
        stock_metrics.append((stock.ticker, metrics))

    # Нормализация метрик
    metrics_values = {
        "volatility": [m[1]["volatility"] for m in stock_metrics],
        "average_return": [m[1]["average_return"] for m in stock_metrics],
        "sharpe_ratio": [m[1]["sharpe_ratio"] for m in stock_metrics],
        "max_drawdown": [m[1]["max_drawdown"] for m in stock_metrics],
        "atr_14": [m[1]["atr_14"] for m in stock_metrics],
    }

    normalized_metrics = []
    for ticker, metrics in stock_metrics:
        norm_metrics = {}
        for key in metrics:
            values = metrics_values[key]
            min_val, max_val = min(values), max(values)
            if max_val == min_val:  # Избегаем деления на ноль
                norm_metrics[key] = 0.5
            else:
                norm_metrics[key] = (metrics[key] - min_val) / (max_val - min_val)

        # Для волатильности используем перевёрнутую параболу: умеренные значения лучше
        norm_metrics["volatility"] = 1 - 4 * (norm_metrics["volatility"] - 0.5) ** 2
        # Для max_drawdown инвертируем: низкая просадка лучше
        norm_metrics["max_drawdown"] = 1 - norm_metrics["max_drawdown"]

        # Вычисляем совокупную оценку
        score = (
            0.4 * norm_metrics["sharpe_ratio"] +
            0.3 * norm_metrics["average_return"] +
            0.15 * norm_metrics["max_drawdown"] +
            0.1 * norm_metrics["volatility"] +
            0.05 * norm_metrics["atr_14"]
        )
        normalized_metrics.append((ticker, score, metrics))

    # Сортируем по оценке и берём топ-N
    normalized_metrics.sort(key=lambda x: x[1], reverse=True)
    top_stocks = normalized_metrics[:top_n]

    # Вывод результатов
    print(f"\n=== Топ-{top_n} акций по совокупной оценке (дневной интервал) ===")
    for ticker, score, metrics in top_stocks:
        print(f"\nАкция: {ticker}, Оценка: {score:.4f}")
        print(f"  Волатильность: {metrics['volatility']:.4f}")
        print(f"  Средняя годовая доходность: {metrics['average_return']:.4f}%")
        print(f"  Коэффициент Шарпа: {metrics['sharpe_ratio']:.4f}")
        print(f"  Максимальная просадка: {metrics['max_drawdown']:.4f}%")
        print(f"  ATR (период 14): {metrics['atr_14']:.4f}")

    return top_stocks


def find_undervalued_stocks(top_n: int = 3) -> List[Tuple[str, float, dict]]:
    """
    Находит топ-N недооценённых акций по совокупной оценке статических метрик на дневном интервале.
    Учитывает низкую текущую цену, умеренную волатильность, низкую просадку и положительный Шарп.
    :param top_n: Количество лучших акций для вывода (по умолчанию 3).
    :return: Список кортежей (ticker, score, metrics_dict) для топ-N акций.
    """
    # Инициализируем Stocks с фильтром по валюте RUB
    stocks = Stocks(filters={"currency": "rub"})
    interval = CandleInterval.CANDLE_INTERVAL_DAY
    one_year_ago = datetime.utcnow() - timedelta(days=365)

    # Вычисляем метрики и собираем данные
    stock_metrics = []
    for stock in stocks:
        candles = stock.candles[interval]
        # Рассчитываем статические метрики
        candles.calculate_static(use_candles=False)

        # Находим минимальную цену за год
        candles.load_candles(from_date=one_year_ago, to_date=datetime.utcnow())
        if not candles.candles:
            continue  # Пропускаем, если нет данных
        min_price = min(candle.close for candle in candles.candles)
        current_price = candles.price or min_price  # Текущая цена или минимум, если None

        # Собираем метрики
        metrics = {
            "volatility": candles.volatility or 0.0,
            "average_return": candles.average_return or 0.0,
            "sharpe_ratio": candles.sharpe_ratio or 0.0,
            "max_drawdown": candles.max_drawdown or 0.0,
            "atr_14": candles.atr_14 or 0.0,
            "price_ratio": min_price / current_price if current_price > 0 else 1.0
        }
        stock_metrics.append((stock.ticker, metrics))

    # Нормализация метрик
    metrics_values = {
        "volatility": [m[1]["volatility"] for m in stock_metrics],
        "average_return": [m[1]["average_return"] for m in stock_metrics],
        "sharpe_ratio": [m[1]["sharpe_ratio"] for m in stock_metrics],
        "max_drawdown": [m[1]["max_drawdown"] for m in stock_metrics],
        "atr_14": [m[1]["atr_14"] for m in stock_metrics],
        "price_ratio": [m[1]["price_ratio"] for m in stock_metrics]
    }

    normalized_metrics = []
    for ticker, metrics in stock_metrics:
        norm_metrics = {}
        for key in metrics:
            values = metrics_values[key]
            min_val, max_val = min(values), max(values)
            if max_val == min_val:  # Избегаем деления на ноль
                norm_metrics[key] = 0.5
            else:
                norm_metrics[key] = (metrics[key] - min_val) / (max_val - min_val)

        # Для волатильности и ATR предпочитаем умеренные значения
        norm_metrics["volatility"] = 1 - 4 * (norm_metrics["volatility"] - 0.5) ** 2
        norm_metrics["atr_14"] = 1 - 4 * (norm_metrics["atr_14"] - 0.5) ** 2
        # Для max_drawdown инвертируем: низкая просадка лучше
        norm_metrics["max_drawdown"] = 1 - norm_metrics["max_drawdown"]

        # Вычисляем совокупную оценку
        score = (
            0.4 * norm_metrics["price_ratio"] +
            0.3 * norm_metrics["sharpe_ratio"] +
            0.15 * norm_metrics["max_drawdown"] +
            0.1 * norm_metrics["volatility"] +
            0.05 * norm_metrics["atr_14"]
        )
        normalized_metrics.append((ticker, score, metrics))

    # Сортируем по оценке и берём топ-N
    normalized_metrics.sort(key=lambda x: x[1], reverse=True)
    top_stocks = normalized_metrics[:top_n]

    # Вывод результатов
    print(f"\n=== Топ-{top_n} недооценённых акций (дневной интервал) ===")
    for ticker, score, metrics in top_stocks:
        print(f"\nАкция: {ticker}, Оценка: {score:.4f}")
        print(f"  Текущая цена к минимальной: {metrics['price_ratio']:.4f}")
        print(f"  Волатильность: {metrics['volatility']:.4f}")
        print(f"  Средняя годовая доходность: {metrics['average_return']:.4f}%")
        print(f"  Коэффициент Шарпа: {metrics['sharpe_ratio']:.4f}")
        print(f"  Максимальная просадка: {metrics['max_drawdown']:.4f}%")
        print(f"  ATR (период 14): {metrics['atr_14']:.4f}")

    return top_stocks


def find_undervalued_volatile_stocks(top_n: int = 3) -> List[Tuple[str, float, dict]]:
    """
    Находит топ-N недооценённых акций с высокой волатильностью на дневном интервале.
    Критерии: цена близка к годовому минимуму и высокая волатильность.
    :param top_n: Количество лучших акций для вывода (по умолчанию 3).
    :return: Список кортежей (ticker, score, metrics_dict) для топ-N акций.
    """
    # Инициализируем Stocks с фильтром по валюте RUB
    stocks = Stocks(filters={"currency": "rub"})
    interval = CandleInterval.CANDLE_INTERVAL_DAY
    one_year_ago = datetime.utcnow() - timedelta(days=365)

    # Собираем метрики для каждой акции
    stock_metrics = []
    for stock in stocks:
        candles = stock.candles[interval]
        # Рассчитываем статические метрики (для volatility)
        candles.calculate_static(use_candles=False)

        # Загружаем свечи за год для вычисления price_ratio
        candles.load_candles(from_date=one_year_ago, to_date=datetime.utcnow())
        if not candles.candles:
            continue  # Пропускаем, если нет данных
        min_price = min(candle.close for candle in candles.candles)
        current_price = candles.price or min_price  # Текущая цена или минимум, если None

        # Собираем метрики
        metrics = {
            "volatility": candles.volatility or 0.0,
            "price_ratio": min_price / current_price if current_price > 0 else 1.0
        }
        # Пропускаем акции с нулевой волатильностью (недостаток данных)
        if metrics["volatility"] == 0.0:
            continue
        stock_metrics.append((stock.ticker, metrics))

    # Нормализация метрик
    metrics_values = {
        "volatility": [m[1]["volatility"] for m in stock_metrics],
        "price_ratio": [m[1]["price_ratio"] for m in stock_metrics]
    }

    normalized_metrics = []
    for ticker, metrics in stock_metrics:
        norm_metrics = {}
        for key in metrics:
            values = metrics_values[key]
            min_val, max_val = min(values), max(values)
            if max_val == min_val:  # Избегаем деления на ноль
                norm_metrics[key] = 0.5
            else:
                norm_metrics[key] = (metrics[key] - min_val) / (max_val - min_val)

        # Вычисляем совокупную оценку
        score = 0.6 * norm_metrics["price_ratio"] + 0.4 * norm_metrics["volatility"]
        normalized_metrics.append((ticker, score, metrics))

    # Сортируем по оценке и берём топ-N
    normalized_metrics.sort(key=lambda x: x[1], reverse=True)
    top_stocks = normalized_metrics[:top_n]

    # Вывод результатов
    print(f"\n=== Топ-{top_n} недооценённых акций с высокой волатильностью (дневной интервал) ===")
    for ticker, score, metrics in top_stocks:
        print(f"\nАкция: {ticker}, Оценка: {score:.4f}")
        print(f"  Текущая цена к минимальной: {metrics['price_ratio']:.4f}")
        print(f"  Волатильность: {metrics['volatility']:.4f}")

    return top_stocks


async def drop_candles():
    bonds = Bonds({'currency': "rub"})
    for bond in bonds:
        bond.candles.drop()
    await bonds.update_candles(0.05)


# asyncio.run(drop_candles())
# test_static_metrics()
# asyncio.run(update_candles())
# sorted_by_static_metrics()
# find_best_stocks(top_n=3)
# find_undervalued_stocks(top_n=3)
# find_undervalued_volatile_stocks(top_n=10)
# drop_candles()
