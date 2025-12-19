"""
Container BOM Optimizer.
Optimizes item selection to hit target profit margin while maximizing weight.
"""
from typing import Any
from services.database import Database
from services.fixed_items import FixedItemsSelector
from services.variable_filler import VariableFiller
from services.container_builder import ContainerBuilder
from services.weight_targets import getWeightRange, getMarginRange
from config import (
    logger,
    CONTAINER_TYPES_WITH_CONTAINER,
    CONTAINER_TYPES_WITHOUT_CONTAINER,
    CONTAINER_EMPTY_WEIGHTS,
)


class Optimizer:
    """Optimizes item selection for container BOM."""

    def __init__(self, db: Database):
        self.db = db
        self.fixedItems = FixedItemsSelector(db)
        self.variableFiller = VariableFiller(db)
        self.containerBuilder = ContainerBuilder(db)

    def optimize(
        self,
        containerLength: float,
        itemModelType: str,
        slatType: str,
        receiptPrice: float,
        containerType: str,
        thickness: int = 6,
        targetProfitMargin: float = 0.20,
    ) -> dict[str, Any]:
        """
        Main optimization function.
        
        Goal: Hit target profit margin while maximizing weight within range.
        """
        # Calculate targets
        targetWeight, minWeight, maxWeight = getWeightRange(containerLength)
        minMargin, maxMargin = getMarginRange(targetProfitMargin)
        targetCost = receiptPrice * (1 - targetProfitMargin)
        
        logger.info(
            f"📦 Optimization: length={containerLength}m, type={containerType}, "
            f"receipt={receiptPrice:,.0f}, targetMargin={targetProfitMargin*100:.0f}%"
        )
        logger.info(
            f"🎯 Targets: weight={targetWeight}kg ({minWeight}-{maxWeight}), "
            f"cost={targetCost:,.0f}, margin={minMargin*100:.0f}-{maxMargin*100:.0f}%"
        )
        
        # Set container builder params
        self.containerBuilder.setSlatParams(slatType, thickness, containerLength)
        
        # Get fixed items
        fixedItems, fixedWeight, fixedCost = self.fixedItems.getAllFixedItems(
            itemModelType, containerLength, slatType, thickness
        )
        
        # Check container status
        needToBuild, containerSize, prebuiltContainer = self._checkContainerStatus(
            containerType
        )
        
        # Pre-built container weight is part of total weight
        # We DON'T reduce effective max - the container weight is counted in total
        effectiveMaxWeight = maxWeight
        prebuiltWeight = 0
        if prebuiltContainer:
            prebuiltWeight = CONTAINER_EMPTY_WEIGHTS.get(containerType, 0)
            logger.info(f"Using pre-built container ({prebuiltWeight}kg) - weight included in total")
        
        # Handle container building if needed
        containerItems = []
        containerBuildIds = set()
        
        if needToBuild:
            buildResult = self.containerBuilder.buildContainer(
                containerSize=containerSize,
                maxCost=targetCost,
                currentCost=fixedCost,
                currentWeight=fixedWeight,
                maxWeight=effectiveMaxWeight,
            )
            if buildResult["success"]:
                containerItems = buildResult["items"]
                containerBuildIds = {item["id"] for item in containerItems}
                fixedCost += buildResult["totalCost"]
                fixedWeight += buildResult["totalWeight"]
                logger.info(f"Built container from materials: {len(containerItems)} items")
        
        # Add pre-built container to BOM if using one
        prebuiltContainerItem = None
        excludeIds = set(containerBuildIds)  # Start with container build IDs
        
        if prebuiltContainer and not needToBuild:
            prebuiltContainerItem = self._getPrebuiltContainerItem(containerType)
            if prebuiltContainerItem:
                fixedCost += prebuiltContainerItem["totalValue"]
                fixedWeight += prebuiltContainerItem["weight"]
                excludeIds.add(prebuiltContainerItem["id"])  # Exclude from variable fill
        
        # Get variable items and fill to targets
        variableItems = self.variableFiller.getVariableItems(containerType)
        
        # Filter out container items when using pre-built container
        if prebuiltContainer and not needToBuild:
            variableItems = [v for v in variableItems if v["type"] != "container"]
        
        # Use new fillToTargets with both weight and margin constraints
        selectedVariables = self.variableFiller.fillToTargets(
            variableItems=variableItems,
            targetCost=targetCost,
            currentCost=fixedCost,
            minWeight=minWeight,  # Hard constraint: must reach minimum weight
            maxWeight=maxWeight,  # Soft constraint: prefer not to exceed
            currentWeight=fixedWeight,
            excludeIds=excludeIds,
            skipContainerBuildTypes=needToBuild,
        )
        
        # Combine all items
        allItems = fixedItems + containerItems + selectedVariables
        if prebuiltContainerItem:
            allItems.append(prebuiltContainerItem)
        
        # Calculate final totals
        totalWeight = sum(item["weight"] for item in allItems)
        totalCost = sum(item["totalValue"] for item in allItems)
        profit = receiptPrice - totalCost
        profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0
        
        # Check if constraints were met (with 0.5% tolerance for floating point)
        weightMet = totalWeight >= minWeight
        actualMargin = profitMargin / 100
        marginMet = (minMargin - 0.005) <= actualMargin <= (maxMargin + 0.005)
        warnings = []
        
        if not weightMet:
            warnings.append(f"Weight {totalWeight:.0f}kg below minimum {minWeight}kg")
        if not marginMet:
            if profitMargin < minMargin * 100:
                warnings.append(f"Margin {profitMargin:.1f}% below target (increase receipt price)")
            else:
                warnings.append(f"Margin {profitMargin:.1f}% above target (weight limit reached)")
        
        status = "✅" if weightMet and marginMet else "⚠️"
        logger.info(
            f"{status} Result: weight={totalWeight:.0f}kg, cost={totalCost:,.0f}, "
            f"margin={profitMargin:.1f}% (target: {targetProfitMargin*100:.0f}%)"
        )
        
        return {
            "items": allItems,
            "totalWeight": round(totalWeight, 2),
            "totalCost": round(totalCost, 2),
            "receiptPrice": receiptPrice,
            "profit": round(profit, 2),
            "profitMargin": round(profitMargin, 2),
            "containerBuiltFromMaterials": needToBuild and len(containerItems) > 0,
            "constraintsMet": weightMet and marginMet,
            "warnings": warnings,
            "constraints": {
                "containerType": containerType,
                "containerLength": containerLength,
                "targetWeight": targetWeight,
                "weightRange": [minWeight, maxWeight],
                "targetProfitMargin": targetProfitMargin * 100,
                "marginRange": [minMargin * 100, maxMargin * 100],
                "usingPrebuiltContainer": prebuiltContainer and not needToBuild,
                "prebuiltContainerWeight": prebuiltWeight if prebuiltContainer else 0,
            },
        }

    def _checkContainerStatus(
        self, containerType: str
    ) -> tuple[bool, str, bool]:
        """
        Check if we need to build a container from materials.
        
        Returns: (needToBuild, containerSize, usingPrebuiltContainer)
        """
        # mooc_long / thung_xe_tai: always build structure, never use container
        if containerType in CONTAINER_TYPES_WITHOUT_CONTAINER:
            return True, "40ft", False
        
        # container_20ft / container_40ft: check inventory
        containerSize = "40ft" if "40" in containerType else "20ft"
        sizeInName = "40" if containerSize == "40ft" else "20"
        
        result = self.db.executeQuery(
            """
            SELECT i.id FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'container' 
              AND i.name ILIKE %s
              AND ir.final_quantity > 0
            LIMIT 1
            """,
            (f"%{sizeInName}%",),
        )
        
        if result:
            logger.info(f"Found pre-built {containerSize} container in inventory")
            return False, containerSize, True
        
        logger.warning(f"No {containerSize} container in inventory, will build from materials")
        return True, containerSize, False

    def _getPrebuiltContainerItem(self, containerType: str) -> dict[str, Any] | None:
        """Get pre-built container item from inventory."""
        sizeInName = "40" if "40" in containerType else "20"
        weight = CONTAINER_EMPTY_WEIGHTS.get(containerType, 0)
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'container' 
              AND i.name ILIKE %s
              AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """,
            (f"%{sizeInName}%",),
        )
        
        if not result:
            return None
        
        row = result[0]
        unitPrice = float(row[4])
        
        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "container",
            "quantity": 1,
            "unitPrice": unitPrice,
            "totalValue": unitPrice,
            "weight": weight,
        }


def main():
    """Test optimizer with different scenarios."""
    db = Database()
    optimizer = Optimizer(db)
    
    testCases = [
        # (containerType, length, model, slat, receipt, margin)
        ("container_20ft", 6.096, "R2DX", "97mm", 400_000_000, 0.20),
        ("mooc_long", 15.0, "KSD", "112mm", 700_000_000, 0.20),
        ("container_40ft", 12.192, "R2DX", "112mm", 800_000_000, 0.15),
    ]
    
    for containerType, length, model, slat, receipt, margin in testCases:
        print("\n" + "=" * 60)
        print(f"Test: {containerType}, {length}m, {model}, {receipt:,.0f} VND, {margin*100}% margin")
        print("=" * 60)
        
        result = optimizer.optimize(
            containerLength=length,
            itemModelType=model,
            slatType=slat,
            receiptPrice=receipt,
            containerType=containerType,
            targetProfitMargin=margin,
        )
        
        print(f"\nResult:")
        print(f"  Total weight: {result['totalWeight']:,.0f} kg")
        print(f"  Total cost: {result['totalCost']:,.0f} VND")
        print(f"  Profit margin: {result['profitMargin']:.1f}%")
        print(f"  Container built: {result['containerBuiltFromMaterials']}")
        print(f"\nItems ({len(result['items'])}):")
        for item in result["items"]:
            print(f"    {item['code']}: {item['quantity']} {item['unit']} = {item['weight']:.0f}kg")
    
    db.close()


if __name__ == "__main__":
    main()
