# main.py
import asyncio
from tools.best_actives import best_stocks, best_bonds, best_etfs
from tools.plot import plot_assets, Selection
from tools.update import *
from api_client import tinkoff_api_client


async def update():
    print(await update_market_db())
    # print(await update_candles_db())


async def best():
    assets = await best_stocks(filters={"currency": "rub"}, update=False)
    # assets = await best_etfs(filters={"currency": "rub"}, update=False)
    """assets = await best_bonds(filters={"currency": "rub",
                                       "floating_coupon_flag": False,
                                       "amortization_flag": False,
                                       "risk_level": 1},
                              key=lambda bond: bond.days_to_maturity > 180 and \
                                               (bond.candles.last_candle.close * 100 / bond.nominal > 60) if bond.candles.last_candle else False
                              )"""

    # Пример вызова (предполагая, что у вас есть список bonds из best_bonds или Bonds):
    plot_assets(assets, Selection.STOCKS)


async def short_term():
    # TODO: Перепроверить все и возможно переписать.
    from strategy.short_term_regime.run_trainig import run_daily_training
    stocks = [Stock("MVID")]
    run_daily_training([s.figi for s in stocks], window_days=60, n_clusters=6)


if __name__ == "__main__":
    # asyncio.run(update())
    asyncio.run(best())
    # asyncio.run(short_term())

    # from test import candles      # Тестирование свечей
    # from test import payments       # Тестирование выплат
