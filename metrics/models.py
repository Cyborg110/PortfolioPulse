# /metrics/models.py
from datetime import datetime
from typing import List, Optional

from metrics.database import metrics_database
from api_client import scraper  # Импорт глобального экземпляра SmartLabScraper


class Metric:
    """Класс для хранения данных одной строки метрик из БД."""

    def __init__(
            self,
            date: datetime,
            type_period: str,
            period: str,
            net_income: Optional[float] = None,
            assets: Optional[float] = None,
            margin: Optional[float] = None,
            market_cap: Optional[float] = None,
            ev: Optional[float] = None,
            eps: Optional[float] = None,
            p_e: Optional[float] = None,
            p_b: Optional[float] = None,
            roe: Optional[float] = None,
            roa: Optional[float] = None
    ):
        self.date = date
        self.type_period = type_period
        self.period = period
        self.net_income = net_income
        self.assets = assets
        self.margin = margin
        self.market_cap = market_cap
        self.ev = ev
        self.eps = eps
        self.p_e = p_e
        self.p_b = p_b
        self.roe = roe
        self.roa = roa


class Metrics:
    """Класс для управления метриками актива для одного типа отчётов (годовые или квартальные)."""

    def __init__(self, ticker: str, type_period: str):
        """
        Инициализирует список метрик для заданного тикера и типа отчёта.
        :param ticker: Тикер актива (например, 'SBER').
        :param type_period: Тип отчёта ('y' для годовых, 'q' для квартальных).
        """
        if type_period not in ['y', 'q']:
            raise ValueError("type_period должен быть 'y' или 'q'")
        self.ticker = ticker
        self.type_period = type_period
        self.metrics: List[Metric] = []
        self.get_params()

    def get_params(self):
        """Загружает метрики из БД и создаёт объекты Metric."""
        self.metrics = []
        if self.type_period == 'y':
            data = metrics_database.query_yearly_metrics(self.ticker)
        else:
            data = metrics_database.query_quarterly_metrics(self.ticker)

        for metric_data in data:
            self.metrics.append(
                Metric(
                    date=datetime.fromisoformat(metric_data['date']),
                    type_period=metric_data['type_period'],
                    period=metric_data['period'],
                    net_income=metric_data['net_income'],
                    assets=metric_data['assets'],
                    margin=metric_data['margin'],
                    market_cap=metric_data['market_cap'],
                    ev=metric_data['ev'],
                    eps=metric_data['eps'],
                    p_e=metric_data['p_e'],
                    p_b=metric_data['p_b'],
                    roe=metric_data['roe'],
                    roa=metric_data['roa']
                )
            )

    def __getitem__(self, index):
        """Поддерживает индексацию по списку metrics."""
        return self.metrics[index]

    def __iter__(self):
        """Поддерживает итерацию по списку metrics."""
        return iter(self.metrics)

    def __len__(self):
        """Возвращает длину списка metrics."""
        return len(self.metrics)

    def update(self):
        """Обновляет метрики через парсер и перезаписывает их в БД."""
        # Получаем данные через глобальный парсер
        metrics_data = scraper.get(self.ticker, period=self.type_period)
        if not metrics_data:
            print(f"Не удалось получить метрики для {self.ticker} ({self.type_period})")
            return

        # Удаляем старые данные
        if self.type_period == 'y':
            metrics_database.delete_yearly_metrics(self.ticker)
        else:
            metrics_database.delete_quarterly_metrics(self.ticker)

        # Добавляем новые данные в БД
        metrics_database.add_metrics(self.ticker, metrics_data)

        # Перезагружаем метрики из БД
        self.get_params()


class TickerMetrics:
    """Класс для управления годовыми и квартальными метриками актива."""

    def __init__(self, ticker: str):
        """
        Инициализирует объекты Metrics для годовых и квартальных метрик.
        :param ticker: Тикер актива (например, 'SBER').
        """
        self.ticker = ticker
        self.yearly = Metrics(ticker, type_period='y')
        self.quarterly = Metrics(ticker, type_period='q')

    def update(self):
        """Обновляет годовые и квартальные метрики."""
        self.yearly.update()
        self.quarterly.update()
