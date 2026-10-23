"""
На вход приходят обычные словари, на выходе получаются обычные словари.
Формат входа:
    recipe = {
        "id": 1,                                   # необязательно
        "title": "Блины",
        "ingredients": [
            {"name": "Мука", "quantity": 500, "unit": "г"},
        ],
    }
    pantry = [
        {"name": "Мука", "quantity": 1000, "unit": "г"},
    ]
"""

from __future__ import annotations

import math
from typing import Any


class MatcherError(ValueError):
    """Некорректные данные на входе движка подбора."""


# Приводим самые частые варианты записи к одной форме.
_UNIT_ALIASES = {
    "гр": "г",
    "гр.": "г",
    "шт.": "шт",
    "штук": "шт",
    "штуки": "шт",
}


def _normalize_name(value: Any, field: str) -> str:
    """Приводит название продукта к виду, удобному для сравнения."""
    if not isinstance(value, str):
        raise MatcherError(f"{field}: название продукта должно быть строкой")

    normalized = " ".join(value.split()).casefold().replace("ё", "е")

    if not normalized:
        raise MatcherError(f"{field}: название продукта не может быть пустым")
    if len(normalized) > 120:
        raise MatcherError(
            f"{field}: название продукта слишком длинное (максимум 120 символов)"
        )
    return normalized


def _normalize_unit(value: Any, field: str) -> str:
    """Приводит единицу измерения к нижнему регистру и убирает пробелы."""
    if not isinstance(value, str):
        raise MatcherError(f"{field}: единица измерения должна быть строкой")

    unit = value.strip().casefold()
    if not unit:
        raise MatcherError(f"{field}: единица измерения не может быть пустой")
    return _UNIT_ALIASES.get(unit, unit)


def _to_number(value: Any, field: str, *, allow_zero: bool) -> float:
    """Проверяет количество и возвращает число.

    Для рецепта количество должно быть строго больше нуля, для склада
    допускается ноль. Строки вида "0,5" поддерживаются, потому что
    пользователь может ввести дробь через запятую.
    """
    if isinstance(value, bool) or value is None:
        raise MatcherError(f"{field}: количество должно быть числом")

    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            raise MatcherError(f"{field}: количество не может быть пустым")
        try:
            number = float(text)
        except ValueError as exc:
            raise MatcherError(
                f"{field}: количество должно быть числом, получено {value!r}"
            ) from exc
    else:
        raise MatcherError(
            f"{field}: количество должно быть числом, получено {type(value).__name__}"
        )

    if not math.isfinite(number):
        raise MatcherError(f"{field}: количество должно быть конечным числом")

    if allow_zero:
        if number < 0:
            raise MatcherError(f"{field}: количество не может быть отрицательным")
    elif number <= 0:
        raise MatcherError(f"{field}: количество в рецепте должно быть больше нуля")

    # Убираем хвосты вида 0.30000000000000004.
    return round(number, 6)


def _parse_items(
    items: Any,
    *,
    source: str,
    allow_empty: bool,
    allow_zero: bool,
) -> list[dict[str, Any]]:
    """Проверяет список ингредиентов и приводит его к внутреннему виду."""
    if not isinstance(items, list):
        raise MatcherError(f"{source}: ожидается список ингредиентов")

    if not items and not allow_empty:
        raise MatcherError(f"{source}: список ингредиентов не может быть пустым")

    parsed: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise MatcherError(
                f"{source}[{index}]: ожидается объект с полями name, quantity, unit"
            )

        label = f"{source}[{index}]"
        parsed.append(
            {
                "name": _normalize_name(item.get("name"), f"{label}.name"),
                "display_name": str(item.get("name", "")).strip(),
                "unit": _normalize_unit(item.get("unit"), f"{label}.unit"),
                "quantity": _to_number(
                    item.get("quantity"),
                    f"{label}.quantity",
                    allow_zero=allow_zero,
                ),
            }
        )

    return parsed


