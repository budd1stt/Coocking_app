

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.matcher import MatcherError, check_recipe, find_cookable_recipes

router = APIRouter(prefix="/api/matcher", tags=["matcher"])


class IngredientIn(BaseModel):
    """Ингредиент в запросе к API."""

    name: str = Field(min_length=1, max_length=120)
    quantity: float
    unit: str = Field(min_length=1, max_length=20)


class RecipeIn(BaseModel):
    """Рецепт в запросе к API."""

    id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    ingredients: list[IngredientIn]


class CheckRequest(BaseModel):
    """Запрос на проверку одного рецепта."""

    recipe: RecipeIn
    pantry: list[IngredientIn] = Field(default_factory=list)


class CookableRequest(BaseModel):
    """Запрос на проверку списка рецептов."""

    recipes: list[RecipeIn]
    pantry: list[IngredientIn] = Field(default_factory=list)


@router.post("/check")
def check(request: CheckRequest) -> dict:
    """Проверяет, можно ли приготовить рецепт из имеющихся продуктов."""
    try:
        return check_recipe(
            request.recipe.model_dump(),
            [item.model_dump() for item in request.pantry],
        )
    except MatcherError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/cookable")
def cookable(request: CookableRequest) -> dict:
    """Делит рецепты на доступные и недоступные."""
    try:
        return find_cookable_recipes(
            [recipe.model_dump() for recipe in request.recipes],
            [item.model_dump() for item in request.pantry],
        )
    except MatcherError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
