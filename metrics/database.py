# /metrics/database.py
from sqlalchemy import Column, Float, DateTime, String, text
from datetime import datetime
from base.database import BaseMetricsDatabase, BaseMetrics


class DynamicMetricsBase(BaseMetrics):
    __abstract__ = True  # Абстрактный класс, не создаёт таблицу
    date = Column(String, primary_key=True)  # Дата отчета (ДД.ММ.ГГГГ)
    type_period = Column(String)  # Тип отчета ('y' или 'q')
    period = Column(String)  # Период (например, '2024' или '2025Q2')
    net_income = Column(Float, nullable=True)  # Чистая прибыль (млрд руб)
    assets = Column(Float, nullable=True)  # Активы (млрд руб)
    margin = Column(Float, nullable=True)  # Чистая рентабельность (%)
    market_cap = Column(Float, nullable=True)  # Рыночная капитализация (млрд руб)
    ev = Column(Float, nullable=True)  # Стоимость компании - долги (млрд руб)
    eps = Column(Float, nullable=True)  # Прибыль на акцию (руб)
    p_e = Column(Float, nullable=True)  # Мультипликатор P/E
    p_b = Column(Float, nullable=True)  # Мультипликатор P/B
    roe = Column(Float, nullable=True)  # Рентабельность капитала (%)
    roa = Column(Float, nullable=True)  # Рентабельность активов (%)


