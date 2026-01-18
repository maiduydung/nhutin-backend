"""
Container BOM Optimizer V2.
4-Phase Constrained Feasibility Algorithm.

Phases:
0. Feasibility Check - Derive bounds, fail early if impossible
1. Fixed Items - Walking floor, aluminum, pump, oil (deterministic)
2. Weight Filling - Reach minWeight with structural materials
3. Margin Tuning - Add expensive/light items to hit target margin
4. Micro-Adjust - Swap cheap/heavy for expensive/light to fine-tune margin
"""
from typing import Any
from services.database import Database
from services.fixed_items import FixedItemsSelector
from services.container_builder import ContainerBuilder
from services.feasibility_checker import FeasibilityChecker, OptimizationBounds
from services.weight_filler import WeightFiller
from services.margin_tuner import MarginTuner
from services.micro_adjuster import MicroAdjuster
from config import (
    logger,
    CONTAINER_TYPES_WITHOUT_CONTAINER,
    CONTAINER_EMPTY_WEIGHTS,
    DEFAULT_EXISTING_TRUCK_BODY_WEIGHT,
)


class OptimizerV2:
    """
    4-Phase optimization engine.
    
    Golden Rule: Never optimize margin before weight feasibility is locked.
    """

    def __init__(self, db: Database):
        self.db = db
        self.feasibilityChecker = FeasibilityChecker()
        self.fixedItems = FixedItemsSelector(db)
        self.containerBuilder = ContainerBuilder(db)
        self.weightFiller = WeightFiller(db)
        self.marginTuner = MarginTuner(db)
        self.microAdjuster = MicroAdjuster()

    def optimize(
        self,
        containerLength: float,
        itemModelType: str,
        slatType: str,
        receiptPrice: float,
        containerType: str,
        thickness: int = 6,
        targetProfitMargin: float = 0.20,
        buildContainer: bool = True,
        existingContainerWeight: float = 0,
        relaxedMode: bool = False,
    ) -> dict[str, Any]:
        """
        Main optimization function using 4-phase approach.
        
        Args:
            buildContainer: Whether to build container structure from materials.
                           Only applies to thung_xe_tai. Set False if user already
                           has a truck body and only needs walking floor installed.
            existingContainerWeight: Weight of user's existing container in kg.
                                    Only used when buildContainer=False.
            relaxedMode: When True, do best-effort optimization even when strict
                        constraints cannot be met. Returns warning instead of error.
        """
        logger.info("=" * 60)
        logger.info(f"🚀 OptimizerV2: {containerType}, {containerLength}m")
        logger.info(f"   Receipt: {receiptPrice:,.0f}, Target margin: {targetProfitMargin*100:.0f}%")
        if relaxedMode:
            logger.info(f"   ⚠️ Relaxed mode: Will do best-effort even if constraints impossible")
        if containerType == "thung_xe_tai" and not buildContainer:
            logger.info(f"   📋 buildContainer=False: Skipping container structure build")
            if existingContainerWeight > 0:
                logger.info(f"   📋 Existing container weight: {existingContainerWeight:,.0f} kg")
        logger.info("=" * 60)
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 0: Derive bounds and check feasibility
        # ─────────────────────────────────────────────────────────────
        bounds = self.feasibilityChecker.deriveBounds(
            containerLength, receiptPrice, targetProfitMargin
        )
        logger.info(f"Phase 0: {bounds}")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 1: Get fixed items (deterministic, no optimization)
        # ─────────────────────────────────────────────────────────────
        fixedItems, fixedWeight, fixedCost = self.fixedItems.getAllFixedItems(
            itemModelType, containerLength, slatType, thickness
        )
        
        # Track all items and used quantities
        allItems = list(fixedItems)
        usedQty = {item["id"]: item["quantity"] for item in fixedItems}
        excludeIds = set(usedQty.keys())
        
        currentWeight = fixedWeight
        currentCost = fixedCost
        
        # ─────────────────────────────────────────────────────────────
        # Handle container (pre-built or build from materials)
        # ─────────────────────────────────────────────────────────────
        containerBuilt = False
        prebuiltContainer = None
        
        # Determine if we should build container structure
        # - mooc_long: always build from materials
        # - thung_xe_tai: build only if buildContainer=True (user may already have truck body)
        shouldBuildContainer = (
            containerType == "mooc_long" or 
            (containerType == "thung_xe_tai" and buildContainer)
        )
        
        if shouldBuildContainer:
            # Mooc Long / Thung Xe Tai: Build structure from materials
            containerSize = "40ft"
            self.containerBuilder.setSlatParams(slatType, thickness, containerLength)
            
            buildResult = self.containerBuilder.buildContainer(
                containerSize=containerSize,
                maxCost=bounds.maxCost,
                currentCost=currentCost,
                currentWeight=currentWeight,
                maxWeight=bounds.maxWeight,
            )
            
            if buildResult["success"]:
                containerBuilt = True  # Only set True when structural build succeeds
                for item in buildResult["items"]:
                    allItems.append(item)
                    usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                    excludeIds.add(item["id"])
                    logger.info(f"   📦 Container: {item['type']}: {item.get('quantity',1):.1f} x {item['unitPrice']:,.0f} = {item['totalValue']:,.0f}")
                
                currentWeight += buildResult["totalWeight"]
                currentCost += buildResult["totalCost"]
                logger.info(f"Phase 1b: Built container structure: +{buildResult['totalWeight']:.0f}kg, +{buildResult['totalCost']:,.0f}")
            else:
                # Structural build failed (low steel) but we still use consumables
                # because we're still fabricating (welding aluminum, cutting, etc.)
                logger.info(f"Phase 1b: Steel build failed, but adding consumables for fabrication")
            
            # ALWAYS add consumables when building - even if steel build fails
            # We're still welding, cutting, and assembling (maybe aluminum instead of steel)
            consumablesResult = self.containerBuilder.getConsumables(containerSize)
            if consumablesResult["items"]:
                for item in consumablesResult["items"]:
                    # Don't double-add if already included in buildResult
                    if item["id"] not in excludeIds:
                        allItems.append(item)
                        usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                        excludeIds.add(item["id"])
                        logger.info(f"   🔧 Consumable: {item['type']}: {item.get('quantity',1):.1f} x {item['unitPrice']:,.0f} = {item['totalValue']:,.0f}")
                
                currentWeight += consumablesResult["totalWeight"]
                currentCost += consumablesResult["totalCost"]
                logger.info(f"Phase 1c: Added consumables: +{consumablesResult['totalWeight']:.0f}kg, +{consumablesResult['totalCost']:,.0f}")
        elif containerType == "thung_xe_tai" and not buildContainer:
            # User already has truck body, skip container building
            # Add the existing container weight to current weight (no cost - already owned)
            # Use default weight if not specified
            effectiveWeight = existingContainerWeight if existingContainerWeight > 0 else DEFAULT_EXISTING_TRUCK_BODY_WEIGHT
            currentWeight += effectiveWeight
            logger.info(f"Phase 1b: Skipped - using existing truck body ({effectiveWeight:.0f} kg)")
        else:
            # Container 20ft / 40ft: Check inventory for pre-built
            prebuiltContainer = self._getPrebuiltContainer(containerType)
            
            if prebuiltContainer:
                allItems.append(prebuiltContainer)
                usedQty[prebuiltContainer["id"]] = 1
                excludeIds.add(prebuiltContainer["id"])
                currentWeight += prebuiltContainer["weight"]
                currentCost += prebuiltContainer["totalValue"]
                logger.info(f"Phase 1b: Using pre-built container: +{prebuiltContainer['weight']:.0f}kg")
            else:
                # No pre-built, build from materials
                containerSize = "40ft" if "40" in containerType else "20ft"
                self.containerBuilder.setSlatParams(slatType, thickness, containerLength)
                
                buildResult = self.containerBuilder.buildContainer(
                    containerSize=containerSize,
                    maxCost=bounds.maxCost,
                    currentCost=currentCost,
                    currentWeight=currentWeight,
                    maxWeight=bounds.maxWeight,
                )
                
                if buildResult["success"]:
                    containerBuilt = True  # Only set True when structural build succeeds
                    for item in buildResult["items"]:
                        allItems.append(item)
                        usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                        excludeIds.add(item["id"])
                    
                    currentWeight += buildResult["totalWeight"]
                    currentCost += buildResult["totalCost"]
                else:
                    # Structural build failed but we still use consumables
                    logger.info(f"Phase 1b: Steel build failed for {containerSize}, but adding consumables")
                
                # ALWAYS add consumables when building from materials
                consumablesResult = self.containerBuilder.getConsumables(containerSize)
                if consumablesResult["items"]:
                    for item in consumablesResult["items"]:
                        if item["id"] not in excludeIds:
                            allItems.append(item)
                            usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                            excludeIds.add(item["id"])
                            logger.info(f"   🔧 Consumable: {item['type']}: {item.get('quantity',1):.1f} x {item['unitPrice']:,.0f} = {item['totalValue']:,.0f}")
                    
                    currentWeight += consumablesResult["totalWeight"]
                    currentCost += consumablesResult["totalCost"]
        
        logger.info(f"After Phase 1: weight={currentWeight:.0f}kg, cost={currentCost:,.0f}")
        
        # ─────────────────────────────────────────────────────────────
        # Check feasibility with fixed items
        # ─────────────────────────────────────────────────────────────
        # Don't exclude types, only exclude specific IDs that were fully used
        # Pass usedQty to let weight filler account for partially used inventory
        materials = self.weightFiller.getAvailableMaterials(
            excludeIds=set(),  # Don't exclude any IDs - use usedQty instead
            excludeTypes=None,
        )
        
        feasibility = self.feasibilityChecker.checkFeasibility(
            bounds, currentCost, currentWeight, materials, usedQty, relaxedMode
        )
        
        # Track if we're in best-effort mode due to relaxed feasibility
        feasibilityWarning = feasibility.reason if feasibility.isWarning else None
        
        if not feasibility.feasible:
            # Auto-fallback: If normal mode fails, automatically retry with relaxed mode
            if not relaxedMode:
                logger.warning(f"⚠️ Normal mode infeasible: {feasibility.reason}")
                logger.warning(f"   Auto-enabling relaxed mode for best-effort result...")
                
                # Retry feasibility check with relaxed mode
                feasibility = self.feasibilityChecker.checkFeasibility(
                    bounds, currentCost, currentWeight, materials, usedQty, relaxedMode=True
                )
                feasibilityWarning = feasibility.reason if feasibility.isWarning else None
                
                # Add inventory shortage warning
                if feasibilityWarning:
                    feasibilityWarning = (
                        f"⚠️ INVENTORY SHORTAGE: {feasibilityWarning}. "
                        f"Running in best-effort mode to complete the order."
                    )
            
            # If still not feasible even in relaxed mode (shouldn't happen, but safety check)
            if not feasibility.feasible:
                logger.error(f"❌ Infeasible even in relaxed mode: {feasibility.reason}")
                logger.error(f"   Fixed items cost: {currentCost:,.0f} VND")
                logger.error(f"   Fixed items weight: {currentWeight:,.0f} kg")
                logger.error(f"   Max budget allowed: {bounds.maxCost:,.0f} VND")
                logger.error(f"   Min weight required: {bounds.minWeight:,.0f} kg")
                logger.error(f"   Max weight allowed: {bounds.maxWeight:,.0f} kg")
                logger.error(f"   Target margin: {bounds.targetMargin*100:.0f}%")
                logger.error(f"   Receipt price: {receiptPrice:,.0f} VND")
                logger.error("=" * 60)
                logger.error("💡 SUGGESTIONS:")
                if currentCost > bounds.maxCost:
                    logger.error("   → Increase receipt price significantly")
                    logger.error("   → Use cheaper walking floor model (KMD < KSD < R2DX)")
                    logger.error("   → Decrease target margin to allow more spending")
                else:
                    logger.error("   → Increase receipt price to allow more material purchase")
                    logger.error("   → Use cheaper walking floor model to free up budget")
                    logger.error("   → Decrease target margin to allow more spending on materials")
                logger.error("=" * 60)
                
                diagnosticInfo = {
                    "fixedItemsCost": currentCost,
                    "fixedItemsWeight": currentWeight,
                    "fixedItemsCount": len(allItems),
                    "maxBudget": bounds.maxCost,
                    "minWeight": bounds.minWeight,
                    "maxWeight": bounds.maxWeight,
                    "remainingBudget": bounds.maxCost - currentCost,
                    "weightNeeded": bounds.minWeight - currentWeight,
                }
                return self._buildResult(
                    [], 0, 0, receiptPrice, bounds,
                    containerBuilt, error=feasibility.reason,
                    diagnosticInfo=diagnosticInfo
                )
        
        # Log warning if in relaxed/best-effort mode
        if feasibilityWarning:
            logger.warning(f"⚠️ Best-effort mode: {feasibilityWarning}")
            logger.warning(f"   Continuing to fill what we can...")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 2: Weight-first filling (reach minWeight)
        # ─────────────────────────────────────────────────────────────
        logger.info("Phase 2: Weight-first filling")
        
        weightItems, currentWeight, currentCost, usedQty = self.weightFiller.fillToMinWeight(
            materials=materials,
            minWeight=bounds.minWeight,
            maxWeight=bounds.maxWeight,
            currentWeight=currentWeight,
            maxCost=bounds.maxCost,
            currentCost=currentCost,
            usedQty=usedQty,
        )
        
        allItems.extend(weightItems)
        excludeIds.update(item["id"] for item in weightItems)
        
        logger.info(f"After Phase 2: weight={currentWeight:.0f}kg, cost={currentCost:,.0f}")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 3: Margin tuning (hit target cost)
        # ─────────────────────────────────────────────────────────────
        logger.info("Phase 3: Margin tuning")
        
        tuningItems = self.marginTuner.getTuningItems(containerType, excludeIds)
        
        marginItems, currentWeight, currentCost, usedQty = self.marginTuner.tuneToTargetMargin(
            items=tuningItems,
            targetCost=bounds.targetCost,
            currentCost=currentCost,
            maxWeight=bounds.maxWeight,
            currentWeight=currentWeight,
            usedQty=usedQty,
        )
        
        allItems.extend(marginItems)
        
        logger.info(f"After Phase 3: weight={currentWeight:.0f}kg, cost={currentCost:,.0f}")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 4: Micro-adjust (swap cheap/heavy for expensive/light)
        # ─────────────────────────────────────────────────────────────
        costGap = bounds.targetCost - currentCost
        # Trigger Phase 4 if we still need significant cost and weight is near max
        if costGap > 1_000_000 and currentWeight >= bounds.minWeight:
            logger.info("Phase 4: Micro-adjusting (at weight limit, need more cost)")
            
            # Get all available items for swapping
            allAvailable = self.marginTuner.getTuningItems(containerType, set())
            
            allItems, currentWeight, currentCost = self.microAdjuster.adjustForMargin(
                currentItems=allItems,
                availableItems=allAvailable,
                targetCost=bounds.targetCost,
                currentCost=currentCost,
                maxWeight=bounds.maxWeight,
                currentWeight=currentWeight,
                usedQty=usedQty,
            )
            
            logger.info(f"After Phase 4: weight={currentWeight:.0f}kg, cost={currentCost:,.0f}")
        
        # ─────────────────────────────────────────────────────────────
        # Build final result
        # ─────────────────────────────────────────────────────────────
        return self._buildResult(
            allItems, currentWeight, currentCost, receiptPrice, bounds, containerBuilt,
            feasibilityWarning=feasibilityWarning,
        )

    def _getPrebuiltContainer(self, containerType: str) -> dict[str, Any] | None:
        """Get pre-built container from inventory."""
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

    def _buildResult(
        self,
        items: list[dict],
        totalWeight: float,
        totalCost: float,
        receiptPrice: float,
        bounds: OptimizationBounds,
        containerBuilt: bool,
        error: str = None,
        diagnosticInfo: dict = None,
        feasibilityWarning: str = None,
    ) -> dict[str, Any]:
        """
        Build the final result dictionary.
        
        For impossible cases (error), returns empty items list but includes
        diagnostic info for UI guidance.
        """
        profit = receiptPrice - totalCost
        profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0
        
        # Check if within bounds (with 0.5% tolerance for margin)
        marginTolerance = 0.5
        weightOk = bounds.minWeight <= totalWeight <= bounds.maxWeight
        marginOk = (bounds.minMargin * 100 - marginTolerance) <= profitMargin <= (bounds.maxMargin * 100 + marginTolerance)
        
        status = "ok" if weightOk and marginOk and not error else "warning"
        if error:
            status = "error"
            # For impossible cases, return empty items
            items = []
            totalWeight = 0
            totalCost = 0
            profit = 0
            profitMargin = 0
        
        logger.info("=" * 60)
        if error:
            logger.info(f"❌ Final: IMPOSSIBLE - {error}")
        elif feasibilityWarning:
            logger.info(f"⚠️ Final (relaxed mode): weight={totalWeight:.0f}kg, margin={profitMargin:.1f}%")
            logger.info(f"   Warning: {feasibilityWarning}")
        else:
            logger.info(f"✅ Final: weight={totalWeight:.0f}kg, margin={profitMargin:.1f}%")
        logger.info(f"   Weight OK: {weightOk} ({bounds.minWeight}-{bounds.maxWeight}kg)")
        logger.info(f"   Margin OK: {marginOk} ({bounds.minMargin*100:.0f}-{bounds.maxMargin*100:.0f}%)")
        logger.info("=" * 60)
        
        result = {
            "status": status,
            "items": items,
            "totalWeight": round(totalWeight, 2),
            "totalCost": round(totalCost, 2),
            "receiptPrice": receiptPrice,
            "profit": round(profit, 2),
            "profitMargin": round(profitMargin, 2),
            "containerBuiltFromMaterials": containerBuilt,
            "constraints": {
                "containerLength": bounds.containerLength,
                "targetWeight": bounds.targetWeight,
                "weightRange": [bounds.minWeight, bounds.maxWeight],
                "weightOk": weightOk,
                "targetProfitMargin": bounds.targetMargin * 100,
                "marginRange": [bounds.minMargin * 100, bounds.maxMargin * 100],
                "marginOk": marginOk,
            },
            "error": error,
            "warning": feasibilityWarning,  # Relaxed mode warning
        }
        
        # Add diagnostic info for impossible cases
        if diagnosticInfo:
            result["diagnostic"] = diagnosticInfo
        
        return result


