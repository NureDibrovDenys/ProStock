from pydantic import BaseModel, Field
from typing import List, Optional

#схема для стіни (координати  -- початок і кінця)
class WallSchema(BaseModel):
    x1: float
    x2: float
    y1: float
    y2: float

#схема для стелажа 
class RackSchema(BaseModel):
    rack_code: str = Field(..., description = "Унікальний код стелажа")
    coord_x: float = Field(..., description = "Координата Х")
    coord_y: float = Field(..., description = "Координата Y")
    width: float = Field(..., description = "Ширина стелажа")
    length: float = Field(..., description = "Довжина стелажа")
    shelves_count: int = Field (..., description = "Кількість полиць")

#схема для складських зон
class ZoneSchema(BaseModel):
    zone_name: str
    zone_type: str = Field(..., description = "Тип зони: Inbound_Dock, Storage_Area, Outbound_Dock")
    coord_x: float
    coord_y: float
    max_capacity_m3: Optional[float] = Field(None, description = "Максимальная місткість у м3")


#головна схема, яка об'єднує всю карту складу для збереження (put/post)
class WarehouseMapUpdateSchema(BaseModel):
  walls: List[WallSchema] = []
  racks: List[RackSchema] = []
  zones: List[ZoneSchema] = []