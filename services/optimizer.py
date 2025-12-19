from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from services.container_builder import ContainerBuilder
from config import (
    logger,
    CONTAINER_TYPES_WITH_CONTAINER,
    CONTAINER_TYPES_WITHOUT_CONTAINER,
    CONTAINER_EMPTY_WEIGHTS,
)


class Optimizer:
    """Optimizes item selection for container weight and profit constraints."""

    MIN_WEIGHT = 3000  # kg
    BASE_MAX_WEIGHT = 6000  # kg (base limit before material loss)
    MATERIAL_LOSS_FACTOR = 0.12  # 12% material loss during processing
    MAX_WEIGHT = int(BASE_MAX_WEIGHT * (1 + MATERIAL_LOSS_FACTOR))  # ~6720 kg with loss factor
    MAX_PROFIT_MARGIN = 0.15  # 15% (target profit margin)

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()
        self.containerBuilder = ContainerBuilder(db)
    
    # =========================================================================
    # Container Type Helper Methods
    # =========================================================================
    
    def _shouldIncludeContainerItem(self, containerType: str) -> bool:
        """
        Check if container type should include a container item in BOM.
        
        - container_20ft, container_40ft: YES (pre-built or built from materials)
        - mooc_long, thung_xe_tai: NO (structure materials only, no container)
        """
        return containerType in CONTAINER_TYPES_WITH_CONTAINER
    
    def _getPrebuiltContainerWeight(self, containerType: str) -> int:
        """
        Get the empty weight of a pre-built container.
        
        Returns:
            Weight in kg (1900 for 20ft, 2500 for 40ft, 0 for others)
        """
        return CONTAINER_EMPTY_WEIGHTS.get(containerType, 0)
    
    def _getPrebuiltContainerItem(
        self, 
        containerType: str, 
        containerSize: str, 
        variableItems: list[dict]
    ) -> dict | None:
        """
        Find and return the pre-built container item from inventory.
        
        Args:
            containerType: e.g., "container_20ft" or "container_40ft"
            containerSize: e.g., "20ft" or "40ft"
            variableItems: List of variable items from inventory
        
        Returns:
            Container item dict with weight, or None if not found
        """
        sizeInName = "40" if containerSize == "40ft" else "20"
        containerWeight = self._getPrebuiltContainerWeight(containerType)
        
        for item in variableItems:
            if item["type"] == "container" and sizeInName in item["name"]:
                return {
                    "id": item["id"],
                    "code": item["code"],
                    "name": item["name"],
                    "unit": item["unit"],
                    "type": "container",
                    "quantity": 1,
                    "unitPrice": item["unitPrice"],
                    "totalValue": item["unitPrice"],
                    "weight": containerWeight,  # Actual container weight!
                }
        
        logger.warning(f"Pre-built {containerSize} container not found in variableItems")
        return None
    
    def _getEffectiveMaxWeight(
        self, 
        containerType: str, 
        usingPrebuiltContainer: bool
    ) -> int:
        """
        Calculate effective max weight based on container type and usage.
        
        - Pre-built container: MAX_WEIGHT - container empty weight
        - Built from materials: MAX_WEIGHT (materials already counted)
        - mooc_long/thung_xe_tai: MAX_WEIGHT (no container)
        """
        if usingPrebuiltContainer and containerType in CONTAINER_EMPTY_WEIGHTS:
            containerWeight = CONTAINER_EMPTY_WEIGHTS[containerType]
            return self.MAX_WEIGHT - containerWeight
        return self.MAX_WEIGHT

    # Hydraulic pump selection by model type
    HYDRAULIC_PUMP_MAP = {
        "R2DX": "130cc",  # R2DX uses 130cc pump
        "KSD": "108cc",   # KSD uses 108cc pump
        "KMD": "108cc",   # KMD uses 108cc pump
    }
    
    # Hydraulic oil constants
    HYDRAULIC_OIL_LITERS = 200  # Full barrel (180-209L range, using 200L)
    HYDRAULIC_OIL_DENSITY = 0.88  # kg/L for ISO VG 68
    HYDRAULIC_OIL_DRUM_WEIGHT = 15  # kg for empty drum
    HYDRAULIC_OIL_TOTAL_WEIGHT = 200  # ~185kg oil + 15kg drum ≈ 200kg

    def optimize(
        self,
        containerLength: float,
        itemModelType: str,
        slatType: str,
        receiptPrice: float,
        containerType: str = None,
        thickness: int = 6,
    ) -> dict[str, Any]:
        """
        Main optimization function.
        Returns optimized item list with weights and costs.
        """
        # Log optimization constraints with material loss factor
        logger.info(
            f"🔧 Optimization constraints: "
            f"baseMaxWeight={self.BASE_MAX_WEIGHT}kg, "
            f"materialLossFactor={self.MATERIAL_LOSS_FACTOR * 100:.0f}%, "
            f"nominalMaxWeight={self.MAX_WEIGHT}kg, "
            f"maxProfitMargin={self.MAX_PROFIT_MARGIN * 100:.0f}%"
        )
        logger.info(
            f"📦 Input: containerType={containerType}, length={containerLength}m, "
            f"model={itemModelType}, slat={slatType}, thickness={thickness}mm, "
            f"receiptPrice={receiptPrice:,.0f}"
        )
        
        # Set slat params on container builder for dynamic aluminum calculation
        self.containerBuilder.setSlatParams(slatType, thickness, containerLength)
        
        # Get fixed items
        walkingFloorWeight, walkingFloorType = (
            self.weightCalculator.calculateWalkingFloorWeight(itemModelType)
        )
        walkingFloorItem = self._getWalkingFloorItem(walkingFloorType, itemModelType, walkingFloorWeight)
        
        # Get hydraulic pump (always included) - 130cc for R2DX, 108cc for others
        hydraulicPumpItem = self._getHydraulicPumpItem(itemModelType)
        
        # Get hydraulic oil (always included) - full barrel 180-209L
        hydraulicOilItem = self._getHydraulicOilItem()
        
        # Get variable items for optimization (with container validation)
        # Pass containerType to exclude container items for mooc_long/thung_xe_tai
        variableItems = self._getVariableItems(containerType)

        # Check if we need to build a container from materials
        needToBuild, containerSize, usingPrebuiltContainer = self._checkNeedToBuildContainer(
            containerType, variableItems
        )
        
        # Calculate effective max weight based on container usage
        effectiveMaxWeight = self._getEffectiveMaxWeight(containerType, usingPrebuiltContainer)
        logger.info(
            f"📦 Container: type={containerType}, needToBuild={needToBuild}, "
            f"prebuilt={usingPrebuiltContainer}, effectiveMaxWeight={effectiveMaxWeight}kg"
        )

        # Calculate aluminum bars (skip if building container - aluminum will be part of build)
        aluminumItem = None
        aluminumWeight = 0.0
        
        if needToBuild:
            # When building container, aluminum is included in container materials
            # This avoids double-counting aluminum (bars + container structure)
            logger.info(
                f"Building container from materials - aluminum included in container build"
            )
        else:
            # Normal case: calculate aluminum bars separately
            aluminumWeight, density, bars = (
                self.weightCalculator.calculateAluminumBarWeight(
                    containerLength, slatType, thickness, self.db
                )
            )
            aluminumItem = self._getAluminumItem(aluminumWeight)

        # Calculate fixed weight and cost
        fixedWeight = walkingFloorWeight + aluminumWeight
        fixedCost = walkingFloorItem["unitPrice"] * walkingFloorItem["quantity"]
        if aluminumItem:
            fixedCost += aluminumItem["unitPrice"] * aluminumItem["quantity"]
        
        # Add hydraulic pump and oil to fixed items
        if hydraulicPumpItem:
            fixedWeight += hydraulicPumpItem["weight"]
            fixedCost += hydraulicPumpItem["totalValue"]
        if hydraulicOilItem:
            fixedWeight += hydraulicOilItem["weight"]
            fixedCost += hydraulicOilItem["totalValue"]

        # Handle container: either use pre-built or build from materials
        builtContainerItems = []
        containerBuildCost = 0.0
        containerBuildWeight = 0.0
        prebuiltContainerItem = None
        
        # If using pre-built container, find and add it to BOM
        if usingPrebuiltContainer and not needToBuild:
            prebuiltContainerItem = self._getPrebuiltContainerItem(
                containerType, containerSize, variableItems
            )
            if prebuiltContainerItem:
                logger.info(
                    f"✅ Added pre-built {containerSize} container to BOM: "
                    f"weight={prebuiltContainerItem['weight']}kg, "
                    f"cost={prebuiltContainerItem['totalValue']:,.0f}"
                )
        
        # If building container, BUILD IT to reserve materials
        if needToBuild:
            maxCost = receiptPrice * (1 - self.MAX_PROFIT_MARGIN)
            
            buildResult = self.containerBuilder.buildContainer(
                containerSize=containerSize,
                maxCost=maxCost,
                currentCost=fixedCost,  # Only walking floor cost
                currentWeight=fixedWeight,  # Only walking floor weight
                maxWeight=effectiveMaxWeight,  # Use effective max weight
            )
            
            if buildResult["success"]:
                builtContainerItems = buildResult["items"]
                containerBuildCost = buildResult["totalCost"]
                containerBuildWeight = buildResult["totalWeight"]
                logger.info(
                    f"Built {containerSize} container from materials: "
                    f"{len(builtContainerItems)} items, "
                    f"cost={containerBuildCost:,.0f}, "
                    f"weight={containerBuildWeight:.0f}kg"
                )
            else:
                logger.warning(
                    f"Failed to build {containerSize} container: {buildResult.get('reason')}"
                )

        # Extract item IDs used for container building (to avoid duplicates)
        containerBuildItemIds = set()
        if builtContainerItems:
            for item in builtContainerItems:
                containerBuildItemIds.add(item["id"])
        
        # Optimize variable items with container build cost/weight already accounted for
        effectiveFixedCost = fixedCost + containerBuildCost
        effectiveFixedWeight = fixedWeight + containerBuildWeight
        
        selectedItems = self._optimizeVariableItems(
            variableItems, effectiveFixedWeight, effectiveFixedCost, receiptPrice, 
            skipContainerBuild=needToBuild,
            containerBuildItemIds=containerBuildItemIds,
            effectiveMaxWeight=effectiveMaxWeight,
        )

        # Combine fixed and variable items (and built container materials if any)
        allItems = [walkingFloorItem]
        if aluminumItem:
            allItems.append(aluminumItem)
        if hydraulicPumpItem:
            allItems.append(hydraulicPumpItem)
        if hydraulicOilItem:
            allItems.append(hydraulicOilItem)
        # Add pre-built container item if using one
        if prebuiltContainerItem:
            allItems.append(prebuiltContainerItem)
        allItems.extend(selectedItems)
        allItems.extend(builtContainerItems)

        # Calculate totals
        totalWeight = sum(item["weight"] for item in allItems)
        totalCost = sum(item["totalValue"] for item in allItems)
        
        # If weight is below MIN_WEIGHT, try to add more aluminum
        # Adding aluminum increases cost and DECREASES profit margin (which is good!)
        if totalWeight < self.MIN_WEIGHT:
            # Find aluminum item to boost (either from fixed items or from container build)
            aluminumToBoost = aluminumItem
            if not aluminumToBoost:
                # Look for aluminum in container build materials
                for item in builtContainerItems:
                    if "aluminum" in item.get("type", "") or "nhôm" in item.get("name", "").lower():
                        aluminumToBoost = item
                        break
            
            if aluminumToBoost:
                additionalAluminum = self._boostAluminumForWeight(
                    aluminumToBoost, totalWeight, totalCost, receiptPrice
                )
                if additionalAluminum:
                    # Update aluminum item with additional quantity
                    aluminumToBoost["quantity"] += additionalAluminum["additionalQty"]
                    aluminumToBoost["weight"] += additionalAluminum["additionalWeight"]
                    aluminumToBoost["totalValue"] += additionalAluminum["additionalCost"]
                    
                    # Recalculate totals
                    totalWeight += additionalAluminum["additionalWeight"]
                    totalCost += additionalAluminum["additionalCost"]
                    
                    logger.info(
                        f"Boosted aluminum by {additionalAluminum['additionalQty']:.2f} kg "
                        f"to reach weight {totalWeight:.2f} kg"
                    )

        # Check profit margin and add more materials if too high
        # Since we allow extra weight due to material loss, we can keep adding
        profit = receiptPrice - totalCost
        profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0
        
        if profitMargin > self.MAX_PROFIT_MARGIN * 100:
            logger.info(
                f"Profit margin {profitMargin:.2f}% exceeds target {self.MAX_PROFIT_MARGIN * 100}%. "
                f"Adding more materials to reduce margin..."
            )
            addedItems = self._fillBudgetToTargetMargin(
                allItems, totalWeight, totalCost, receiptPrice, 
                aluminumItem, variableItems, containerBuildItemIds
            )
            
            if addedItems:
                # Recalculate totals
                totalWeight = sum(item["weight"] for item in allItems)
                totalCost = sum(item["totalValue"] for item in allItems)
                profit = receiptPrice - totalCost
                profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0
                logger.info(
                    f"After budget fill: weight={totalWeight:.2f}kg, "
                    f"cost={totalCost:,.0f}, margin={profitMargin:.2f}%"
                )

        # Calculate estimated usable weight after material loss
        estimatedUsableWeight = round(totalWeight * (1 - self.MATERIAL_LOSS_FACTOR), 2)
        
        # Log final results
        logger.info(
            f"✅ Optimization complete: "
            f"totalWeight={totalWeight:.2f}kg (usable after {self.MATERIAL_LOSS_FACTOR * 100:.0f}% loss: {estimatedUsableWeight:.2f}kg), "
            f"cost={totalCost:,.0f}, margin={profitMargin:.2f}%"
        )
        
        return {
            "items": allItems,
            "totalWeight": round(totalWeight, 2),
            "totalCost": round(totalCost, 2),
            "receiptPrice": receiptPrice,
            "profit": round(profit, 2),
            "profitMargin": round(profitMargin, 2),
            "containerBuiltFromMaterials": needToBuild and len(builtContainerItems) > 0,
            # Material loss factor info for frontend display
            "constraints": {
                "baseMaxWeight": self.BASE_MAX_WEIGHT,
                "materialLossFactor": self.MATERIAL_LOSS_FACTOR,
                "materialLossPercent": round(self.MATERIAL_LOSS_FACTOR * 100, 1),
                "nominalMaxWeight": self.MAX_WEIGHT,
                "effectiveMaxWeight": effectiveMaxWeight,
                "maxProfitMargin": self.MAX_PROFIT_MARGIN,
                "maxProfitMarginPercent": round(self.MAX_PROFIT_MARGIN * 100, 1),
                "minWeight": self.MIN_WEIGHT,
                # Container-specific info
                "containerType": containerType,
                "usingPrebuiltContainer": usingPrebuiltContainer,
                "prebuiltContainerWeight": self._getPrebuiltContainerWeight(containerType) if usingPrebuiltContainer else 0,
            },
            "estimatedUsableWeight": estimatedUsableWeight,
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
        # Target: at least 5% profit margin (MIN_BOOST_PROFIT_MARGIN)
        # This ensures we don't accidentally spend the entire receipt price
        MIN_BOOST_PROFIT_MARGIN = 0.05  # 5% minimum profit after boost
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

    def _fillBudgetToTargetMargin(
        self,
        allItems: list[dict],
        currentWeight: float,
        currentCost: float,
        receiptPrice: float,
        aluminumItem: dict,
        variableItems: list[dict],
        containerBuildItemIds: set[int],
    ) -> bool:
        """
        Fill remaining budget to reach target profit margin.
        
        With material loss factor, we can add more weight beyond BASE_MAX_WEIGHT.
        Priority: aluminum first (best weight-to-cost), then other materials.
        
        Returns True if items were added.
        """
        targetCost = receiptPrice * (1 - self.MAX_PROFIT_MARGIN)
        budgetRemaining = targetCost - currentCost
        
        if budgetRemaining <= 0:
            return False
        
        addedItems = False
        selectedMap = {item["id"]: item for item in allItems}
        
        # Priority 1: Add more aluminum (best for weight and cost)
        # Find aluminum item - could be fixed item OR from container build
        aluminumToBoost = aluminumItem
        if not aluminumToBoost:
            # Look for aluminum in allItems (e.g., from container build)
            for item in allItems:
                if item.get("type") == "aluminum" or "nhôm" in item.get("name", "").lower():
                    aluminumToBoost = item
                    break
        
        if aluminumToBoost and aluminumToBoost["id"] in selectedMap:
            # Get total available aluminum from ALL aluminum items in inventory
            result = self.db.executeQuery(
                """
                SELECT COALESCE(SUM(ir.final_quantity), 0)
                FROM inventory_records ir
                JOIN items i ON ir.item_id = i.id
                WHERE i.type = 'aluminum'
                AND ir.final_quantity > 0
                """
            )
            
            if result:
                totalAvailableQty = float(result[0][0])
                # Sum all aluminum already used in allItems
                alreadyUsed = sum(
                    item["quantity"] for item in allItems 
                    if item.get("type") == "aluminum" or "nhôm" in item.get("name", "").lower()
                )
                remainingAvailable = totalAvailableQty - alreadyUsed
                
                if remainingAvailable > 0:
                    unitPrice = aluminumToBoost["unitPrice"]
                    maxByBudget = budgetRemaining / unitPrice if unitPrice > 0 else 0
                    # Also respect weight limit
                    weightRemaining = self.MAX_WEIGHT - currentWeight
                    maxByWeight = weightRemaining  # aluminum: 1 kg = 1 kg weight
                    additionalQty = min(remainingAvailable, maxByBudget, maxByWeight)
                    
                    if additionalQty > 0:
                        additionalCost = additionalQty * unitPrice
                        aluminumToBoost["quantity"] += additionalQty
                        aluminumToBoost["weight"] += additionalQty  # aluminum: weight = quantity
                        aluminumToBoost["totalValue"] += additionalCost
                        
                        budgetRemaining -= additionalCost
                        currentWeight += additionalQty
                        currentCost += additionalCost
                        addedItems = True
                        
                        logger.info(
                            f"Added {additionalQty:.2f}kg aluminum to fill budget "
                            f"(remaining: {budgetRemaining:,.0f}, weight: {currentWeight:.0f}kg)"
                        )
        
        # Priority 2: Add more of existing steel/material items
        for item in allItems:
            if budgetRemaining <= 0:
                break
            
            if item.get("id") in containerBuildItemIds:
                continue
            
            itemType = item.get("type", "")
            if itemType not in ["steel_box", "steel_i", "steel_square", "steel_u", 
                               "steel_pipe", "steel_plate", "galvanized_sheet"]:
                continue
            
            # Find original item to get available quantity
            originalItem = None
            for vi in variableItems:
                if vi["id"] == item["id"]:
                    originalItem = vi
                    break
            
            if not originalItem:
                continue
            
            remainingAvailable = originalItem["availableQuantity"] - item["quantity"]
            if remainingAvailable <= 0:
                continue
            
            unitPrice = item["unitPrice"]
            if unitPrice <= 0:
                continue
            
            maxByBudget = int(budgetRemaining / unitPrice)
            additionalQty = min(remainingAvailable, maxByBudget)
            
            if additionalQty > 0:
                weightPerUnit = self.weightCalculator.calculateItemWeight(
                    originalItem["type"], originalItem["unit"], 1, originalItem["name"]
                )
                additionalWeight = weightPerUnit * additionalQty
                additionalCost = unitPrice * additionalQty
                
                item["quantity"] += additionalQty
                item["weight"] += additionalWeight
                item["totalValue"] += additionalCost
                
                budgetRemaining -= additionalCost
                addedItems = True
                
                logger.info(
                    f"Added {additionalQty} {item['unit']} {item['code']} "
                    f"({additionalWeight:.2f}kg) to fill budget"
                )
        
        # Priority 3: Add new items from inventory if budget still remaining
        if budgetRemaining > 100000:  # Only if significant budget left
            for vi in variableItems:
                if budgetRemaining <= 0:
                    break
                
                if vi["id"] in selectedMap or vi["id"] in containerBuildItemIds:
                    continue
                
                if vi["type"] == "container":
                    continue
                
                unitPrice = vi["unitPrice"]
                if unitPrice <= 0:
                    continue
                
                maxByBudget = int(budgetRemaining / unitPrice)
                quantity = min(vi["availableQuantity"], maxByBudget)
                
                if quantity > 0:
                    weightPerUnit = self.weightCalculator.calculateItemWeight(
                        vi["type"], vi["unit"], 1, vi["name"]
                    )
                    weight = weightPerUnit * quantity
                    totalValue = unitPrice * quantity
                    
                    newItem = {
                        "id": vi["id"],
                        "code": vi["code"],
                        "name": vi["name"],
                        "unit": vi["unit"],
                        "quantity": quantity,
                        "unitPrice": unitPrice,
                        "totalValue": totalValue,
                        "weight": weight,
                    }
                    allItems.append(newItem)
                    selectedMap[vi["id"]] = newItem
                    
                    budgetRemaining -= totalValue
                    addedItems = True
                    
                    logger.info(
                        f"Added new item {vi['code']} ({quantity} {vi['unit']}, "
                        f"{weight:.2f}kg) to fill budget"
                    )
        
        return addedItems

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

    def _getHydraulicPumpItem(self, itemModelType: str) -> dict[str, Any] | None:
        """
        Get hydraulic pump based on walking floor model type.
        - R2DX: 130cc pump
        - KSD, KMD, or others: 108cc pump
        
        Always includes 1 pump in the BOM.
        """
        # Determine pump size based on model type
        pumpSize = self.HYDRAULIC_PUMP_MAP.get(itemModelType.upper(), "108cc")
        
        # Query for pump matching the size
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
            WHERE i.type = 'hydraulic_pump' 
              AND ir.final_quantity > 0
              AND (i.name ILIKE %s OR i.code ILIKE %s)
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """,
            (f"%{pumpSize}%", f"%{pumpSize}%"),
        )

        if not result:
            # Fallback: get any available hydraulic pump
            logger.warning(
                f"No {pumpSize} hydraulic pump found, trying any available pump"
            )
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
                WHERE i.type = 'hydraulic_pump' AND ir.final_quantity > 0
                ORDER BY i.id, ir.record_date DESC
                LIMIT 1
                """
            )

        if not result:
            logger.warning("No hydraulic pump available in inventory")
            return None

        row = result[0]
        quantity = 1  # Always 1 pump
        unitPrice = float(row[6])
        # Pump weight: approximately 50kg per unit
        pumpWeight = 50.0

        logger.info(
            f"🔧 Selected hydraulic pump: {row[1]} ({pumpSize}) - "
            f"qty: {quantity}, weight: {pumpWeight}kg"
        )

        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "hydraulic_pump",
            "quantity": quantity,
            "unitPrice": unitPrice,
            "totalValue": unitPrice * quantity,
            "weight": pumpWeight,
        }

    def _getHydraulicOilItem(self) -> dict[str, Any] | None:
        """
        Get hydraulic oil (full barrel 180-209L).
        
        Oil specs:
        - Volume: 180-209L per barrel
        - Density: ~0.88 kg/L (ISO VG 68)
        - Oil weight: 209L × 0.88 = ~184kg
        - With drum: ~200kg total
        
        Always includes 1 barrel in the BOM.
        Database stores oil by barrel (unit='barrel'), not by liter.
        """
        # Query for hydraulic oil - type is 'hydraulic_oil', unit is 'barrel'
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
            WHERE i.type = 'hydraulic_oil'
              AND ir.final_quantity >= 1
            ORDER BY i.id, ir.record_date DESC
            LIMIT 1
            """
        )

        if not result:
            # Fallback: search by name patterns (nhớt, dầu thủy lực, hydraulic oil)
            logger.warning(
                "No hydraulic_oil type found, trying name-based search"
            )
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
                WHERE ir.final_quantity >= 1
                  AND (
                      i.name ILIKE '%%nhớt%%hydraulic%%'
                      OR i.name ILIKE '%%hydraulic%%oil%%'
                      OR i.name ILIKE '%%dầu%%thủy lực%%'
                  )
                ORDER BY i.id, ir.record_date DESC
                LIMIT 1
                """
            )

        if not result:
            logger.warning("No hydraulic oil available in inventory")
            return None

        row = result[0]
        # Quantity: 1 barrel (unit is 'barrel', each barrel is 180-209L)
        quantity = 1
        unitPrice = float(row[6])  # Price per barrel
        # Weight: ~200kg for a full barrel (184kg oil + 16kg drum)
        oilWeight = self.HYDRAULIC_OIL_TOTAL_WEIGHT

        logger.info(
            f"🛢️ Selected hydraulic oil: {row[1]} - "
            f"qty: {quantity} barrel, weight: {oilWeight}kg, price: {unitPrice:,.0f} VND"
        )

        return {
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": "hydraulic_oil",
            "quantity": quantity,
            "unitPrice": unitPrice,
            "totalValue": unitPrice * quantity,
            "weight": oilWeight,
        }

    def _getVariableItems(self, containerType: str = None) -> list[dict[str, Any]]:
        """Get all variable items available for optimization.
        
        Includes all item types except walking floors, aluminum, hydraulic pump, 
        and hydraulic oil (which are fixed items - always included in BOM).
        This allows the optimizer to use whatever inventory is available.
        
        Args:
            containerType: Container type (e.g., "container_40ft", "mooc_long")
                          Used to filter container items.
                          - container_20ft/40ft: Include container items
                          - mooc_long/thung_xe_tai: Exclude container items
        """
        # Include all item types that can be used as variable items
        # Excludes: walking_floor_*, aluminum, hydraulic_pump, hydraulic_oil (these are fixed items)
        variableTypes = [
            'steel_box', 'steel_i', 'steel_square', 'steel_u', 'steel_pipe', 'steel_plate',
            'galvanized_sheet', 'stainless_steel',
        ]
        
        # Only include container items for container_20ft and container_40ft
        # mooc_long and thung_xe_tai do NOT include container items
        if self._shouldIncludeContainerItem(containerType):
            variableTypes.append('container')
        else:
            logger.info(
                f"Excluding container items from variable items for '{containerType}'"
            )
        
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

    def _checkNeedToBuildContainer(
        self,
        containerType: str,
        variableItems: list[dict[str, Any]],
    ) -> tuple[bool, str, bool]:
        """
        Check if we need to build a container from materials.
        
        Container Types:
        - container_20ft/40ft: Check inventory, build if not available
        - mooc_long/thung_xe_tai: Always build structure (no container item)
        
        Returns:
            (needToBuild, containerSize, usingPrebuiltContainer)
            - needToBuild: True if need to build structure from materials
            - containerSize: "20ft", "40ft", or "" for scaling reference
            - usingPrebuiltContainer: True if using pre-built container from inventory
        """
        # For mooc_long and thung_xe_tai: always build structure, never use container
        if containerType in CONTAINER_TYPES_WITHOUT_CONTAINER:
            logger.info(
                f"Container type '{containerType}' does not include container item. "
                f"Building structure from materials only."
            )
            # Use 40ft as scaling base for material calculation
            return True, "40ft", False
        
        # For container_20ft and container_40ft: check inventory
        containerSize = None
        if containerType == "container_40ft":
            containerSize = "40ft"
        elif containerType == "container_20ft":
            containerSize = "20ft"
        
        if not containerSize:
            logger.warning(f"Unknown container type: {containerType}")
            return False, "", False
        
        # Check if requested container is available in inventory
        for item in variableItems:
            if item["type"] == "container":
                sizeInName = "40" if containerSize == "40ft" else "20"
                if sizeInName in item["name"]:
                    logger.info(f"Found pre-built {containerSize} container in inventory")
                    return False, containerSize, True  # Pre-built container available
        
        # No matching container found - need to build from materials
        logger.warning(
            f"No {containerSize} container in inventory. "
            f"Will build from materials."
        )
        return True, containerSize, False

    def _optimizeVariableItems(
        self,
        variableItems: list[dict[str, Any]],
        fixedWeight: float,
        fixedCost: float,
        receiptPrice: float,
        skipContainerBuild: bool = False,
        containerBuildItemIds: set[int] = None,
        effectiveMaxWeight: int = None,
    ) -> list[dict[str, Any]]:
        """
        Greedy optimization: aggressively fill weight range to effective max weight.
        Maximizes variety by selecting from different types.
        Respects profit margin constraint.
        
        Args:
            skipContainerBuild: If True, don't add containers (we'll build from materials)
            containerBuildItemIds: Set of item IDs already used for container building (to avoid duplicates)
            effectiveMaxWeight: Max weight considering container type and pre-built usage
        """
        # Use effective max weight if provided, otherwise default to MAX_WEIGHT
        maxWeight = effectiveMaxWeight if effectiveMaxWeight else self.MAX_WEIGHT
        
        # Target maximum weight (be greedy!)
        targetWeight = maxWeight - fixedWeight
        remainingWeight = targetWeight
        selectedItems = []
        usedTypes = set()
        currentCost = fixedCost
        maxCost = receiptPrice * (1 - self.MAX_PROFIT_MARGIN)  # Max cost to stay within profit margin
        
        # Types used for container building - exclude these when building container
        containerBuildTypes = {'steel_box', 'galvanized_sheet', 'aluminum'}
        containerBuildItemIds = containerBuildItemIds or set()

        # Group items by type for variety
        itemsByType = {}
        for item in variableItems:
            itemType = item["type"]
            
            # Skip items already used for container building (by ID)
            if item["id"] in containerBuildItemIds:
                logger.debug(f"Skipping item {item['code']} - already used for container build")
                continue
            
            # Skip container build material types when building container from materials
            if skipContainerBuild and itemType in containerBuildTypes:
                logger.debug(f"Skipping {itemType} item {item['code']} - reserved for container build")
                continue
                
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
            
            # Skip container type items when building container from materials
            if skipContainerBuild and itemType == "container":
                logger.info(f"Skipping container items - will build from materials")
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
            weightSpaceLeft = maxWeight - currentTotalWeight
            
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
        # But skip if we're building container from materials
        containerFirst = sorted(
            zeroWeightItems,
            key=lambda x: (0 if x["type"] == "container" else 1, -x["unitPrice"])
        )
        
        for item in containerFirst:
            # Skip containers if we're building from materials
            if skipContainerBuild and item["type"] == "container":
                logger.info(f"Skipping container '{item['name']}' - will build from materials")
                continue
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
        # IMPORTANT: Apply same exclusions as above to avoid duplicates with container build
        itemsWithRatio = []
        for item in variableItems:
            # Skip items already used for container building (by ID)
            if item["id"] in containerBuildItemIds:
                continue
            
            # Skip container build material types when building container from materials
            if skipContainerBuild and item["type"] in containerBuildTypes:
                continue
            
            # Skip container type items when building container from materials
            if skipContainerBuild and item["type"] == "container":
                continue
            
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
                if currentTotalWeight >= maxWeight or currentCost >= maxCost:
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
                weightNeeded = maxWeight - currentTotalWeight
                
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

