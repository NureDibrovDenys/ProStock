from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, condecimal, field_validator, model_validator
from typing_extensions import Annotated

from app.core.enums import ObstacleType, PointType, ZoneType

# Формат мапи узгоджений із фронтом (frontend/API.md, розділ «Мапа складу»).
# Одиниці — метри, coord_x/coord_y — центр об'єкта, rotation_angle — градуси за годинниковою стрілкою.
# length — розмір уздовж власної осі X об'єкта (до повороту), width — уздовж осі Y.

#обмеження (у JSON віддаються числом, а не рядком "8.00")
_as_number = PlainSerializer(float, return_type=float, when_used="json")
Numeric_MAX_8_2 = Annotated[Decimal, condecimal(max_digits=8, decimal_places= 2), _as_number]
Numeric_MAX_10_2 = Annotated[Decimal, condecimal(max_digits=10, decimal_places= 2), _as_number]
Numeric_MAX_5_2 = Annotated[Decimal, condecimal(max_digits=5, decimal_places= 2), _as_number]

#схема для сітки складу (одна сітка на склад)
class GridSchema(BaseModel):
    cell_size: Numeric_MAX_8_2 = Field(Decimal("1.0"), gt=0, description="Розмір клітинки сітки")
    grid_width: Numeric_MAX_10_2 = Field(..., gt=0, description="Ширина сітки")
    grid_height: Numeric_MAX_10_2 = Field(..., gt=0, description="Висота сітки")

#схема для вершини контуру приміщення (по внутрішній грані стіни)
class WallSchema(BaseModel):
   vertex_order: int = Field(..., ge=1, description="Порядковий номер вершини")
   coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х вершини")
   coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y вершини")

#схема для внутрішньої перегородки (відрізок по осьовій лінії стіни)
class PartitionSchema(BaseModel):
    partition_id: int | None = None
    start_x: Numeric_MAX_8_2 = Field(..., description="Координата Х початку")
    start_y: Numeric_MAX_8_2 = Field(..., description="Координата Y початку")
    end_x: Numeric_MAX_8_2 = Field(..., description="Координата Х кінця")
    end_y: Numeric_MAX_8_2 = Field(..., description="Координата Y кінця")
    thickness: Numeric_MAX_5_2 = Field(Decimal("0.20"), gt=0, description="Товщина перегородки")
    height: Numeric_MAX_8_2 | None = Field(None, gt=0, description="Висота; null — до стелі")

    @model_validator(mode = "after")
    def must_have_length(self):
        if self.start_x == self.end_x and self.start_y == self.end_y:
            raise ValueError("Перегородка має нульову довжину")
        return self

#схема для перешкоди (колона, стовп)
class ObstacleSchema(BaseModel):
    obstacle_id: int | None = None
    obstacle_name: str | None = Field(None, max_length=100, description="Назва перешкоди")
    obstacle_type: ObstacleType = Field(..., description= "Тип перешкоди: column, pillar, niche, restricted_zone, other")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина")
    rotation_angle: float = Field(0.0, ge=0, lt=360, description="Кут повороту в градусах [0, 360)")
    max_height: Numeric_MAX_8_2 | None = Field(None, gt=0, description="Максимальна висота")

#схема для точки приймання / відвантаження
class EntryPointSchema(BaseModel):
    point_id: int | None = None
    point_name: str = Field(...,min_length=1, max_length= 100, description="Навза точки" )
    point_type: PointType = Field(..., description="Тип точки: inbound, outbound, general_entry")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
#схема для стелажа 
class RackSchema(BaseModel):
    rack_id: int | None = None
    rack_code: str = Field(..., min_length = 1, description = "Унікальний код стелажа")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина стелажа")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина стелажа")
    rotation_angle: float = Field(0.0, ge=0, lt=360, description="Кут повороту в градусах [0, 360)")
    shelves_count: int = Field(..., ge=1, description="Кількість полиць")

