"""
Phase 0: Feasibility Checker.
Derives hard bounds and checks if optimization is possible BEFORE attempting it.
Fails early with clear explanations when constraints are impossible.
"""
from dataclasses import dataclass
from typing import Any
from config import logger


@dataclass
class OptimizationBounds:
    """Hard bounds derived from user inputs."""
    # Weight bounds (from container length)
    targetWeight: int
    minWeight: int
    maxWeight: int
    
    # Cost bounds (from receipt price and margin)
    targetCost: float
    maxCost: float  # Maximum we can spend (receiptPrice × (1 - minMargin))
    minCost: float  # Minimum we need to spend (receiptPrice × (1 - maxMargin))
    
    # Input values for reference
    receiptPrice: float
    targetMargin: float
    minMargin: float
    maxMargin: float
    containerLength: float
    
    def __str__(self) -> str:
        return (
            f"Bounds(weight={self.minWeight}-{self.maxWeight}kg, "
            f"cost={self.minCost/1e6:.1f}M-{self.maxCost/1e6:.1f}M, "
            f"margin={self.minMargin*100:.0f}-{self.maxMargin*100:.0f}%)"
        )


@dataclass
class FeasibilityResult:
    """Result of feasibility check."""
    feasible: bool
    bounds: OptimizationBounds | None
    reason: str | None = None
    fixedCost: float = 0
    fixedWeight: float = 0


