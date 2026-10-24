from datetime import datetime, timedelta
from time import timezone
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Any 
from jose import jwt, JWSError, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.enums import RoleName

#хешування паролів через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#секретний ключ (тимчасово)
SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY не задано. Додайте рядок SECRET_KEY=... у файл backend/.env "
        "(згенерувати: python -c \"import secrets; print(secrets.token_hex(32))\")"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

#джерело назв ролей для перевірки доступу
ROOT = RoleName.ROOT.value
ADMIN = RoleName.ADMIN.value
WAREHOUSE_MANAGER = RoleName.WAREHOUSE_MANAGER.value
STOREKEEPER = RoleName.WORKER.value
GUEST = RoleName.GUEST.value
ALL_ROLES = {role.value for role in RoleName}

MAX_PASSWORD_BYTES = 72


bearer_scheme = HTTPBearer(auto_error=False)

#хешування пароля
def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Пароль занадто довгий (максимум 72 байти)")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()

#перевірка пароля 
def verify_password(plain_password: str, hashed_password: str) -> bool:
    raw = plain_password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()
    except ValueError: #пошкоджений кеш
        return False


#генерація jwt токена
def create_access_token(date: dict, expires_date: timedelta | None = None):
    to_encode = date.copy()
    if expires_date:
        expire = datetime.now(timezone.utc) + expires_date
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail = "Не вдалося перевірити облікові дані",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_exception
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")

        if not email or role not in ALL_ROLES:
            raise credentials_exception
        return {"email":email, "role":role}
    except JWTError as exc:
        raise credentials_exception from exc

#фабрика функцій (контроль доступу)
def require_roles(*allowed_roles: str):
    def role_checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict [str, Any]:
        if current_user["role"] not in allowed_roles:
                raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для виконання цієї операції",
            )
        return current_user

    return role_checker

