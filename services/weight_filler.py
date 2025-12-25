"""
Phase 2: Weight-First Filler.
Fills materials to reach minimum weight BEFORE worrying about margin.

Golden Rule: Never optimize margin before weight feasibility is locked.
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger


class WeightFiller:
    """
    Fills materials to reach weight target.
    
    Priority order (structural relevance, NOT ratio):
    1. Steel (structural frame)
    2. Galvanized sheets (walls/roof)
    3. Stainless steel (accessories)
    """
    
    # Priority order - structural items first, then aluminum for weight
    PRIORITY_ORDER = [
        "steel_box",
        "steel_u", 
        "steel_i",
        "steel_square",
        "steel_pipe",
        "steel_plate",
        "galvanized_sheet",
        "stainless_steel",
        "aluminum",  # Aluminum is heavy and useful for weight filling
    ]
    
    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()
    
    def getAvailableMaterials(
        self, 
        excludeIds: set[int] = None,
        excludeTypes: set[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch all available materials with weight > 0."""
        excludeIds = excludeIds or set()
        excludeTypes = excludeTypes or set()
        
        types = [t for t in self.PRIORITY_ORDER if t not in excludeTypes]
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type,
                ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = ANY(%s) AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """,
            (types,),
        )
        
        materials = []
        for row in result:
            if row[0] in excludeIds:
                continue
                
            weightPerUnit = self.weightCalculator.calculateItemWeight(
                row[4], row[3], 1, row[2]
            )
            
            # Skip zero-weight items in weight-filling phase
            if weightPerUnit <= 0:
                continue
            
            materials.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "availableQty": int(row[5]),
                "unitPrice": float(row[6]),
                "weightPerUnit": weightPerUnit,
                "priority": self.PRIORITY_ORDER.index(row[4]) if row[4] in self.PRIORITY_ORDER else 99,
            })
        
        return materials
    
    def fillToMinWeight(
        self,
        materials: list[dict[str, Any]],
        minWeight: int,
        maxWeight: int,
        currentWeight: float,
        maxCost: float,
        currentCost: float,
        usedQty: dict[int, int] = None,
    ) -> tuple[list[dict[str, Any]], float, float, dict[int, int]]:
        """
        Phase 2: Fill to minimum weight using structural priority.
        
        Strategy:
        - Sort by structural priority (steel first, then sheets)
        - Fill until we reach minWeight
        - Stop if we hit maxWeight or maxCost
        
        Returns:
            (selectedItems, totalWeight, totalCost, updatedUsedQty)
        """
        usedQty = dict(usedQty) if usedQty else {}
        selected = []
        totalWeight = currentWeight
        totalCost = currentCost
        
        weightNeeded = minWeight - totalWeight
        
        if weightNeeded <= 0:
            logger.info(f"Weight filler: Already at {totalWeight:.0f}kg (min: {minWeight})")
            return selected, totalWeight, totalCost, usedQty
        
        logger.info(f"Weight filler: Need {weightNeeded:.0f}kg to reach min {minWeight}kg")
        
        # Sort by priority (structural relevance)
        sortedMaterials = sorted(materials, key=lambda m: m["priority"])
        
        for mat in sortedMaterials:
            if totalWeight >= minWeight:
                break
            
            if totalCost >= maxCost:
                logger.warning("Hit max cost before reaching min weight")
                break
            
            # Calculate how much we can take
            alreadyUsed = usedQty.get(mat["id"], 0)
            remaining = mat["availableQty"] - alreadyUsed
            
            if remaining <= 0:
                continue
            
            weightStillNeeded = max(0, minWeight - totalWeight)
            budgetLeft = maxCost - totalCost
            
            # How many units to reach weight target?
            qtyForWeight = int(weightStillNeeded / mat["weightPerUnit"]) + 1
            qtyForBudget = int(budgetLeft / mat["unitPrice"]) if mat["unitPrice"] > 0 else remaining
            qtyForMaxWeight = int((maxWeight - totalWeight) / mat["weightPerUnit"])
            
            qty = min(remaining, qtyForWeight, qtyForBudget, qtyForMaxWeight)
            qty = max(0, qty)
            
            if qty <= 0:
                continue
            
            weight = mat["weightPerUnit"] * qty
            cost = mat["unitPrice"] * qty
            
            selected.append({
                "id": mat["id"],
                "code": mat["code"],
                "name": mat["name"],
                "unit": mat["unit"],
                "type": mat["type"],
                "quantity": qty,
                "unitPrice": mat["unitPrice"],
                "totalValue": round(cost, 2),
                "weight": round(weight, 2),
            })
            
            usedQty[mat["id"]] = alreadyUsed + qty
            totalWeight += weight
            totalCost += cost
        
        selectedWeight = sum(i["weight"] for i in selected)
        selectedCost = sum(i["totalValue"] for i in selected)
        
        logger.info(
            f"Weight filler: Added {len(selected)} items, "
            f"+{selectedWeight:.0f}kg, +{selectedCost:,.0f} VND. "
            f"Total now: {totalWeight:.0f}kg"
        )
        
        return selected, totalWeight, totalCost, usedQty