def _merge_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Складывает одинаковые продукты (название + единица измерения)."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for item in items:
        key = (item["name"], item["unit"])
        if key in merged:
            merged[key]["quantity"] = round(
                merged[key]["quantity"] + item["quantity"], 6
            )
        else:
            merged[key] = dict(item)

    return list(merged.values())


def _ensure_single_unit(items: list[dict[str, Any]], source: str) -> None:
    """Запрещает одному продукту в рецепте иметь разные единицы измерения."""
    units_by_name: dict[str, set[str]] = {}
    for item in items:
        units_by_name.setdefault(item["name"], set()).add(item["unit"])

    for name, units in units_by_name.items():
        if len(units) > 1:
            raise MatcherError(
                f"{source}: для продукта {name!r} указаны разные единицы "
                f"измерения: {', '.join(sorted(units))}"
            )


def _build_pantry_index(pantry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Строит индекс склада по названию продукта.

    Известное ограничение: если один и тот же продукт лежит на складе
    в разных единицах, количества складываются как числа без пересчёта.
    """
    index: dict[str, dict[str, Any]] = {}

    for item in pantry:
        existing = index.get(item["name"])
        if existing is None:
            index[item["name"]] = dict(item)
        else:
            existing["quantity"] = round(existing["quantity"] + item["quantity"], 6)

    return index


def check_recipe(recipe: Any, pantry: Any) -> dict[str, Any]:
    """Сравнивает один рецепт с продуктами на складе.

    Возвращает словарь:
        {
            "id": 1,
            "title": "Блины",
            "can_cook": False,
            "missing": [
                {
                    "name": "Мука",
                    "unit": "г",
                    "required": 500.0,
                    "available": 200.0,
                    "missing": 300.0,
                }
            ],
            "required_count": 1,
            "available_count": 0,
        }
    """
    if not isinstance(recipe, dict):
        raise MatcherError("recipe: ожидается объект рецепта")

    raw_title = recipe.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        raise MatcherError("recipe.title: название рецепта не может быть пустым")

    recipe_items = _parse_items(
        recipe.get("ingredients"),
        source="recipe.ingredients",
        allow_empty=False,
        allow_zero=False,
    )
    recipe_items = _merge_items(recipe_items)
    _ensure_single_unit(recipe_items, "recipe.ingredients")

    pantry_items = _parse_items(
        pantry,
        source="pantry",
        allow_empty=True,
        allow_zero=True,
    )
    pantry_index = _build_pantry_index(pantry_items)

    missing: list[dict[str, Any]] = []

    for need in recipe_items:
        have = pantry_index.get(need["name"])
        available = round(have["quantity"], 6) if have else 0.0

        if available < need["quantity"]:
            missing.append(
                {
                    "name": need["display_name"],
                    "unit": need["unit"],
                    "required": need["quantity"],
                    "available": available,
                    "missing": round(need["quantity"] - available, 6),
                }
            )

    return {
        "id": recipe.get("id"),
        "title": raw_title.strip(),
        "can_cook": not missing,
        "missing": missing,
        "required_count": len(recipe_items),
        "available_count": len(recipe_items) - len(missing),
    }


def find_cookable_recipes(recipes: Any, pantry: Any) -> dict[str, Any]:
    """Делит рецепты на две группы: доступные и требующие покупок.

    Возвращает:
        {
            "available": [результаты check_recipe для доступных рецептов],
            "unavailable": [результаты check_recipe для остальных],
            "total": 2,
        }
    """
    if not isinstance(recipes, list):
        raise MatcherError("recipes: ожидается список рецептов")

    available: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    for recipe in recipes:
        result = check_recipe(recipe, pantry)
        if result["can_cook"]:
            available.append(result)
        else:
            unavailable.append(result)

    return {
        "available": available,
        "unavailable": unavailable,
        "total": len(recipes),
    }
