# /payments/database.py
from sqlalchemy import Column, Integer, Float, DateTime, String, text
from datetime import datetime
from base.database import BasePaymentsDatabase, BasePayment
from api_client import tinkoff_api_client


class DynamicCouponBase(BasePayment):
    __abstract__ = True  # Абстрактный класс для купонов
    id = Column(Integer, primary_key=True)
    payment_date = Column(DateTime, index=True, unique=True)  # Дата выплаты (payment_date)
    coupon_number = Column(Integer)  # Номер купона
    fix_date = Column(DateTime)  # Дата фиксации
    coupon_start_date = Column(DateTime)  # Начало периода
    coupon_end_date = Column(DateTime)  # Конец периода
    coupon_period = Column(Integer)  # Длительность периода (дни)
    coupon_type = Column(Integer)  # Тип купона (enum as int)
    amount = Column(Float)  # Сумма на облигацию
    currency = Column(String)  # Валюта amount
    update_time = Column(DateTime)  # Время записи в БД


class DynamicDividendBase(BasePayment):
    __abstract__ = True  # Абстрактный класс для дивидендов
    id = Column(Integer, primary_key=True)
    payment_date = Column(DateTime, index=True, unique=True)  # Дата выплаты
    declared_date = Column(DateTime)  # Дата объявления
    last_buy_date = Column(DateTime)  # Последняя дата покупки
    record_date = Column(DateTime)  # Дата фиксации реестра
    dividend_type = Column(String)  # Тип дивиденда
    regularity = Column(String)  # Регулярность
    amount = Column(Float)  # Сумма на акцию (dividend_net)
    currency = Column(String)  # Валюта amount
    close_price = Column(Float)  # Цена закрытия
    close_price_currency = Column(String)  # Валюта close_price
    yield_value = Column(Float)  # Доходность (yield_value units + nano)
    created_at = Column(DateTime)  # Дата создания в API
    update_time = Column(DateTime)  # Время записи в БД


