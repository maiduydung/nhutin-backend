"""
Variable Items Filler.
Fills remaining budget with variable items to hit target profit margin.
Weight is maximized as a secondary goal; margin target is the priority.
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger, CONTAINER_TYPES_WITH_CONTAINER


class VariableFiller:
    """Fills variable items to hit profit margin target."""

    VARIABLE_TYPES = [
        "steel_box", "steel_i", "steel_square", "steel_u", "steel_pipe", "steel_plate",
        "galvanized_sheet", "stainless_steel", "aluminum",
    ]
    
    CONTAINER_BUILD_TYPES = {"steel_box", "galvanized_sheet"}

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()

    def getVariableItems(self, containerType: str) -> list[dict]:
        """Fetch available variable items from inventory."""
        types = self.VARIABLE_TYPES.copy()
        
        if containerType in CONTAINER_TYPES_WITH_CONTAINER:
            types.append("container")
        
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
            weightPerUnit = self.weightCalculator.calculateItemWeight(
                row[4], row[3], 1, row[2]
            )
            items.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "availableQty": int(row[5]),
                "unitPrice": float(row[6]),
                "weightPerUnit": weightPerUnit,
            })
        
        return items

    def fillToTarget(
        self,
        variableItems: list[dict],
        targetCost: float,
        currentCost: float,
        targetWeight: int,
        currentWeight: float,
        maxWeight: int,
        excludeIds: set[int] = None,
        skipContainerBuildTypes: bool = False,
    ) -> list[dict]:
        """
        Fill with variable items to hit target cost (margin priority).
        
        Strategy:
        1. PRIORITY: Spend budget to hit target cost (margin target)
        2. SECONDARY: Maximize weight, but don't let weight limits block spending
        
        Two-pass approach:
        - Pass 1: Add items with best weight-to-cost ratio (respect weight limit here)
        - Pass 2: If budget remains, add MORE items even if exceeding weight limit
        """
        excludeIds = excludeIds or set()
        budgetRemaining = targetCost - currentCost
        weightRemaining = maxWeight - currentWeight
        
        if budgetRemaining <= 0:
            logger.warning(f"No budget remaining: target={targetCost:,.0f}, current={currentCost:,.0f}")
            return []
        
        # Filter candidates
        candidates = []
        for item in variableItems:
            if item["id"] in excludeIds:
                continue
            if skipContainerBuildTypes and item["type"] in self.CONTAINER_BUILD_TYPES:
                continue
            if item["unitPrice"] <= 0 or item["availableQty"] <= 0:
                continue
            
            ratio = item["weightPerUnit"] / item["unitPrice"] if item["unitPrice"] > 0 else 0
            candidates.append((ratio, item))
        
        selected = []
        selectedMap = {}  # id -> selected item
        usedQty = {}  # id -> quantity already used
        
        # PASS 1: Fill with weight-to-cost ratio, respecting weight limit
        sortedByRatio = sorted(candidates, key=lambda x: x[0], reverse=True)
        
        for ratio, item in sortedByRatio:
            if budgetRemaining <= 0 or weightRemaining <= 0:
                break
            
            maxByBudget = int(budgetRemaining / item["unitPrice"])
            maxByWeight = int(weightRemaining / item["weightPerUnit"]) if item["weightPerUnit"] > 0 else item["availableQty"]
            maxQty = min(item["availableQty"], maxByBudget, maxByWeight)
            
            if maxQty <= 0:
                continue
            
            weight = item["weightPerUnit"] * maxQty
            cost = item["unitPrice"] * maxQty
            
            selectedItem = {
                "id": item["id"],
                "code": item["code"],
                "name": item["name"],
                "unit": item["unit"],
                "type": item["type"],
                "quantity": maxQty,
                "unitPrice": item["unitPrice"],
                "totalValue": round(cost, 2),
                "weight": round(weight, 2),
            }
            
            selected.append(selectedItem)
            selectedMap[item["id"]] = selectedItem
            usedQty[item["id"]] = maxQty
            budgetRemaining -= cost
            weightRemaining -= weight
        
        # PASS 2: If budget remains, add more items IGNORING weight limit
        # Sort by cost (most expensive first to fill budget faster)
        if budgetRemaining > 10000:  # More than 10K VND remaining
            logger.info(f"Pass 2: {budgetRemaining:,.0f} budget remaining, filling without weight limit")
            sortedByCost = sorted(candidates, key=lambda x: x[1]["unitPrice"], reverse=True)
            
            for ratio, item in sortedByCost:
                if budgetRemaining <= 10000:
                    break
                
                alreadyUsed = usedQty.get(item["id"], 0)
                remaining = item["availableQty"] - alreadyUsed
                
                if remaining <= 0:
                    continue
                
                maxByBudget = int(budgetRemaining / item["unitPrice"])
                addQty = min(remaining, maxByBudget)
                
                if addQty <= 0:
                    continue
                
                addWeight = item["weightPerUnit"] * addQty
                addCost = item["unitPrice"] * addQty
                
                if item["id"] in selectedMap:
                    # Update existing item
                    existing = selectedMap[item["id"]]
                    existing["quantity"] += addQty
                    existing["totalValue"] = round(existing["totalValue"] + addCost, 2)
                    existing["weight"] = round(existing["weight"] + addWeight, 2)
                else:
                    # Add new item
                    selectedItem = {
                        "id": item["id"],
                        "code": item["code"],
                        "name": item["name"],
                        "unit": item["unit"],
                        "type": item["type"],
                        "quantity": addQty,
                        "unitPrice": item["unitPrice"],
                        "totalValue": round(addCost, 2),
                        "weight": round(addWeight, 2),
                    }
                    selected.append(selectedItem)
                    selectedMap[item["id"]] = selectedItem
                
                usedQty[item["id"]] = usedQty.get(item["id"], 0) + addQty
                budgetRemaining -= addCost
        
        totalSelectedWeight = sum(i["weight"] for i in selected)
        totalSelectedCost = sum(i["totalValue"] for i in selected)
        
        logger.info(
            f"Variable fill: {len(selected)} items, "
            f"weight={totalSelectedWeight:.0f}kg, cost={totalSelectedCost:,.0f}, "
            f"budget remaining={budgetRemaining:,.0f}"
        )
        
        return selected
