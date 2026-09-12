"""
main.py
=======
Точка входа CLI приложения finance.

Здесь:
  * читаем .env;
  * автозагружаем Excel-данные (расходы + портфель) сразу после bootstrap;
  * запускаем CLI-меню;
  * при ошибках даём пользователю время прочитать сообщение
    (start.bat добавляет pause после завершения).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# На Windows переключаем вывод в UTF-8, чтобы консоль корректно
# показывала кириллицу и спецсимволы без падения на cp1251.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

# Разрешаем относительные импорты внутри пакета src/ при запуске
# `python src\main.py` из корня проекта.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import numpy as np
from dotenv import load_dotenv

import calc
import draw
import excel_parser


# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    """Конфигурация приложения, загруженная из .env."""
    expenses_file: Path
    portfolio_file: Path
    inflation_percent: float
    current_capital: float


def load_config() -> Config:
    """Загрузить конфигурацию из .env. Понятно сообщить о проблемах."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    def _require(name: str) -> str:
        v = os.getenv(name)
        if v is None or v == "":
            raise EnvironmentError(
                f"Не задана переменная окружения {name}. "
                f"Создайте .env на основе .env.example"
            )
        return v

    try:
        inflation = float(_require("INFLATION_PCT"))
        capital = float(_require("CURRENT_CAPITAL"))
    except ValueError as exc:
        raise EnvironmentError(
            f"INFLATION_PCT и CURRENT_CAPITAL должны быть числами: {exc}"
        ) from exc

    return Config(
        expenses_file=Path(_require("EXPENSES_FILE")),
        portfolio_file=Path(_require("PORTFOLIO_FILE")),
        inflation_percent=inflation,
        current_capital=capital,
    )


# ---------------------------------------------------------------------------
# Состояние и автозагрузка
# ---------------------------------------------------------------------------

@dataclass
class State:
    """Состояние приложения: конфиг + загруженные данные."""
    config: Config
    expenses: list[calc.ExpenseRow] | None = None
    portfolio: list[calc.PortfolioRow] | None = None


def bootstrap(state: State) -> None:
    """Загрузить Excel-данные и провалидировать их при старте приложения."""
    state.expenses = excel_parser.parse_expenses(state.config.expenses_file)
    portfolio = excel_parser.parse_portfolio(state.config.portfolio_file)
    calc.validate_weights(portfolio)
    state.portfolio = portfolio


def ensure_expenses(state: State) -> list[calc.ExpenseRow]:
    """Возвращает уже загруженные расходы (загружаются при bootstrap)."""
    assert state.expenses is not None, "расходы должны быть загружены в bootstrap"
    return state.expenses


def ensure_portfolio(state: State) -> list[calc.PortfolioRow]:
    """Возвращает уже загруженный портфель (загружается при bootstrap)."""
    assert state.portfolio is not None, "портфель должен быть загружен в bootstrap"
    return state.portfolio


# ---------------------------------------------------------------------------
# Действия CLI-меню
# ---------------------------------------------------------------------------

def _ask(prompt: str, cast=float) -> float:
    """Считать число у пользователя с повтором при ошибке."""
    while True:
        raw = input(prompt).strip().replace(",", ".")
        try:
            return cast(raw)
        except ValueError:
            print("  ! некорректное число, попробуйте ещё раз")


def action_show_expenses(state: State) -> str:
    """Показать таблицу активных расходов и итоговую сумму."""
    rows = ensure_expenses(state)
    active = [r for r in rows if r.include]
    lines = ["Активные расходы:"]
    lines.append(f"{'Категория 1':<14} | {'Наименование':<28} | {'/ мес':>12}")
    lines.append("-" * 60)
    for r in active:
        lines.append(
            f"{r.category1[:14]:<14} | {r.name[:28]:<28} | {r.monthly_amount:>12,.2f}"
        )
    lines.append("-" * 60)
    lines.append(f"{'ИТОГО':<14} | {'':<28} | {calc.total_monthly_expenses(rows):>12,.2f}")
    return "\n".join(lines)


