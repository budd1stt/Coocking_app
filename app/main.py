"""Точка входа приложения.

Пока подключён только модуль подбора рецептов. Остальные роутеры будут
добавлены по мере разработки.
"""

from fastapi import FastAPI

from app.routers.matcher import router as matcher_router

app = FastAPI(title="Cooking App")
app.include_router(matcher_router)
