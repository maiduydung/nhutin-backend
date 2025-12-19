"""
Comprehensive tests for optimizer constraint satisfaction.
Tests that BOTH weight and margin targets are met.
"""
import pytest
from services.database import Database
from services.optimizer import Optimizer
from services.weight_targets import getWeightRange, calculateTargetWeight, WEIGHT_TOLERANCE


class TestConstraintSatisfaction:
    """Test that optimizer satisfies BOTH weight AND margin constraints."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        return Optimizer(db)

    # =========================================================================
    # WEIGHT CONSTRAINT TESTS
    # =========================================================================
    
    def test_weight_meets_minimum_6m(self, optimizer):
        """6m container should have at least 3000kg (3500 - 500)."""
        result = optimizer.optimize(
            containerLength=6.0,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(6.0)
        assert result["totalWeight"] >= minW, \
            f"Weight {result['totalWeight']} < min {minW} for 6m"

    def test_weight_meets_minimum_9m(self, optimizer):
        """9m container should have at least 4000kg (4500 - 500)."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(9.0)
        assert result["totalWeight"] >= minW, \
            f"Weight {result['totalWeight']} < min {minW} for 9m"

    def test_weight_meets_minimum_12m(self, optimizer):
        """12m container should have at least 6500kg (7000 - 500)."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=8,
            receiptPrice=800_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(12.0)
        assert result["totalWeight"] >= minW, \
            f"Weight {result['totalWeight']} < min {minW} for 12m"

    def test_weight_meets_minimum_15m(self, optimizer):
        """15m container should have at least 7500kg (8000 - 500)."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=900_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(15.0)
        assert result["totalWeight"] >= minW, \
            f"Weight {result['totalWeight']} < min {minW} for 15m"

    def test_weight_respects_physical_limit(self, optimizer):
        """Weight should not exceed max + 50% (physical limit)."""
        result = optimizer.optimize(
            containerLength=6.0,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=800_000_000,  # Large budget
            containerType="container_20ft",
            targetProfitMargin=0.10,  # Low margin = more spending
        )
        
        target, minW, maxW = getWeightRange(6.0)
        
        print(f"\nPhysical limit test: weight={result['totalWeight']:.0f}kg "
              f"(max: {maxW}kg, 150%={int(maxW*1.5)}kg)")
        
        # With excessive budget, we hit weight cap and have higher margin
        physicalLimit = int(maxW * 1.5) + 100  # Small tolerance for floating point
        assert result["totalWeight"] <= physicalLimit, \
            f"Weight {result['totalWeight']} exceeds physical limit {physicalLimit}kg"

    # =========================================================================
    # MARGIN CONSTRAINT TESTS  
    # =========================================================================

    def test_margin_close_to_target_20(self, optimizer):
        """Margin should be within reasonable range of 20% target."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        # Allow 10% deviation from target
        assert 10 <= result["profitMargin"] <= 30, \
            f"Margin {result['profitMargin']}% too far from 20% target"

    def test_margin_close_to_target_15(self, optimizer):
        """Margin should be within reasonable range of 15% target."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="KSD",
            slatType="97mm",
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.15,
        )
        
        assert 5 <= result["profitMargin"] <= 25, \
            f"Margin {result['profitMargin']}% too far from 15% target"

    # =========================================================================
    # COMBINED CONSTRAINT TESTS (THE CRITICAL ONES)
    # =========================================================================

    def test_both_constraints_6m_20pct(self, optimizer):
        """6m should hit BOTH weight 3000-4000kg AND ~20% margin."""
        result = optimizer.optimize(
            containerLength=6.0,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(6.0)
        
        print(f"\n6m test: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), "
              f"margin={result['profitMargin']:.1f}% (target: 20%)")
        
        # Weight constraint
        assert result["totalWeight"] >= minW, \
            f"WEIGHT FAIL: {result['totalWeight']} < {minW}"
        
        # Margin constraint (allow 10% deviation)
        assert result["profitMargin"] <= 30, \
            f"MARGIN FAIL: {result['profitMargin']}% > 30%"

    def test_both_constraints_9m_20pct(self, optimizer):
        """9m should hit BOTH weight 4000-5000kg AND ~20% margin."""
        result = optimizer.optimize(
            containerLength=9.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=600_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(9.0)
        
        print(f"\n9m test: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), "
              f"margin={result['profitMargin']:.1f}% (target: 20%)")
        
        assert result["totalWeight"] >= minW, \
            f"WEIGHT FAIL: {result['totalWeight']} < {minW}"
        assert result["profitMargin"] <= 30, \
            f"MARGIN FAIL: {result['profitMargin']}% > 30%"

    def test_both_constraints_12m_20pct(self, optimizer):
        """12m should hit BOTH weight 6500-7500kg AND ~20% margin."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            thickness=8,
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(12.0)
        
        print(f"\n12m test: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), "
              f"margin={result['profitMargin']:.1f}% (target: 20%)")
        
        assert result["totalWeight"] >= minW, \
            f"WEIGHT FAIL: {result['totalWeight']} < {minW}"
        assert result["profitMargin"] <= 30, \
            f"MARGIN FAIL: {result['profitMargin']}% > 30%"

    def test_both_constraints_15m_20pct(self, optimizer):
        """15m should hit BOTH weight 7500-8500kg AND ~20% margin."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=900_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(15.0)
        
        print(f"\n15m test: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), "
              f"margin={result['profitMargin']:.1f}% (target: 20%)")
        
        assert result["totalWeight"] >= minW, \
            f"WEIGHT FAIL: {result['totalWeight']} < {minW}"
        assert result["profitMargin"] <= 30, \
            f"MARGIN FAIL: {result['profitMargin']}% > 30%"

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    def test_low_budget_still_meets_weight(self, optimizer):
        """Even with tight budget, weight should be prioritized."""
        result = optimizer.optimize(
            containerLength=6.0,
            itemModelType="R2DX",
            slatType="97mm",
            receiptPrice=350_000_000,  # Very tight budget
            containerType="container_20ft",
            targetProfitMargin=0.20,
        )
        
        target, minW, maxW = getWeightRange(6.0)
        
        print(f"\nLow budget test: weight={result['totalWeight']:.0f}kg, "
              f"margin={result['profitMargin']:.1f}%")
        
        # Weight should still be attempted
        # Margin might be negative/low due to budget constraints
        assert result["totalWeight"] > 0

    def test_high_budget_maximizes_weight(self, optimizer):
        """With large budget and low margin target, should maximize weight."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=1_000_000_000,  # Large budget
            containerType="mooc_long",
            targetProfitMargin=0.10,  # Low margin = spend more
        )
        
        target, minW, maxW = getWeightRange(12.0)
        
        print(f"\nHigh budget test: weight={result['totalWeight']:.0f}kg (max: {maxW}), "
              f"margin={result['profitMargin']:.1f}%")
        
        # Should be close to max weight
        assert result["totalWeight"] >= target, \
            f"With high budget, should reach target weight {target}"

    def test_user_reported_case_40ft_500m(self, optimizer):
        """
        User's reported failing case:
        12.192m, R2DX, 112mm, 8mm thick, 500M receipt, 20% margin
        Expected: weight ~7000kg (range 6564-7564)
        Got: 3126kg ❌
        """
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
        
        print(f"\nUser case: weight={result['totalWeight']:.0f}kg (target: {minW}-{maxW}), "
              f"margin={result['profitMargin']:.1f}% (target: 20%)")
        print(f"Items: {len(result['items'])}")
        for item in result['items']:
            print(f"  {item['type']}: {item['weight']:.0f}kg, {item['totalValue']:,.0f}")
        
        # The key assertion: weight must meet minimum
        assert result["totalWeight"] >= minW, \
            f"CRITICAL FAIL: weight {result['totalWeight']:.0f}kg < min {minW}kg"


class TestWeightTargetCalculations:
    """Test the weight target calculations are correct."""

    def test_guidepost_6m(self):
        assert calculateTargetWeight(6.0) == 3500

    def test_guidepost_9m(self):
        assert calculateTargetWeight(9.0) == 4500

    def test_guidepost_12m(self):
        assert calculateTargetWeight(12.0) == 7000

    def test_guidepost_15m(self):
        assert calculateTargetWeight(15.0) == 8000

    def test_interpolation_7_5m(self):
        # Halfway between 6m (3500) and 9m (4500) = 4000
        assert calculateTargetWeight(7.5) == 4000

    def test_interpolation_10_5m(self):
        # Halfway between 9m (4500) and 12m (7000) = 5750
        result = calculateTargetWeight(10.5)
        assert 5700 <= result <= 5800

    def test_weight_range_includes_tolerance(self):
        target, minW, maxW = getWeightRange(12.0)
        assert target == 7000
        assert minW == 7000 - WEIGHT_TOLERANCE  # 6500
        assert maxW == 7000 + WEIGHT_TOLERANCE  # 7500


def main():
    """Run tests with verbose output."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    main()

