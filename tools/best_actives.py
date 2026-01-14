# tools.py
import logging
import asyncio

from t_tech.invest import CandleInterval

from stocks.models import Stocks, Stock
from bonds.models import Bonds, Bond
from etfs.models import Etfs, Etf
from futures.models import Future, Futures
from options.models import Option, Options
from currencies.models import Currency, Currencies
from commodities.models import Commodity, Commodities


async def best_bonds(filters: dict = None, key=None, update=False):
    """
    Поиск лучших облигаций с выводом сжатой информации по каждой.
    :param filters: Фильтры для БД. {'currency': 'rub', ...}
    :param key: Функция фильтрации, для вывода данных по Bond.
    :param update: Обновление перед выборкой
    :return: None
    """

    bonds = Bonds(filters=filters)
    if update:
        await bonds.update_candles(sleep=0.05)
        await bonds.update_payments(sleep=0.05)
    bonds.calculate_metrics()

    result = []
    for bond in sorted(bonds.bonds,
                       key=lambda x: [x.current_yield or 0, x.coupon_quantity_per_year, x.ytm or 0, x.current_yield or 0],
                       reverse=True):
        if not key or key(bond) or key is None:
            result.append(bond)
            print(bond)
            print("=" * 50)
    return result


async def best_stocks(filters: dict = None, key=None, update=False):
    """
    Поиск лучших акций на основе заданных фильтров и сортировки.
    :param filters: Фильтры для БД. {'currency': 'rub', 'sector': 'IT', ...}
    :param key: Функция фильтрации, для вывода данных по Stock.
    :param update: Обновление
    :return: None
    """
    stocks = Stocks(filters=filters)
    if update:
        await stocks.update_candles(0.05)
        await stocks.update_payments(0.05)
    stocks.calculate_metrics()

    interval = CandleInterval.CANDLE_INTERVAL_DAY

    res = []
    for stock in sorted(stocks.stocks,
                        key=lambda x: [x.candles.max_drawdown],
                        reverse=True):
        if key and key(stock) or key is None:
            res.append(stock)
            print(stock)
            print("=" * 50)
    return res


async def best_etfs(filters: dict = None, key=None, update=False):
    """
    Поиск лучших ETF на основе заданных фильтров и сортировки.
    :param filters: Фильтры для БД. {'currency': 'rub', 'sector': 'IT', ...}
    :param key: Функция фильтрации, для вывода данных по Stock.
    :param update: Обновление инфы
    :return: None
    """
    interval = CandleInterval.CANDLE_INTERVAL_DAY

    etfs = Etfs(filters=filters)
    if update:
        await etfs.update_candles(sleep=0.05)
        await etfs.update_payments(sleep=0.05)
    etfs.calculate_metrics()

    res = []
    for etf in sorted(etfs.etfs,
                        key=lambda x: [x.payments.dividend_stability, x.payments.trailing_yield],
                        reverse=True):
        if key and key(etf) or key is None:
            res.append(etf)
            print(etf)
            print("="*50)
    return res
