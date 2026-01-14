# /candles/database.py
from sqlalchemy import Column, Float, DateTime
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from t_tech.invest import CandleInterval

from settings import Settings
from base.database import BaseCandlesDatabase, BaseCandle
from api_client import tinkoff_api_client


class DynamicCandleBase(BaseCandle):
    __abstract__ = True  # Абстрактный класс, не создаёт таблицу
    time = Column(DateTime, primary_key=True)  # Время свечи
    open = Column(Float)                      # Цена открытия
    high = Column(Float)                      # Максимальная цена
    low = Column(Float)                       # Минимальная цена
    close = Column(Float)                     # Цена закрытия
    volume = Column(Float)                    # Объём


class CandlesDatabase(BaseCandlesDatabase):
    MAX_DAYS_PARS = {CandleInterval.CANDLE_INTERVAL_HOUR: 3 * 365,          # Максимум для сбора данных
                     CandleInterval.CANDLE_INTERVAL_DAY: 20 * 365}

    MAX_STEP_DAYS = {CandleInterval.CANDLE_INTERVAL_HOUR: 90,           # Максимальный шаг в днях
                     CandleInterval.CANDLE_INTERVAL_DAY: 5 * 365}       # для сбора данных

    def __init__(self):
        """
        Инициализация базы данных для свечей.
        """
        super().__init__()

    async def _create_candle_table(self, table_name: str):
        """
        Создаёт таблицу для свечей с указанным именем (figi + interval: CandleInterval).
        :param table_name: Имя таблицы (например, 'BBG000PGXPS4_4').
        """
        # Заменяем недопустимые символы в имени таблицы
        safe_table_name = table_name.replace("-", "_")

        class DynamicCandle(DynamicCandleBase):
            __tablename__ = safe_table_name

        DynamicCandle.__table__.create(self.engine, checkfirst=True)  # Проверяем существование

    async def _delete_last_candle_and_get_time(self, table_name: str):
        """
        Удаляет последнюю свечу и возвращает её время.
        :param table_name: Имя таблицы.
        :return: datetime последней свечи или None, если таблица пуста.
        """
        safe_table_name = table_name.replace("-", "_")
        with self.Session() as session:
            # Получаем время последней свечи
            last_time = session.execute(
                text(f"SELECT MAX(time) FROM {safe_table_name}")
            ).scalar()

            if last_time:
                # Удаляем последнюю свечу
                session.execute(
                    text(f"DELETE FROM {safe_table_name} WHERE time = :last_time"),
                    {"last_time": last_time}
                )
                session.commit()
                return datetime.fromisoformat(last_time)
            else:
                return None

    async def _clean_old_candles(self, table_name: str, limit: int = Settings.Candles.MAX_CANDLES_DB):
        """
        Удаляет старые свечи, если их больше лимита (1000).
        :param table_name: Имя таблицы.
        :param limit: Максимальное количество свечей.
        """
        if limit == 0:          # Вырубаем ограничение на очистку БД
            return

        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                count = session.execute(
                    text(f"SELECT COUNT(*) FROM {safe_table_name}")
                ).scalar()
                if count > limit:
                    excess = count - limit
                    session.execute(
                        text(
                            f"DELETE FROM {safe_table_name} WHERE time IN "
                            f"(SELECT time FROM {safe_table_name} ORDER BY time ASC LIMIT :excess)"
                        ),
                        {"excess": excess}
                    )
                    session.commit()
        except Exception as e:
            session.rollback()
            print(f"Ошибка при очистке старых свечей для {safe_table_name}: {str(e)}")

    async def fetch_data_iteratively(self, figi: str, interval: CandleInterval,
                                     from_time: datetime, to_time: datetime):
        """
        Итеративно собирает свечи для актива, разбивая период на интервалы по 6 лет, и сохраняет их в БД.
        :param figi: FIGI актива (например, 'BBG000PGXPS4').
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY).
        :param from_time: Начало периода сбора свечей (offset-naive, UTC).
        :param to_time: Конец периода сбора свечей (offset-naive, UTC).
        """
        max_period = timedelta(days=self.MAX_STEP_DAYS[interval])
        current_from = max(from_time.replace(tzinfo=None), to_time - timedelta(days=self.MAX_DAYS_PARS[interval]))
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")

        # Нормализуем to_time к offset-naive
        if to_time.tzinfo is not None:
            to_time = to_time.replace(tzinfo=None)

        while current_from < to_time:
            current_to = min(current_from + max_period, to_time)

            # Запрашиваем свечи через API
            candles = await tinkoff_api_client.get_candles(figi, current_from, current_to, interval)
            with self.Session() as session:
                for candle in candles:
                    # Нормализуем candle.time к offset-naive (удаляем UTC offset)
                    candle_time = candle.time.replace(tzinfo=None)
                    session.execute(
                        text(f"""
                            INSERT OR REPLACE INTO {safe_table_name} 
                            (time, open, high, low, close, volume)
                            VALUES (:time, :open, :high, :low, :close, :volume)"""),
                        {
                            "time": candle_time,
                            "open": (candle.open.units + candle.open.nano / 1e9),
                            "high": (candle.high.units + candle.high.nano / 1e9),
                            "low": (candle.low.units + candle.low.nano / 1e9),
                            "close": (candle.close.units + candle.close.nano / 1e9),
                            "volume": candle.volume
                        }
                    )
                session.commit()

            # Обновляем current_from для следующего интервала
            current_from = current_to
            if current_to >= to_time:
                break

    async def fetch_data(self, figi: str, interval: CandleInterval, from_time: datetime = None):
        """
        Получает свечи для актива и сохраняет их в БД.
        :param figi: FIGI актива (например, 'BBG000PGXPS4').
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :param from_time: Стартовое время сбора свечей (например, first_1day_candle_date).
        """
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")

        # Проверяем существование таблицы
        try:
            with self.Session() as session:
                session.execute(text(f"SELECT 1 FROM {safe_table_name} LIMIT 1"))
            # Таблица существует: удаляем последнюю свечу и получаем её время
            last_candle_time = await self._delete_last_candle_and_get_time(safe_table_name)
            from_time = last_candle_time if last_candle_time else from_time
        except Exception:
            # Таблица не существует: создаём
            await self._create_candle_table(table_name)

        # Определяем временной диапазон
        to_time = datetime.utcnow()
        if from_time is None:
            # Если from_time не задано, используем минимально допустимую дату (6 лет назад)
            from_time = to_time - timedelta(days=self.MAX_DAYS_PARS[interval])

        # Вызываем итеративный сбор данных
        await self.fetch_data_iteratively(figi, interval, from_time, to_time)

        # Очищаем старые свечи
        await self._clean_old_candles(safe_table_name)

    def query_candles(self, figi: str, interval: CandleInterval, from_time: datetime, to_time: datetime):
        """
        Запрашивает свечи из таблицы по FIGI и интервалу.
        :param figi: FIGI актива.
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :param from_time: Начало периода.
        :param to_time: Конец периода.
        :return: Список свечей.
        """
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                result = session.execute(
                    text(f"""
                        SELECT open, high, low, close, volume, time
                        FROM {safe_table_name}
                        WHERE time >= :from_time AND time <= :to_time
                        ORDER BY time ASC
                    """),
                    {"from_time": from_time, "to_time": to_time}
                ).fetchall()
                return [
                    {
                        "open_": row[0],
                        "high": row[1],
                        "low": row[2],
                        "close": row[3],
                        "volume": row[4],
                        "time": datetime.fromisoformat(row[5])
                    } for row in result
                ]
        except Exception as e:
            # Таблица отсутствует
            return []

    def query_last_candle(self, figi: str, interval: CandleInterval) -> dict | None:
        """
        Запрашивает последнюю свечу из таблицы по FIGI и интервалу.
        :param figi: FIGI актива.
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :return: Словарь с данными свечи или None, если свеча не найдена.
        """
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                result = session.execute(
                    text(f"""
                        SELECT open, high, low, close, volume, time
                        FROM {safe_table_name}
                        ORDER BY time DESC
                        LIMIT 1
                    """)
                ).fetchone()
                if result:
                    return {
                        "open_": result[0],
                        "high": result[1],
                        "low": result[2],
                        "close": result[3],
                        "volume": result[4],
                        "time": datetime.fromisoformat(result[5])
                    }
                return None
        except Exception:
            return None

    def query_candle_before_date(self, figi: str, interval: CandleInterval, date: datetime) -> dict | None:
        """
        Запрашивает свечу, ближайшую к указанной дате, но не позднее неё.
        :param figi: FIGI актива.
        :param interval: Интервал свечи (CandleInterval.CANDLE_INTERVAL_DAY или CANDLE_INTERVAL_HOUR).
        :param date: Дата для поиска свечи.
        :return: Словарь с данными свечи или None, если свеча не найдена.
        """
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                result = session.execute(
                    text(f"""
                        SELECT open, high, low, close, volume, time
                        FROM {safe_table_name}
                        WHERE time <= :date
                        ORDER BY time DESC
                        LIMIT 1
                    """),
                    {"date": date}
                ).fetchone()
                if result:
                    return {
                        "open_": result[0],
                        "high": result[1],
                        "low": result[2],
                        "close": result[3],
                        "volume": result[4],
                        "time": datetime.fromisoformat(result[5])
                    }
                return None
        except Exception:
            return None

    def drop(self, figi: str, interval: CandleInterval) -> None:
        """
        Удаление таблицы.
        :param figi: FIGI таблицы
        :param interval: Интервал таблицы
        :return: None
        """
        table_name = f"{figi}_{interval.value}"
        safe_table_name = table_name.replace("-", "_")
        try:
            with self.Session() as session:
                session.execute(text(f"DROP TABLE IF EXISTS {safe_table_name}"))
                session.commit()
        except Exception:
            return None


candles_database = CandlesDatabase()