class MetricsDatabase(BaseMetricsDatabase):
    def __init__(self):
        """
        Инициализация базы данных для метрик.
        """
        super().__init__()

    def table_exists(self, ticker: str) -> bool:
        """
        Проверяет, существует ли таблица для заданного тикера в базе данных.
        :param ticker: Тикер актива (например, 'SBER').
        :return: True, если таблица существует, иначе False.
        """
        safe_table_name = ticker.replace("-", "_")
        try:
            with self.Session() as session:
                session.execute(text(f"SELECT 1 FROM {safe_table_name} LIMIT 1"))
                return True
        except Exception:
            return False

    def create_metrics_table(self, table_name: str):
        """
        Создаёт таблицу для метрик с именем, основанным на тикере.
        :param table_name: Уникальное название (тикер актива, например, 'SBER').
        """
        safe_table_name = table_name.replace("-", "_")

        class DynamicMetrics(DynamicMetricsBase):
            __tablename__ = safe_table_name

        DynamicMetrics.__table__.create(self.engine, checkfirst=True)  # Проверяем существование

    def delete_quarterly_metrics(self, table_name: str):
        """
        Удаляет все квартальные записи из таблицы.
        :param table_name: Тикер актива.
        """
        safe_table_name = table_name.replace("-", "_")
        # Проверка наличия таблицы
        if not self.table_exists(safe_table_name):
            return

        with self.Session() as session:
            session.execute(
                text(f"DELETE FROM {safe_table_name} WHERE type_period = 'q'")
            )
            session.commit()

    def delete_yearly_metrics(self, table_name: str):
        """
        Удаляет все годовые записи из таблицы.
        :param table_name: Тикер актива.
        """
        safe_table_name = table_name.replace("-", "_")
        # Проверка наличия таблицы
        if not self.table_exists(safe_table_name):
            return

        with self.Session() as session:
            session.execute(
                text(f"DELETE FROM {safe_table_name} WHERE type_period = 'y'")
            )
            session.commit()

    def query_yearly_metrics(self, ticker: str):
        """
        Запрашивает годовые метрики из таблицы по тикеру.
        :param ticker: Тикер актива.
        :return: Список годовых метрик.
        """
        safe_table_name = ticker.replace("-", "_")
        # Проверка наличия таблицы
        if not self.table_exists(safe_table_name):
            return []

        with self.Session() as session:
            result = session.execute(
                text(f"""
                    SELECT date, type_period, period, net_income, assets,
                           margin, market_cap, ev, eps, p_e, p_b, roe, roa
                    FROM {safe_table_name}
                    WHERE type_period = 'y'
                    ORDER BY date ASC
                """),
            ).fetchall()
            return [
                {
                    'date': row[0],
                    'type_period': row[1],
                    'period': row[2],
                    'net_income': row[3],
                    'assets': row[4],
                    'margin': row[5],
                    'market_cap': row[6],
                    'ev': row[7],
                    'eps': row[8],
                    'p_e': row[9],
                    'p_b': row[10],
                    'roe': row[11],
                    'roa': row[12]
                }
                for row in result
            ]

    def query_quarterly_metrics(self, ticker: str):
        """
        Запрашивает квартальные метрики из таблицы по тикеру.
        :param ticker: Тикер актива.
        :return: Список квартальных метрик.
        """
        safe_table_name = ticker.replace("-", "_")
        # Проверка наличия таблицы
        if not self.table_exists(safe_table_name):
            return []

        with self.Session() as session:
            result = session.execute(
                text(f"""
                    SELECT date, type_period, period, net_income, assets,
                           margin, market_cap, ev, eps, p_e, p_b, roe, roa
                    FROM {safe_table_name}
                    WHERE type_period = 'q'
                    ORDER BY date ASC
                """),
            ).fetchall()
            return [
                {
                    'date': row[0],
                    'type_period': row[1],
                    'period': row[2],
                    'net_income': row[3],
                    'assets': row[4],
                    'margin': row[5],
                    'market_cap': row[6],
                    'ev': row[7],
                    'eps': row[8],
                    'p_e': row[9],
                    'p_b': row[10],
                    'roe': row[11],
                    'roa': row[12]
                }
                for row in result
            ]

    def add_metrics(self, ticker: str, metrics_data: list):
        """
        Добавляет метрики в таблицу по тикеру.
        :param ticker: Тикер актива.
        :param metrics_data: Список словарей с метриками.
        """
        safe_table_name = ticker.replace("-", "_")
        # Проверка наличия таблицы
        if not self.table_exists(safe_table_name):
            self.create_metrics_table(safe_table_name)

        # Добавляем данные
        with self.Session() as session:
            for metric in metrics_data:
                # Конвертируем дату из строки ДД.ММ.ГГГГ
                date_str = metric.get('date')
                try:
                    date_val = datetime.strptime(date_str, '%d.%m.%Y') if date_str else datetime.utcnow()
                except (ValueError, TypeError):
                    date_val = datetime.utcnow()

                # Определяем type_period из period
                period = metric.get('period', '')
                type_period = 'y' if period and len(period) == 4 and period.isdigit() else 'q'

                # Конвертируем пустые строки в None для числовых метрик
                insert_data = {
                    'date': date_val.isoformat(),
                    'type_period': type_period,
                    'period': period,
                    'net_income': None if metric.get('net_income') == '' else metric.get('net_income'),
                    'assets': None if metric.get('assets') == '' else metric.get('assets'),
                    'margin': None if metric.get('margin') == '' else metric.get('margin'),
                    'market_cap': None if metric.get('market_cap') == '' else metric.get('market_cap'),
                    'ev': None if metric.get('ev') == '' else metric.get('ev'),
                    'eps': None if metric.get('eps') == '' else metric.get('eps'),
                    'p_e': None if metric.get('p_e') == '' else metric.get('p_e'),
                    'p_b': None if metric.get('p_b') == '' else metric.get('p_b'),
                    'roe': None if metric.get('roe') == '' else metric.get('roe'),
                    'roa': None if metric.get('roa') == '' else metric.get('roa')
                }

                session.execute(
                    text(f"""
                        INSERT OR REPLACE INTO {safe_table_name}
                        (date, type_period, period, net_income, assets,
                         margin, market_cap, ev, eps, p_e, p_b, roe, roa)
                        VALUES (:date, :type_period, :period, :net_income, :assets,
                                :margin, :market_cap, :ev, :eps, :p_e, :p_b, :roe, :roa)
                    """),
                    insert_data
                )
            session.commit()


# Глобальный экземпляр
metrics_database = MetricsDatabase()
