"""
draw.py
=======
Визуализация результатов. Получает готовые данные из calc.py и
показывает графики пользователю через matplotlib.pyplot.show() —
он сам решает, сохранять ли изображение. Никаких расчётов здесь нет.
"""

from __future__ import annotations

import matplotlib

# Использовать неинтерактивный backend по умолчанию; если у пользователя
# есть дисплей/окно — show() всё равно откроет его.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def show_and_release(fig, title: str | None = None) -> None:
    """Показать фигуру в интерактивном окне matplotlib и закрыть её.

    Зачем: пользователь смотрит график и сам решает, сохранять его
    или нет (через меню окна matplotlib). После закрытия окна CLI
    продолжает работу.
    """
    if title:
        fig.canvas.manager.set_window_title(title) if fig.canvas.manager else None
    # Переключаемся на интерактивный backend прямо перед показом,
    # чтобы окно действительно появилось у пользователя.
    try:
        plt.switch_backend("TkAgg")
    except Exception:  # noqa: BLE001
        try:
            plt.switch_backend("Qt5Agg")
        except Exception:  # noqa: BLE001
            pass
    fig.show()
    plt.show(block=True)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 11.1. Структура расходов
# ---------------------------------------------------------------------------

def plot_expenses_pie(data: pd.DataFrame):
    """Круговая диаграмма расходов (названия уже схлопнуты в «Прочее» в calc)."""
    fig, ax = plt.subplots(figsize=(8, 8))
    if data.empty:
        ax.text(0.5, 0.5, "Нет данных о расходах", ha="center", va="center")
        ax.set_axis_off()
        return fig

    labels = data["name"].tolist()
    sizes = data["amount"].astype(float).tolist()
    ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        textprops={"fontsize": 9},
    )
    ax.set_title("Структура месячных расходов", fontsize=12)
    ax.axis("equal")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 11.2. Время достижения цели: капитал и доходность
# ---------------------------------------------------------------------------

def plot_time_vs_capital_and_return(data: pd.DataFrame):
    """Heatmap «время до цели» по осям «капитал» и «доходность»."""
    fig, ax = plt.subplots(figsize=(9, 6))
    if data.empty:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.set_axis_off()
        return fig

    pivot = data.pivot(
        index="return_percent", columns="capital", values="years",
    ).sort_index()
    arr = pivot.values.astype(float)
    vmax = float(pd.Series(arr[~pd.isna(arr)]).max()) if (~pd.isna(arr)).any() else 1.0
    arr_filled = pd.DataFrame(arr).fillna(vmax * 1.5).values

    im = ax.imshow(arr_filled, aspect="auto", origin="lower", cmap="viridis_r")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{c:,.0f}" for c in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{r:.1f}%" for r in pivot.index])
    ax.set_xlabel("Текущий капитал")
    ax.set_ylabel("Годовая доходность, %")
    ax.set_title("Время достижения цели (лет)\nчем темнее — тем быстрее")
    fig.colorbar(im, ax=ax, label="лет")
    fig.tight_layout()
    return fig


def plot_time_vs_capital(data: pd.DataFrame):
    """Линейный график: годы до цели vs начальный капитал."""
    fig, ax = plt.subplots(figsize=(9, 5))
    if data.empty:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.set_axis_off()
        return fig
    ok = data[data["achievable"]]
    bad = data[~data["achievable"]]
    ax.plot(ok["capital"], ok["years"], "o-", label="достижимо")
    if not bad.empty:
        ax.scatter(
            bad["capital"],
            [0] * len(bad),
            marker="x",
            color="red",
            label="недостижимо",
        )
    ax.set_xlabel("Текущий капитал")
    ax.set_ylabel("Лет до цели")
    ax.set_title("Зависимость срока от капитала")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_time_vs_return(data: pd.DataFrame):
    """Линейный график: годы до цели vs годовая доходность."""
    fig, ax = plt.subplots(figsize=(9, 5))
    if data.empty:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.set_axis_off()
        return fig
    ok = data[data["achievable"]]
    bad = data[~data["achievable"]]
    ax.plot(ok["return_percent"], ok["years"], "o-", label="достижимо")
    if not bad.empty:
        ax.scatter(
            bad["return_percent"],
            [0] * len(bad),
            marker="x",
            color="red",
            label="недостижимо",
        )
    ax.set_xlabel("Годовая доходность, %")
    ax.set_ylabel("Лет до цели")
    ax.set_title("Зависимость срока от доходности")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 11.3. Время достижения цели: расходы
# ---------------------------------------------------------------------------

def plot_time_vs_expenses(data: pd.DataFrame):
    """Зависимость срока от расходов; недостижимое помечено крестиками."""
    fig, ax = plt.subplots(figsize=(9, 5))
    if data.empty:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.set_axis_off()
        return fig
    ok = data[data["achievable"]]
    bad = data[~data["achievable"]]
    ax.plot(ok["monthly_expenses"], ok["years"], "o-", label="достижимо")
    if not bad.empty:
        ax.scatter(
            bad["monthly_expenses"],
            [0] * len(bad),
            marker="x",
            color="red",
            label="недостижимо (расходы > дохода)",
        )
    ax.set_xlabel("Месячные расходы")
    ax.set_ylabel("Лет до цели")
    ax.set_title("Зависимость срока от расходов")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig
