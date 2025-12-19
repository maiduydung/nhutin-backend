"""
Scenario-based tests for optimizer.
Tests real-world use cases with various parameter combinations.
"""
import pytest
from services.database import Database
from services.optimizer import Optimizer
from services.weight_targets import getWeightRange, WEIGHT_TOLERANCE


class TestContainerScenarios:
    """Test various container type scenarios."""

    @pytest.fixture
    def optimizer(self):
        return Optimizer(Database())

    # =========================================================================
    # CONTAINER_20FT SCENARIOS
    # =========================================================================

    def test_container_20ft_small_budget(self, optimizer):
        """20ft with 300M should still meet weight."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=300_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(6.096)
        print(f"\n20ft small budget: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        assert result["totalWeight"] >= minW

    def test_container_20ft_medium_budget(self, optimizer):
        """20ft with 500M - may hit physical limit before spending budget."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(6.096)
        print(f"\n20ft medium budget: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        # Weight should be met
        assert result["totalWeight"] >= minW
        # Margin may be higher than target if we hit physical weight limit
        # 6m container can only fit ~6000kg, but 500M budget could buy more

    def test_container_20ft_large_budget(self, optimizer):
        """20ft with 800M should hit weight and have good margin."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=800_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.15,
        )
        target, minW, maxW = getWeightRange(6.096)
        print(f"\n20ft large budget: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        assert result["totalWeight"] >= minW

    # =========================================================================
    # CONTAINER_40FT SCENARIOS
    # =========================================================================

    def test_container_40ft_standard_12m(self, optimizer):
        """Standard 40ft (12.192m) with reasonable budget."""
        result = optimizer.optimize(
            containerLength=12.192,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=8,
            receiptPrice=700_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(12.192)
        print(f"\n40ft standard: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["totalWeight"] >= minW

    def test_container_40ft_tight_budget(self, optimizer):
        """40ft with tight budget (500M)."""
        result = optimizer.optimize(
            containerLength=12.192,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=8,
            receiptPrice=500_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(12.192)
        print(f"\n40ft tight budget: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        # Weight is prioritized, margin may be low
        assert result["totalWeight"] >= minW

    def test_container_40ft_large_budget(self, optimizer):
        """40ft with large budget (1B)."""
        result = optimizer.optimize(
            containerLength=12.192,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=1_000_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(12.192)
        print(f"\n40ft large budget: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["totalWeight"] >= minW
        assert 15 <= result["profitMargin"] <= 25

    # =========================================================================
    # MOOC_LONG SCENARIOS (always builds container)
    # =========================================================================

    def test_mooc_long_9m(self, optimizer):
        """Mooc long 9m."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(9.0)
        print(f"\nMooc long 9m: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["containerBuiltFromMaterials"] is True
        assert result["totalWeight"] >= minW

    def test_mooc_long_12m(self, optimizer):
        """Mooc long 12m."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(12.0)
        print(f"\nMooc long 12m: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["containerBuiltFromMaterials"] is True
        assert result["totalWeight"] >= minW

    def test_mooc_long_15m(self, optimizer):
        """Mooc long 15m (largest)."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=900_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(15.0)
        print(f"\nMooc long 15m: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["containerBuiltFromMaterials"] is True
        assert result["totalWeight"] >= minW

    # =========================================================================
    # THUNG_XE_TAI SCENARIOS
    # =========================================================================

    def test_thung_xe_tai_8m(self, optimizer):
        """Truck body 8m."""
        result = optimizer.optimize(
            containerLength=8.0,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
        )
        target, minW, maxW = getWeightRange(8.0)
        print(f"\nThung xe tai 8m: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), margin={result['profitMargin']:.1f}%")
        assert result["containerBuiltFromMaterials"] is True
        assert result["totalWeight"] >= minW


class TestProfitMarginScenarios:
    """Test different profit margin targets."""

    @pytest.fixture
    def optimizer(self):
        return Optimizer(Database())

    def test_margin_5_percent(self, optimizer):
        """5% margin target - should spend almost all budget."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.05,
        )
        print(f"\n5% margin target: actual={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW
        # With low margin target, should be close
        assert result["profitMargin"] <= 15

    def test_margin_10_percent(self, optimizer):
        """10% margin target."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.10,
        )
        print(f"\n10% margin target: actual={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW

    def test_margin_20_percent(self, optimizer):
        """20% margin target (default)."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\n20% margin target: actual={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW
        assert 15 <= result["profitMargin"] <= 25

    def test_margin_30_percent(self, optimizer):
        """30% margin target - tighter budget."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.30,
        )
        print(f"\n30% margin target: actual={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW


class TestItemModelScenarios:
    """Test different item model types."""

    @pytest.fixture
    def optimizer(self):
        return Optimizer(Database())

    def test_model_ksd(self, optimizer):
        """KSD model type."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\nKSD model: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW
        # Should have walking_floor item with ksd
        walkingFloors = [i for i in result["items"] if "walking_floor" in i["type"]]
        assert len(walkingFloors) == 1

    def test_model_kmd(self, optimizer):
        """KMD model type."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="KMD",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\nKMD model: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW

    def test_model_r2dx(self, optimizer):
        """R2DX model type."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\nR2DX model: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW


class TestSlatThicknessScenarios:
    """Test slat type and thickness combinations."""

    @pytest.fixture
    def optimizer(self):
        return Optimizer(Database())

    def test_97mm_6mm(self, optimizer):
        """97mm slat, 6mm thickness."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="R2DX",
            slatType="97mm",
            thickness=6,
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\n97mm/6mm: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(9.0)
        assert result["totalWeight"] >= minW

    def test_112mm_6mm(self, optimizer):
        """112mm slat, 6mm thickness."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=6,
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\n112mm/6mm: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(9.0)
        assert result["totalWeight"] >= minW

    def test_112mm_8mm(self, optimizer):
        """112mm slat, 8mm thickness."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=8,
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        print(f"\n112mm/8mm: weight={result['totalWeight']:.0f}kg, margin={result['profitMargin']:.1f}%")
        target, minW, maxW = getWeightRange(9.0)
        assert result["totalWeight"] >= minW


class TestResponseSchema:
    """Test that response schema is correct for frontend."""

    @pytest.fixture
    def optimizer(self):
        return Optimizer(Database())

    def test_response_has_required_fields(self, optimizer):
        """Response should have all required fields for frontend."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        # Required top-level fields
        assert "items" in result
        assert "totalWeight" in result
        assert "totalCost" in result
        assert "receiptPrice" in result
        assert "profit" in result
        assert "profitMargin" in result
        assert "containerBuiltFromMaterials" in result
        assert "constraints" in result
        
        # Items should be a list
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        
        # Each item should have required fields
        for item in result["items"]:
            assert "id" in item
            assert "code" in item
            assert "name" in item
            assert "unit" in item
            assert "type" in item
            assert "quantity" in item
            assert "unitPrice" in item
            assert "totalValue" in item
            assert "weight" in item

    def test_constraints_field_structure(self, optimizer):
        """Constraints field should have correct structure."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        constraints = result["constraints"]
        assert "containerType" in constraints
        assert "containerLength" in constraints
        assert "targetWeight" in constraints
        assert "weightRange" in constraints
        assert "targetProfitMargin" in constraints
        assert "marginRange" in constraints
        
        # weightRange should be [min, max]
        assert isinstance(constraints["weightRange"], list)
        assert len(constraints["weightRange"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