class FeasibilityChecker:
    """
    Checks if optimization is feasible before attempting it.
    
    This eliminates 80% of edge cases by failing early with clear explanations.
    """
    
    # Weight guideposts: length (m) → target weight (kg)
    WEIGHT_GUIDEPOSTS = [
        (6.0, 3500),   # 6m → 3.5 tons
        (9.0, 4500),   # 9m → 4.5 tons
        (12.0, 7000),  # 12m → 7 tons
        (15.0, 8000),  # 15m → 8 tons
    ]
    
    WEIGHT_TOLERANCE = 500  # ±500kg acceptable range
    MARGIN_TOLERANCE = 0.05  # 5% breathing room (margin can be lower than target)
    MIN_ALLOWED_MARGIN = 0.05  # Never go below 5% profit
    
    def calculateTargetWeight(self, containerLength: float) -> int:
        """Linear interpolation between guideposts."""
        if containerLength <= self.WEIGHT_GUIDEPOSTS[0][0]:
            return self.WEIGHT_GUIDEPOSTS[0][1]
        if containerLength >= self.WEIGHT_GUIDEPOSTS[-1][0]:
            return self.WEIGHT_GUIDEPOSTS[-1][1]
        
        for i in range(len(self.WEIGHT_GUIDEPOSTS) - 1):
            len1, w1 = self.WEIGHT_GUIDEPOSTS[i]
            len2, w2 = self.WEIGHT_GUIDEPOSTS[i + 1]
            
            if len1 <= containerLength <= len2:
                ratio = (containerLength - len1) / (len2 - len1)
                return int(round(w1 + ratio * (w2 - w1)))
        
        return self.WEIGHT_GUIDEPOSTS[-1][1]
    
    def deriveBounds(
        self,
        containerLength: float,
        receiptPrice: float,
        targetMargin: float,
    ) -> OptimizationBounds:
        """
        Phase 0: Derive all hard bounds from inputs.
        
        This creates the "feasibility rectangle" that the optimizer must hit.
        """
        # Weight bounds from container length
        targetWeight = self.calculateTargetWeight(containerLength)
        minWeight = targetWeight - self.WEIGHT_TOLERANCE
        maxWeight = targetWeight + self.WEIGHT_TOLERANCE
        
        # Margin bounds (can be slightly lower than target, but not higher)
        maxMargin = targetMargin  # Never exceed target margin
        minMargin = max(self.MIN_ALLOWED_MARGIN, targetMargin - self.MARGIN_TOLERANCE)
        
        # Cost bounds from margin bounds
        # Higher margin = lower cost, lower margin = higher cost
        targetCost = receiptPrice * (1 - targetMargin)
        maxCost = receiptPrice * (1 - minMargin)  # Minimum margin = maximum cost
        minCost = receiptPrice * (1 - maxMargin)  # Maximum margin = minimum cost
        
        return OptimizationBounds(
            targetWeight=targetWeight,
            minWeight=minWeight,
            maxWeight=maxWeight,
            targetCost=targetCost,
            maxCost=maxCost,
            minCost=minCost,
            receiptPrice=receiptPrice,
            targetMargin=targetMargin,
            minMargin=minMargin,
            maxMargin=maxMargin,
            containerLength=containerLength,
        )
    
    def checkFeasibility(
        self,
        bounds: OptimizationBounds,
        fixedCost: float,
        fixedWeight: float,
        availableMaterials: list[dict[str, Any]],
        usedQty: dict[int, int] = None,
    ) -> FeasibilityResult:
        """
        Check if it's possible to hit the feasibility rectangle.
        
        Returns FeasibilityResult with:
        - feasible: bool
        - reason: explanation if not feasible
        """
        usedQty = usedQty or {}
        
        logger.info(f"🔍 Checking feasibility: {bounds}")
        logger.info(f"   Fixed items: {fixedWeight:.0f}kg, {fixedCost:,.0f} VND")
        
        # Check 1: Fixed items already exceed constraints
        if fixedWeight > bounds.maxWeight:
            return FeasibilityResult(
                feasible=False,
                bounds=bounds,
                reason=f"Fixed items ({fixedWeight:.0f}kg) exceed max weight ({bounds.maxWeight}kg)",
                fixedCost=fixedCost,
                fixedWeight=fixedWeight,
            )
        
        if fixedCost > bounds.maxCost:
            return FeasibilityResult(
                feasible=False,
                bounds=bounds,
                reason=f"Fixed items ({fixedCost:,.0f}) exceed max budget ({bounds.maxCost:,.0f})",
                fixedCost=fixedCost,
                fixedWeight=fixedWeight,
            )
        
        # Check 2: Can we reach minimum weight with available materials?
        weightNeeded = bounds.minWeight - fixedWeight
        totalAvailableWeight = sum(
            max(0, m["availableQty"] - usedQty.get(m["id"], 0)) * m["weightPerUnit"] 
            for m in availableMaterials
            if m["weightPerUnit"] > 0
        )
        
        if weightNeeded > 0 and totalAvailableWeight < weightNeeded:
            return FeasibilityResult(
                feasible=False,
                bounds=bounds,
                reason=f"Not enough materials to reach min weight. Need {weightNeeded:.0f}kg more, only {totalAvailableWeight:.0f}kg available in inventory",
                fixedCost=fixedCost,
                fixedWeight=fixedWeight,
            )
        
        # Check 3: Do we have enough BUDGET to buy materials to reach min weight?
        # This is critical - materials may exist but we may not be able to afford them
        remainingBudget = bounds.maxCost - fixedCost
        
        if weightNeeded > 0:
            # Calculate minimum cost to add the weight needed
            # Sort materials by cost-per-kg (cheapest first) to get best case
            weightedMaterials = [
                m for m in availableMaterials 
                if m["weightPerUnit"] > 0 and m["unitPrice"] > 0
            ]
            weightedMaterials.sort(key=lambda m: m["unitPrice"] / m["weightPerUnit"])
            
            minCostToReachWeight = 0
            weightStillNeeded = weightNeeded
            
            for m in weightedMaterials:
                availableQty = max(0, m["availableQty"] - usedQty.get(m["id"], 0))
                weightPerUnit = m["weightPerUnit"]
                unitPrice = m["unitPrice"]
                
                if availableQty <= 0 or weightPerUnit <= 0:
                    continue
                
                # How much of this material do we need?
                qtyNeeded = weightStillNeeded / weightPerUnit
                qtyToUse = min(qtyNeeded, availableQty)
                
                minCostToReachWeight += qtyToUse * unitPrice
                weightStillNeeded -= qtyToUse * weightPerUnit
                
                if weightStillNeeded <= 0:
                    break
            
            if minCostToReachWeight > remainingBudget:
                return FeasibilityResult(
                    feasible=False,
                    bounds=bounds,
                    reason=(
                        f"Insufficient budget to reach weight target. "
                        f"Fixed items cost {fixedCost:,.0f} VND, leaving only {remainingBudget:,.0f} VND. "
                        f"Need {weightNeeded:,.0f}kg more which costs at least {minCostToReachWeight:,.0f} VND"
                    ),
                    fixedCost=fixedCost,
                    fixedWeight=fixedWeight,
                )
        
        # Check 4: Can we spend enough to reach margin target?
        costNeeded = bounds.minCost - fixedCost
        totalAvailableCost = sum(
            max(0, m["availableQty"] - usedQty.get(m["id"], 0)) * m["unitPrice"]
            for m in availableMaterials
            if m["unitPrice"] > 0
        )
        
        if costNeeded > 0 and totalAvailableCost < costNeeded:
            return FeasibilityResult(
                feasible=False,
                bounds=bounds,
                reason=f"Not enough materials to reach margin target. Need to spend {costNeeded:,.0f} more, only {totalAvailableCost:,.0f} available",
                fixedCost=fixedCost,
                fixedWeight=fixedWeight,
            )
        
        logger.info(f"   ✅ Feasibility check passed")
        return FeasibilityResult(
            feasible=True,
            bounds=bounds,
            fixedCost=fixedCost,
            fixedWeight=fixedWeight,
        )


def main():
    """Test feasibility checker."""
    checker = FeasibilityChecker()
    
    testCases = [
        (15.0, 700_000_000, 0.20),
        (6.096, 350_000_000, 0.20),
        (12.0, 550_000_000, 0.15),
    ]
    
    for length, receipt, margin in testCases:
        bounds = checker.deriveBounds(length, receipt, margin)
        print(f"\nLength: {length}m, Receipt: {receipt/1e6:.0f}M, Margin: {margin*100:.0f}%")
        print(f"  Weight: {bounds.minWeight}-{bounds.maxWeight}kg (target: {bounds.targetWeight})")
        print(f"  Cost: {bounds.minCost/1e6:.1f}M-{bounds.maxCost/1e6:.1f}M (target: {bounds.targetCost/1e6:.1f}M)")
        print(f"  Margin: {bounds.minMargin*100:.0f}-{bounds.maxMargin*100:.0f}%")


if __name__ == "__main__":
    main()

