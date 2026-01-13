# /test/payments.py
import asyncio
from datetime import datetime, timedelta
from stocks.models import Stock, Stocks
from etfs.models import Etf, Etfs
from bonds.models import Bond, Bonds


async def test_payments():
    """
    Функция для тестирования модуля Payments внутри объекта Stock.
    Создает объект Stock, рассчитывает метрики (включая Payments) и выводит все метрики Payments.
    """
    ticker = "RU000A107D74"
    stock = Bond(ticker)
    await stock.payments.update_payments()
    stock.calculate_metrics()  # Рассчитывает все метрики, включая Payments

    payments = stock.payments
    print(f"Метрики для {ticker} (Payments):")
    print(f"Annual Yield: {payments.annual_yield:.2f}%")
    print(f"Average Yield: {payments.average_yield:.2f}%")
    print(f"Yield Volatility: {payments.yield_volatility:.2f}%")
    print(f"Total Payout Amount: {payments.total_payout_amount:.2f}")
    print(f"Payout Frequency: {payments.payout_frequency:.2f} выплат/год")
    print(f"Yield Growth Rate: {payments.yield_growth_rate:.2f}%")
    print(f"Cumulative Yield: {payments.cumulative_yield:.2f}%")
    print(f"Payout to Price Ratio: {payments.payout_to_price_ratio:.4f}")


async def payments_metrics():
    active = Stock("MTSS")

    # active.payments.drop()
    await active.payments.update_payments()

    active.payments.load_payments()
    active.payments.calculate_metrics(use_buffer=True)

    for payment in active.payments:
        print(payment)
    print("Годовая доходность: ", active.payments.total_yield_3y)


async def update_payments():
    # ticker = "RU000A1008V9"  # RU000A1008D7 - фиксированный купон; RU000A1008V9 - плавающий
    bonds = Bonds({"currency": "rub"})
    # await bond.update_payments()
    # bonds.calculate_metrics()

    for bond in bonds:
        print(f"Тикер: {bond.ticker}")
        print(f"Прогноз годового купона: {bond.payments.amount_year}")
        print(f"Амортизация: {bond.amortization_flag}; Плавающий: {bond.floating_coupon_flag}")
        print(f"Купонная доходность {bond.current_yield}")
        print(f"YTM: {bond.ytm}")

        print("="*30)


asyncio.run(payments_metrics())
# asyncio.run(test_payments())