def action_portfolio(state: State) -> str:
    """Показать структуру портфеля и его ожидаемую доходность (gross/net)."""
    rows = ensure_portfolio(state)
    exp = calc.portfolio_expected_return_percent(rows)
    after = calc.portfolio_after_costs_percent(rows)
    lines = ["Структура портфеля:"]
    lines.append(f"{'Актив':<18} | {'Доля,%':>7} | {'Дох,%':>7} | {'Налог,%':>7} | {'Ком,%':>7}")
    lines.append("-" * 60)
    for r in rows:
        lines.append(
            f"{r.asset_type[:18]:<18} | {r.weight_percent:>7.2f} | "
            f"{r.expected_return_percent:>7.2f} | {r.tax_percent:>7.2f} | {r.fee_percent:>7.2f}"
        )
    lines.append("-" * 60)
    lines.append(f"Ожидаемая доходность (gross): {exp:.2f}% годовых")
    lines.append(f"Ожидаемая доходность (net):   {after:.2f}% годовых")
    return "\n".join(lines)


def action_time_to_capital(state: State) -> str:
    """Рассчитать срок достижения целевого капитала."""
    portfolio = ensure_portfolio(state)
    ret = calc.portfolio_expected_return_percent(portfolio)
    print(f"Текущая ожидаемая доходность портфеля: {ret:.2f}% годовых")
    print(f"Текущий капитал (из .env): {state.config.current_capital:,.2f}")
    target = _ask("Целевой капитал: ")
    custom_ret = input(
        f"Годовая доходность, % [{ret:.2f}]: "
    ).strip().replace(",", ".")
    if custom_ret:
        ret = float(custom_ret)
    result = calc.time_to_goal_capital(
        current_capital=state.config.current_capital,
        target_capital=target,
        annual_return_percent=ret,
    )
    expenses = calc.total_monthly_expenses(ensure_expenses(state))
    if expenses > 0:
        print(f"Месячные расходы: {expenses:,.2f}")
    return str(result)


def action_required_income(state: State) -> str:
    """Рассчитать необходимый капитал под доход ИЛИ доход под цель за N лет."""
    print("1) Капитал для целевого пассивного дохода")
    print("2) Доход для достижения целевого капитала за N лет")
    choice = input("Выберите режим [1/2]: ").strip()
    portfolio = ensure_portfolio(state)
    ret = calc.portfolio_expected_return_percent(portfolio)
    custom = input(f"Годовая доходность, % [{ret:.2f}]: ").strip().replace(",", ".")
    if custom:
        ret = float(custom)
    if choice == "1":
        target = _ask("Целевой месячный пассивный доход: ")
        cap = calc.required_capital_for_income(target, ret)
        return (
            f"Нужен капитал ~ {cap:,.2f} "
            f"при доходности {ret:.2f}% годовых"
        )
    if choice == "2":
        cur = _ask("Текущий капитал: ")
        tgt = _ask("Целевой капитал: ")
        years = _ask("Срок, лет: ")
        try:
            res = calc.required_monthly_income(cur, tgt, years)
        except ValueError as exc:
            return f"! ошибка: {exc}"
        return (
            f"Нужен ежемесячный доход ~ {res['monthly_income']:,.2f} "
            f"(эквивалентная доходность ~ {res['annual_return_percent']:.2f}% годовых)"
        )
    return "Отменено"


def action_plot_expenses(state: State) -> str:
    """Круговая диаграмма структуры расходов."""
    rows = ensure_expenses(state)
    data = calc.expenses_for_pie(rows)
    fig = draw.plot_expenses_pie(data)
    draw.show_and_release(fig, title="Структура расходов")
    return "График показан в отдельном окне (закройте его, чтобы продолжить)"


def action_plot_capital_return(state: State) -> str:
    """Графики зависимости срока от капитала и доходности."""
    portfolio = ensure_portfolio(state)
    ret = calc.portfolio_expected_return_percent(portfolio)
    capital_values = np.linspace(
        max(1.0, state.config.current_capital * 0.25),
        max(state.config.current_capital * 4.0, 1e6),
        8,
    )
    return_values = np.linspace(max(0.5, ret * 0.25), max(ret * 2.0, 10.0), 6)
    rows = []
    for c in capital_values:
        for r in return_values:
            res = calc.time_to_goal_capital(
                current_capital=float(c),
                target_capital=state.config.current_capital * 5
                if state.config.current_capital > 0
                else 1_000_000,
                annual_return_percent=float(r),
            )
            rows.append(
                {
                    "capital": float(c),
                    "return_percent": float(r),
                    "years": res.years if res.achievable else np.nan,
                }
            )
    import pandas as pd  # локальный импорт, чтобы не тянуть в main без нужды
    df = pd.DataFrame(rows)
    target_used = (
        state.config.current_capital * 5
        if state.config.current_capital > 0
        else 1_000_000
    )
    fig1 = draw.plot_time_vs_capital_and_return(df)
    draw.show_and_release(fig1, title="Срок vs капитал/доходность (heatmap)")

    cap_df = calc.time_vs_capital(capital_values, target_used, ret)
    fig2 = draw.plot_time_vs_capital(cap_df)
    draw.show_and_release(fig2, title="Срок vs капитал")

    ret_df = calc.time_vs_return(
        return_values,
        state.config.current_capital if state.config.current_capital > 0 else capital_values[0],
        target_used,
    )
    fig3 = draw.plot_time_vs_return(ret_df)
    draw.show_and_release(fig3, title="Срок vs доходность")
    return "Графики показаны в отдельных окнах (закрывайте по одному)"


