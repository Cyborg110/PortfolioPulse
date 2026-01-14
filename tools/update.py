# tools/update.py
import logging
import asyncio

from t_tech.invest import CandleInterval

from api_client import tinkoff_api_client
from stocks.database import stocks_database, Stock as Stock_db
from bonds.database import bonds_database, Bond as Bond_db
from etfs.database import etfs_database, Etf as Etf_db
from futures.database import futures_database, Future as Future_db
from options.database import options_database, Option as Option_db
from currencies.database import currencies_database, Currency as Currency_db
from commodities.database import commodities_database, Commodity as Commodity_db

from stocks.models import Stock, Stocks
from bonds.models import Bond, Bonds
from etfs.models import Etf, Etfs
from futures.models import Future, Futures
from options.models import Option, Options
from currencies.models import Currency, Currencies
from currencies.converter import converter
from commodities.models import Commodity, Commodities


async def update_market_db():
    """
    Полное обновление всех таблиц базы данных market_data данными из Tinkoff Invest API.
    Каждая таблица очищается перед обновлением.

    - Собирает и возвращает новые/удалённые TICKER по каждому типу активов.
    - Формат: {"stocks": {"new": [...], "removed": [...]}, ...}

    Returns:
        dict: Результаты обновления + изменения по ticker.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    # Список: (название, БД, модель, API-метод)
    asset_configs = [
        ("Stocks", stocks_database, Stock_db, tinkoff_api_client.get_shares, Stock),
        ("Bonds", bonds_database, Bond_db, tinkoff_api_client.get_bonds, Bond),
        ("ETFs", etfs_database, Etf_db, tinkoff_api_client.get_etfs, Etf),
        # ("Futures", futures_database, Future_db, tinkoff_api_client.get_futures, Future),
        ("Currencies", currencies_database, Currency_db, tinkoff_api_client.get_currencies, Currency),
        ("Commodities", commodities_database, Commodity_db, tinkoff_api_client.get_commodity, Commodity),
        # ("Options", options_database, Option_db, tinkoff_api_client.get_options, Option),
    ]

    results = {}
    ticker_changes = {}  # <-- Теперь по TICKER

    for db_name, db, model_db, api_getter, model in asset_configs:
        try:
            logger.info(f"Обновление {db_name}...")

            # 1. Получаем данные из API
            instruments = await api_getter()
            api_tickers = {inst.ticker for inst in instruments if inst.ticker}

            # 2. Получаем текущие TICKER из БД
            with db.Session() as session:
                db_tickers = {row[0] for row in session.query(model_db.ticker).all() if row[0]}

            # 3. Определяем изменения
            new_tickers = api_tickers - db_tickers
            removed_tickers = db_tickers - api_tickers

            # Удаление всей информации по удаленным тикерам
            for ticker in removed_tickers:
                remove_ticker(ticker, model)

            # Сохраняем изменения
            ticker_changes[db_name.lower()] = {
                "new": sorted(list(new_tickers)),
                "removed": sorted(list(removed_tickers))
            }

            # 4. Полная перезапись (как и было)
            with db.Session() as session:
                session.query(model_db).delete()
                session.commit()

            await db.fetch_data()

            with db.Session() as session:
                count = session.query(model_db).count()

            logger.info(f"Успешно обновлено {db_name}: {count} записей")
            results[db_name] = {"status": "success", "records": count}

        except Exception as e:
            logger.error(f"Ошибка при обновлении {db_name}: {str(e)}")
            results[db_name] = {"status": "error", "message": str(e)}
            ticker_changes[db_name.lower()] = {"new": [], "removed": []}

    # Добавляем изменения по ticker в результат
    results["ticker_changes"] = ticker_changes

    return results


def remove_ticker(ticker, models: [Stock, Etf, Bond, Currency, Commodity, Future, Option]):
    """
    Удаление всей информации (свечи, выплаты) по тикеру.
    :param ticker:
    :param models:
    :return:
    """
    mod = models(ticker)        # Модель актива
    mod.drop()


async def update_candles_db():
    """
    Обновление всеx таблиц свечей.
    :return:
    """
    filters = {"currency": "rub", "buy_available_flag": True, "sell_available_flag": True}

    # stocks = Stocks(filters=filters)
    # bonds = Bonds(filters=filters)
    # etfs = Etfs(filters=filters)
    # futures = Futures(filters=filters)
    # currencies = Currencies()
    commodities = Commodities()

    print("\n--------Обновляем свечи--------\n")

    """print("--------Обновляем акции--------")
    await stocks.update_candles(sleep=0.05)
    await asyncio.sleep(30)

    print("--------Обновляем Облигации--------")
    await bonds.update_candles(sleep=0.05)
    await asyncio.sleep(30)

    print("--------Обновляем ETF--------")
    await etfs.update_candles(sleep=0.05)
    await asyncio.sleep(30)"""

    print("--------Обновляем фьючерсы--------")
    # await futures.update_candles(sleep=0.05)
    # await asyncio.sleep(30)

    print("--------Обновляем валюты--------")
    # await currencies.update_candles(sleep=0.05)
    # await asyncio.sleep(30)

    # print("--------Обновляем валюты конвертера--------")
    # await converter.update_candles(sleep=0.05)

    print("--------Обновляем индексы--------")
    await commodities.update_candles(sleep=0.05)
    await asyncio.sleep(30)


async def update_payments_db():
    """
    Обновление всей таблицы выплат (акции, etf, облигации).
    :return:
    """
    filters = {"currency": "rub"}

    stocks = Stocks(filters=filters)
    bonds = Bonds(filters=filters)
    etfs = Etfs(filters=filters)

    print("\n--------Обновляем выплаты--------\n")

    print("--------ETF--------")
    await etfs.update_payments(sleep=0.075)
    await asyncio.sleep(30)

    print("--------Акции--------")
    await stocks.update_payments(sleep=0.075)
    await asyncio.sleep(30)

    print("--------Облигации--------")
    await bonds.update_payments(sleep=0.075)
    await asyncio.sleep(30)
