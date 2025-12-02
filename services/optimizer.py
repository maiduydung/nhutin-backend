from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger


class Optimizer:
    """Optimizes item selection for container weight and profit constraints."""

    MIN_WEIGHT = 3000  # kg
    MAX_WEIGHT = 3700  # kg (soft limit)
    MAX_PROFIT_MARGIN = 0.20  # 20%

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()

    def optimize(
        self,
        containerLength: float,
        itemModelType: str,
        slatType: str,
        receiptPrice: float,
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

        # Get variable items for optimization
        variableItems = self._getVariableItems()

        # Optimize variable items
        selectedItems = self._optimizeVariableItems(
            variableItems, fixedWeight, fixedCost, receiptPrice
        )

        # Combine fixed and variable items
        allItems = [walkingFloorItem, aluminumItem] + selectedItems

        # Calculate totals
        totalWeight = sum(item["weight"] for item in allItems)
        totalCost = sum(item["totalValue"] for item in allItems)
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

    def _getVariableItems(self) -> list[dict[str, Any]]:
        """Get all variable items available for optimization."""
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
            WHERE i.type IN ('steel_box', 'steel_i', 'steel_square', 'galvanized_sheet')
              AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """
        )

        items = []
        for row in result:
            items.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "availableQuantity": int(row[5]),
                "unitPrice": float(row[6]),
            })

        return items

    def _optimizeVariableItems(
        self,
        variableItems: list[dict[str, Any]],
        fixedWeight: float,
        fixedCost: float,
        receiptPrice: float,
    ) -> list[dict[str, Any]]:
        """
        Simple greedy optimization: select items to fill weight range.
        Maximizes variety by selecting from different types.
        Respects profit margin constraint.
        """
        targetWeight = (self.MIN_WEIGHT + self.MAX_WEIGHT) / 2 - fixedWeight
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

        # Select at least one item from each available type (if budget allows)
        # Prioritize items with better weight-to-cost ratio
        for itemType, items in itemsByType.items():
            if not items or remainingWeight <= 0:
                continue
            
            # Find best item from this type (best weight-to-cost ratio)
            bestItem = None
            bestRatio = 0
            
            for item in items:
                weightPerUnit = self.weightCalculator.calculateItemWeight(
                    item["type"], item["unit"], 1, item["name"]
                )
                if weightPerUnit <= 0 or item["unitPrice"] <= 0:
                    continue
                
                ratio = weightPerUnit / item["unitPrice"]  # kg per VND
                if ratio > bestRatio:
                    bestRatio = ratio
                    bestItem = item
            
            if not bestItem:
                continue
            
            item = bestItem
            weightPerUnit = self.weightCalculator.calculateItemWeight(
                item["type"], item["unit"], 1, item["name"]
            )

            # Calculate max quantity based on weight and budget
            maxWeightQuantity = int(remainingWeight / weightPerUnit) if weightPerUnit > 0 else 0
            maxBudgetQuantity = int((maxCost - currentCost) / item["unitPrice"]) if item["unitPrice"] > 0 else 0
            
            maxQuantity = min(
                item["availableQuantity"],
                maxWeightQuantity,
                maxBudgetQuantity
            )
            
            if maxQuantity > 0:
                quantity = maxQuantity
                weight = weightPerUnit * quantity
                totalValue = item["unitPrice"] * quantity
                
                # Double-check profit constraint
                if currentCost + totalValue > maxCost:
                    # Try to take as much as budget allows
                    maxBudgetQty = int((maxCost - currentCost) / item["unitPrice"])
                    if maxBudgetQty <= 0:
                        continue
                    quantity = min(maxBudgetQty, item["availableQuantity"], maxWeightQuantity)
                    weight = weightPerUnit * quantity
                    totalValue = item["unitPrice"] * quantity
                
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
                
                remainingWeight -= weight
                currentCost += totalValue
                usedTypes.add(itemType)

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

        for ratio, item in itemsWithRatio:
            if currentCost >= maxCost:
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

            # Calculate max quantity based on weight and budget
            maxWeightQuantity = int(remainingWeight / weightPerUnit) if weightPerUnit > 0 and remainingWeight > 0 else item["availableQuantity"]
            maxBudgetQuantity = int((maxCost - currentCost) / item["unitPrice"]) if item["unitPrice"] > 0 else 0
            
            maxAdditionalQty = min(
                remainingAvailable,
                maxWeightQuantity,
                maxBudgetQuantity
            )
            
            if maxAdditionalQty > 0:
                additionalWeight = weightPerUnit * maxAdditionalQty
                additionalCost = item["unitPrice"] * maxAdditionalQty
                
                # Final check
                if currentCost + additionalCost > maxCost:
                    continue

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
                
                remainingWeight -= additionalWeight
                currentCost += additionalCost

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

