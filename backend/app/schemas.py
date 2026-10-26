from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, condecimal, field_validator, model_validator
from typing_extensions import Annotated

from app.core.enums import ObstacleType, PointType, ZoneType

#обмеження
Numeric_MAX_8_2 = Annotated[Decimal, condecimal(max_digits=8, decimal_places= 2)] 
Numeric_MAX_10_2 = Annotated[Decimal, condecimal(max_digits=10, decimal_places= 2)]

#схема для сітки складу (одна сітка на склад)
class GridSchema(BaseModel):
    cell_size: Numeric_MAX_8_2 = Field(Decimal("1.0"), gt=0, description="Розмір клітинки сітки")
    grid_width: Numeric_MAX_10_2 = Field(..., gt=0, description="Ширина сітки")
    grid_height: Numeric_MAX_10_2 = Field(..., gt=0, description="Висота сітки")

#схема для стіни (координати  -- початок і кінця)
class WallSchema(BaseModel):
   coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х вершини")
   coord_y: Numeric_MAX_10_2 = Field(..., description="Координата Y вершини")
#схема для перешкоди (колона, стовп)
class ObstacleSchema(BaseModel):
    obstacle_name: str | None = Field(None, max_length=100, description="Назва перешкоди")
    obstacle_type: ObstacleType = Field(..., description= "Тип перешкоди: column, pillar, niche, restricted_zone, other")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина")
    max_height: Numeric_MAX_8_2 | None = Field(None, gt=0, description="Максимальна висота")

#схема для точки приймання / відвантаження
class EntryPointSchema(BaseModel):
    point_name: str = Field(...,min_length=1, max_length= 100, description="Навза точки" )
    point_type: PointType = Field(..., description="Тип точки: inbound, outbound, general_entry")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
#схема для стелажа 
class RackSchema(BaseModel):
    rack_code: str = Field(..., description = "Унікальний код стелажа")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина стелажа")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина стелажа")
    rotation_angle: float = Field(0.0, ge=0, lt=360, description="Кут повороту в градусах [0, 360)")
    shelves_count: int = Field(..., ge=1, description="Кількість полиць")

#схема для складських зон
class ZoneSchema(BaseModel):
    zone_name: str = Field(..., min_length = 1, max_length = 100, description = "Назва зони")
    zone_type: ZoneType = Field(..., description = "Тип зони: inbound_dock, storage_area, outbound_dock")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина зони")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина зони")
    max_capacity_m3: Numeric_MAX_10_2 | None = Field(None, gt=0, description="Максимальна місткість у м3")
#головна схема, яка об'єднує всю карту складу для збереження (put/post)
class WarehouseMapUpdateSchema(BaseModel):
    grid: GridSchema | None = None
    walls: list[WallSchema] = Field(default_factory=list)
    obstacles: list[ObstacleSchema] = Field(default_factory=list)
    entry_point: list[EntryPointSchema] = Field(default_factory=list)
    racks: list [RackSchema] = Field(default_factory=list)
    zones: list [ZoneSchema] = Field(default_factory=list)

    #приклад (автоматично при тестувані у свагері підставляє у тіло запроса готовий json приклад)
    model_config = {
        "json_schema_extra": {
            "example": {
                "grid": {"cell_size": 1.0, "grid_width": 40, "grid_height": 20},
                "walls": [
                    {"coord_x": 0, "coord_y": 0},
                    {"coord_x": 40, "coord_y": 0},
                    {"coord_x": 40, "coord_y": 20},
                    {"coord_x": 0, "coord_y": 20}
                ],
                "obstacles": [
                    {"obstacle_name": "Колона 1", "obstacle_type": "column",
                     "coord_x": 20, "coord_y": 10, "width": 1, "length": 1, "max_height": 6}
                ],
                "entry_points": [
                    {"point_name": "Головний вхід", "point_type": "general_entry", "coord_x": 0, "coord_y": 10}
                ],
                "zones": [
                    {"zone_name": "Зона приймання", "zone_type": "inbound_dock",
                     "coord_x": 0, "coord_y": 0, "width": 8, "length": 20, "max_capacity_m3": 120}
                ],
                "racks": [
                    {"rack_code": "A-01", "coord_x": 12, "coord_y": 2, "width": 1.2, "length": 6,
                     "rotation_angle": 0, "shelves_count": 4}
                ]
            }
        }
    }

    #контур стін (перевірки, щоб було мінімум 3 вершини)
    @field_validator("walls")
    @classmethod
    def walls_must_form_polygon(cls, value):
        """
        Перевіряє, що контур стін є замкненим полігоном (мінімум 3 вершини).
        Дозволяє передавати порожній список, якщо стіни не оновлюються.
        """  
        if 0 < len(value) < 3:
            raise ValueError("Контур стін має містити мінімум 3 вершини")
        return value

    @model_validator(mode = "after")
    def rack_codes_must_be_uniqe(self):
        seen = set()
        duplicates = set()
        for rack in self.racks:
            if rack.rack_code in seen:
                duplicates.add(rack.rack_code)
            else:
                seen.add(rack.rack_code)

        if duplicates:
            raise ValueError(f"Повторюються коди стелажів: {','.join(sorted(duplicates))}")
        return self

#відповідь get: карта + ідентифікатор складу
class WareHouseMapSchema(WarehouseMapUpdateSchema):
    warehouse_id: int

#схеми для токена та логіну 
class UserLoginSchema(BaseModel):
    """Тіло запиту на вхід. Валідація — до звернення до БД."""

    email: EmailStr = Field(..., description="Робоча пошта")
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Пароль (перевірка складності — на етапі створення)",
    )

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        from app.users.schemas import normalize_email
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_bytes_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Пароль занадто довгий (максимум 72 байти)")
        return value


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0


class AuthUserSchema(BaseModel):
    """Профіль користувача, який повертається разом із токеном."""

    user_id: int
    user_email: str
    first_name: str
    last_name: str
    role: str
    status: str
    permissions: dict[str, bool]


class AuthResponseSchema(TokenSchema):
    user: AuthUserSchema


class ProfileSchema(AuthUserSchema):
    created_at: datetime