def main():
    """Test OptimizerV2."""
    db = Database()
    optimizer = OptimizerV2(db)
    
    testCases = [
        ("mooc_long", 15.0, "KSD", "112mm", 700_000_000, 0.20),
        ("container_20ft", 6.096, "R2DX", "97mm", 350_000_000, 0.20),
        ("container_40ft", 12.192, "R2DX", "112mm", 900_000_000, 0.15),
    ]
    
    for containerType, length, model, slat, receipt, margin in testCases:
        print("\n" + "=" * 70)
        print(f"TEST: {containerType}, {length}m, {receipt/1e6:.0f}M, {margin*100:.0f}%")
        print("=" * 70)
        
        result = optimizer.optimize(
            containerLength=length,
            itemModelType=model,
            slatType=slat,
            receiptPrice=receipt,
            containerType=containerType,
            thickness=6,
            targetProfitMargin=margin,
        )
        
        print(f"\nResult: {result['status']}")
        print(f"  Weight: {result['totalWeight']:,.0f}kg (range: {result['constraints']['weightRange']}) {'✅' if result['constraints']['weightOk'] else '❌'}")
        print(f"  Margin: {result['profitMargin']:.1f}% (range: {result['constraints']['marginRange']}) {'✅' if result['constraints']['marginOk'] else '❌'}")
        print(f"  Items: {len(result['items'])}")
    
    db.close()


if __name__ == "__main__":
    main()

