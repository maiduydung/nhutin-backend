"""
Container BOM Optimizer V2.
4-Phase Constrained Feasibility Algorithm.

Phases:
0. Feasibility Check - Derive bounds, fail early if impossible
1. Fixed Items - Walking floor, aluminum, pump, oil (deterministic)
2. Weight Filling - Reach minWeight with structural materials
3. Margin Tuning - Add expensive/light items to hit target margin
"""
from typing import Any
from services.database import Database
from services.fixed_items import FixedItemsSelector
from services.container_builder import ContainerBuilder
from services.feasibility_checker import FeasibilityChecker, OptimizationBounds
from services.weight_filler import WeightFiller
from services.margin_tuner import MarginTuner
from config import (
    logger,
    CONTAINER_TYPES_WITHOUT_CONTAINER,
    CONTAINER_EMPTY_WEIGHTS,
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
        Main optimization function using 4-phase approach.
        """
        logger.info("=" * 60)
        logger.info(f"🚀 OptimizerV2: {containerType}, {containerLength}m")
        logger.info(f"   Receipt: {receiptPrice:,.0f}, Target margin: {targetProfitMargin*100:.0f}%")
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
        
        if containerType in CONTAINER_TYPES_WITHOUT_CONTAINER:
            # Mooc Long / Thung Xe Tai: Build structure from materials
            containerBuilt = True
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
                for item in buildResult["items"]:
                    allItems.append(item)
                    usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                    excludeIds.add(item["id"])
                
                currentWeight += buildResult["totalWeight"]
                currentCost += buildResult["totalCost"]
                logger.info(f"Phase 1b: Built container structure: +{buildResult['totalWeight']:.0f}kg")
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
                containerBuilt = True
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
                    for item in buildResult["items"]:
                        allItems.append(item)
                        usedQty[item["id"]] = usedQty.get(item["id"], 0) + item["quantity"]
                        excludeIds.add(item["id"])
                    
                    currentWeight += buildResult["totalWeight"]
                    currentCost += buildResult["totalCost"]
        
        logger.info(f"After Phase 1: weight={currentWeight:.0f}kg, cost={currentCost:,.0f}")
        
        # ─────────────────────────────────────────────────────────────
        # Check feasibility with fixed items
        # ─────────────────────────────────────────────────────────────
        materials = self.weightFiller.getAvailableMaterials(
            excludeIds=excludeIds,
            excludeTypes={"galvanized_sheet", "steel_box"} if containerBuilt else None,
        )
        
        feasibility = self.feasibilityChecker.checkFeasibility(
            bounds, currentCost, currentWeight, materials
        )
        
        if not feasibility.feasible:
            logger.error(f"❌ Infeasible: {feasibility.reason}")
            return self._buildResult(
                allItems, currentWeight, currentCost, receiptPrice, bounds,
                containerBuilt, error=feasibility.reason
            )
        
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
        # Build final result
        # ─────────────────────────────────────────────────────────────
        return self._buildResult(
            allItems, currentWeight, currentCost, receiptPrice, bounds, containerBuilt
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
    ) -> dict[str, Any]:
        """Build the final result dictionary."""
        profit = receiptPrice - totalCost
        profitMargin = (profit / receiptPrice) * 100 if receiptPrice > 0 else 0
        
        # Check if within bounds
        weightOk = bounds.minWeight <= totalWeight <= bounds.maxWeight
        marginOk = bounds.minMargin * 100 <= profitMargin <= bounds.maxMargin * 100
        
        status = "ok" if weightOk and marginOk and not error else "warning"
        if error:
            status = "error"
        
        logger.info("=" * 60)
        logger.info(f"✅ Final: weight={totalWeight:.0f}kg, margin={profitMargin:.1f}%")
        logger.info(f"   Weight OK: {weightOk} ({bounds.minWeight}-{bounds.maxWeight}kg)")
        logger.info(f"   Margin OK: {marginOk} ({bounds.minMargin*100:.0f}-{bounds.maxMargin*100:.0f}%)")
        logger.info("=" * 60)
        
        return {
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
        }


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

