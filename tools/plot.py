# tools/plot.py
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Tuple, Callable, Any

import matplotlib
# matplotlib.use("MacOSX")


def plot_assets(
    assets: List[Any],
    pairs: List[Tuple[Callable[[Any], float],
                     Callable[[Any], float],
                     str, str]],
    title_prefix: str = "Asset"
):
    if not assets or not pairs:
        print("Нет данных.")
        return

    valid_assets = [
        a for a in assets
        if any(
            (gx(a) is not None and not np.isnan(gx(a)) and
             gy(a) is not None and not np.isnan(gy(a)))
            for gx, gy, _, _ in pairs
        )
    ]
    if not valid_assets:
        print("Нет валидных активов.")
        return

    n_plots = len(pairs)
    n_rows = int(np.ceil(np.sqrt(n_plots)))
    n_cols = int(np.ceil(n_plots / n_rows))

    fig = plt.figure(
        figsize=(8 * n_cols + 2.5, 6.5 * n_rows),  # ← Размер сабплотов
        constrained_layout=True
    )
    grid = plt.GridSpec(
        n_rows, n_cols + 1,
        figure=fig,
        width_ratios=[1] * n_cols + [0.35],  # ← ширина панели
        wspace=0.05, hspace=0.05  # ← расстояние между графиками
    )

    scatters = []
    bond_to_idx = []
    current_annotations = []
    info_text = None

    # --- Правая панель ---
    info_ax = fig.add_subplot(grid[:, -1])
    info_ax.axis('off')
    info_text = info_ax.text(
        0.02, 0.98, "Кликните на точку...",
        va='top', ha='left', fontsize=8.5, family='monospace',
        transform=info_ax.transAxes, color='darkblue'
    )

    # --- Subplot‑ы ---
    for i, (gx, gy, lx, ly) in enumerate(pairs):
        row, col = divmod(i, n_cols)
        ax = fig.add_subplot(grid[row, col])

        xs, ys, assets_in_plot = [], [], []
        for a in valid_assets:
            xv = gx(a)
            yv = gy(a)
            if xv is not None and not np.isnan(xv) and yv is not None and not np.isnan(yv):
                xs.append(xv)
                ys.append(yv)
                assets_in_plot.append(a)

        if not xs:
            ax.text(0.5, 0.5, f"Нет данных\n{lx} vs {ly}", ha='center', va='center', color='red')
            ax.set_axis_off()
            scatters.append(None)
            bond_to_idx.append({})
            continue

        xs = np.array(xs)
        ys = np.array(ys)

        sc = ax.scatter(
            xs, ys,
            s=50, c='steelblue', edgecolor='k', alpha=0.7,
            picker=True, pickradius=6
        )
        scatters.append(sc)
        bond_to_idx.append({a: idx for idx, a in enumerate(assets_in_plot)})

        ax.set_xlabel(lx, fontsize=10)
        ax.set_ylabel(ly, fontsize=10)
        ax.set_title(f"{lx} vs {ly}", fontsize=11, pad=10)
        ax.grid(True, ls=':', alpha=0.6)

    # --- Обработчик клика ---
    def on_pick(event):
        for ann in current_annotations:
            ann.set_visible(False)
        current_annotations.clear()

        for sc in scatters:
            if sc is None: continue
            n = len(sc.get_offsets())
            sc.set_sizes(np.full(n, 50))
            sc.set_facecolor('steelblue')

        artist = event.artist
        if not hasattr(artist, 'axes'): return
        ax = artist.axes
        ind = event.ind[0]

        subplot_idx = next((i for i, sc in enumerate(scatters) if sc is artist), None)
        if subplot_idx is None: return

        asset = next((a for a, idx in bond_to_idx[subplot_idx].items() if idx == ind), None)
        if asset is None: return

        # Подсветка
        for i, sc in enumerate(scatters):
            if sc is None: continue
            idx = bond_to_idx[i].get(asset)
            if idx is None: continue

            n_points = len(sc.get_offsets())
            sizes = np.full(n_points, 50)
            sizes[idx] = 220
            sc.set_sizes(sizes)

            base_color = np.array([0.2745, 0.5098, 0.7059, 0.7])
            colors = np.tile(base_color, (n_points, 1))
            colors[idx] = [1, 0, 0, 1]
            sc.set_facecolors(colors)

        # Аннотация
        x0, y0 = artist.get_offsets()[ind]
        ann = ax.annotate(
            getattr(asset, 'ticker', str(asset)),
            (x0, y0),
            xytext=(12, 12), textcoords='offset points',
            bbox=dict(boxstyle='round', fc='yellow', alpha=0.85),
            arrowprops=dict(arrowstyle='->', color='black')
        )
        current_annotations.append(ann)

        # Правая панель
        info_text.set_text(str(asset))
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('pick_event', on_pick)

    # Скрываем пустые
    for i in range(n_plots, n_rows * n_cols):
        row, col = divmod(i, n_cols)
        empty_ax = fig.add_subplot(grid[row, col])
        empty_ax.axis('off')

    try:
        plt.show()
    except Exception as e:
        plt.savefig('assets_analysis_large.png', dpi=300, bbox_inches='tight')
        print(f"Сохранено в assets_analysis_large.png ({e})")


