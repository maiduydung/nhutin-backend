"""
Phase 3: Margin Tuner.
After weight is locked, tune cost to hit target profit margin.

Strategy: Add expensive/light items (high price, low kg/VND).
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger, CONTAINER_TYPES_WITH_CONTAINER


class MarginTuner:
    """
    Tunes profit margin by adding expensive items with minimal weight impact.
    
    Candidate items (high price, low weight):
    - Containers (weight=0, high cost)
    - Aluminum (expensive per kg)
    - Stainless steel (expensive per kg)
    """
    
    TUNING_TYPES = [
        "container",
        "aluminum", 
        "stainless_steel",
        "galvanized_sheet",
        "steel_box",
    ]
    
    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()
    
    def getTuningItems(
        self,
        containerType: str,
        excludeIds: set[int] = None,
    ) -> list[dict[str, Any]]:
        """Fetch items suitable for margin tuning (expensive, light)."""
        excludeIds = excludeIds or set()
        
        types = self.TUNING_TYPES.copy()
        
        # Only include container if type supports it
        if containerType not in CONTAINER_TYPES_WITH_CONTAINER:
            types = [t for t in types if t != "container"]
        
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
        
        items = []
        for row in result:
            if row[0] in excludeIds:
                continue
            
            weightPerUnit = self.weightCalculator.calculateItemWeight(
                row[4], row[3], 1, row[2]
            )
            unitPrice = float(row[6])
            
            if unitPrice <= 0:
                continue
            
            # Calculate cost-to-weight ratio (higher = better for margin tuning)
            # Want items that add COST with minimal WEIGHT
            costWeightRatio = unitPrice / max(weightPerUnit, 0.1)
            
            items.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "availableQty": int(row[5]),
                "unitPrice": unitPrice,
                "weightPerUnit": weightPerUnit,
                "costWeightRatio": costWeightRatio,
            })
        
        return items
    
    def tuneToTargetMargin(
        self,
        items: list[dict[str, Any]],
        targetCost: float,
        currentCost: float,
        maxWeight: int,
        currentWeight: float,
        usedQty: dict[int, int] = None,
    ) -> tuple[list[dict[str, Any]], float, float, dict[int, int]]:
        """
        Phase 3: Add items to reach target cost (and thus target margin).
        
        Strategy:
        - Sort by cost-to-weight ratio (highest first = most cost per kg)
        - Add items until we reach targetCost
        - Stop if we exceed maxWeight
        
        Returns:
            (selectedItems, totalWeight, totalCost, updatedUsedQty)
        """
        usedQty = dict(usedQty) if usedQty else {}
        selected = []
        totalWeight = currentWeight
        totalCost = currentCost
        
        costNeeded = targetCost - totalCost
        
        if costNeeded <= 0:
            logger.info(f"Margin tuner: Already at {totalCost:,.0f} (target: {targetCost:,.0f})")
            return selected, totalWeight, totalCost, usedQty
        
        logger.info(f"Margin tuner: Need {costNeeded:,.0f} more to reach target {targetCost:,.0f}")
        
        # Sort by cost-to-weight ratio (most expensive per kg first)
        sortedItems = sorted(items, key=lambda x: x["costWeightRatio"], reverse=True)
        
        for item in sortedItems:
            if totalCost >= targetCost:
                break
            
            if totalWeight >= maxWeight:
                logger.warning("Hit max weight before reaching target cost")
                break
            
            # Calculate how much we can take
            alreadyUsed = usedQty.get(item["id"], 0)
            remaining = item["availableQty"] - alreadyUsed
            
            if remaining <= 0:
                continue
            
            costStillNeeded = targetCost - totalCost
            weightLeft = maxWeight - totalWeight
            
            # How many units to reach cost target?
            qtyForCost = int(costStillNeeded / item["unitPrice"]) + 1
            qtyForWeight = int(weightLeft / item["weightPerUnit"]) if item["weightPerUnit"] > 0 else remaining
            
            qty = min(remaining, qtyForCost, qtyForWeight)
            qty = max(0, qty)
            
            if qty <= 0:
                continue
            
            weight = item["weightPerUnit"] * qty
            cost = item["unitPrice"] * qty
            
            # Don't overshoot maxWeight
            if totalWeight + weight > maxWeight:
                # Reduce quantity to fit
                qtyThatFits = int((maxWeight - totalWeight) / item["weightPerUnit"])
                if qtyThatFits <= 0:
                    continue
                qty = qtyThatFits
                weight = item["weightPerUnit"] * qty
                cost = item["unitPrice"] * qty
            
            selected.append({
                "id": item["id"],
                "code": item["code"],
                "name": item["name"],
                "unit": item["unit"],
                "type": item["type"],
                "quantity": qty,
                "unitPrice": item["unitPrice"],
                "totalValue": round(cost, 2),
                "weight": round(weight, 2),
            })
            
            usedQty[item["id"]] = alreadyUsed + qty
            totalWeight += weight
            totalCost += cost
        
        selectedWeight = sum(i["weight"] for i in selected)
        selectedCost = sum(i["totalValue"] for i in selected)
        
        logger.info(
            f"Margin tuner: Added {len(selected)} items, "
            f"+{selectedWeight:.0f}kg, +{selectedCost:,.0f} VND. "
            f"Total now: {totalCost:,.0f}"
        )
        
        return selected, totalWeight, totalCost, usedQty

