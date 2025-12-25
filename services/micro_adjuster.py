"""
Phase 4: Micro-Adjuster.
Swaps cheap/heavy items for expensive/light items to fine-tune margin.

Used when we're at weight limit but need to increase cost to hit margin target.
"""
from typing import Any
from config import logger


class MicroAdjuster:
    """
    Fine-tunes the BOM by swapping items.
    
    Strategy:
    - Identify cheap/heavy items (low VND per kg)
    - Swap for expensive/light items (high VND per kg)
    - Maintain weight within limits while increasing cost
    """
    
    MAX_ITERATIONS = 50  # Allow more iterations for large cost gaps
    
    def adjustForMargin(
        self,
        currentItems: list[dict[str, Any]],
        availableItems: list[dict[str, Any]],
        targetCost: float,
        currentCost: float,
        maxWeight: int,
        currentWeight: float,
        usedQty: dict[int, int],
    ) -> tuple[list[dict[str, Any]], float, float]:
        """
        Phase 4: Swap items to increase cost while staying within weight limit.
        
        Returns:
            (adjustedItems, newWeight, newCost)
        """
        costGap = targetCost - currentCost
        
        if costGap <= 0:
            logger.info("Micro-adjuster: No adjustment needed, at target cost")
            return currentItems, currentWeight, currentCost
        
        logger.info(f"Micro-adjuster: Need +{costGap:,.0f} VND to reach target {targetCost:,.0f}")
        
        # Build maps for easy lookup
        itemsById = {item["id"]: item for item in currentItems}
        availableById = {item["id"]: item for item in availableItems}
        
        # Find swappable items (those that can be reduced)
        # Prioritize cheap/heavy items (low cost per kg)
        swappable = []
        for item in currentItems:
            if item.get("weight", 0) <= 0 or item.get("totalValue", 0) <= 0:
                continue
            
            # Skip fixed items (walking floor, pump, oil) - don't swap these
            if item.get("type") in ["walking_floor_r2dx", "walking_floor_ksd", "walking_floor_kmd", 
                                    "hydraulic_pump", "hydraulic_oil"]:
                continue
            
            costPerKg = item["totalValue"] / item["weight"]
            swappable.append({
                "item": item,
                "costPerKg": costPerKg,
            })
        
        # Sort by cost per kg (cheapest first - these are best to swap out)
        swappable.sort(key=lambda x: x["costPerKg"])
        
        # Find expensive items we can swap in
        expensive = []
        for item in availableItems:
            if item.get("weightPerUnit", 0) <= 0:
                continue
            
            alreadyUsed = usedQty.get(item["id"], 0)
            remaining = item["availableQty"] - alreadyUsed
            
            if remaining <= 0:
                continue
            
            costPerKg = item["unitPrice"] / item["weightPerUnit"]
            expensive.append({
                "item": item,
                "costPerKg": costPerKg,
                "remaining": remaining,
            })
        
        # Sort by cost per kg (most expensive first - best to swap in)
        expensive.sort(key=lambda x: x["costPerKg"], reverse=True)
        
        if not swappable or not expensive:
            logger.info("Micro-adjuster: No swappable items found")
            return currentItems, currentWeight, currentCost
        
        # Track changes
        adjustedItems = list(currentItems)
        newWeight = currentWeight
        newCost = currentCost
        newUsedQty = dict(usedQty)
        iterations = 0
        
        while costGap > 1_000_000 and iterations < self.MAX_ITERATIONS:
            iterations += 1
            madeSwap = False
            
            # Try to find a profitable swap
            for cheapItem in swappable:
                if madeSwap:
                    break
                
                currentItem = cheapItem["item"]
                
                # Can we reduce this item?
                currentQty = currentItem.get("quantity", 0)
                if currentQty <= 1:
                    continue
                
                # How much can we remove? (Keep at least 1)
                maxRemove = currentQty - 1
                
                for expensiveItem in expensive:
                    if madeSwap:
                        break
                    
                    availItem = expensiveItem["item"]
                    
                    # Skip if same item
                    if availItem["id"] == currentItem["id"]:
                        continue
                    
                    # Skip if expensive item isn't actually more expensive per kg
                    if expensiveItem["costPerKg"] <= cheapItem["costPerKg"] * 1.2:
                        continue
                    
                    # Calculate swap: remove X kg of cheap, add X kg of expensive
                    swapWeight = min(100, maxRemove * currentItem.get("weight", 0) / currentQty)  # Swap up to 100kg at a time
                    
                    if swapWeight <= 0:
                        continue
                    
                    # How many units of cheap to remove?
                    cheapPerUnit = currentItem.get("weight", 0) / currentQty if currentQty > 0 else 1
                    removeQty = int(swapWeight / cheapPerUnit)
                    
                    if removeQty <= 0:
                        continue
                    
                    # How many units of expensive to add?
                    addQty = int(swapWeight / availItem["weightPerUnit"])
                    addQty = min(addQty, expensiveItem["remaining"])
                    
                    if addQty <= 0:
                        continue
                    
                    # Calculate net change
                    removeCost = removeQty * currentItem.get("unitPrice", 0)
                    removeWeight = removeQty * cheapPerUnit
                    
                    addCost = addQty * availItem["unitPrice"]
                    addWeight = addQty * availItem["weightPerUnit"]
                    
                    netCost = addCost - removeCost
                    netWeight = addWeight - removeWeight
                    
                    # Check if swap improves cost without exceeding weight
                    if netCost > 0 and (newWeight + netWeight) <= maxWeight:
                        # Execute swap
                        # Update the current item
                        for i, item in enumerate(adjustedItems):
                            if item["id"] == currentItem["id"]:
                                newQty = item["quantity"] - removeQty
                                if newQty <= 0:
                                    adjustedItems.pop(i)
                                else:
                                    item["quantity"] = newQty
                                    item["weight"] = round(newQty * cheapPerUnit, 2)
                                    item["totalValue"] = round(newQty * item["unitPrice"], 2)
                                break
                        
                        # Add or update the expensive item
                        existingIdx = None
                        for i, item in enumerate(adjustedItems):
                            if item["id"] == availItem["id"]:
                                existingIdx = i
                                break
                        
                        if existingIdx is not None:
                            adjustedItems[existingIdx]["quantity"] += addQty
                            adjustedItems[existingIdx]["weight"] = round(
                                adjustedItems[existingIdx]["weight"] + addWeight, 2
                            )
                            adjustedItems[existingIdx]["totalValue"] = round(
                                adjustedItems[existingIdx]["totalValue"] + addCost, 2
                            )
                        else:
                            adjustedItems.append({
                                "id": availItem["id"],
                                "code": availItem["code"],
                                "name": availItem["name"],
                                "unit": availItem["unit"],
                                "type": availItem["type"],
                                "quantity": addQty,
                                "unitPrice": availItem["unitPrice"],
                                "totalValue": round(addCost, 2),
                                "weight": round(addWeight, 2),
                            })
                        
                        # Update tracking
                        newWeight += netWeight
                        newCost += netCost
                        costGap -= netCost
                        newUsedQty[availItem["id"]] = newUsedQty.get(availItem["id"], 0) + addQty
                        expensiveItem["remaining"] -= addQty
                        
                        logger.info(
                            f"Micro-adjuster: Swapped {removeQty} {currentItem['code'][:20]} "
                            f"for {addQty} {availItem['code'][:20]}: +{netCost:,.0f} VND"
                        )
                        madeSwap = True
            
            if not madeSwap:
                break
        
        totalAdjustment = newCost - currentCost
        logger.info(
            f"Micro-adjuster: {iterations} iterations, "
            f"+{totalAdjustment:,.0f} VND, final cost={newCost:,.0f}"
        )
        
        return adjustedItems, newWeight, newCost

