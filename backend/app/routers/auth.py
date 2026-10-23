from concurrent.interpreters import get_current
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.utils.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, hash_password, verify_password, get_current_user
from app.schemas import TokenSchema, UserLoginSchema
#роутер для аутентифікації 
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


#тимчасова імітація бд
FAKE_USER_DB = {
    "admin@prostock.com": {
        "email": "admin@prostock.com",
        # Захешований пароль для рядка "admin123" (створений за допомогою passlib)
        "password_hash": hash_password("admin123"),
        "role": "Адміністратор"
    }
}

@router.post("/login", response_model=TokenSchema)
def login(user_credentials: UserLoginSchema):
    #ендпоінти для входу в систему
    user = FAKE_USER_DB.get(user_credentials.email)
    if not user or not verify_password(user_credentials.password, user["password_hash"]):
        #якщо дані невірні
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Невірний email або пароль",
            headers = {"WWW-Authenticate": "Bearer"},
        )

    #Розрахунок часу дії токена
    acess_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    #створення jwt-токена
    acess_token = create_access_token(
        date = {"sub": user["email"], "role": user["role"]},
        expires_date= acess_token_expires
    )

    return {
        "access_token": acess_token,
        "token_type": "bearer"
    }


#повертає емейл і роль з перевіреного jwt
@router.get("/me")
def current_user(current_user: dict = Depends(get_current_user)):
    return current_user