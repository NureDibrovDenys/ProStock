from fastapi import FastAPI
from app.routers import map as map_router
from app.routers import auth  as auth_router


#екземпляр додатку фастАпі
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

