# /payments/dividends.py
from datetime import datetime, timedelta
from typing import Dict, Optional
import numpy as np

from .models import PaymentBase, PaymentsBase
from payments.database import payments_database
from candles.models import Candles, CandleInterval


class Dividend(PaymentBase):
    """Одна дивидендная выплата."""

    def __init__(self,
                 payment_date: datetime,
                 amount: float,
                 declared_date: datetime = None,
                 last_buy_date: datetime = None,
                 record_date: datetime = None,
                 dividend_type: str = None,
                 regularity: str = None,
                 currency: str = None,
                 close_price: float = None,
                 close_price_currency: str = None,
                 yield_value: float = None,
                 created_at: datetime = None,
                 update_time: datetime = None):
        super().__init__(payment_date, amount)
        self.declared_date = declared_date
        self.last_buy_date = last_buy_date
        self.record_date = record_date
        self.dividend_type = dividend_type
        self.regularity = regularity
        self.currency = currency
        self.close_price = close_price
        self.close_price_currency = close_price_currency
        self.yield_value = yield_value
        self.created_at = created_at
        self.update_time = update_time

    def calculate_yield_value(self, candles: Candles):
        return self.yield_value


class Dividends(PaymentsBase):
    """
    Модуль дивидендов.
    Считает ВСЕ метрики для сравнительного анализа акций по дивидендам.
    НЕ зависит от Stock — только от candles (для цены) и payments.
    """

    RECENT_YEARS = 3  # для CAGR и стабильности

    def __init__(self, figi: str, instrument_type: str, candles: Candles):
        if instrument_type not in {"stock", "etf"}:
            raise ValueError("instrument_type must be 'stock' or 'etf'")
        super().__init__(figi, instrument_type, candles)

        # === Внутренние структуры ===
        self.yearly_dividends: Dict[int, float] = {}  # {год: сумма_дивидендов}
        self.last_annual_dividend: float = 0.0  # последний полный год
        self.next_payment: Optional[Dividend] = None  # будущая выплата (если объявлена)

        # === Метрики ===
        self.payout_frequency: float = 0.0      # Средняя частота выплат в год (на основе интервалов между датами)
        self.dividend_cagr_3y: float = 0.0      # CAGR годовых дивидендов за последние 3 полных года (%)
        self.dividend_stability: float = 0.0    # Стабильность выплат: 1 - коэффициент вариации годовых сумм
        self.trailing_yield: float = 0.0        # Текущая дивидендная доходность: сумма за последние 12 мес / цена (%)
        self.forward_yield: float = 0.0         # Ожидаемая годовая доходность: прогноз на следующий год / цена (%)
        self.yield_plus_growth: float = 0.0     # Сводная метрика: forward_yield + dividend_cagr_3y
        self.risk_adj_yield: float = 0.0        # Доходность на единицу риска: forward_yield / волатильность

    def load_payments(self,
                      from_time: datetime = datetime.fromtimestamp(0),
                      to_time: datetime = None) -> None:
        """Загружает ВСЕ выплаты из БД (включая будущие)."""
        to_time = to_time or datetime.fromtimestamp(10 ** 10)
        raw = payments_database.query_payments(
            figi=self.figi,
            instrument_type=self.instrument_type,
            from_time=from_time,
            to_time=to_time,
        )
        self.payments = [Dividend(**row) for row in raw]
        self.payments.sort(key=lambda p: p.payment_date)

        self._aggregate_yearly()
        self._find_next_payment()

    def calculate_metrics(self) -> None:
        """Запускает расчёт всех метрик."""
        self.load_payments()

        self._calc_payout_frequency()
        self._calc_dividend_cagr_3y()
        self._calc_dividend_stability()
        self._calc_trailing_yield()
        self._calc_forward_yield()
        self._calc_yield_plus_growth()
        self._calc_risk_adj_yield()

        self.clear_buffer()

    # ==================================================================== #
    # 1. _aggregate_yearly — агрегация по годам
    # ==================================================================== #
    def _aggregate_yearly(self) -> None:
        """Собирает сумму дивидендов по календарным годам."""
        self.yearly_dividends = {}
        now_year = datetime.utcnow().year
        for p in self.payments:
            y = p.payment_date.year
            if y > now_year:
                continue
            self.yearly_dividends[y] = self.yearly_dividends.get(y, 0.0) + p.amount

        # Последний полный год
        complete_years = [y for y in self.yearly_dividends.keys() if y < now_year]
        if complete_years:
            last_year = max(complete_years)
            self.last_annual_dividend = self.yearly_dividends[last_year]
        else:
            self.last_annual_dividend = 0.0

    # ==================================================================== #
    # 2. _find_next_payment — поиск следующей известной выплаты
    # ==================================================================== #
    def _find_next_payment(self) -> None:
        """Находит первую выплату после текущей даты. Если нет — None."""
        now = datetime.utcnow()
        future = [p for p in self.payments if p.payment_date > now]
        self.next_payment = future[0] if future else None

    # ==================================================================== #
    # 3. _calc_payout_frequency — частота выплат
    # ==================================================================== #
    def _calc_payout_frequency(self) -> None:
        """Среднее количество выплат в год."""
        if len(self.payments) < 2:
            self.payout_frequency = 0.0
            return

        diffs = [(self.payments[i].payment_date - self.payments[i - 1].payment_date).days
                 for i in range(1, len(self.payments))]
        avg_days = np.mean([d for d in diffs if d > 0])
        self.payout_frequency = round(365.25 / avg_days, 2) if avg_days > 0 else 0.0

    # ==================================================================== #
    # 4. _calc_dividend_cagr_3y — рост дивидендов
    # ==================================================================== #
    def _calc_dividend_cagr_3y(self) -> None:
        """CAGR годовых дивидендов за последние 3 полных года."""
        complete_years = sorted([y for y in self.yearly_dividends.keys()
                                 if y < datetime.utcnow().year])
        if len(complete_years) < 3:
            self.dividend_cagr_3y = 0.0
            return

        recent_years = complete_years[-3:]
        d_first = self.yearly_dividends[recent_years[0]]
        d_last = self.yearly_dividends[recent_years[-1]]

        if d_first <= 0:
            self.dividend_cagr_3y = 0.0
            return

        cagr = (d_last / d_first) ** (1 / 3) - 1
        self.dividend_cagr_3y = round(cagr * 100, 2)

    # ==================================================================== #
    # 5. _calc_dividend_stability — стабильность
    # ==================================================================== #
    def _calc_dividend_stability(self) -> None:
        """1 - коэффициент вариации годовых дивидендов."""
        values = [v for v in self.yearly_dividends.values() if v > 0]
        if len(values) < 2:
            self.dividend_stability = 0.0
            return

        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)
        cv = std_val / mean_val if mean_val > 0 else 0
        self.dividend_stability = round(1 - cv, 3)

    # ==================================================================== #
    # 6. _calc_trailing_yield — Trailing 12M Yield
    # ==================================================================== #
    def _calc_trailing_yield(self) -> None:
        """Сумма дивидендов за последние 12 месяцев / текущая цена."""
        price = self.candles.price
        if not price or price <= 0:
            self.trailing_yield = 0.0
            return

        now = datetime.utcnow()
        last_12m = sum(
            p.amount for p in self.payments
            if p.payment_date > now - timedelta(days=365)
        )
        self.trailing_yield = round((last_12m / price) * 100, 2)

    # ==================================================================== #
    # 7. _calc_forward_yield — Ожидаемая годовая доходность
    # ==================================================================== #
    def _calc_forward_yield(self) -> None:
        """Ожидаемый годовой дивиденд / цена."""
        price = self.candles.price
        if not price or price <= 0:
            self.forward_yield = 0.0
            return

        if self.next_payment and self.next_payment.amount > 0:
            annual = self.next_payment.amount * self.payout_frequency
        else:
            annual = self.last_annual_dividend

        self.forward_yield = round((annual / price) * 100, 2)

    # ==================================================================== #
    # 8. _calc_yield_plus_growth — Доходность + рост
    # ==================================================================== #
    def _calc_yield_plus_growth(self) -> None:
        """forward_yield + cagr_3y."""
        self.yield_plus_growth = round(self.forward_yield + self.dividend_cagr_3y, 2)

    # ==================================================================== #
    # 9. _calc_risk_adj_yield — Доходность на риск
    # ==================================================================== #
    def _calc_risk_adj_yield(self) -> None:
        """forward_yield / volatility."""
        vol = self.candles.volatility
        if not vol or vol <= 0:
            self.risk_adj_yield = 0.0
            return
        self.risk_adj_yield = round(self.forward_yield / vol, 3)

    def drop(self):
        """
        Очистка БД
        :return:
        """
        payments_database.drop(self.figi)

    def __str__(self) -> str:
        """
        Красивый вывод всех дивидендных метрик.
        Название класса — в первой строке.
        Все метрики — в столбик, выровнены по правому краю.
        """
        width = 28
        return (
            f"Dividends\n"
            f"\t{'Частота выплат (раз/год):':<{width}}{self.payout_frequency:>8.2f}\n"
            f"\t{'CAGR дивидендов 3г (%):':<{width}}{self.dividend_cagr_3y:>8.2f}\n"
            f"\t{'Стабильность выплат:':<{width}}{self.dividend_stability:>8.3f}\n"
            f"\t{'Trailing yield 12м (%):':<{width}}{self.trailing_yield:>8.2f}\n"
            f"\t{'Forward yield (%):':<{width}}{self.forward_yield:>8.2f}\n"
            f"\t{'Yield + Growth:':<{width}}{self.yield_plus_growth:>8.2f}\n"
            f"\t{'Risk-adj yield:':<{width}}{self.risk_adj_yield:>8.3f}"
        )
