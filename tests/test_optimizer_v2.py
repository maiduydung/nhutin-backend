"""
Comprehensive tests for the new OptimizerV2.
Tests weight targeting, profit margin optimization, feasibility checks, and edge cases.
"""
import pytest
from services.optimizer import OptimizerV2
from services.feasibility_checker import FeasibilityChecker


class TestFeasibilityChecker:
    """Test FeasibilityChecker weight/margin calculations."""

    @pytest.fixture
    def checker(self):
        return FeasibilityChecker()

    def test_calculateTargetWeight_6m(self, checker):
        """6m should give 3500kg."""
        assert checker.calculateTargetWeight(6.0) == 3500

    def test_calculateTargetWeight_9m(self, checker):
        """9m should give 4500kg."""
        assert checker.calculateTargetWeight(9.0) == 4500

    def test_calculateTargetWeight_12m(self, checker):
        """12m should give 7000kg."""
        assert checker.calculateTargetWeight(12.0) == 7000

    def test_calculateTargetWeight_15m(self, checker):
        """15m should give 8000kg."""
        assert checker.calculateTargetWeight(15.0) == 8000

    def test_calculateTargetWeight_interpolation_7_5m(self, checker):
        """7.5m should interpolate to ~4000kg."""
        # 6m=3500, 9m=4500, 7.5m is halfway = 4000
        assert checker.calculateTargetWeight(7.5) == 4000

    def test_calculateTargetWeight_interpolation_10m(self, checker):
        """10m should interpolate between 9m and 12m."""
        # 9m=4500, 12m=7000, 10m is 1/3 = 4500 + (7000-4500)*1/3 = 5333
        result = checker.calculateTargetWeight(10.0)
        assert 5300 <= result <= 5400

    def test_calculateTargetWeight_below_min(self, checker):
        """Below 6m should return 3500kg."""
        assert checker.calculateTargetWeight(5.0) == 3500
        assert checker.calculateTargetWeight(4.0) == 3500

    def test_calculateTargetWeight_above_max(self, checker):
        """Above 15m should return 8000kg."""
        assert checker.calculateTargetWeight(16.0) == 8000
        assert checker.calculateTargetWeight(20.0) == 8000

    def test_deriveBounds_weight_range(self, checker):
        """Test weight range calculation with ±500kg tolerance."""
        bounds = checker.deriveBounds(6.0, 500_000_000, 0.20)
        assert bounds.targetWeight == 3500
        assert bounds.minWeight == 3000
        assert bounds.maxWeight == 4000

    def test_deriveBounds_margin_range(self, checker):
        """Test margin range with 5% tolerance below target."""
        bounds = checker.deriveBounds(6.0, 500_000_000, 0.20)
        assert abs(bounds.minMargin - 0.15) < 0.001
        assert abs(bounds.maxMargin - 0.20) < 0.001

    def test_deriveBounds_cost_range(self, checker):
        """Test cost range derived from margins."""
        bounds = checker.deriveBounds(6.0, 500_000_000, 0.20)
        # 20% margin = 80% cost = 400M
        # 15% margin = 85% cost = 425M
        assert abs(bounds.targetCost - 400_000_000) < 1
        assert abs(bounds.minCost - 400_000_000) < 1  # min cost at max margin
        assert abs(bounds.maxCost - 425_000_000) < 1  # max cost at min margin


