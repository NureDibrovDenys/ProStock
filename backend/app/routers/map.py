from fastapi import APIRouter, Depends

from app.utils.security import ROOT,ADMIN, WAREHOUSE_MANAGER, get_current_user, require_roles
from backend.app.core.db import get_async_session
from ..schemas import WareHouseMapSchema, WarehouseMapUpdateSchema
from app.warehouses.services.warehouse_map_service import WarehouseMapService
from sqlalchemy.ext.asyncio import AsyncSession
router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])

@router.get(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
   
)
async def get_warehouse_map(
    warehouse_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
    ):
    return await WarehouseMapService.get_map(
        session=session,
        warehouse_id=warehouse_id
    )

@router.put("/{warehouse_id}/map", dependencies=[Depends(require_roles(ROOT, ADMIN, WAREHOUSE_MANAGER))])
async def save_warehouse_map(
    warehouse_id: int, 
    map_data: WarehouseMapUpdateSchema, 
    session: AsyncSession = Depends(get_async_session)
    ):
    saved_map = await WarehouseMapService.save_map(
        session=session,
        warehouse_id = warehouse_id,
        map_data=map_data.model_dump(mode="python"),
    )

    return {
        "status": "success",
        "message": f"Топологія складу {warehouse_id} успішно збережена у тимчасову пам'ять.",
        "data": saved_map,
    }