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
        
        # Pick the CHEAPEST available walking floor, not just first by id
        result = self.db.executeQuery(
            """
            SELECT i.id, i.code, i.name, i.unit,
                   ir.final_value::numeric / ir.final_quantity as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = %s AND ir.final_quantity > 0
            ORDER BY ir.final_value::numeric / ir.final_quantity ASC
            LIMIT 1
            """,
            (itemType,),
        )

        if not result:
            raise ValueError(f"No walking floor available for type: {itemType}")

        row = result[0]
        unitPrice = float(row[4])
        
        logger.info(f"   📦 Walking floor: id={row[0]}, price={unitPrice:,.0f}, weight={weight}kg")
        
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
            # Try gear_pump as fallback (same thing as hydraulic_pump)
            logger.warning("No hydraulic_pump found, trying gear_pump")
            result = self.db.executeQuery(
                """
                SELECT DISTINCT ON (i.id)
                    i.id, i.code, i.name, i.unit,
                    CASE WHEN ir.final_quantity > 0 
                         THEN ir.final_value::numeric / ir.final_quantity 
                         ELSE 0 END as unit_price
                FROM items i
                JOIN inventory_records ir ON i.id = ir.item_id
                WHERE i.type = 'gear_pump' AND ir.final_quantity > 0
                ORDER BY i.id, ir.record_date DESC
                LIMIT 1
                """
            )

        if not result:
            logger.warning("No pump available (checked both hydraulic_pump and gear_pump)")
            return None

        row = result[0]
        unitPrice = float(row[4])
        
        logger.info(f"   📦 Pump: id={row[0]}, price={unitPrice:,.0f}, weight={HYDRAULIC_PUMP_WEIGHT_KG}kg")
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "pump",  # Generic type since it could be hydraulic_pump or gear_pump
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
        
        logger.info(f"   📦 Oil: id={row[0]}, price={unitPrice:,.0f}, weight={HYDRAULIC_OIL_WEIGHT_KG}kg")
        
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
        totalValue = round(weight * unitPrice, 2)
        
        logger.info(f"   📦 Aluminum: id={row[0]}, qty={weight:.1f}kg x {unitPrice:,.0f} = {totalValue:,.0f}")
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "aluminum",
            "quantity": round(weight, 2),
            "unitPrice": unitPrice,
            "totalValue": totalValue,
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

