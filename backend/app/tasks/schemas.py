from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import TaskStatus, TaskStepStatus, TaskType
from app.core.validators import StrippedStr, UniquePositiveIds


class PutawayStepOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inbound_order_item_id: int = Field(..., gt=0)
    target_shelf_id: int = Field(..., gt=0)


class PutawayTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_user_ids: UniquePositiveIds | None = Field(
        default=None,
        max_length=20,
        description=(
            "List of warehouse worker IDs; "
            "if empty or None, the task is added to the general queue."
        ),
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Execution priority (from 1 to 100)",
    )
    notes: StrippedStr | None = Field(
        default=None,
        max_length=2000,
        description="Manager's comment for warehouse staff",
    )
    step_overrides: list[PutawayStepOverride] | None = Field(
        default=None,
        description=(
            "Optional manual assignment of target shelves for items on a waybill"
        ),
    )
    
    @field_validator("step_overrides")
    @classmethod
    def _unique_item_overrides(
        cls, value: list[PutawayStepOverride] | None
    ) -> list[PutawayStepOverride] | None:
        if not value:
            return value
        
        item_ids: list[int] = [item.inbound_order_item_id for item in value]
        has_duplicates: bool = len(item_ids) != len(set(item_ids))
        if has_duplicates:
            raise ValueError(
                "Duplicate inbound_order_item_id values in step_overrides are not allowed"
            )
        
        return value


class WarehouseTaskAssigneeResponse(BaseModel):
    user_id: int
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseTaskStepResponse(BaseModel):
    step_id: int
    inbound_order_item_id: int
    product_id: int
    product_name: str
    sku_code: str
    target_shelf_id: int | None
    completed_by_user_id: int | None
    planned_quantity: Decimal
    actual_quantity: Decimal
    package_type: str
    step_status: TaskStepStatus

    model_config = ConfigDict(from_attributes=True)


class WarehouseTaskResponse(BaseModel):
    task_id: int
    warehouse_id: int
    inbound_order_id: int
    invoice_number: str
    task_type: TaskType
    task_status: TaskStatus
    priority: int
    assignees: list[WarehouseTaskAssigneeResponse]
    created_by_user_id: int
    notes: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    steps: list[WarehouseTaskStepResponse]

    model_config = ConfigDict(from_attributes=True)
