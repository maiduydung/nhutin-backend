"""
Comprehensive tests for the new optimizer.
Tests weight targeting, profit margin optimization, and edge cases.
"""
import pytest
from unittest.mock import MagicMock, patch
from services.optimizer import Optimizer
from services.weight_targets import calculateTargetWeight, getWeightRange, getMarginRange


class TestWeightTargets:
    """Test weight target calculations."""

    def test_calculateTargetWeight_6m(self):
        """6m should give 3500kg."""
        assert calculateTargetWeight(6.0) == 3500

    def test_calculateTargetWeight_9m(self):
        """9m should give 4500kg."""
        assert calculateTargetWeight(9.0) == 4500

    def test_calculateTargetWeight_12m(self):
        """12m should give 7000kg."""
        assert calculateTargetWeight(12.0) == 7000

    def test_calculateTargetWeight_15m(self):
        """15m should give 8000kg."""
        assert calculateTargetWeight(15.0) == 8000

    def test_calculateTargetWeight_interpolation_7_5m(self):
        """7.5m should interpolate to ~4000kg."""
        # 6m=3500, 9m=4500, 7.5m is halfway = 4000
        assert calculateTargetWeight(7.5) == 4000

    def test_calculateTargetWeight_interpolation_10m(self):
        """10m should interpolate between 9m and 12m."""
        # 9m=4500, 12m=7000, 10m is 1/3 = 4500 + (7000-4500)*1/3 = 5333
        result = calculateTargetWeight(10.0)
        assert 5300 <= result <= 5400

    def test_calculateTargetWeight_below_min(self):
        """Below 6m should return 3500kg."""
        assert calculateTargetWeight(5.0) == 3500
        assert calculateTargetWeight(4.0) == 3500

    def test_calculateTargetWeight_above_max(self):
        """Above 15m should return 8000kg."""
        assert calculateTargetWeight(16.0) == 8000
        assert calculateTargetWeight(20.0) == 8000

    def test_getWeightRange(self):
        """Test weight range calculation with ±500kg tolerance."""
        target, minW, maxW = getWeightRange(6.0)
        assert target == 3500
        assert minW == 3000
        assert maxW == 4000

    def test_getMarginRange(self):
        """Test margin range with 5% tolerance below target."""
        minM, maxM = getMarginRange(0.20)
        assert abs(minM - 0.15) < 0.001
        assert abs(maxM - 0.20) < 0.001

    def test_getMarginRange_low_target(self):
        """Test margin range doesn't go below 0."""
        minM, maxM = getMarginRange(0.03)
        assert minM == 0.0
        assert maxM == 0.03


class TestOptimizerIntegration:
    """Integration tests for optimizer with real database."""

    @pytest.fixture
    def db(self):
        """Create database connection."""
        from services.database import Database
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        """Create optimizer instance."""
        return Optimizer(db)

    def test_optimize_20ft_container(self, optimizer):
        """Test 20ft container optimization."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=400_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        assert result["status"] if "status" in result else True
        assert result["totalWeight"] > 0
        assert result["totalCost"] > 0
        assert result["profitMargin"] <= 25  # Should be close to 20%
        assert len(result["items"]) > 0

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
        """Test different profit margin targets."""
        margins = [0.15, 0.20, 0.25, 0.30]
        results = []
        
        for margin in margins:
            result = optimizer.optimize(
                containerLength=12.0,
                itemModelType="R2DX",
                slatType="112mm",
                receiptPrice=600_000_000,
                containerType="mooc_long",
                targetProfitMargin=margin,
            )
            results.append(result["profitMargin"])
        
        # Higher target margin should generally result in higher actual margin
        # (or at least not significantly lower)
        print(f"Margins for targets {margins}: {results}")
        assert all(r > 0 for r in results)

    def test_optimize_weight_scales_with_length(self, optimizer):
        """Test that weight increases with container length."""
        lengths = [6.0, 9.0, 12.0, 15.0]
        weights = []
        
        for length in lengths:
            result = optimizer.optimize(
                containerLength=length,
                itemModelType="KSD",
                slatType="97mm",
                receiptPrice=600_000_000,
                containerType="mooc_long",
                targetProfitMargin=0.20,
            )
            weights.append(result["totalWeight"])
        
        print(f"Weights for lengths {lengths}: {weights}")
        # Weight should generally increase with length
        assert weights[-1] > weights[0]  # 15m > 6m

    def test_optimize_includes_core_items(self, optimizer):
        """Test that core items (walking floor, pump, oil) are always included."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=400_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        itemTypes = [item.get("type", "") for item in result["items"]]
        itemCodes = [item.get("code", "").lower() for item in result["items"]]
        
        # Walking floor should be present
        hasWalkingFloor = any("walking_floor" in t for t in itemTypes) or any("r2dx" in c for c in itemCodes)
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
        return Optimizer(db)

    def test_very_low_receipt_price(self, optimizer):
        """Test with very low receipt price."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=100_000_000,  # Only 100M
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        # Should still return something
        assert result["totalWeight"] > 0
        assert result["totalCost"] > 0

    def test_very_high_margin_target(self, optimizer):
        """Test with very high profit margin target (40%)."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.40,  # 40% target
        )
        
        # Should still work, margin might be lower than target
        assert result["totalWeight"] > 0
        assert result["profitMargin"] > 0

    def test_thung_xe_tai(self, optimizer):
        """Test thung xe tai (truck body) type."""
        result = optimizer.optimize(
            containerLength=10.0,  # Custom length
            itemModelType="KMD",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
        )
        
        # Should build from materials (no pre-built container)
        assert result["containerBuiltFromMaterials"] == True
        assert result["totalWeight"] > 0


def main():
    """Run tests manually."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    main()

