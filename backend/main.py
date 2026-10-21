from fastapi import FastAPI

#екземпляр додатку фастАпі
app = FastAPI(
    title = "ProStock API",
    description = "Backend API для системи управління ProStock"
)

@app.get("/")
def root():
    return {
        "message": "API ProStock працює!"
    }