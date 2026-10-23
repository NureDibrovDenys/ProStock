from datetime import datetime, timedelta
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
 
from jose import jwt, JWSError, JWTError
from passlib.context import CryptContext

#хешування паролів через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#секретний ключ (тимчасово)
SECRET_KEY = (
    "secret_key_ProStock"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

#джерело назв ролей для перевірки доступу
ADMIN = "administrator"
WAREHOUSE_MANAGER = "warehouse_manager"
STOREKEEPER = "storekeeper"
ALL_ROLES = {ADMIN, WAREHOUSE_MANAGER, STOREKEEPER}

bearer_scheme = HTTPBearer(auto_error=False)

#хешування пароля
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

#перевірка пароля 
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

#генерація jwt токена
def create_access_token(date: dict, expires_date: timedelta | None = None):
    to_encode = date.copy()
    if expires_date:
        expire = datetime.utcnow() + expires_date
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

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

