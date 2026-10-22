from datetime import datetime, timedelta
import bcrypt
from jose import jwt
from passlib.context import CryptContext

#хешування паролів через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#секретний ключ (тимчасово)
SECRET_KEY = (
    "secret_key_ProStock"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

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
