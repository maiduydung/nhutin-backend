"""
Fixed Items Service.
Handles selection of fixed items that are ALWAYS included in the BOM:
- Walking floor, Hydraulic pump, Hydraulic oil, Aluminum bars
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import (
    logger,
    WALKING_FLOORS,
    HYDRAULIC_PUMP_MAP,
    HYDRAULIC_OIL_WEIGHT_KG,
    HYDRAULIC_PUMP_WEIGHT_KG,
)


class FixedItemsSelector:
    """Selects fixed items for container BOM."""

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()

    def getWalkingFloor(self, itemModelType: str) -> dict[str, Any]:
        """Get one walking floor set based on model type."""
        if itemModelType not in WALKING_FLOORS:
            raise ValueError(f"Unknown walking floor type: {itemModelType}")
        
        config = WALKING_FLOORS[itemModelType]
        itemType = config["type"]
        weight = config["weight"]
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = %s AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """,
            (itemType,),
        )

        if not result:
            raise ValueError(f"No walking floor available for type: {itemType}")

        row = result[0]
        unitPrice = float(row[4])
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": itemType,
            "quantity": 1,
            "unitPrice": unitPrice,
            "totalValue": unitPrice,
            "weight": weight,
        }

    def getHydraulicPump(self, itemModelType: str) -> dict[str, Any] | None:
        """Get hydraulic pump based on walking floor model."""
        pumpSize = HYDRAULIC_PUMP_MAP.get(itemModelType.upper(), "108cc")
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'hydraulic_pump' 
              AND ir.final_quantity > 0
              AND (i.name ILIKE %s OR i.code ILIKE %s)
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """,
            (f"%{pumpSize}%", f"%{pumpSize}%"),
        )

        if not result:
            logger.warning(f"No {pumpSize} pump found, trying any available")
            result = self.db.executeQuery(
                """
                SELECT DISTINCT ON (i.id)
                    i.id, i.code, i.name, i.unit,
                    CASE WHEN ir.final_quantity > 0 
                         THEN ir.final_value::numeric / ir.final_quantity 
                         ELSE 0 END as unit_price
                FROM items i
                JOIN inventory_records ir ON i.id = ir.item_id
                WHERE i.type = 'hydraulic_pump' AND ir.final_quantity > 0
                ORDER BY i.id, ir.record_date DESC
                LIMIT 1
                """
            )

        if not result:
            logger.warning("No hydraulic pump available")
            return None

        row = result[0]
        unitPrice = float(row[4])
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "hydraulic_pump",
            "quantity": 1,
            "unitPrice": unitPrice,
            "totalValue": unitPrice,
            "weight": HYDRAULIC_PUMP_WEIGHT_KG,
        }

    def getHydraulicOil(self) -> dict[str, Any] | None:
        """Get hydraulic oil (1 barrel ~200kg)."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'hydraulic_oil' AND ir.final_quantity >= 1
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """
        )

        if not result:
            logger.warning("No hydraulic oil available")
            return None

        row = result[0]
        unitPrice = float(row[4])
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "hydraulic_oil",
            "quantity": 1,
            "unitPrice": unitPrice,
            "totalValue": unitPrice,
            "weight": HYDRAULIC_OIL_WEIGHT_KG,
        }

    def getAluminumBars(
        self, containerLength: float, slatType: str, thickness: int
    ) -> dict[str, Any]:
        """Get aluminum bars based on container specs."""
        weight, density, bars = self.weightCalculator.calculateAluminumBarWeight(
            containerLength, slatType, thickness, self.db
        )
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'aluminum' AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """
        )

        if not result:
            raise ValueError("No aluminum inventory available")

        row = result[0]
        unitPrice = float(row[4])
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "aluminum",
            "quantity": round(weight, 2),
            "unitPrice": unitPrice,
            "totalValue": round(weight * unitPrice, 2),
            "weight": round(weight, 2),
        }

    def getAllFixedItems(
        self,
        itemModelType: str,
        containerLength: float,
        slatType: str,
        thickness: int,
    ) -> tuple[list[dict], float, float]:
        """
        Get all fixed items and calculate totals.
        
        Returns:
            (items, totalWeight, totalCost)
        """
        items = []
        totalWeight = 0.0
        totalCost = 0.0
        
        # Walking floor (required)
        walkingFloor = self.getWalkingFloor(itemModelType)
        items.append(walkingFloor)
        totalWeight += walkingFloor["weight"]
        totalCost += walkingFloor["totalValue"]
        
        # Aluminum bars (required)
        aluminum = self.getAluminumBars(containerLength, slatType, thickness)
        items.append(aluminum)
        totalWeight += aluminum["weight"]
        totalCost += aluminum["totalValue"]
        
        # Hydraulic pump (optional but usually available)
        pump = self.getHydraulicPump(itemModelType)
        if pump:
            items.append(pump)
            totalWeight += pump["weight"]
            totalCost += pump["totalValue"]
        
        # Hydraulic oil (optional but usually available)
        oil = self.getHydraulicOil()
        if oil:
            items.append(oil)
            totalWeight += oil["weight"]
            totalCost += oil["totalValue"]
        
        logger.info(
            f"Fixed items: {len(items)} items, "
            f"weight={totalWeight:.0f}kg, cost={totalCost:,.0f}"
        )
        
        return items, totalWeight, totalCost

