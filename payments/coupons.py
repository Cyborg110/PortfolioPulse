# /payments/coupons.py
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from .models import PaymentBase, PaymentsBase
from payments.database import payments_database
from candles.models import Candles


class Coupon(PaymentBase):
    """
    Класс для представления одной выплаты (купона).
    """
    def __init__(self, payment_date: datetime, amount: float, coupon_number: int = None,
                 fix_date: str = None, coupon_start_date: str = None,
                 coupon_end_date: str = None, coupon_period: int = None,
                 coupon_type: int = None, currency: str = None, update_time: str = None):
        """
        Инициализация объекта купона.
        :param payment_date: Дата выплаты.
        :param amount: Сумма выплаты.
        :param coupon_number: Номер купона (опционально).
        :param fix_date: Дата фиксации (опционально).
        :param coupon_start_date: Начало периода купона (опционально).
        :param coupon_end_date: Конец периода купона (опционально).
        :param coupon_period: Длительность периода (дни, опционально).
        :param coupon_type: Тип купона (опционально).
        :param currency: Валюта выплаты (опционально).
        :param update_time: Время обновления записи (опционально).
        """
        super().__init__(payment_date, amount)
        self.coupon_number = coupon_number
        self.fix_date = datetime.fromisoformat(fix_date).replace(tzinfo=None)
        self.coupon_start_date = datetime.fromisoformat(coupon_start_date).replace(tzinfo=None)
        self.coupon_end_date = datetime.fromisoformat(coupon_end_date).replace(tzinfo=None)
        self.coupon_period = coupon_period
        self.coupon_type = coupon_type
        self.currency = currency
        self.update_time = datetime.fromisoformat(update_time).replace(tzinfo=None)

        # Рассчитываемые метрики
        self.yield_value: Optional[float] = None

    def calculate_yield_value(self, candles: Candles):
        """
        Рассчитывает процентную доходность выплаты и сохраняет в self.yield_value.
        :param candles: Объект MultiTimeframeCandles для получения цены актива.
        """
        candle = candles.get_candle_by_date(self.payment_date)
        if candle and candle.close > 0:
            self.yield_value = (self.amount / candle.close) * 100
        else:
            self.yield_value = 0.0

    def __str__(self):
        return f"Купон\t" \
               f"Дата: {self.payment_date};\t" \
               f"Сумма: {self.amount} ({self.yield_value} %);\t"


