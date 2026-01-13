# settings.py
# Токен для подключения к API тинькоф инвестиции
from tinkoff.invest import CandleInterval


class Settings:
    class Candles:
        MAX_CANDLES_DB = 0          # Максимальное кол-во свечей в БД (0 - нет ограничений)
        RISK_FREE_RATE = 0.165       # Текущая безрисковая ставка (ставка ЦБ)
        INFLATION_RATE = 0.05  # Placeholder для 2025
        DEFAULT_LOAD_DAYS = {                           # Авто-загрузка свечей для расчета метрик
            CandleInterval.CANDLE_INTERVAL_DAY: 365*5,    # 3 год для дневных свечей
            CandleInterval.CANDLE_INTERVAL_HOUR: 365     # 1 год для часовых свечей
        }

    class Payments:
        MAX_PAYMENTS_YEARS = 1  # Фиксированный период для расчета метрик (в годах)

    class Converter:
        BASE_CURRENCY = "rub"




