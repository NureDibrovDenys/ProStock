from fastapi import APIRouter, Depends

from app.utils.security import ROOT,ADMIN, WAREHOUSE_MANAGER, get_current_user, require_roles
from ..schemas import WareHouseMapSchema, WarehouseMapUpdateSchema
from app.warehouses.services.warehouse_map_service import WarehouseMapService

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])

@router.get(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(get_current_user)],
)
def get_warehouse_map(warehouse_id: int):
    return WarehouseMapService.get_map(warehouse_id)

#відповідь — збережена мапа з id нових об'єктів (фронт кладе її у кеш замість надісланої)
@router.put(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(require_roles(ROOT, ADMIN, WAREHOUSE_MANAGER))],
)
def save_warehouse_map(warehouse_id: int, map_data: WarehouseMapUpdateSchema):
    return WarehouseMapService.save_map(
        warehouse_id,
        map_data.model_dump(mode="json"),
    )
