from fastapi import FastAPI
# from app.logs.router import router as logs_router
# from app.orders.router import router as orders_router
# from app.products.router import router as products_router
# from app.storages.router import router as storage_router
# from app.tasks.router import router as tasks_router
# from app.users.router import router as users_router
# from app.tasks.router import router as warehouses_router

from app.routers import map as map_router
from app.routers import auth  as auth_router

app = FastAPI(
    title = "ProStock API",
    description = "Backend API для системи управління ProStock"
)

#підключення роутера для роботи з топологією складу
app.include_router(map_router.router)

#роутер для автентифікації
app.include_router(auth_router.router)

@app.get("/")
def root():
    return {
        "message": "API ProStock працює!"
    }

