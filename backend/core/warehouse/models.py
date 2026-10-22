from django.db import models
from django.core.validators import MinValueValidator
from ..core.enums import (
    ObstacleTypeEnum,
    PointTypeEnum,
    ZoneTypeEnum,
    ShelfStatusEnum,
    InactiveReasonEnum
)

class Warehouse(models.Model):
    warehouse_id = models.BigAutoField(primary_key=True)
    warehouse_name = models.CharField(max_length=150)
    warehouse_address = models.TextField(
        blank=True,
        null=True
    )
    total_warehouse_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    
    def __str__(self):
        return self.warehouse_name
    
    class Meta:
        db_table = 'warehouse'
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'

class WarehouseGrid(models.Model):
    grid_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    cell_size = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0.01)]
    )
    grid_width = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    grid_height = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    
    def __str__(self):
        return f"Grid {self.grid_id} ({self.warehouse.warehouse_name})"

    class Meta:
        db_table = 'warehouse_grid'
        verbose_name = 'Warehouse Grid'
        verbose_name_plural = 'Warehouse Grids'

class WarehouseWalls(models.Model):
    wall_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    vertex_order = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    coord_x = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    coord_y = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    
    def __str__(self):
        return f"Wall {self.wall_id} ({self.warehouse.warehouse_name})"

    class Meta:
        db_table = 'warehouse_walls'
        verbose_name = 'Warehouse Walls'
        verbose_name_plural = 'Warehouse Walls'
        ordering = ['warehouse', 'vertex_order']
        constraints = [
            models.UniqueConstraint(
                fields=['warehouse', 'vertex_order'],
                name='unique_vertex_per_warehouse'
            )
        ]

class WarehouseObstacles(models.Model):
    obstacle_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    obstacle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    obstacle_type = models.CharField(
        max_length=50,
        choices=ObstacleTypeEnum.choices
    )
    coord_x = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    coord_y = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    max_height = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True
    )
    
    def __str__(self):
        return f"Obstacle {self.obstacle_id} ({self.warehouse.warehouse_name})"

    class Meta:
        db_table = 'warehouse_obstacles'
        verbose_name = 'Warehouse Obstacles'
        verbose_name_plural = 'Warehouse Obstacles'

class WarehouseEntryPoints(models.Model):
    point_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    point_name = models.CharField(max_length=100)
    point_type = models.CharField(
        max_length=50,
        choices=PointTypeEnum.choices
    )
    coord_x = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    coord_y = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    
    def __str__(self):
        return f"Point {self.point_id} ({self.warehouse.warehouse_name})"

    class Meta:
        db_table = 'warehouse_entry_points'
        verbose_name = 'Warehouse Entry Points'
        verbose_name_plural = 'Warehouse Entry Points'

class Zone(models.Model):
    zone_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    zone_name = models.CharField(max_length=100)
    zone_type = models.CharField(
        max_length=50,
        choices=ZoneTypeEnum.choices
    )
    coord_x = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    coord_y = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    max_capacity_m3 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    
    def __str__(self):
        return f"Zone {self.zone_id} ({self.warehouse.warehouse_name})"

    class Meta:
        db_table = 'zone'
        verbose_name = 'Zone'
        verbose_name_plural = 'Zones'

class Rack(models.Model):
    rack_id = models.BigAutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        db_column='warehouse_id'
    )
    rack_code = models.CharField(max_length=30)
    coord_x = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    coord_y = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="mm"
    )
    length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="mm"
    )
    rotation_angle = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    shelves_count = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    def __str__(self):
        return f"Rack {self.rack_id} ({self.warehouse.warehouse_name})"
    
    class Meta:
        db_table = 'rack'
        verbose_name = 'Rack'
        verbose_name_plural = 'Racks'

class Shelf(models.Model):
    shelf_id = models.BigAutoField(primary_key=True)
    rack = models.ForeignKey(
        Rack,
        on_delete=models.CASCADE,
        db_column='rack_id'
    )
    shelf_code = models.CharField(
        max_length=50,
        unique=True
    )
    qr = models.CharField(
        max_length=100,
        unique=True
    )
    shelf_length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="mm"
    )
    shelf_width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="mm"
    )
    shelf_height = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="mm"
    )
    shelf_max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        help_text="kg"
    )
    is_occupied = models.BooleanField(default=False)
    shelf_status = models.CharField(
        max_length=20,
        choices=ShelfStatusEnum.choices,
        default=ShelfStatusEnum.ACTIVE
    )
    inactive_reason = models.CharField(
        max_length=50,
        choices=InactiveReasonEnum.choices,
        blank=True,
        null=True,
        help_text="Filled in only when status INACTIVE"
    )
    
    # TODO: implement logic for automatic cleanup reasons for blocking
    #  when status changes from INACTIVE to another
    # TODO: role-based access control (storekeeper can't change shelf status)
    
    def occupy(self):
        self.is_occupied = True
        self.shelf_status = ShelfStatusEnum.OCCUPIED
        self.save(update_fields=['is_occupied', 'shelf_status'])
    
    @property
    def total_volume_m3(self):
        """
        Total shelf volume in cubic meters (m³).
        Provided that the data is stored in mm.
        """
        return (
            float(self.shelf_length)
            * float(self.shelf_width)
            * float(self.shelf_height)
        ) / 1_000_000_000
    
    # TODO: implement the logic for calculating the current weight.
    #  Change inventory_set to find every boxes on the shelf
    #  by Pallet.current_shelf and Box.shelf
    # @property
    # def current_weight(self):
    #     """
    #     Current total items weight on this shelf.
    #     Calculated from direct boxes and boxes on pallets.
    #     """
    #     return sum(
    #         (item.quantity * item.product.weight)
    #         for item in self.inventory_set.all()
    #     )
    
    # @property
    # def remaining_weight(self):
    #     return self.shelf_max_weight - self.current_weight
    
    # @property
    # def can_fit_cargo(self, product_weight, product_quantity=1):
    #     """
    #     Check whether the shelf can withstand the additional weight
    #     """
    #     required_weight = product_weight * product_quantity
    #     return self.remaining_weight >= required_weight
    
    # @property
    # def fill_percentage(self):
    #     if self.shelf_max_weight == 0:
    #         return 0.0
    #     percentage = (self.current_weight / self.shelf_max_weight) * 100
    #     return min(round(percentage, 2), 100.0)

    def __str__(self):
        return (
            f"Shelf {self.shelf_code}. "
            f"Rack {self.rack.rack_id}. "
            f"Warehouse ({self.rack.warehouse.warehouse_name})"
        )

    class Meta:
        db_table = 'shelf'
        verbose_name = 'Shelf'
        verbose_name_plural = 'Shelves'