#схема для складських зон
class ZoneSchema(BaseModel):
    zone_id: int | None = None
    zone_name: str = Field(..., min_length = 1, max_length = 100, description = "Назва зони")
    zone_type: ZoneType = Field(..., description = "Тип зони: inbound_dock, storage_area, outbound_dock")
    coord_x: Numeric_MAX_8_2 = Field(..., description="Координата Х")
    coord_y: Numeric_MAX_8_2 = Field(..., description="Координата Y")
    width: Numeric_MAX_8_2 = Field(..., gt=0, description="Ширина зони")
    length: Numeric_MAX_8_2 = Field(..., gt=0, description="Довжина зони")
    rotation_angle: float = Field(0.0, ge=0, lt=360, description="Кут повороту в градусах [0, 360)")
    max_capacity_m3: Numeric_MAX_10_2 | None = Field(None, gt=0, description="Максимальна місткість у м3")


def _segments_cross(a, b, c, d) -> bool:
    """Чи перетинаються відрізки ab і cd усередині (дотик кінцями не рахується)."""
    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 0) - (v < 0)
    return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0

#головна схема, яка об'єднує всю карту складу для збереження (put/post)
class WarehouseMapUpdateSchema(BaseModel):
    grid: GridSchema | None = None
    walls: list[WallSchema] = Field(default_factory=list)
    partitions: list[PartitionSchema] = Field(default_factory=list)
    obstacles: list[ObstacleSchema] = Field(default_factory=list)
    entry_points: list[EntryPointSchema] = Field(default_factory=list)
    racks: list [RackSchema] = Field(default_factory=list)
    zones: list [ZoneSchema] = Field(default_factory=list)

    #приклад (автоматично при тестувані у свагері підставляє у тіло запроса готовий json приклад)
    model_config = {
        "json_schema_extra": {
            "example": {
                "grid": {"cell_size": 1.0, "grid_width": 40, "grid_height": 20},
                "walls": [
                    {"vertex_order": 1, "coord_x": 0, "coord_y": 0},
                    {"vertex_order": 2, "coord_x": 40, "coord_y": 0},
                    {"vertex_order": 3, "coord_x": 40, "coord_y": 20},
                    {"vertex_order": 4, "coord_x": 0, "coord_y": 20}
                ],
                "partitions": [
                    {"start_x": 20, "start_y": 0, "end_x": 20, "end_y": 12, "thickness": 0.2, "height": None}
                ],
                "obstacles": [
                    {"obstacle_name": "Колона 1", "obstacle_type": "column",
                     "coord_x": 20, "coord_y": 15, "width": 1, "length": 1, "rotation_angle": 0, "max_height": 6}
                ],
                "entry_points": [
                    {"point_name": "Головний вхід", "point_type": "general_entry", "coord_x": 0, "coord_y": 10}
                ],
                "zones": [
                    {"zone_name": "Зона приймання", "zone_type": "inbound_dock",
                     "coord_x": 4, "coord_y": 10, "width": 20, "length": 8, "rotation_angle": 0, "max_capacity_m3": 120}
                ],
                "racks": [
                    {"rack_code": "A-01", "coord_x": 12, "coord_y": 2, "width": 1.2, "length": 6,
                     "rotation_angle": 0, "shelves_count": 4}
                ]
            }
        }
    }

    #контур стін (перевірки, щоб був простий полігон із мінімум 3 вершин)
    @field_validator("walls")
    @classmethod
    def walls_must_form_polygon(cls, value):
        """
        Перевіряє, що контур стін є простим полігоном: мінімум 3 вершини,
        унікальні vertex_order, без самоперетинів, площа (за vertex_order) додатна.
        Дозволяє передавати порожній список, якщо контур ще не намальований.
        """
        if not value:
            return value
        if len(value) < 3:
            raise ValueError("Контур стін має містити мінімум 3 вершини")
        orders = [w.vertex_order for w in value]
        if len(set(orders)) != len(orders):
            raise ValueError("Номери вершин контуру (vertex_order) повторюються")

        pts = [(w.coord_x, w.coord_y) for w in sorted(value, key=lambda w: w.vertex_order)]
        n = len(pts)
        doubled_area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        if doubled_area <= 0:
            raise ValueError("Контур стін має нульову або від'ємну площу (вершини мають іти за годинниковою стрілкою на екрані)")
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue  #сусідні ребра (останнє й перше)
                if _segments_cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                    raise ValueError("Контур стін самоперетинається")
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
    warehouse_id: int
    permissions: dict[str, bool]


class AuthResponseSchema(TokenSchema):
    user: AuthUserSchema


class ProfileSchema(AuthUserSchema):
    created_at: datetime