class Selection:
    """
    Подборки пар метрик для plot_assets.
    Только числовые метрики. Подписи осей — на русском.
    """

    # ==================================================================
    # 1. ОБЩИЕ — для любого актива
    # ==================================================================

    # --- Свечи (Candles) ---
    CANDLES: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda x: x.candles.volatility, lambda x: x.candles.average_return * 252,
         "Волатильность (%)", "Годовая доходность (%)"),
        (lambda x: x.candles.max_drawdown, lambda x: x.candles.sharpe_ratio,
         "Макс. просадка (%)", "Коэффициент Шарпа"),
        (lambda x: x.candles.avg_volume, lambda x: x.candles.volatility,
         "Средний объём", "Волатильность (%)"),
        (lambda x: x.candles.atr_14, lambda x: x.candles.avg_volume,
         "ATR (14 дней)", "Средний объём"),
        (lambda x: x.candles.rsi, lambda x: x.candles.sharpe_ratio,
         "RSI", "Коэффициент Шарпа"),
    ]

    # --- Выплаты (Payments) ---
    PAYMENTS: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda x: x.payments.trailing_yield, lambda x: x.payments.dividend_cagr_3y,
         "Текущая дивидендная доходность (%)", "CAGR дивидендов 3 года (%)"),
        (lambda x: x.payments.dividend_stability, lambda x: x.payments.forward_yield,
         "Стабильность дивидендов", "Прогнозная доходность (%)"),
        (lambda x: x.payments.risk_adj_yield, lambda x: x.payments.yield_plus_growth,
         "Доходность с учётом риска", "Доходность + рост"),
        (lambda x: x.payments.last_annual_dividend, lambda x: x.payments.dividend_cagr_3y,
         "Последний годовой дивиденд", "CAGR 3 года (%)"),
    ]

    # --- Свечи + Выплаты ---
    CANDLES_PAYMENTS: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda x: x.candles.volatility, lambda x: x.payments.trailing_yield,
         "Волатильность (%)", "Текущая дивидендная доходность (%)"),
        (lambda x: x.candles.sharpe_ratio, lambda x: x.payments.dividend_stability,
         "Коэффициент Шарпа", "Стабильность дивидендов"),
        (lambda x: x.candles.max_drawdown, lambda x: x.payments.yield_plus_growth,
         "Макс. просадка (%)", "Доходность + рост"),
        (lambda x: x.candles.avg_volume, lambda x: x.payments.forward_yield,
         "Средний объём", "Прогнозная доходность (%)"),
        (lambda x: x.candles.atr_14, lambda x: x.payments.risk_adj_yield,
         "ATR (14 дней)", "Доходность с учётом риска"),
    ]

    # ==================================================================
    # 2. СПЕЦИФИЧНЫЕ
    # ==================================================================

    # --- Облигации (Bond) ---
    BONDS: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda b: b.macaulay_duration, lambda b: b.ytm,
         "Дюрация Маколея (лет)", "Доходность к погашению (%)"),
        (lambda b: b.days_to_maturity, lambda b: b.ytm,
         "Дней до погашения", "Доходность к погашению (%)"),
        (lambda b: b.candles.volatility, lambda b: b.current_yield,
         "Волатильность (%)", "Текущая купонная доходность (%)"),
        (lambda b: b.macaulay_duration, lambda b: b.price_drop_on_1pct,
         "Дюрация Маколея (лет)", "Падение цены при росте ставки на 1% (%)"),
        (lambda b: b.candles.sharpe_ratio, lambda b: b.ytm,
         "Коэффициент Шарпа", "Доходность к погашению (%)"),
        (lambda b: b.candles.max_drawdown, lambda b: b.total_return,
         "Макс. просадка (%)", "Общая доходность (%)"),
    ]

    # --- Акции (Stock) ---
    STOCKS: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda s: s.candles.volatility, lambda s: s.candles.average_return * 252, "Волатильность (%)", "Годовая доходность (%)"),
        (lambda s: s.candles.max_drawdown, lambda s: s.payments.trailing_yield, "Макс. просадка (%)", "Текущая дивидендная доходность (%)"),
        (lambda s: s.candles.sharpe_ratio, lambda s: s.payments.dividend_cagr_3y, "Коэффициент Шарпа", "CAGR дивидендов 3 года (%)"),
        (lambda s: s.candles.avg_volume, lambda s: s.payments.yield_plus_growth, "Средний объём", "Доходность + рост"),
        # (lambda s: s.candles.atr_14, lambda s: s.payments.risk_adj_yield, "ATR (14 дней)", "Доходность с учётом риска"),
        # (lambda s: s.candles.rsi, lambda s: s.payments.forward_yield, "RSI", "Прогнозная доходность (%)"),
    ]

    # --- ETF ---
    ETF: List[Tuple[Callable[[Any], float], Callable[[Any], float], str, str]] = [
        (lambda e: e.candles.volatility, lambda e: e.candles.average_return * 252,
         "Волатильность (%)", "Годовая доходность (%)"),
        (lambda e: e.candles.sharpe_ratio, lambda e: e.payments.trailing_yield,
         "Коэффициент Шарпа", "Текущая дивидендная доходность (%)"),
        (lambda e: e.candles.max_drawdown, lambda e: e.payments.forward_yield,
         "Макс. просадка (%)", "Прогнозная доходность (%)"),
        (lambda e: e.candles.avg_volume, lambda e: e.payments.yield_plus_growth,
         "Средний объём", "Доходность + рост"),
        (lambda e: e.candles.atr_14, lambda e: e.payments.risk_adj_yield,
         "ATR (14 дней)", "Доходность с учётом риска"),
        # (lambda e: e.candles.rsi, lambda e: e.payments.dividend_stability, "RSI", "Стабильность дивидендов"),
    ]
