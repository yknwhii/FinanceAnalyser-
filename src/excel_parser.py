"""
excel_parser.py
===============
Чтение и валидация входных Excel-файлов.

Здесь нет финансовых формул — только I/O, проверка структуры и
приведение типов. Возвращаемые dataclass-объекты потребляет calc.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from calc import ExpenseRow, PortfolioRow


# Ожидаемые колонки входных файлов расходов и портфеля.
EXPENSE_COLUMNS: list[str] = [
    "категория 1",
    "категория 2",
    "наименование",
    "норма расхода на 1 мес",
    "единица измерения",
    "учитывать",
]

PORTFOLIO_COLUMNS: list[str] = [
    "Тип актива",
    "Доля портфеля",
    "% Ожидаемая доходность",
    "налог %",
    "комиссия %",
]


class ExcelParseError(Exception):
    """Ошибка чтения или валидации Excel-файла."""


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Привести названия колонок к нормализованному виду (strip)."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _check_columns(df: pd.DataFrame, required: Iterable[str], file_label: str) -> None:
    """Проверить наличие обязательных колонок; иначе ExcelParseError."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ExcelParseError(
            f"В файле «{file_label}» отсутствуют колонки: {', '.join(missing)}"
        )


def _read_excel(path: Path | str) -> pd.DataFrame:
    """Прочитать Excel-файл и нормализовать названия колонок."""
    p = Path(path)
    if not p.exists():
        raise ExcelParseError(f"Файл не найден: {p}")
    try:
        df = pd.read_excel(p)
    except Exception as exc:  # noqa: BLE001 - сообщаем понятно
        raise ExcelParseError(
            f"Не удалось прочитать Excel-файл «{p}»: {exc}"
        ) from exc
    return _normalize_columns(df)


def _to_bool(value) -> bool:
    """Привести значение ячейки к bool (поддерживает bool/int/str)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return False
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "да", "y", "yes"):
            return True
        if s in ("false", "0", "нет", "n", "no", ""):
            return False
    return False


def _to_float(value, field: str) -> float:
    """Привести ячейку к float; пустые -> 0; нечисловое -> ExcelParseError."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ExcelParseError(
            f"Поле «{field}» содержит нечисловое значение: {value!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Расходы
# ---------------------------------------------------------------------------

def parse_expenses(path: Path | str) -> list[ExpenseRow]:
    """Прочитать Excel расходов и вернуть список ExpenseRow.

    Допущения:
      * колонка «учитывать» — bool (TRUE/FALSE, 1/0, да/нет);
      * «норма расхода на 1 мес» — единственный источник месячной суммы.
    """
    df = _read_excel(path)
    _check_columns(df, EXPENSE_COLUMNS, "расходы")
    rows: list[ExpenseRow] = []
    for idx, row in df.iterrows():
        try:
            monthly = _to_float(row["норма расхода на 1 мес"], "норма расхода на 1 мес")
            if monthly < 0:
                raise ExcelParseError(
                    f"Строка {idx + 2}: отрицательное значение нормы расхода"
                )
            include = _to_bool(row["учитывать"])
            rows.append(
                ExpenseRow(
                    category1=str(row["категория 1"]).strip(),
                    category2=str(row["категория 2"]).strip(),
                    name=str(row["наименование"]).strip(),
                    monthly_amount=monthly,
                    unit=str(row["единица измерения"]).strip(),
                    include=include,
                )
            )
        except ExcelParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ExcelParseError(
                f"Строка {idx + 2}: ошибка разбора — {exc}"
            ) from exc
    return rows


# ---------------------------------------------------------------------------
# Портфель
# ---------------------------------------------------------------------------

def parse_portfolio(path: Path | str) -> list[PortfolioRow]:
    """Прочитать Excel портфеля и вернуть список PortfolioRow.

    Допущения:
      * вес портфеля — проценты (сумма ≈ 100%);
      * доходность, налог, комиссия — проценты.
    """
    df = _read_excel(path)
    _check_columns(df, PORTFOLIO_COLUMNS, "портфель")
    rows: list[PortfolioRow] = []
    for idx, row in df.iterrows():
        try:
            weight = _to_float(row["Доля портфеля"], "Доля портфеля")
            ret = _to_float(row["% Ожидаемая доходность"], "% Ожидаемая доходность")
            tax = _to_float(row["налог %"], "налог %")
            fee = _to_float(row["комиссия %"], "комиссия %")
            if weight < 0 or ret < 0 or tax < 0 or fee < 0:
                raise ExcelParseError(
                    f"Строка {idx + 2}: отрицательные значения недопустимы"
                )
            rows.append(
                PortfolioRow(
                    asset_type=str(row["Тип актива"]).strip(),
                    weight_percent=weight,
                    expected_return_percent=ret,
                    tax_percent=tax,
                    fee_percent=fee,
                )
            )
        except ExcelParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ExcelParseError(
                f"Строка {idx + 2}: ошибка разбора — {exc}"
            ) from exc
    return rows
