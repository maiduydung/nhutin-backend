"""
Variable Items Filler.
Fills with variable items to meet BOTH weight AND margin targets.

Algorithm:
1. First, ensure we reach minWeight (HARD constraint)
2. Then, keep adding until budget is spent to hit margin target
3. Weight may exceed maxWeight if needed to hit margin (SOFT constraint)
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger, CONTAINER_TYPES_WITH_CONTAINER


class VariableFiller:
    """Fills variable items to meet weight and margin targets."""

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

    def fillToTargets(
        self,
        variableItems: list[dict],
        targetCost: float,
        currentCost: float,
        minWeight: int,
        maxWeight: int,
        currentWeight: float,
        excludeIds: set[int] = None,
        skipContainerBuildTypes: bool = False,
    ) -> list[dict]:
        """
        Fill with variable items to meet BOTH weight AND margin targets.
        
        Priority:
        1. WEIGHT is the hard constraint (must reach minWeight)
        2. MARGIN is the goal (spend budget to hit target)
        3. maxWeight is soft - can exceed if needed for margin
        """
        excludeIds = excludeIds or set()
        weightNeeded = max(0, minWeight - currentWeight)
        budgetAvailable = max(0, targetCost - currentCost)
        
        logger.info(
            f"Fill targets: weightNeeded={weightNeeded:.0f}kg, "
            f"budget={budgetAvailable:,.0f}, currentWeight={currentWeight:.0f}kg"
        )
        
        # Filter candidates
        candidates = self._filterCandidates(
            variableItems, excludeIds, skipContainerBuildTypes
        )
        
        selected = []
        selectedMap = {}
        usedQty = {}
        totalWeight = 0
        totalCost = 0
        
        # Sort by weight-to-cost ratio (most efficient first)
        sortedByRatio = sorted(
            candidates, 
            key=lambda x: x["weightPerUnit"] / x["unitPrice"] if x["unitPrice"] > 0 else 0,
            reverse=True
        )
        
        # PHASE 1: Fill to minimum weight (HARD CONSTRAINT)
        if weightNeeded > 0:
            totalWeight, totalCost = self._fillToMinWeight(
                sortedByRatio, selected, selectedMap, usedQty,
                weightNeeded, budgetAvailable
            )
            logger.info(f"Phase 1 (weight): added {totalWeight:.0f}kg, cost={totalCost:,.0f}")
        
        # PHASE 2: Fill remaining budget to hit margin target
        budgetRemaining = budgetAvailable - totalCost
        
        if budgetRemaining > 100000:  # At least 100k VND left
            addedWeight, addedCost = self._fillRemainingBudget(
                sortedByRatio, selected, selectedMap, usedQty,
                budgetRemaining, currentWeight + totalWeight, maxWeight
            )
            totalWeight += addedWeight
            totalCost += addedCost
            logger.info(
                f"Phase 2 (margin): added {addedWeight:.0f}kg more, cost={addedCost:,.0f}"
            )
        
        logger.info(
            f"Variable fill complete: {len(selected)} items, "
            f"weight={totalWeight:.0f}kg, cost={totalCost:,.0f}"
        )
        
        return selected

    def _filterCandidates(
        self, items: list[dict], excludeIds: set[int], skipBuildTypes: bool
    ) -> list[dict]:
        """Filter items to valid candidates."""
        candidates = []
        for item in items:
            if item["id"] in excludeIds:
                continue
            if skipBuildTypes and item["type"] in self.CONTAINER_BUILD_TYPES:
                continue
            if item["unitPrice"] <= 0 or item["availableQty"] <= 0:
                continue
            if item["weightPerUnit"] <= 0:
                continue
            candidates.append(item)
        return candidates

    def _fillToMinWeight(
        self,
        sortedItems: list[dict],
        selected: list,
        selectedMap: dict,
        usedQty: dict,
        weightNeeded: float,
        budgetAvailable: float,
    ) -> tuple[float, float]:
        """
        Phase 1: Add items until minWeight is reached.
        Ignores budget constraint - weight is priority.
        """
        totalWeight = 0
        totalCost = 0
        
        for item in sortedItems:
            if totalWeight >= weightNeeded:
                break
            
            weightStillNeeded = weightNeeded - totalWeight
            qtyNeededForWeight = max(1, int(weightStillNeeded / item["weightPerUnit"]) + 1)
            maxQty = min(item["availableQty"], qtyNeededForWeight)
            
            if maxQty <= 0:
                continue
            
            weight = item["weightPerUnit"] * maxQty
            cost = item["unitPrice"] * maxQty
            
            self._addToSelected(selected, selectedMap, usedQty, item, maxQty, weight, cost)
            totalWeight += weight
            totalCost += cost
        
        return totalWeight, totalCost

    def _fillRemainingBudget(
        self,
        sortedItems: list[dict],
        selected: list,
        selectedMap: dict,
        usedQty: dict,
        budgetRemaining: float,
        currentWeight: float,
        maxWeight: int,
    ) -> tuple[float, float]:
        """
        Phase 2: Spend remaining budget to hit margin target.
        maxWeight + 50% tolerance is the hard cap (physical limit).
        """
        totalWeight = 0
        totalCost = 0
        
        # Allow 50% overage max (physical container limit)
        hardWeightCap = int(maxWeight * 1.5)
        
        for item in sortedItems:
            if budgetRemaining <= 100000:
                break
            if currentWeight + totalWeight >= hardWeightCap:
                break
            
            alreadyUsed = usedQty.get(item["id"], 0)
            remaining = item["availableQty"] - alreadyUsed
            
            if remaining <= 0:
                continue
            
            # How much can we add?
            maxByBudget = int(budgetRemaining / item["unitPrice"])
            weightRoom = max(0, hardWeightCap - (currentWeight + totalWeight))
            maxByWeight = max(1, int(weightRoom / item["weightPerUnit"])) if item["weightPerUnit"] > 0 else remaining
            
            addQty = min(remaining, maxByBudget, maxByWeight)
            
            if addQty <= 0:
                continue
            
            weight = item["weightPerUnit"] * addQty
            cost = item["unitPrice"] * addQty
            
            self._addToSelected(selected, selectedMap, usedQty, item, addQty, weight, cost)
            totalWeight += weight
            totalCost += cost
            budgetRemaining -= cost
        
        return totalWeight, totalCost

    def _addToSelected(
        self,
        selected: list,
        selectedMap: dict,
        usedQty: dict,
        item: dict,
        qty: int,
        weight: float,
        cost: float,
    ):
        """Add or update item in selected list."""
        if item["id"] in selectedMap:
            existing = selectedMap[item["id"]]
            existing["quantity"] += qty
            existing["totalValue"] = round(existing["totalValue"] + cost, 2)
            existing["weight"] = round(existing["weight"] + weight, 2)
        else:
            selectedItem = {
                "id": item["id"],
                "code": item["code"],
                "name": item["name"],
                "unit": item["unit"],
                "type": item["type"],
                "quantity": qty,
                "unitPrice": item["unitPrice"],
                "totalValue": round(cost, 2),
                "weight": round(weight, 2),
            }
            selected.append(selectedItem)
            selectedMap[item["id"]] = selectedItem
        
        usedQty[item["id"]] = usedQty.get(item["id"], 0) + qty

    # Backwards compatibility
    def fillToTarget(self, *args, **kwargs):
        return self.fillToTargets(
            variableItems=kwargs.get("variableItems", args[0] if args else []),
            targetCost=kwargs.get("targetCost", args[1] if len(args) > 1 else 0),
            currentCost=kwargs.get("currentCost", args[2] if len(args) > 2 else 0),
            minWeight=kwargs.get("targetWeight", args[3] if len(args) > 3 else 0),
            maxWeight=kwargs.get("maxWeight", args[4] if len(args) > 4 else 999999),
            currentWeight=kwargs.get("currentWeight", args[5] if len(args) > 5 else 0),
            excludeIds=kwargs.get("excludeIds"),
            skipContainerBuildTypes=kwargs.get("skipContainerBuildTypes", False),
        )