class PaymentsDatabase(BasePaymentsDatabase):
    def __init__(self):
        """
        Инициализация базы данных для выплат.
        """
        super().__init__()

    def _table_exists(self, table_name: str) -> bool:
        """
        Проверяет существование таблицы по имени.
        :param table_name: Имя таблицы (safe FIGI).
        :return: True, если таблица существует, иначе False.
        """
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                session.execute(text(f"SELECT 1 FROM {safe_table_name} LIMIT 1"))
            return True
        except Exception:
            return False

    async def _create_payment_table(self, table_name: str, instrument_type: str):
        """
        Создаёт таблицу для выплат с именем, основанным на FIGI.
        :param table_name: уникальное название (FIGI актива).
        :param instrument_type: 'bond' для купонов, 'stock'/'etf' для дивидендов.
        """
        safe_table_name = table_name.replace("-", "_")

        if instrument_type == "bond":
            class DynamicPayments(DynamicCouponBase):
                __tablename__ = safe_table_name
        elif instrument_type in ["stock", "etf"]:
            class DynamicPayments(DynamicDividendBase):
                __tablename__ = safe_table_name
        else:
            raise ValueError(f"Неподдерживаемый тип: {instrument_type}")

        DynamicPayments.__table__.create(self.engine, checkfirst=True)

    async def _clear_future_payments(self, table_name: str) -> None:
        """
        Удаляет "будущие" записи: где payment_date/coupon_date > max(update_time).
        :param table_name: safe FIGI.
        """
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                max_update_time = session.execute(text(f"SELECT MAX(update_time) FROM {safe_table_name}")).scalar()
                if max_update_time:
                    # Удаляем будущие относительно max_update_time
                    session.execute(
                        text(f"DELETE FROM {safe_table_name} WHERE payment_date > :max_update_time"),
                        {"max_update_time": max_update_time}
                    )
                    session.commit()
        except Exception as e:
            print(f"Ошибка при очистке будущих выплат для {safe_table_name}: {str(e)}")

    async def _delete_last_payment_and_get_time(self, table_name: str, instrument_type: str) -> datetime | None:
        """
        Удаляет последнюю выплату и возвращает её дату.
        :param table_name: safe FIGI.
        :param instrument_type: Тип для выбора поля даты.
        :return: datetime последней выплаты или None.
        """
        safe_table_name = table_name.replace("-", "_")
        date_field = "payment_date"
        try:
            with self.Session() as session:
                last_time_str = session.execute(text(f"SELECT MAX({date_field}) FROM {safe_table_name}")).scalar()
                last_time = datetime.fromisoformat(last_time_str) if last_time_str else None

                if last_time:
                    session.execute(
                        text(f"DELETE FROM {safe_table_name} WHERE {date_field} = :last_time"),
                        {"last_time": last_time}
                    )
                    session.commit()
                return last_time
        except Exception as e:
            print(f"Ошибка при обработке последней выплаты для {safe_table_name}: {str(e)}")
            return None

    async def fetch_data(self, figi: str, instrument_type: str, to_time: datetime = None):
        """
        Получает выплаты для актива и сохраняет их в БД.
        :param figi: FIGI актива.
        :param instrument_type: Тип инструмента ('stock', 'bond', 'etf').
        :param to_time: Конец периода (обязательно, иначе utcnow()).
        """
        if to_time is None:
            to_time = datetime(2040, 1, 1)

        safe_table_name = figi.replace("-", "_")

        table_exists = self._table_exists(safe_table_name)

        if not table_exists:
            await self._create_payment_table(figi, instrument_type)
            from_time = datetime(2000, 1, 1)
        else:
            await self._clear_future_payments(figi)
            last_payment_time = await self._delete_last_payment_and_get_time(figi, instrument_type)
            from_time = last_payment_time or datetime(2000, 1, 1)  # Переопределяем from_time

        # Запрашиваем выплаты через API
        if instrument_type == "bond":
            payments = await tinkoff_api_client.get_bond_coupons(figi, from_time, to_time)
        elif instrument_type in ["stock", "etf"]:
            payments = await tinkoff_api_client.get_dividends(figi, from_time, to_time)
        else:
            raise ValueError(f"Неподдерживаемый тип: {instrument_type}")

        # Сохраняем выплаты в базу
        now = datetime.utcnow()
        with self.Session() as session:
            for payment in payments:
                if instrument_type == "bond":
                    session.execute(
                        text(f"""
                            INSERT OR REPLACE INTO {safe_table_name}
                            (payment_date, coupon_number, fix_date, coupon_start_date, coupon_end_date,
                             coupon_period, coupon_type, amount, currency, update_time)
                            VALUES (:payment_date, :coupon_number, :fix_date, :coupon_start_date,
                                    :coupon_end_date, :coupon_period, :coupon_type, :amount,
                                    :currency, :update_time)
                        """),
                        {
                            "payment_date": payment["coupon_date"],
                            "coupon_number": payment["coupon_number"],
                            "fix_date": payment["fix_date"],
                            "coupon_start_date": payment["coupon_start_date"],
                            "coupon_end_date": payment["coupon_end_date"],
                            "coupon_period": payment["coupon_period"],
                            "coupon_type": payment["coupon_type"].value if hasattr(payment["coupon_type"], 'value') else payment["coupon_type"],
                            "amount": payment["pay_one_bond"].units + payment["pay_one_bond"].nano / 1e9,
                            "currency": payment["pay_one_bond"].currency,
                            "update_time": now
                        }
                    )
                else:  # dividends
                    session.execute(
                        text(f"""
                            INSERT OR REPLACE INTO {safe_table_name}
                            (payment_date, declared_date, last_buy_date, record_date, dividend_type,
                             regularity, amount, currency, close_price, close_price_currency,
                             yield_value, created_at, update_time)
                            VALUES (:payment_date, :declared_date, :last_buy_date, :record_date,
                                    :dividend_type, :regularity, :amount, :currency, :close_price,
                                    :close_price_currency, :yield_value, :created_at, :update_time)
                        """),
                        {
                            "payment_date": payment["payment_date"],
                            "declared_date": payment["declared_date"],
                            "last_buy_date": payment["last_buy_date"],
                            "record_date": payment["record_date"],
                            "dividend_type": payment["dividend_type"],
                            "regularity": payment["regularity"],
                            "amount": payment["dividend_net"].units + payment["dividend_net"].nano / 1e9,
                            "currency": payment["dividend_net"].currency,
                            "close_price": payment["close_price"].units + payment["close_price"].nano / 1e9,
                            "close_price_currency": payment["close_price"].currency,
                            "yield_value": payment["yield_value"].units + payment["yield_value"].nano / 1e9,
                            "created_at": payment["created_at"],
                            "update_time": now
                        }
                    )
            session.commit()

    def query_payments(self, figi: str, instrument_type: str, from_time: datetime = None, to_time: datetime = None):
        """
        Запрашивает выплаты из таблицы по FIGI.
        :param figi: FIGI актива.
        :param instrument_type: Тип для выбора полей.
        :param from_time: Начало периода.
        :param to_time: Конец периода.
        :return: Список выплат (dicts с тип-специфическими ключами).
        """
        safe_table_name = figi.replace("-", "_")
        from_time = from_time or datetime.fromtimestamp(0)
        to_time = to_time or datetime.utcnow()
        date_field = "payment_date" if instrument_type == "bond" else "payment_date"
        try:
            with self.Session() as session:
                if instrument_type == "bond":
                    keys = [
                        "payment_date", "coupon_number", "fix_date", "coupon_start_date", "coupon_end_date",
                        "coupon_period", "coupon_type", "amount", "currency", "update_time"
                    ]
                    result = session.execute(
                        text(f"""
                            SELECT {', '.join(keys)}
                            FROM {safe_table_name}
                            WHERE {date_field} >= :from_time AND {date_field} <= :to_time
                            ORDER BY {date_field} ASC
                        """),
                        {"from_time": from_time, "to_time": to_time}
                    ).fetchall()
                    return [dict(zip(keys, row)) for row in result]
                else:
                    keys = [
                        "payment_date", "declared_date", "last_buy_date", "record_date", "dividend_type",
                        "regularity", "amount", "currency", "close_price", "close_price_currency",
                        "yield_value", "created_at", "update_time"
                    ]
                    result = session.execute(
                        text(f"""
                            SELECT {', '.join(keys)}
                            FROM {safe_table_name}
                            WHERE {date_field} >= :from_time AND {date_field} <= :to_time
                            ORDER BY {date_field} ASC
                        """),
                        {"from_time": from_time, "to_time": to_time}
                    ).fetchall()
                    return [dict(zip(keys, row)) for row in result]
        except Exception as e:
            return []

    def drop(self, figi: str) -> None:
        """
        Удаление таблицы.
        :param figi: FIGI таблицы
        """
        safe_table_name = figi.replace("-", "_")
        try:
            with self.Session() as session:
                session.execute(text(f"DROP TABLE IF EXISTS {safe_table_name}"))
                session.commit()
        except Exception:
            pass


# Глобальный экземпляр
payments_database = PaymentsDatabase()
