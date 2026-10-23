"""Тесты модуля подбора рецептов (Модуль 3).

Запуск из корня проекта:
    source .venv/bin/activate
    pytest

"""

import pytest

from app.services.matcher import MatcherError, check_recipe


def ing(name: str, quantity: float | str, unit: str = "г") -> dict:
    """Короткий помощник для создания ингредиента."""
    return {"name": name, "quantity": quantity, "unit": unit}


RECIPE = {
    "id": 1,
    "title": "Блины",
    "ingredients": [
        ing("Мука", 500),
        ing("Молоко", 0.5, "л"),
        ing("Яйца", 2, "шт"),
    ],
}


def test_basic_scenarios():
    # 1. Все продукты есть на складе.
    pantry = [ing("Мука", 1000), ing("Молоко", 1, "л"), ing("Яйца", 10, "шт")]
    result = check_recipe(RECIPE, pantry)
    assert result["can_cook"] is True
    assert result["missing"] == []

    # 2. Части не хватает — она попадает в список недостающего.
    pantry = [ing("Мука", 200), ing("Молоко", 0.2, "л"), ing("Яйца", 1, "шт")]
    result = check_recipe(RECIPE, pantry)
    assert result["can_cook"] is False
    missing = {item["name"]: item["missing"] for item in result["missing"]}
    assert missing == {"Мука": 300.0, "Молоко": 0.3, "Яйца": 1.0}

    # 3. Отрицательное количество — ошибка входных данных.
    recipe = {"title": "Тесто", "ingredients": [ing("Мука", -500)]}
    with pytest.raises(MatcherError, match="больше нуля"):
        check_recipe(recipe, [])