def action_plot_expenses_vs_time(state: State) -> str:
    """График зависимости срока от уровня расходов."""
    portfolio = ensure_portfolio(state)
    ret = calc.portfolio_expected_return_percent(portfolio)
    expenses = ensure_expenses(state)
    base = calc.total_monthly_expenses(expenses) or 10000.0
    expense_values = np.linspace(0, base * 2.0, 10)
    target = (
        state.config.current_capital * 5
        if state.config.current_capital > 0
        else 1_000_000
    )
    df = calc.time_vs_expenses(
        expense_values,
        state.config.current_capital,
        target,
        ret,
    )
    fig = draw.plot_time_vs_expenses(df)
    draw.show_and_release(fig, title="Срок vs расходы")
    return "График показан в отдельном окне (закройте его, чтобы продолжить)"


# ---------------------------------------------------------------------------
# Меню (легко расширять: добавить функцию и пункт в MENU)
# ---------------------------------------------------------------------------

MENU: dict[str, tuple[str, Callable[[State], str]]] = {
    "1": ("Показать расходы", action_show_expenses),
    "2": ("Портфель: ожидаемая доходность", action_portfolio),
    "3": ("Время достижения цели по капиталу", action_time_to_capital),
    "4": ("Необходимый доход", action_required_income),
    "5": ("График: структура расходов", action_plot_expenses),
    "6": ("График: срок vs капитал/доходность", action_plot_capital_return),
    "7": ("График: срок vs расходы", action_plot_expenses_vs_time),
    "0": ("Выход", None),
}


def print_menu() -> None:
    """Вывести пункты меню в консоль."""
    print("\n=== finance ===")
    for key, (label, _) in MENU.items():
        print(f"  {key}. {label}")


def run(state: State) -> int:
    """Главный цикл CLI."""
    print("Добро пожаловать в finance — локальный финансовый помощник.")
    print(
        f"Загружено расходов: {len(ensure_expenses(state))}, "
        f"портфель: {len(ensure_portfolio(state))} активов."
    )
    while True:
        print_menu()
        choice = input("Выберите пункт: ").strip()
        if choice not in MENU:
            print("  ! нет такого пункта")
            continue
        if choice == "0":
            print("До встречи!")
            return 0
        label, handler = MENU[choice]
        print(f"-> {label}")
        try:
            result = handler(state)
        except FileNotFoundError as exc:
            print(f"  ! файл не найден: {exc}")
            continue
        except excel_parser.ExcelParseError as exc:
            print(f"  ! ошибка Excel: {exc}")
            continue
        except EnvironmentError as exc:
            print(f"  ! конфигурация: {exc}")
            continue
        except ValueError as exc:
            print(f"  ! некорректные данные: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - ловим всё, чтобы не падать
            print(f"  ! непредвиденная ошибка: {exc}")
            continue
        print(result)
    return 0


def main() -> int:
    """Точка входа: загрузить конфиг, данные, запустить CLI."""
    try:
        config = load_config()
    except EnvironmentError as exc:
        print(f"Ошибка конфигурации: {exc}")
        return 2
    state = State(config=config)
    try:
        bootstrap(state)
    except FileNotFoundError as exc:
        print(f"Ошибка: файл не найден — {exc}")
        return 3
    except excel_parser.ExcelParseError as exc:
        print(f"Ошибка Excel: {exc}")
        return 4
    except ValueError as exc:
        print(f"Ошибка данных: {exc}")
        return 5
    return run(state)


if __name__ == "__main__":
    sys.exit(main())
