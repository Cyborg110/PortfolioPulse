# /payments/models.py
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import numpy as np
from typing import List, Optional
from t_tech.invest import CandleInterval

from settings import Settings
from api_client import tinkoff_api_client
from payments.database import payments_database
from candles.models import Candles


class PaymentBase(ABC):
    """
    Базовый абстрактный класс для представления выплаты.
    """
    def __init__(self, payment_date: [str, datetime], amount: float):
        """
        Инициализация базового объекта выплаты.
        :param payment_date: Дата выплаты.
        :param amount: Сумма выплаты.
        """
        self.payment_date = datetime.fromisoformat(payment_date).replace(tzinfo=None) if isinstance(payment_date, str) else payment_date.replace(tzinfo=None)
        self.amount = amount
        self.yield_percent: Optional[float] = None  # Процентная доходность выплаты
        self.currency: Optional[str] = None
        self.update_time: Optional[datetime] = None

    @abstractmethod
    def calculate_yield_value(self, candles: Candles):
        """
        Рассчитывает процентную доходность выплаты и сохраняет в self.yield_percent.
        :param candles: Объект MultiTimeframeCandles для получения цены актива.
        """
        pass

    def __str__(self):
        return f"Дата: {self.payment_date};\t" \
               f"Сумма: {self.amount} ({self.yield_percent} %);\t"


class PaymentsBase(ABC):
    """
    Базовый абстрактный класс для работы с набором выплат.
    """

    def __init__(self, figi: str, instrument_type: str, candles: Candles):
        """
        Инициализация объекта выплат.
        :param figi: FIGI актива.
        :param instrument_type: Тип инструмента ('stock', 'bond', 'etf').
        :param candles: Объект MultiTimeframeCandles для доступа к свечным данным.
        """
        self.figi = figi
        self.instrument_type = instrument_type
        self.candles = candles
        self.payments: List[PaymentBase] = []

    @abstractmethod
    def load_payments(self, from_time: datetime = datetime.fromtimestamp(0), to_time: datetime = None):
        """
        Загружает выплаты за указанный период в буфер self.payments.
        """
        pass

    async def update_payments(self, to_time: datetime = None):
        """
        Загружает выплаты в базу данных, затем обновляет self.payments.
        """
        await payments_database.fetch_data(
            figi=self.figi,
            instrument_type=self.instrument_type,
            to_time=to_time
        )
        self.load_payments()

    def drop(self) -> None:
        """
        Удаление всех выплат в базе данных.
        :return:
        """
        payments_database.drop(figi=self.figi)

    def clear_buffer(self) -> None:
        """
        Очищает список выплат, не трогая рассчитанные метрики и последнюю выплату.
        """
        self.payments = []

    def __iter__(self):
        return iter(self.payments)

    def __len__(self):
        return len(self.payments)
