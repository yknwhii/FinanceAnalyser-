"""
Тесты парсера Excel. Создают временные xlsx-файлы через openpyxl
в каталоге проекта (sandbox не разрешает системный tmp).
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import excel_parser  # noqa: E402


# Папка для временных xlsx — внутри workspace, чтобы sandbox разрешил запись.
TMP_DIR = Path(ROOT) / "tests" / "_tmp"
TMP_DIR.mkdir(exist_ok=True)


def write_xlsx(path: Path, header: list[str], rows: list[list]) -> None:
    """Записать простой xlsx-файл с одной таблицей."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_parse_expenses_basic():
    """Базовый разбор расходов: bool в «учитывать» понимается."""
    p = TMP_DIR / "exp_basic.xlsx"
    if p.exists():
        p.unlink()
    write_xlsx(
        p,
        [
            "категория 1", "категория 2", "наименование",
            "норма расхода на 1 мес", "единица измерения", "учитывать",
        ],
        [
            ["еда", "бакалея", "хлеб", 100, "мес", True],
            ["еда", "молочное", "молоко", 200, "мес", "да"],
            ["прочее", "прочее", "бонус", 1000, "мес", False],
        ],
    )
    rows = excel_parser.parse_expenses(p)
    assert len(rows) == 3
    assert rows[0].monthly_amount == 100
    assert rows[1].include is True
    assert rows[2].include is False


def test_parse_expenses_missing_column():
    """Если обязательной колонки нет — ExcelParseError."""
    p = TMP_DIR / "exp_missing.xlsx"
    if p.exists():
        p.unlink()
    write_xlsx(p, ["категория 1", "наименование"], [["a", "b"]])
    with pytest.raises(excel_parser.ExcelParseError):
        excel_parser.parse_expenses(p)


def test_parse_expenses_missing_file():
    """Несуществующий файл — ExcelParseError."""
    with pytest.raises(excel_parser.ExcelParseError):
        excel_parser.parse_expenses(TMP_DIR / "nope_xxxx.xlsx")


def test_parse_portfolio_basic():
    """Базовый разбор портфеля."""
    p = TMP_DIR / "port_basic.xlsx"
    if p.exists():
        p.unlink()
    write_xlsx(
        p,
        ["Тип актива", "Доля портфеля", "% Ожидаемая доходность", "налог %", "комиссия %"],
        [
            ["Акции", 60, 10, 5, 0],
            ["Облигации", 40, 6, 0, 1],
        ],
    )
    rows = excel_parser.parse_portfolio(p)
    assert len(rows) == 2
    assert rows[0].weight_percent == 60
    assert rows[1].expected_return_percent == 6


def test_parse_expenses_non_numeric_raises():
    """Нечисловое значение в месячной норме — ExcelParseError."""
    p = TMP_DIR / "exp_bad.xlsx"
    if p.exists():
        p.unlink()
    write_xlsx(
        p,
        [
            "категория 1", "категория 2", "наименование",
            "норма расхода на 1 мес", "единица измерения", "учитывать",
        ],
        [
            ["еда", "бакалея", "хлеб", "abc", "мес", True],
        ],
    )
    with pytest.raises(excel_parser.ExcelParseError):
        excel_parser.parse_expenses(p)