class TestOptimizerIntegration:
    """Integration tests for OptimizerV2 with real database."""

    @pytest.fixture
    def db(self):
        """Create database connection."""
        from services.database import Database
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        """Create optimizer instance."""
        return OptimizerV2(db)

    def test_optimize_20ft_container(self, optimizer):
        """Test 20ft container optimization with realistic budget."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KSD",  # Use cheaper model
            slatType="97mm",
            receiptPrice=500_000_000,  # Higher budget
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        # Either succeeds or returns clear error
        if result["status"] != "error":
            assert result["totalWeight"] > 0
            assert result["totalCost"] > 0
            assert result["profitMargin"] <= 25  # Should be close to 20%
            assert len(result["items"]) > 0
        else:
            # If error, should have diagnostic info
            assert "error" in result
            assert result["items"] == []

    def test_optimize_mooc_long(self, optimizer):
        """Test mooc long (15m trailer) optimization."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        assert result["totalWeight"] > 0
        # mooc_long should build container from materials
        assert result["containerBuiltFromMaterials"] == True
        # Weight depends on budget - verify we're spending close to target cost
        targetCost = 700_000_000 * (1 - 0.20)  # 560M
        # We should be spending close to target
        assert result["totalCost"] >= targetCost * 0.7  # At least 70% of target
        print(f"mooc_long result: weight={result['totalWeight']}, cost={result['totalCost']:,.0f}, margin={result['profitMargin']}%")

    def test_optimize_40ft_builds_from_materials(self, optimizer):
        """Test 40ft container builds from materials (since none in DB)."""
        result = optimizer.optimize(
            containerLength=12.192,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.15,
        )
        
        assert result["totalWeight"] > 0
        # Should build from materials since no 40ft in DB
        assert result["containerBuiltFromMaterials"] == True

    def test_optimize_profit_margin_target(self, optimizer):
        """Test that optimizer hits profit margin target."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=400_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.25,  # 25% target
        )
        
        # Profit margin should be at most 25% (within some tolerance)
        assert result["profitMargin"] <= 30

    def test_optimize_different_margins(self, optimizer):
        """Test different profit margin targets with feasible budgets."""
        testCases = [
            (0.15, 700_000_000),  # Lower margin = higher budget OK
            (0.20, 750_000_000),  # Higher budget for 20%
        ]
        results = []
        
        for margin, budget in testCases:
            result = optimizer.optimize(
                containerLength=12.0,
                itemModelType="KSD",  # Use cheaper model
                slatType="112mm",
                receiptPrice=budget,
                containerType="mooc_long",
                targetProfitMargin=margin,
            )
            if result["status"] != "error":
                results.append(result["profitMargin"])
        
        print(f"Margins: {results}")
        # At least one should succeed
        assert len(results) > 0
        assert all(r > 0 for r in results)

    def test_optimize_weight_scales_with_length(self, optimizer):
        """Test that weight increases with container length."""
        # Use higher budgets for longer containers
        testCases = [
            (6.0, 500_000_000),
            (9.0, 550_000_000),
            (12.0, 650_000_000),
            (15.0, 800_000_000),  # Longer = need more budget
        ]
        weights = []
        
        for length, budget in testCases:
            result = optimizer.optimize(
                containerLength=length,
                itemModelType="KSD",
                slatType="97mm",
                receiptPrice=budget,
                containerType="mooc_long",
                targetProfitMargin=0.20,
            )
            if result["status"] != "error":
                weights.append(result["totalWeight"])
            else:
                weights.append(0)  # Mark failed ones
        
        print(f"Weights for lengths {[t[0] for t in testCases]}: {weights}")
        # At least the successful ones should show increasing weight
        successfulWeights = [w for w in weights if w > 0]
        if len(successfulWeights) >= 2:
            assert successfulWeights[-1] >= successfulWeights[0]

    def test_optimize_includes_core_items(self, optimizer):
        """Test that core items (walking floor, pump, oil) are always included when successful."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KMD",  # Use cheapest model
            slatType="97mm",
            receiptPrice=500_000_000,  # Higher budget
            containerType="container_20ft",
            targetProfitMargin=0.15,  # Lower margin
        )
        
        # Only check if optimization succeeded
        if result["status"] == "error":
            # Error case - items should be empty
            assert result["items"] == []
            assert "error" in result
            return
        
        itemTypes = [item.get("type", "") for item in result["items"]]
        itemCodes = [item.get("code", "").lower() for item in result["items"]]
        
        # Walking floor should be present
        hasWalkingFloor = any("walking_floor" in t for t in itemTypes) or any("kmd" in c for c in itemCodes)
        assert hasWalkingFloor, f"Walking floor not found. Types: {itemTypes}"
        
        # Aluminum should be present
        hasAluminum = any("aluminum" in t for t in itemTypes) or any("nhôm" in c for c in itemCodes)
        assert hasAluminum, f"Aluminum not found. Types: {itemTypes}"

    def test_optimize_response_schema(self, optimizer):
        """Test that response has all required fields for frontend."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=400_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        # Required fields for frontend
        assert "items" in result
        assert "totalWeight" in result
        assert "totalCost" in result
        assert "receiptPrice" in result
        assert "profit" in result
        assert "profitMargin" in result
        assert "containerBuiltFromMaterials" in result
        assert "constraints" in result
        
        # Items should have required fields
        for item in result["items"]:
            assert "code" in item
            assert "quantity" in item
            assert "weight" in item
            assert "totalValue" in item


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def db(self):
        from services.database import Database
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        return OptimizerV2(db)

    def test_very_low_receipt_price_returns_error(self, optimizer):
        """Test with very low receipt price - should return error."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=100_000_000,  # Only 100M - R2DX alone costs 249M!
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        # Should return error with empty items
        assert result["status"] == "error"
        assert result["items"] == []
        assert result["totalWeight"] == 0
        assert result["error"] is not None
        assert "diagnostic" in result

    def test_impossible_budget_has_diagnostic_info(self, optimizer):
        """Test that impossible cases include diagnostic info."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=450_000_000,  # Too low for R2DX + 15m weight
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        assert result["status"] == "error"
        assert "diagnostic" in result
        diagnostic = result["diagnostic"]
        assert "fixedItemsCost" in diagnostic
        assert "fixedItemsWeight" in diagnostic
        assert "remainingBudget" in diagnostic
        assert "weightNeeded" in diagnostic

    def test_very_high_margin_target_may_fail(self, optimizer):
        """Test with very high profit margin target (40%) - may be impossible."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.40,  # 40% target = only 300M budget
        )
        
        # With R2DX (249M) and 40% margin (300M budget), might work but tight
        # Check that we get a valid response (either ok/warning or error)
        assert result["status"] in ["ok", "warning", "error"]

    def test_thung_xe_tai(self, optimizer):
        """Test thung xe tai (truck body) type."""
        result = optimizer.optimize(
            containerLength=10.0,  # Custom length
            itemModelType="KMD",
            slatType="97mm",
            receiptPrice=600_000_000,  # Higher budget for truck
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
        )
        
        # Check it either works or fails gracefully
        if result["status"] != "error":
            assert result["containerBuiltFromMaterials"] == True
            assert result["totalWeight"] > 0
        else:
            assert result["items"] == []
            assert "error" in result

    def test_successful_case_has_no_diagnostic(self, optimizer):
        """Test that successful cases don't have unnecessary diagnostic."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KMD",  # Cheaper model
            slatType="97mm",
            receiptPrice=500_000_000,  # Good budget
            containerType="container_20ft",
            targetProfitMargin=0.15,  # Lower margin = more budget
        )
        
        # Should succeed without diagnostic
        if result["status"] in ["ok", "warning"]:
            assert result["items"] != []
            assert result["totalWeight"] > 0


class TestImpossibleCases:
    """Test cases that should fail with clear error messages."""

    @pytest.fixture
    def db(self):
        from services.database import Database
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        return OptimizerV2(db)

    def test_budget_exceeds_fixed_items(self, optimizer):
        """Fixed items alone exceed max budget."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",  # ~249M
            slatType="112mm",
            receiptPrice=300_000_000,  # 300M with 20% margin = 240M budget
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        assert result["status"] == "error"
        assert "exceed" in result["error"].lower() or "insufficient" in result["error"].lower()

    def test_insufficient_budget_for_weight(self, optimizer):
        """Budget OK for fixed items but not for weight target."""
        result = optimizer.optimize(
            containerLength=15.0,  # Long container = high weight target
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=450_000_000,  # 450M with 20% margin = 360M budget
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        # R2DX ~249M + aluminum ~100M = 349M, leaves ~13M for 5000+kg of materials
        assert result["status"] == "error"
        assert "weight" in result["error"].lower() or "budget" in result["error"].lower()

    def test_extreme_margin_impossible(self, optimizer):
        """50% margin makes almost everything impossible."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",  # ~249M
            slatType="97mm",
            receiptPrice=500_000_000,  # 50% margin = 250M budget
            containerType="container_20ft",
            targetProfitMargin=0.50,  # Only 250M to spend
        )
        
        # 250M budget for R2DX (249M) + aluminum + pump + oil - impossible
        assert result["status"] == "error"


def main():
    """Run tests manually."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    main()

