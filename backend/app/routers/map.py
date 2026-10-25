from fastapi import APIRouter, Depends

from app.utils.security import ROOT,ADMIN, WAREHOUSE_MANAGER, get_current_user, require_roles
from ..schemas import WarehouseMapUpdateSchema

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])

# 📌 Тимчасове сховище в пам'яті (імітація бази даних для тестування)
fake_database = {}

@router.get("/{warehouse_id}/map", dependencies=[Depends(get_current_user)])
def get_warehouse_map(warehouse_id: int):
    #завантаження топології складу з "бази даних"
    if warehouse_id not in fake_database:
        #якщо карти для цього складу не має, повертаємо порожню структуру
        return {"warehouse_id": warehouse_id, "zones": [], "walls": [], "racks": []}

    return fake_database[warehouse_id]

@router.put("/{warehouse_id}/map", dependencies=[Depends(require_roles(ROOT, ADMIN, WAREHOUSE_MANAGER))])
def save_warehouse_map(warehouse_id: int, map_data: WarehouseMapUpdateSchema):
    #збереження топології складу в "базу даних"
    fake_database[warehouse_id] = map_data.model_dump()  #збереження як словник
    fake_database[warehouse_id]["warehouse_id"] = warehouse_id  #додаємо ідентифікатор складу

    return {
        "status": "success",
        "message": f"Топологія складу {warehouse_id} успішно збережена у тимчасову пам'ять.",
        "data": fake_database[warehouse_id]
    }