class Coupons(PaymentsBase):
    """
    Класс для работы с набором купонов, запрашиваемых из базы данных.
    """

    def __init__(self, figi: str, candles: Candles):
        """
        Инициализация объекта купонов.
        :param figi: FIGI актива.
        :param candles: Объект MultiTimeframeCandles для доступа к свечным данным.
        """
        super().__init__(figi, "bond", candles)
        # Дополнительные метрики
        self.is_approximate: bool = False           # Флаг не точности расчетов
        self.amount_year: float | None = None       # Годовой купон
        self.average_amount: float | None = None   # Средний купон

    def load_payments(self, from_time: datetime = datetime.fromtimestamp(0), to_time: datetime = None):
        """
        Загружает купоны за указанный период в буфер self.payments.
        """
        to_time = to_time if to_time else datetime.fromtimestamp(10**10)
        payment_data = payments_database.query_payments(
            figi=self.figi,
            instrument_type=self.instrument_type,
            from_time=from_time,
            to_time=to_time
        )
        self.payments = [Coupon(**data) for data in payment_data]
        self.payments.sort(key=lambda p: p.payment_date)

    def calculate_coupon_yeild(self) -> None:
        """
        Расчет доходности по каждому купону
        :return: None
        """
        for p in self.payments:
            p.calculate_yield_value(candles=self.candles)

    def calculate_amount_year(self, floating_coupon_flag: bool = False,
                              coupon_quantity_per_year: Optional[int] = None) -> float:
        """
        Рассчитывает ожидаемый годовой купон, используя coupon_start_date/end_date для фильтрации,
        с нормализацией и взвешиванием для floating coupons. Поддерживает freq = 1, 2, 4, 12.
        :param floating_coupon_flag: Флаг плавающего купона (для взвешивания future/historical).
        :param coupon_quantity_per_year: Частота купонов в год (для ограничения и нормализации).
        :return: Годовой купон (float).
        """
        if not self.payments:
            self.amount_year = 0.0
            self.is_approximate = True
            return 0.0

        now = datetime.utcnow()
        one_year_future = now + timedelta(days=365)
        filtered_payments = sorted([p for p in self.payments if p.payment_date <= one_year_future and p.amount],
                                   key=lambda p: p.payment_date)
        if not filtered_payments:
            self.amount_year = 0.0
            self.is_approximate = True
            return 0.0

        last_coupon = filtered_payments[-1]  # Последний coupon в пределах года
        # Устанавливаем start_date на основе coupon_end_date
        start_date = (last_coupon.coupon_end_date - timedelta(days=365)
                      if last_coupon.coupon_end_date else last_coupon.payment_date - timedelta(days=365))

        # Фильтрация по coupon_start_date, cap на freq
        selected_payments = sorted([p for p in filtered_payments
                                    if p.coupon_start_date >= start_date],
                                   key=lambda p: p.payment_date)[:coupon_quantity_per_year]
        if not selected_payments:
            self.amount_year = 0.0
            self.is_approximate = True
            return 0.0

        known_amount = sum(p.amount for p in selected_payments)
        num_selected = len(selected_payments)

        # Рассчитываем span_days для нормализации
        first_payment = min(selected_payments, key=lambda p: p.payment_date)
        last_payment = max(selected_payments, key=lambda p: p.payment_date)
        span_days = ((last_payment.coupon_end_date - first_payment.coupon_start_date).days + 1
                     if first_payment.coupon_start_date and last_payment.coupon_end_date
                     else (last_payment.payment_date - first_payment.payment_date).days + 1)

        self.is_approximate = floating_coupon_flag or num_selected < coupon_quantity_per_year or span_days < 90

        if num_selected < coupon_quantity_per_year:  # Нормализация для малых данных
            self.amount_year = known_amount * (coupon_quantity_per_year / num_selected) if num_selected > 0 else 0.0
        elif floating_coupon_flag:
            # Для floating: взвешивание future (0.7) и historical (0.3)
            future_known = [p for p in selected_payments if p.payment_date > now]
            historical = [p for p in selected_payments if p.payment_date <= now]
            future_sum = sum(p.amount for p in future_known)
            future_count = len(future_known)
            historical_sum = sum(p.amount for p in historical)
            historical_count = len(historical)

            avg_future = future_sum / future_count if future_count > 0 else (
                historical_sum / historical_count if historical_count > 0 else 0.0)
            avg_historical = historical_sum / historical_count if historical_count > 0 else avg_future
            remaining_count = coupon_quantity_per_year - future_count
            self.amount_year = future_sum + remaining_count * (0.7 * avg_future + 0.3 * avg_historical)
        else:
            self.amount_year = known_amount  # Для fixed: сумма freq coupons

        return self.amount_year

    def get_future_cash_flows(self, nominal: float, amortization_flag: bool,
                              maturity_date: datetime, floating_coupon_flag: bool) -> List[Dict]:
        """
        Возвращает список будущих cash flows для фиксированных и плавающих купонов.
        Для fixed: Итеративный ratio для анализа амортизации, nominal добавляется к последнему купону (без амортизации).
        Для floating: Как в предыдущей версии (approx_avg_coupon).
        :param nominal: Текущий номинал.
        :param amortization_flag: Флаг амортизации.
        :param maturity_date: Дата погашения.
        :param floating_coupon_flag: Флаг плавающего купона.
        :return: [{"date": datetime, "amount": float}].
        """
        now = datetime.utcnow()
        future_payments = [p for p in self.payments if p.payment_date > now]
        future_payments = sorted(future_payments, key=lambda p: p.payment_date)
        remaining_coupons = len(future_payments)

        cash_flows = [{"date": p.payment_date, "amount": p.amount} for p in future_payments]
        if not cash_flows:
            return cash_flows

        self.is_approximate = floating_coupon_flag and amortization_flag

        if floating_coupon_flag:
            future_known = [p for p in self.payments if p.payment_date > now and p.amount]
            historical = [p for p in self.payments if p.payment_date <= now and p.amount]
            future_sum = sum(p.amount for p in future_known)
            future_count = len(future_known)
            historical_sum = sum(p.amount for p in historical)
            historical_count = len(historical)

            avg_future = future_sum / future_count if future_count > 0 else (
                historical_sum / historical_count if historical_count > 0 else 0.0)
            avg_historical = historical_sum / historical_count if historical_count > 0 else avg_future
            avg_coupon = 0.7 * avg_future + 0.3 * avg_historical
            for i in range(len(cash_flows)):
                cash_flows[i]["amount"] += avg_coupon
            cash_flows[-1]["amount"] += nominal

        else:  # Fixed
            cash_flows = [{"date": p["date"], "amount": p["amount"] if p["amount"] else cash_flows[0]["amount"]}
                          for p in cash_flows]
            if amortization_flag:
                # Шаг 1: Fixed с амортизацией
                if remaining_coupons >= 1:
                    current_nominal = nominal
                    for i in range(1, len(future_payments)):
                        if future_payments[i-1].amount == 0:
                            break
                        ratio = 1 - (future_payments[i].amount / future_payments[i-1].amount)
                        cash_flows[i-1]["amount"] += current_nominal * ratio
                        current_nominal -= current_nominal * ratio
                        # Шаг 2: Fixed без амортизации
                    if current_nominal:
                        if cash_flows and cash_flows[-1]["date"] == maturity_date:
                            # Суммируем nominal с последним купоном
                            cash_flows[-1]["amount"] += current_nominal
                        else:
                            # Добавляем nominal отдельно
                            cash_flows.append({"date": maturity_date, "amount": current_nominal})

                # Нет финальной выплаты nominal (учтена в амортизации)

            else:
                # Шаг 2: Fixed без амортизации
                if cash_flows and cash_flows[-1]["date"] == maturity_date:
                    # Суммируем nominal с последним купоном
                    cash_flows[-1]["amount"] += nominal
                else:
                    # Добавляем nominal отдельно
                    cash_flows.append({"date": maturity_date, "amount": nominal})

        return cash_flows

    def drop(self):
        """
        Очистка БД
        :return:
        """
        payments_database.drop(self.figi)
