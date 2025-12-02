from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger


class Optimizer:
    """Optimizes item selection for container weight and profit constraints."""

    MIN_WEIGHT = 3000  # kg
    MAX_WEIGHT = 3700  # kg (soft limit)
    MAX_PROFIT_MARGIN = 0.25  # 25%

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()

    def optimize(
        self,
        containerLength: float,
        itemModelType: str,
        slatType: str,
        receiptPrice: float,
        containerType: str = None,
    ) -> dict[str, Any]:
        """
        Main optimization function.
        Returns optimized item list with weights and costs.
        """
        # Get fixed items
        walkingFloorWeight, walkingFloorType = (
            self.weightCalculator.calculateWalkingFloorWeight(itemModelType)
        )
        walkingFloorItem = self._getWalkingFloorItem(walkingFloorType, itemModelType, walkingFloorWeight)
        
        aluminumWeight, hasEnoughAlum = (
            self.weightCalculator.calculateAluminumBarWeight(
                containerLength, slatType, self.db
            )
        )
        aluminumItem = self._getAluminumItem(aluminumWeight)

        # Calculate fixed weight and cost
        fixedWeight = walkingFloorWeight + aluminumWeight
        fixedCost = (
            walkingFloorItem["unitPrice"] * walkingFloorItem["quantity"]
            + aluminumItem["unitPrice"] * aluminumItem["quantity"]
        )

        # Get variable items for optimization (with container validation)
        variableItems = self._getVariableItems(containerType)

        # Optimize variable items
        selectedItems = self._optimizeVariableItems(
            variableItems, fixedWeight, fixedCost, receiptPrice
        )

        # Combine fixed and variable items
        allItems = [walkingFloorItem, aluminumItem] + selectedItems

        # Calculate totals
        totalWeight = sum(item["weight"] for item in allItems)
        totalCost = sum(item["totalValue"] for item in allItems)
        
        # If weight is below MIN_WEIGHT, try to add more aluminum
        # Adding aluminum increases cost and DECREASES profit margin (which is good!)
        if totalWeight < self.MIN_WEIGHT:
            additionalAluminum = self._boostAluminumForWeight(
                aluminumItem, totalWeight, totalCost, receiptPrice
            )
            if additionalAluminum:
                # Update aluminum item with additional quantity
                aluminumItem["quantity"] += additionalAluminum["additionalQty"]
                aluminumItem["weight"] += additionalAluminum["additionalWeight"]
                aluminumItem["totalValue"] += additionalAluminum["additionalCost"]
                
                # Recalculate totals
                totalWeight += additionalAluminum["additionalWeight"]
                totalCost += additionalAluminum["additionalCost"]
                
                logger.info(
                    f"Boosted aluminum by {additionalAluminum['additionalQty']:.2f} kg "
                    f"to reach weight {totalWeight:.2f} kg"
                )

        profit = receiptPrice - totalCost
        profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0

        return {
            "items": allItems,
            "totalWeight": round(totalWeight, 2),
            "totalCost": round(totalCost, 2),
            "receiptPrice": receiptPrice,
            "profit": round(profit, 2),
            "profitMargin": round(profitMargin, 2),
        }
    
    def _boostAluminumForWeight(
        self,
        aluminumItem: dict[str, Any],
        currentWeight: float,
        currentCost: float,
        receiptPrice: float,
    ) -> dict[str, Any] | None:
        """
        Add more aluminum bars when weight is below MIN_WEIGHT.
        
        Note: Adding aluminum INCREASES cost which DECREASES profit margin.
        So this boost helps achieve both weight and profit margin targets.
        
        Returns additional aluminum info or None if not possible.
        """
        weightNeeded = self.MIN_WEIGHT - currentWeight
        if weightNeeded <= 0:
            return None
        
        # Get aluminum inventory availability
        result = self.db.executeQuery(
            """
            SELECT ir.final_quantity
            FROM inventory_records ir
            JOIN items i ON ir.item_id = i.id
            WHERE i.type = 'aluminum'
            ORDER BY ir.record_date DESC
            LIMIT 1
            """
        )
        
        if not result:
            logger.warning("No aluminum inventory available for weight boost")
            return None
        
        availableQty = float(result[0][0])
        alreadyUsed = aluminumItem["quantity"]
        remainingAvailable = availableQty - alreadyUsed
        
        if remainingAvailable <= 0:
            logger.warning("No additional aluminum available for weight boost")
            return None
        
        unitPrice = aluminumItem["unitPrice"]
        
        # For weight boost, we want to add weight but still maintain a minimum profit margin
        # Target: at least 10% profit margin (MIN_BOOST_PROFIT_MARGIN)
        # This ensures we don't accidentally spend the entire receipt price
        MIN_BOOST_PROFIT_MARGIN = 0.10  # 10% minimum profit after boost
        maxCostAfterBoost = receiptPrice * (1 - MIN_BOOST_PROFIT_MARGIN)
        budgetForBoost = maxCostAfterBoost - currentCost
        
        if budgetForBoost <= 0:
            logger.warning(f"Cannot boost aluminum: already at {((receiptPrice - currentCost) / receiptPrice * 100):.1f}% margin")
            return None
        
        maxByWeight = weightNeeded  # Aluminum weight = quantity in kg
        maxByInventory = remainingAvailable
        maxByCost = budgetForBoost / unitPrice if unitPrice > 0 else remainingAvailable
        
        additionalQty = min(maxByWeight, maxByInventory, maxByCost)
        
        if additionalQty <= 0:
            return None
        
        additionalWeight = additionalQty  # For aluminum, weight = quantity in kg
        additionalCost = additionalQty * unitPrice
        
        # Calculate new profit margin after boost
        newTotalCost = currentCost + additionalCost
        newProfit = receiptPrice - newTotalCost
        newProfitMargin = (newProfit / receiptPrice) * 100 if receiptPrice > 0 else 0
        
        logger.info(
            f"Weight boost: Adding {additionalQty:.2f} kg aluminum "
            f"(needed: {weightNeeded:.2f} kg, available: {remainingAvailable:.2f} kg, "
            f"new margin: {newProfitMargin:.2f}%)"
        )
        
        return {
            "additionalQty": round(additionalQty, 2),
            "additionalWeight": round(additionalWeight, 2),
            "additionalCost": round(additionalCost, 2),
        }

    def _getWalkingFloorItem(
        self, itemType: str, itemModelType: str, weight: float
    ) -> dict[str, Any]:
        """Get one walking floor set from inventory."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                ir.final_quantity, ir.final_value,
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
        quantity = 1  # Always 1 set

        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "quantity": quantity,
            "unitPrice": float(row[6]),
            "totalValue": float(row[6]) * quantity,
            "weight": weight,
        }

    def _getAluminumItem(self, aluminumWeight: float) -> dict[str, Any]:
        """Get aluminum item from inventory (for cost calculation)."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                ir.final_quantity, ir.final_value,
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
        unitPrice = float(row[6])
        # Quantity in kg equals the calculated weight
        quantity = aluminumWeight
        totalValue = unitPrice * quantity
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "quantity": round(quantity, 2),
            "unitPrice": unitPrice,
            "totalValue": round(totalValue, 2),
            "weight": round(aluminumWeight, 2),
        }

    def _getVariableItems(self, containerType: str = None) -> list[dict[str, Any]]:
        """Get all variable items available for optimization.
        
        Includes all item types except walking floors and aluminum (which are fixed items).
        This allows the optimizer to use whatever inventory is available.
        
        Args:
            containerType: Optional container type (e.g., "container_40ft", "container_20ft")
                          Used to validate and filter container items.
        """
        # Include all item types that can be used as variable items
        # Excludes: walking_floor_*, aluminum (these are fixed items)
        variableTypes = [
            'steel_box', 'steel_i', 'steel_square', 'steel_u', 'steel_pipe', 'steel_plate',
            'galvanized_sheet', 'stainless_steel', 'hydraulic_pump', 'container'
        ]
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type,
                ir.final_quantity, ir.final_value,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = ANY(%s)
              AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """,
            (variableTypes,)
        )

        items = []
        containerItems = []
        requestedContainerSize = None
        
        # Parse requested container size from containerType (e.g., "container_40ft" -> "40")
        if containerType:
            if "40" in containerType:
                requestedContainerSize = "40"
            elif "20" in containerType:
                requestedContainerSize = "20"
        
        for row in result:
            item = {
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "availableQuantity": int(row[5]),
                "unitPrice": float(row[7]),
            }
            
            # Handle container items separately for validation
            if item["type"] == "container":
                containerItems.append(item)
            else:
                items.append(item)
        
        # Container validation and fallback
        if containerItems:
            selectedContainer = self._selectContainerWithFallback(
                containerItems, requestedContainerSize
            )
            if selectedContainer:
                items.append(selectedContainer)
        
        return items
    
    def _selectContainerWithFallback(
        self,
        containerItems: list[dict[str, Any]],
        requestedSize: str = None
    ) -> dict[str, Any] | None:
        """
        Select container item with fallback logic.
        If requested container size is not available, use any available container.
        
        Args:
            containerItems: List of available container items
            requestedSize: Requested container size ("20" or "40")
        
        Returns:
            Selected container item or None if no containers available
        """
        if not containerItems:
            return None
        
        # Try to find the requested container size
        if requestedSize:
            for container in containerItems:
                containerName = container["name"].lower()
                if requestedSize in containerName:
                    logger.info(f"Found requested {requestedSize}ft container: {container['name']}")
                    return container
            
            # Requested container not found - log error and use fallback
            availableSizes = []
            for c in containerItems:
                if "40" in c["name"]:
                    availableSizes.append("40ft")
                elif "20" in c["name"]:
                    availableSizes.append("20ft")
            
            logger.error(
                f"Requested {requestedSize}ft container not found in database. "
                f"Available containers: {availableSizes}. Using fallback."
            )
        
        # Fallback: use the first available container
        fallbackContainer = containerItems[0]
        logger.warning(
            f"Using fallback container: {fallbackContainer['name']} "
            f"(requested: {requestedSize}ft)"
        )
        return fallbackContainer

    def _optimizeVariableItems(
        self,
        variableItems: list[dict[str, Any]],
        fixedWeight: float,
        fixedCost: float,
        receiptPrice: float,
    ) -> list[dict[str, Any]]:
        """
        Greedy optimization: aggressively fill weight range to MAX_WEIGHT.
        Maximizes variety by selecting from different types.
        Respects profit margin constraint.
        """
        # Target maximum weight (be greedy!)
        targetWeight = self.MAX_WEIGHT - fixedWeight
        remainingWeight = targetWeight
        selectedItems = []
        usedTypes = set()
        currentCost = fixedCost
        maxCost = receiptPrice * (1 - self.MAX_PROFIT_MARGIN)  # Max cost to stay within profit margin

        # Group items by type for variety
        itemsByType = {}
        for item in variableItems:
            itemType = item["type"]
            if itemType not in itemsByType:
                itemsByType[itemType] = []
            itemsByType[itemType].append(item)

        # Separate items into weight-contributing and zero-weight items
        zeroWeightItems = []
        weightItems = []
        
        for itemType, items in itemsByType.items():
            for item in items:
                weightPerUnit = self.weightCalculator.calculateItemWeight(
                    item["type"], item["unit"], 1, item["name"]
                )
                item["_weightPerUnit"] = weightPerUnit
                
                if weightPerUnit > 0:
                    weightItems.append(item)
                else:
                    zeroWeightItems.append(item)
        
        # Step 1: Select weight-contributing items first (by type for variety)
        itemsByTypeWeighted = {}
        for item in weightItems:
            if item["type"] not in itemsByTypeWeighted:
                itemsByTypeWeighted[item["type"]] = []
            itemsByTypeWeighted[item["type"]].append(item)
        
        for itemType, items in itemsByTypeWeighted.items():
            if not items:
                continue
            
            # Find best item from this type (best weight-to-cost ratio)
            bestItem = None
            bestRatio = 0
            
            for item in items:
                if item["unitPrice"] <= 0:
                    continue
                ratio = item["_weightPerUnit"] / item["unitPrice"]  # kg per VND
                if ratio > bestRatio:
                    bestRatio = ratio
                    bestItem = item
            
            if not bestItem:
                continue
            
            item = bestItem
            weightPerUnit = item["_weightPerUnit"]

            # Calculate max quantity - be greedy! Take ALL available if budget allows
            currentTotalWeight = fixedWeight + sum(i["weight"] for i in selectedItems)
            weightSpaceLeft = self.MAX_WEIGHT - currentTotalWeight
            
            maxWeightQuantity = int(weightSpaceLeft / weightPerUnit) if weightPerUnit > 0 else item["availableQuantity"]
            maxBudgetQuantity = int((maxCost - currentCost) / item["unitPrice"]) if item["unitPrice"] > 0 else item["availableQuantity"]
            
            maxQuantity = min(item["availableQuantity"], maxWeightQuantity, maxBudgetQuantity)
            
            if maxQuantity > 0:
                quantity = maxQuantity
                weight = weightPerUnit * quantity
                totalValue = item["unitPrice"] * quantity
                
                if currentCost + totalValue > maxCost:
                    if item["unitPrice"] <= 0:
                        continue
                    maxBudgetQty = int((maxCost - currentCost) / item["unitPrice"])
                    if maxBudgetQty > 0:
                        quantity = min(maxBudgetQty, item["availableQuantity"], maxWeightQuantity)
                        weight = weightPerUnit * quantity
                        totalValue = item["unitPrice"] * quantity
                    else:
                        continue
                
                selectedItems.append({
                    "id": item["id"],
                    "code": item["code"],
                    "name": item["name"],
                    "unit": item["unit"],
                    "quantity": quantity,
                    "unitPrice": item["unitPrice"],
                    "totalValue": totalValue,
                    "weight": weight,
                })
                
                currentCost += totalValue
                usedTypes.add(itemType)
        
        # Step 2: Add zero-weight items (like containers) to fill budget
        # Prioritize containers first - they're essential for shipping!
        containerFirst = sorted(
            zeroWeightItems,
            key=lambda x: (0 if x["type"] == "container" else 1, -x["unitPrice"])
        )
        
        for item in containerFirst:
            if currentCost >= maxCost:
                # For containers, we allow slightly exceeding budget (up to 85% of receipt)
                # because a container is essential for shipping
                if item["type"] == "container":
                    extendedMaxCost = receiptPrice * 0.85
                    if currentCost >= extendedMaxCost:
                        logger.warning(f"Cannot add container - cost {currentCost:,.0f} exceeds extended budget {extendedMaxCost:,.0f}")
                        break
                    logger.info(f"Extending budget for container (essential item)")
                else:
                    break
            
            if item["unitPrice"] <= 0:
                continue
            
            effectiveMaxCost = receiptPrice * 0.85 if item["type"] == "container" else maxCost
            budgetRemaining = effectiveMaxCost - currentCost
            maxQty = min(item["availableQuantity"], int(budgetRemaining / item["unitPrice"]))
            
            # For containers, we want at least 1 if budget allows
            if item["type"] == "container" and maxQty <= 0 and item["availableQuantity"] > 0:
                if item["unitPrice"] <= budgetRemaining:
                    maxQty = 1
            
            if maxQty > 0:
                totalValue = item["unitPrice"] * maxQty
                selectedItems.append({
                    "id": item["id"],
                    "code": item["code"],
                    "name": item["name"],
                    "unit": item["unit"],
                    "quantity": maxQty,
                    "unitPrice": item["unitPrice"],
                    "totalValue": totalValue,
                    "weight": 0,  # Zero weight item
                })
                currentCost += totalValue
                usedTypes.add(item["type"])

        # Fill remaining weight - can add more to already selected items or select new ones
        # Create a map of selected items by ID for easy lookup
        selectedMap = {item["id"]: item for item in selectedItems}
        
        # Calculate weight-to-cost ratio for all items
        itemsWithRatio = []
        for item in variableItems:
            weightPerUnit = self.weightCalculator.calculateItemWeight(
                item["type"], item["unit"], 1, item["name"]
            )
            if weightPerUnit > 0 and item["unitPrice"] > 0:
                ratio = weightPerUnit / item["unitPrice"]
                itemsWithRatio.append((ratio, item))
        
        # Sort by ratio (descending)
        itemsWithRatio.sort(key=lambda x: x[0], reverse=True)

        # Keep filling until we reach MAX_WEIGHT or run out of budget
        # Recalculate current weight after first phase
        currentTotalWeight = fixedWeight + sum(item["weight"] for item in selectedItems)
        
        # Keep iterating until we can't add more
        maxIterations = 20  # Prevent infinite loops
        iteration = 0
        
        while iteration < maxIterations:
            iteration += 1
            addedSomething = False
            previousWeight = currentTotalWeight
            previousCost = currentCost
            
            for ratio, item in itemsWithRatio:
                # Stop if we've reached max weight or budget
                if currentTotalWeight >= self.MAX_WEIGHT or currentCost >= maxCost:
                    break
                
                # Check if we've already selected this item
                if item["id"] in selectedMap:
                    selectedItem = selectedMap[item["id"]]
                    # Calculate how much more we can add
                    alreadyTaken = selectedItem["quantity"]
                    remainingAvailable = item["availableQuantity"] - alreadyTaken
                else:
                    selectedItem = None
                    alreadyTaken = 0
                    remainingAvailable = item["availableQuantity"]
                
                if remainingAvailable <= 0:
                    continue

                weightPerUnit = self.weightCalculator.calculateItemWeight(
                    item["type"], item["unit"], 1, item["name"]
                )
                
                if weightPerUnit <= 0:
                    continue

                # Calculate how much weight we still need
                weightNeeded = self.MAX_WEIGHT - currentTotalWeight
                
                # Calculate max quantity - be greedy! Fill to MAX_WEIGHT
                maxWeightQuantity = int(weightNeeded / weightPerUnit) if weightPerUnit > 0 else remainingAvailable
                maxBudgetQuantity = int((maxCost - currentCost) / item["unitPrice"]) if item["unitPrice"] > 0 else remainingAvailable
                
                maxAdditionalQty = min(
                    remainingAvailable,
                    maxWeightQuantity,
                    maxBudgetQuantity
                )
                
                if maxAdditionalQty > 0:
                    additionalWeight = weightPerUnit * maxAdditionalQty
                    additionalCost = item["unitPrice"] * maxAdditionalQty
                    
                    # Final check - make sure we don't exceed budget
                    if currentCost + additionalCost > maxCost:
                        # Take as much as budget allows
                        if item["unitPrice"] <= 0:
                            continue
                        maxBudgetQty = int((maxCost - currentCost) / item["unitPrice"])
                        if maxBudgetQty <= 0:
                            continue
                        maxAdditionalQty = min(maxBudgetQty, remainingAvailable)
                        additionalWeight = weightPerUnit * maxAdditionalQty
                        additionalCost = item["unitPrice"] * maxAdditionalQty

                    if selectedItem:
                        # Add to existing item
                        selectedItem["quantity"] += maxAdditionalQty
                        selectedItem["weight"] += additionalWeight
                        selectedItem["totalValue"] += additionalCost
                    else:
                        # Create new item entry
                        newItem = {
                            "id": item["id"],
                            "code": item["code"],
                            "name": item["name"],
                            "unit": item["unit"],
                            "quantity": maxAdditionalQty,
                            "unitPrice": item["unitPrice"],
                            "totalValue": additionalCost,
                            "weight": additionalWeight,
                        }
                        selectedItems.append(newItem)
                        selectedMap[item["id"]] = newItem
                    
                    currentTotalWeight += additionalWeight
                    currentCost += additionalCost
                    addedSomething = True
            
            # If we didn't add anything this iteration, we're done
            if currentTotalWeight == previousWeight and currentCost == previousCost:
                break
        
        return selectedItems


def main():
    """Test optimizer."""
    from services.database import Database
    
    db = Database()
    optimizer = Optimizer(db)
    
    result = optimizer.optimize(
        containerLength=6.096,
        itemModelType="R2DX",
        slatType="97mm",
        receiptPrice=600_000_000,
    )
    
    print("Optimization result:")
    print(f"Total weight: {result['totalWeight']} kg")
    print(f"Total cost: {result['totalCost']:,.0f} VND")
    print(f"Profit margin: {result['profitMargin']:.2f}%")
    print(f"\nItems ({len(result['items'])}):")
    for item in result["items"]:
        print(
            f"  {item['code']}: {item['quantity']} {item['unit']} "
            f"| Weight: {item['weight']:.2f} kg | "
            f"Value: {item['totalValue']:,.0f} VND"
        )
    
    db.close()


if __name__ == "__main__":
    main()

