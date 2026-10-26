from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.warehouses.models import (
    Rack,
    Warehouse,
    WarehouseEntryPoint,
    WarehouseGrid,
    WarehouseObstacle,
    WarehouseWall,
    Zone,
)


class WarehouseMapService:
    """Сервіс роботи з картою складу до підключення постійного сховища."""

    @staticmethod
    async def get_map(
        session: AsyncSession,
        warehouse_id: int,
    ) -> dict:
        warehouse = await session.get(Warehouse, warehouse_id)
        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Склад не знайдено",
            )
        #завантаження всіх елементів карти
        grid_result = await session.execute(
            select(WarehouseGrid).where(
                WarehouseGrid.warehouse_id == warehouse_id
            )
        )
        grid = grid_result.scalars().first()

        walls_result = await session.execute(
            select(WarehouseWall)
            .where(WarehouseWall.warehouse_id == warehouse_id)
            .order_by(WarehouseWall.vertex_order)
        )
        obstacles_result = await session.execute(
            select(WarehouseObstacle).where(
                WarehouseObstacle.warehouse_id == warehouse_id
            )
        )

        points_result = await session.execute(
            select(WarehouseEntryPoint).where(
                WarehouseEntryPoint.warehouse_id == warehouse_id
            )
        )

        zones_result = await session.execute(
            select(Zone).where(Zone.warehouse_id == warehouse_id)
        )

        racks_result = await session.execute(
            select(Rack).where(Rack.warehouse_id == warehouse_id)
        )

        return {
            "warehouse_id": warehouse_id,
            "grid": (
                {
                    "cell_size": grid.cell_size,
                    "grid_width": grid.grid_width,
                    "grid_height": grid.grid_height,
                }
                if grid else None
            ),
            "walls": [
                {"coord_x": wall.x, "coord_y": wall.y}
                for wall in walls_result.scalars().all()
            ],
            "obstacles": [
                {
                    "obstacle_name": item.name,
                    "obstacle_type": item.type,
                    "coord_x": item.x,
                    "coord_y": item.y,
                    "width": item.width,
                    "length": item.length,
                    "max_height": item.max_height,
                }
                for item in obstacles_result.scalars().all()
            ],
            "entry_points": [
                {
                    "point_name": item.point_name,
                    "point_type": item.point_type,
                    "coord_x": item.x,
                    "coord_y": item.y,
                }
                for item in points_result.scalars().all()
            ],
            "zones": [
                {
                    "zone_name": item.name,
                    "zone_type": item.type,
                    "coord_x": item.x,
                    "coord_y": item.y,
                    "width": item.width,
                    "length": item.length,
                    "max_capacity_m3": item.max_capacity_m3,
                }
                for item in zones_result.scalars().all()
            ],
            "racks": [
                {
                    "rack_code": item.code,
                    "coord_x": item.x,
                    "coord_y": item.y,
                    "width": item.width,
                    "length": item.length,
                    "rotation_angle": item.rotation_angle,
                    "shelves_count": item.shelves_count,
                }
                for item in racks_result.scalars().all()
            ],
        }

    @staticmethod
    async def save_map(
        session: AsyncSession,
        warehouse_id: int,
        map_data: dict
    ) -> dict:
        #перевіряємо існування складу
        warehouse = await session.get(Warehouse, warehouse_id)

        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Склад не знайдено"
            )

        try:
            #усі зміни виконуються в одній транзакції
            async with session.begin_nested():
                #видаляємо старі елементи карти
                for model in (
                    WarehouseGrid,
                    WarehouseWall,
                    WarehouseObstacle,
                    WarehouseEntryPoint,
                    Zone,
                    Rack,
                ):
                    await session.execute(
                        delete(model).where(
                            model.warehouse_id == warehouse_id
                        )
                    )

                # Створюємо сітку
                grid_data = map_data.get("grid")
                if grid_data:
                    session.add(
                        WarehouseGrid(
                            warehouse_id=warehouse_id,
                            cell_size=grid_data["cell_size"],
                            grid_width=grid_data["grid_width"],
                            grid_height=grid_data["grid_height"],
                        )
                    )

                # Створюємо вершини стін у заданому порядку
                for order, wall in enumerate(
                    map_data.get("walls", []),
                    start=1,
                ):
                    session.add(
                        WarehouseWall(
                            warehouse_id=warehouse_id,
                            vertex_order=order,
                            x=wall["coord_x"],
                            y=wall["coord_y"],
                        )
                    )

                # Створюємо перешкоди
                for item in map_data.get("obstacles", []):
                    session.add(
                        WarehouseObstacle(
                            warehouse_id=warehouse_id,
                            name=item.get("obstacle_name"),
                            type=item["obstacle_type"],
                            x=item["coord_x"],
                            y=item["coord_y"],
                            width=item["width"],
                            length=item["length"],
                            max_height=item.get("max_height"),
                        )
                    )

                # Створюємо точки входу
                for item in map_data.get("entry_points", []):
                    session.add(
                        WarehouseEntryPoint(
                            warehouse_id=warehouse_id,
                            point_name=item["point_name"],
                            point_type=item["point_type"],
                            x=item["coord_x"],
                            y=item["coord_y"],
                        )
                    )

                # Створюємо зони
                for item in map_data.get("zones", []):
                    session.add(
                        Zone(
                            warehouse_id=warehouse_id,
                            name=item["zone_name"],
                            type=item["zone_type"],
                            x=item["coord_x"],
                            y=item["coord_y"],
                            width=item["width"],
                            length=item["length"],
                            max_capacity_m3=item.get("max_capacity_m3"),
                        )
                    )

                # Створюємо стелажі
                for item in map_data.get("racks", []):
                    session.add(
                        Rack(
                            warehouse_id=warehouse_id,
                            code=item["rack_code"],
                            x=item["coord_x"],
                            y=item["coord_y"],
                            width=item["width"],
                            length=item["length"],
                            rotation_angle=item.get(
                                "rotation_angle",
                                Decimal("0"),
                            ),
                            shelves_count=item["shelves_count"],
                        )
                    )

                await session.flush()

            await session.commit()

        except Exception:
            await session.rollback()
            raise

        return await WarehouseMapService.get_map(
            session,
            warehouse_id,
        )



    # ⡅⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⢀⡀⢀⢀⡀⢀⡀⢀⡀⢀⢈⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡈⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣃⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣤⣄⣫⣝⣫⣝⣭⣭⣯⣹⡇
    # ⠅⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⠠⡀⡀⡀⡀⠠⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣵⣿⣏⡮⢽⣯⣹⡅
    # ⡂⡀⢀⢀⢀⡀⡀⡀⢀⢀⡀⢂⡀⢐⡀⢐⡂⢀⡀⢀⡀⢂⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢂⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣾⣿⣿⣿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣻⣷⣿⣟⡳⣻⡇
    # ⠅⡀⡀⡀⡀⡀⡀⡀⠄⡀⡀⠁⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⡿⠊⠑⠾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣻⡷⢽⡽⠆
    # ⡆⡀⡀⡀⠠⡀⡀⠐⡐⡀⡀⠠⠠⠄⠠⡠⡐⠄⡀⡀⡀⠢⢄⠆⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠰⡀⡇⠠⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣷⣽⣿⠇⡀⡀⡀⠠⠚⠗⡻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠐⢪⢇⣺⡖⡂
    # ⡅⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡂⢀⡀⡀⢄⡐⠠⡐⠄⠐⠈⠐⡀⡀⠄⡀⡀⡀⠠⡀⡀⡀⡀⡀⡀⡀⡀⢐⡀⡇⢈⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⡀⡀⡀⡀⡀⡀⠐⢐⠛⣿⠈⡈⡉⠉⢃⠙⢿⣿⣿⡘⡣⠦⡍⣸⠆
    # ⡃⡀⡀⡀⠈⠈⠑⠁⠈⠁⡀⡀⡀⠁⡂⢈⡁⡀⡀⢁⢌⣈⢈⠌⠂⢡⣷⣿⣿⣦⢀⠈⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⢀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣟⡀⡀⡀⡀⡀⡀⡀⡀⡀⠐⠁⡀⢈⠂⡀⡀⡀⢘⣿⣿⢂⣳⣟⣿⣿⡇
    # ⠂⡀⠅⠁⣀⣤⣴⣶⣿⣿⣿⣿⣤⠐⠆⡰⡀⣿⢓⠬⠐⠠⠢⠦⣽⣿⣿⣿⣿⣿⣿⣧⡀⡀⡀⡀⡀⡀⡀⢐⡀⡇⠨⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡇⢸⠇⡀⡀⡀⢠⣄⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢸⢟⠟⣵⣷⣿⣿⣿⡇
    # ⡶⢟⣯⣳⣱⢿⣿⣿⣿⣿⣿⣿⣿⣿⢤⣤⡰⠽⣡⣿⢿⢻⣎⣫⣿⢿⣿⣿⣿⣿⣿⣿⣷⡀⡀⠄⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢠⣾⡀⡀⡀⣤⢄⣀⠈⠙⠦⡀⡀⡀⠤⠹⠻⠿⢦⡀⡾⣾⣾⣷⣿⣿⣿⣿⡇
    # ⣷⣳⣷⣳⣾⣖⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⢁⣼⡻⣟⣳⡾⠮⣿⣿⣿⣿⣿⣿⣿⣳⣿⣧⡀⡀⡀⡀⡀⢰⡀⡧⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠈⡗⡀⡀⡀⡀⡀⠈⠐⣛⠂⡀⡀⢀⡔⣤⡤⢀⡀⠐⣾⣟⣾⣿⣿⣿⣿⣿⡇
    # ⣗⣾⣿⣟⣿⣗⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣗⣪⣥⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣿⣿⡀⠐⢀⡀⡀⢐⡀⣗⢰⠘⡀⠐⡀⡄⡀⣀⣀⡠⠤⠄⠒⠒⣠⡀⡃⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠈⠉⡀⡞⠉⠛⠛⠿⣿⣯⣿⣿⡇
    # ⣿⣿⣿⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣷⠂⡀⡀⡀⡀⡀⣯⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⣤⣤⣾⣿⣿⡇⠁⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠃⡀⡀⡀⡀⡀⡀⡀⠐⠁
    # ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠐⡀⡀⢘⡀⣿⢸⠘⡀⠦⣄⣤⣾⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀
    # ⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣯⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡋⠁⡀⠠⠄⠠⠠⠨⡀⢿⠸⢈⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡇⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠁⡀⡀⡀⡀⠠⠄⡀⡀⡀⡀
    # ⠛⠛⠛⠛⡛⣹⠻⣿⣿⣿⣿⣿⣿⡟⣿⣿⣿⣿⣾⣿⣭⢴⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠐⡀⠄⡀⠠⠐⡀⢩⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠹⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡦⡀⡀⡀⣌⡀⡀⠠⠄⠈⡀⡀⠄⡀⡀⠂
    # ⣦⣾⣿⣿⣿⠍⡨⠈⣭⢭⡭⢍⡟⣿⣿⣭⣽⢿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠠⠄⡀⠨⡀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⡀⢿⡀⡀⡀⡀⠉⠙⠶⠶⠦⠄⠍⡀⡀⠸⣿⣷⣄⡀⡀⡀⡀⡀⡀⡀⡀⠁
    # ⣿⣟⢝⡷⠛⡇⣹⣐⡨⣧⣮⣵⣽⣿⢌⢇⣛⡋⣋⣙⣛⣛⣛⡛⠛⠳⠹⣿⣿⣿⣿⣿⣿⡿⢐⠨⡀⡀⠘⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⢿⡠⡀⡀⡀⡀⡀⡀⡀⡀⡀⣴⡀⡀⠈⣿⣿⣿⣄⡀⡀⡀⡀⣠⣤⡁
    # ⣏⡣⣿⢛⣹⠣⣧⢿⡇⢏⠻⡺⠿⡳⡻⠯⢿⣾⡷⡳⢷⣾⢾⡩⣓⣤⢶⣾⣿⡆⣿⣿⣿⠠⠨⠌⠌⢠⡀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣄⡀⠻⣆⡀⡀⡀⡀⡀⣴⣀⣾⣿⣷⡀⡀⡀⢸⣿⣿⣿⣤⠺⣽⠻⠄⠃
    # ⣯⠚⡣⡀⣼⡥⣿⡼⡷⣱⠒⠙⠛⠺⣻⣿⣿⣯⠼⠯⠽⢦⣮⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠨⡨⢌⠄⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⣉⣲⣴⣦⣽⣾⠏⡀⠙⢿⡀⡀⡀⡀⣿⣿⣿⣿⣿⡄⡀⠉⠃
    # ⣟⡀⡏⡀⣿⣪⡿⣫⣭⣧⣾⣶⣳⣭⣽⣿⣿⣿⣿⣿⣿⣿⠿⠟⣉⣩⣬⣍⠿⣿⣿⣿⣿⣿⣄⡌⢌⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⢠⡀⡀⡀⠁⡀⡀⡀⢹⣿⣿⣿⣿⣿⡀⡀⡀
    # ⣿⣻⡤⡐⣿⣿⣃⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣝⢻⣋⣜⣞⣳⣾⣞⣺⣿⣹⣿⣿⣿⢘⡀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⠈⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⡀⠂
    # ⣿⢸⣷⣳⣿⣿⣿⣿⣿⡿⣻⣻⡿⣿⣿⣿⣿⣼⣿⣿⡿⣿⣺⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⡀⠂⡀⡀⡀⡀⡀⡀⡀⡀⡀⢿⣿⣿⣿⣿⣿⡟⠆
    # ⣟⡼⣻⣿⣿⣿⣿⣛⣫⣽⣯⣿⡯⢟⣿⣯⣿⣿⣽⣯⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡏⡶⡄⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣼⣿⣿⣿⣿⣿⣧⡀
    # ⣽⣿⣿⣿⣿⠿⠽⢽⣯⣭⣽⣷⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣒⣿⣿⣿⣿⣿⣿⣿⣿⣿⢡⡟⣠⠧⠄⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⡿⣯⣺⣳⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢹⠛⢿⠿⣧⡟⣿⣿⣿⣿⢧⢱⠁⡀⡅⡇⡀⡀⡀⡀⡀⡀⡀⡀⡀⣼⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⣿⣿⣟⣿⣿⣿⣿⣹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢰⣰⣡⣿⣸⣿⢳⣷⣿⣿⡏⣼⡟⠸⣰⠷⢻⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⡿⣽⣿⣷⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣿⣿⣿⣬⣼⡇⡀⣿⡇⣘⣷⡀⡀⡀⡀⡀⡀⡀⡀⠸⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⣳⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⣼⣿⣟⣥⣧⣷⣿⣿⣯⠠⢸⢻⡀⣿⣾⣷⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⡿⡀
    # ⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠻⠿⠟⠛⠛⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠷⠿⠿⠿⠿⠰⠾⠿⠫⠿⠿⠿⠿⡀⡀⡀⡀⡀⡀⡀⠘⠿⠿⠿⠿⠿⠧⠇

  
