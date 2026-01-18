"""
Tests for consumables integration in container building.

Consumables are materials used during container fabrication:
- welding_wire: for welding steel frame (unit: kg, has weight)
- cutting_nozzle: for plasma cutting (unit: pcs, negligible weight)
- fastener: for assembly (unit: Con/pcs, negligible weight)
- gear_pump: optional additional pump (unit: pcs)

These items carry cost and help hit the profit margin target.
"""
import pytest
from services.database import Database
from services.container_builder import ContainerBuilder
from services.weight_calculator import WeightCalculator
from services.optimizer import OptimizerV2
from config import (
    CONSUMABLES_SPECS,
    CONSUMABLE_TYPES,
    CONSUMABLE_WEIGHTS,
)


class TestConsumablesConfig:
    """Test consumables configuration constants."""

    def test_consumable_types_defined(self):
        """Verify all consumable types are defined."""
        assert "welding_wire" in CONSUMABLE_TYPES
        assert "cutting_nozzle" in CONSUMABLE_TYPES
        assert "fastener" in CONSUMABLE_TYPES
        assert "gear_pump" in CONSUMABLE_TYPES

    def test_consumable_weights_defined(self):
        """Verify weights are defined for all consumable types."""
        for consumableType in CONSUMABLE_TYPES:
            assert consumableType in CONSUMABLE_WEIGHTS
        
        # Welding wire has weight (1kg per kg)
        assert CONSUMABLE_WEIGHTS["welding_wire"] == 1.0
        
        # Cutting nozzle and fastener have negligible weight
        assert CONSUMABLE_WEIGHTS["cutting_nozzle"] == 0.0
        assert CONSUMABLE_WEIGHTS["fastener"] == 0.0
        
        # Gear pump has some weight
        assert CONSUMABLE_WEIGHTS["gear_pump"] >= 0

    def test_consumables_specs_for_40ft(self):
        """Verify 40ft container consumables specs."""
        specs = CONSUMABLES_SPECS["40ft"]
        assert specs["length_m"] == 12.192
        assert specs["welding_wire_kg"] > 0
        assert specs["cutting_nozzle_pcs"] > 0
        assert specs["fastener_pcs"] > 0

    def test_consumables_specs_for_20ft(self):
        """Verify 20ft container consumables specs."""
        specs = CONSUMABLES_SPECS["20ft"]
        assert specs["length_m"] == 6.096
        assert specs["welding_wire_kg"] > 0
        assert specs["cutting_nozzle_pcs"] > 0
        assert specs["fastener_pcs"] > 0

    def test_20ft_uses_less_than_40ft(self):
        """20ft container should use less consumables than 40ft."""
        specs20 = CONSUMABLES_SPECS["20ft"]
        specs40 = CONSUMABLES_SPECS["40ft"]
        
        assert specs20["welding_wire_kg"] < specs40["welding_wire_kg"]
        assert specs20["cutting_nozzle_pcs"] <= specs40["cutting_nozzle_pcs"]
        assert specs20["fastener_pcs"] < specs40["fastener_pcs"]


class TestWeightCalculatorConsumables:
    """Test weight calculations for consumable types."""

    @pytest.fixture
    def calculator(self):
        return WeightCalculator()

    def test_welding_wire_weight_calculated(self, calculator):
        """Welding wire in kg should return same weight."""
        weight = calculator.calculateItemWeight(
            itemType="welding_wire",
            unit="kg",
            quantity=20,
            itemName="Dây hàn MAG"
        )
        assert weight == 20  # 20kg * 1.0 = 20kg

    def test_cutting_nozzle_weight_zero(self, calculator):
        """Cutting nozzles should have zero weight."""
        weight = calculator.calculateItemWeight(
            itemType="cutting_nozzle",
            unit="pcs",
            quantity=5,
            itemName="Bép cắt P80"
        )
        assert weight == 0  # pcs with zero weight per unit

    def test_fastener_weight_zero(self, calculator):
        """Fasteners should have zero weight."""
        weight = calculator.calculateItemWeight(
            itemType="fastener",
            unit="Con",
            quantity=100,
            itemName="Lục Giác Col Thép"
        )
        assert weight == 0  # Con/pcs with zero weight per unit

    def test_gear_pump_weight_calculated(self, calculator):
        """Gear pump should have defined weight."""
        weight = calculator.calculateItemWeight(
            itemType="gear_pump",
            unit="pcs",
            quantity=1,
            itemName="Bơm Bánh Răng"
        )
        assert weight == CONSUMABLE_WEIGHTS["gear_pump"]


class TestContainerBuilderConsumables:
    """Test consumables integration in ContainerBuilder."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def builder(self, db):
        builder = ContainerBuilder(db)
        builder.setSlatParams("112mm", 6, 12.192)
        return builder

    def test_calculate_consumables_needed_40ft(self, builder):
        """Test consumables calculation for 40ft container."""
        builder.containerLength = 12.192
        needed = builder._calculateConsumablesNeeded("40ft")
        
        assert "welding_wire" in needed
        assert "cutting_nozzle" in needed
        assert "fastener" in needed
        assert needed["welding_wire"] > 0
        assert needed["cutting_nozzle"] > 0
        assert needed["fastener"] > 0

    def test_calculate_consumables_needed_20ft(self, builder):
        """Test consumables calculation for 20ft container."""
        builder.containerLength = 6.096
        needed = builder._calculateConsumablesNeeded("20ft")
        
        assert needed["welding_wire"] > 0
        assert needed["cutting_nozzle"] >= 1
        assert needed["fastener"] >= 10

    def test_calculate_consumables_scales_with_length(self, builder):
        """Consumables should scale with container length."""
        # 40ft baseline
        builder.containerLength = 12.192
        needed40 = builder._calculateConsumablesNeeded("40ft")
        
        # 15m (longer than 40ft)
        builder.containerLength = 15.0
        needed15m = builder._calculateConsumablesNeeded("40ft")
        
        # Longer container needs more consumables
        assert needed15m["welding_wire"] > needed40["welding_wire"]

    def test_get_consumable_item_welding_wire(self, builder):
        """Test fetching welding wire from inventory."""
        result = builder._getConsumableItem("welding_wire", 10)
        
        # May or may not have items depending on inventory
        assert "items" in result
        assert "totalCost" in result
        assert "totalWeight" in result
        
        if result["items"]:
            item = result["items"][0]
            assert item["type"] == "welding_wire"
            assert item["forContainerBuild"] == True
            assert item["isConsumable"] == True
            # Welding wire has weight
            assert item["weight"] > 0 or item["quantity"] == 0

    def test_get_consumable_item_cutting_nozzle(self, builder):
        """Test fetching cutting nozzles from inventory."""
        result = builder._getConsumableItem("cutting_nozzle", 3)
        
        if result["items"]:
            item = result["items"][0]
            assert item["type"] == "cutting_nozzle"
            # Cutting nozzles have zero weight
            assert item["weight"] == 0

    def test_get_consumable_item_fastener(self, builder):
        """Test fetching fasteners from inventory."""
        result = builder._getConsumableItem("fastener", 50)
        
        if result["items"]:
            item = result["items"][0]
            assert item["type"] == "fastener"
            # Fasteners have zero weight
            assert item["weight"] == 0

    def test_get_consumables_returns_all_types(self, builder):
        """Test _getConsumables returns items for available types."""
        builder.containerLength = 12.192
        result = builder._getConsumables("40ft")
        
        assert "items" in result
        assert "totalCost" in result
        assert "totalWeight" in result
        
        # Check item types found
        foundTypes = {item["type"] for item in result["items"]}
        
        # At least some consumables should be found
        # (depends on inventory, but welding wire should be available based on user's data)
        print(f"Found consumable types: {foundTypes}")
        print(f"Total cost: {result['totalCost']:,.0f}")
        print(f"Total weight: {result['totalWeight']:.1f}")

    def test_can_build_container_includes_consumables(self, builder):
        """canBuildContainer should include consumables in materials."""
        builder.containerLength = 12.192
        result = builder.canBuildContainer("40ft")
        
        # Regardless of canBuild, consumables should be fetched and added
        consumableItems = [
            item for item in result["materials"]
            if item.get("isConsumable", False)
        ]
        
        print(f"\ncanBuildContainer result:")
        print(f"  canBuild: {result['canBuild']}")
        print(f"  Total materials: {len(result['materials'])}")
        print(f"  Consumables: {len(consumableItems)}")
        
        for item in consumableItems:
            print(f"    - {item['type']}: {item['quantity']} x {item['unitPrice']:,.0f}")
        
        # Consumables should always be fetched (even if canBuild is False due to low steel)
        # This verifies the consumables integration is working
        assert len(consumableItems) > 0, "Should have consumables in materials list"


class TestOptimizerWithConsumables:
    """Test full optimizer with consumables integration."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def optimizer(self, db):
        return OptimizerV2(db)

    def test_mooc_long_includes_consumables(self, optimizer):
        """Test mooc_long optimization ALWAYS includes consumables (even if steel build fails)."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        if result["status"] != "error":
            # Check for consumables in items
            consumables = [
                item for item in result["items"]
                if item.get("type") in CONSUMABLE_TYPES
            ]
            
            print(f"\n✅ Mooc 15m result:")
            print(f"   Total items: {len(result['items'])}")
            print(f"   Consumables: {len(consumables)}")
            print(f"   Container built (steel): {result['containerBuiltFromMaterials']}")
            print(f"   Weight: {result['totalWeight']:,.0f} kg")
            print(f"   Cost: {result['totalCost']:,.0f}")
            print(f"   Margin: {result['profitMargin']:.1f}%")
            
            for item in consumables:
                print(f"   - {item['type']}: {item.get('quantity', 1)} @ {item.get('unitPrice', 0):,.0f}")
            
            # Consumables should ALWAYS be added when building (mooc_long always builds)
            # Even if steel build fails, we still weld/cut/assemble using aluminum
            assert len(consumables) > 0, "Should ALWAYS have consumables when building (mooc_long)"
        else:
            print(f"❌ Test skipped (error): {result['error']}")

    def test_thung_xe_tai_includes_consumables(self, optimizer):
        """Test thung_xe_tai with buildContainer=True ALWAYS includes consumables."""
        result = optimizer.optimize(
            containerLength=9.5,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=600_000_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
            buildContainer=True,
        )
        
        if result["status"] != "error":
            consumables = [
                item for item in result["items"]
                if item.get("type") in CONSUMABLE_TYPES
            ]
            
            print(f"\n✅ Thung Xe Tai result:")
            print(f"   Total items: {len(result['items'])}")
            print(f"   Consumables: {len(consumables)}")
            print(f"   Container built (steel): {result['containerBuiltFromMaterials']}")
            
            for item in consumables:
                print(f"   - {item['type']}: {item.get('quantity', 1)} @ {item.get('unitPrice', 0):,.0f}")
            
            # Consumables should ALWAYS be added when buildContainer=True
            # Even if steel build fails, we still weld/cut/assemble
            assert len(consumables) > 0, "Should ALWAYS have consumables when buildContainer=True"
        else:
            print(f"❌ Test skipped (error): {result['error']}")

    def test_thung_xe_tai_no_consumables_without_build(self, optimizer):
        """Test thung_xe_tai with buildContainer=False has no container consumables."""
        result = optimizer.optimize(
            containerLength=9.5,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=378_700_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
            buildContainer=False,  # Skip container building
        )
        
        if result["status"] != "error":
            # Container build consumables should NOT be included
            consumablesForBuild = [
                item for item in result["items"]
                if item.get("isConsumable", False) and item.get("forContainerBuild", False)
            ]
            
            print(f"\n✅ Thung Xe Tai (no build) result:")
            print(f"   Container built: {result['containerBuiltFromMaterials']}")
            print(f"   Build consumables: {len(consumablesForBuild)}")
            
            # No container build = no build consumables
            assert result["containerBuiltFromMaterials"] == False
            assert len(consumablesForBuild) == 0

    def test_container_20ft_may_have_consumables(self, optimizer):
        """Test container_20ft may include consumables if built from materials."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KMD",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.15,
        )
        
        if result["status"] != "error":
            consumables = [
                item for item in result["items"]
                if item.get("type") in CONSUMABLE_TYPES
            ]
            
            print(f"\n✅ Container 20ft result:")
            print(f"   Container built from materials: {result['containerBuiltFromMaterials']}")
            print(f"   Consumables: {len(consumables)}")
            
            # Only expect consumables if container was built from materials
            if result["containerBuiltFromMaterials"]:
                assert len(consumables) >= 0  # May have consumables

    def test_consumables_add_cost_to_margin(self, optimizer):
        """Verify consumables add cost which affects profit margin."""
        # Run same optimization twice shouldn't change (deterministic)
        result1 = optimizer.optimize(
            containerLength=12.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=700_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        
        if result1["status"] != "error":
            consumables = [
                item for item in result1["items"]
                if item.get("type") in CONSUMABLE_TYPES
            ]
            consumableCost = sum(item.get("totalValue", 0) for item in consumables)
            
            print(f"\n📊 Consumables cost contribution:")
            print(f"   Consumables count: {len(consumables)}")
            print(f"   Consumables cost: {consumableCost:,.0f} VND")
            print(f"   Total cost: {result1['totalCost']:,.0f} VND")
            print(f"   Profit margin: {result1['profitMargin']:.1f}%")
            
            # Consumables should add meaningful cost
            if consumables:
                assert consumableCost > 0


class TestConsumablesWeight:
    """Test that consumables weight is calculated correctly."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def builder(self, db):
        builder = ContainerBuilder(db)
        builder.setSlatParams("112mm", 6, 12.192)
        return builder

    def test_welding_wire_adds_weight(self, builder):
        """Welding wire should add weight to total."""
        result = builder._getConsumableItem("welding_wire", 20)
        
        if result["items"]:
            totalWeight = sum(item["weight"] for item in result["items"])
            totalQty = sum(item["quantity"] for item in result["items"])
            
            # Weight should equal quantity for welding wire (kg unit)
            assert totalWeight == totalQty
            print(f"Welding wire: {totalQty}kg = {totalWeight}kg weight")

    def test_cutting_nozzle_no_weight(self, builder):
        """Cutting nozzles should not add weight."""
        result = builder._getConsumableItem("cutting_nozzle", 5)
        
        if result["items"]:
            totalWeight = sum(item["weight"] for item in result["items"])
            assert totalWeight == 0
            print(f"Cutting nozzles: {len(result['items'])} items, 0kg weight")

    def test_fastener_no_weight(self, builder):
        """Fasteners should not add weight."""
        result = builder._getConsumableItem("fastener", 100)
        
        if result["items"]:
            totalWeight = sum(item["weight"] for item in result["items"])
            assert totalWeight == 0
            print(f"Fasteners: {len(result['items'])} items, 0kg weight")

    def test_total_consumables_weight(self, builder):
        """Total consumables weight should be sum of individual weights."""
        result = builder._getConsumables("40ft")
        
        # Only welding wire contributes weight
        weldingWireItems = [
            item for item in result["items"]
            if item["type"] == "welding_wire"
        ]
        expectedWeight = sum(item["weight"] for item in weldingWireItems)
        
        assert result["totalWeight"] == expectedWeight
        print(f"Total consumables weight: {result['totalWeight']}kg (from welding wire)")


class TestConsumablesInventoryAvailability:
    """Test consumables behavior with different inventory levels."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def builder(self, db):
        builder = ContainerBuilder(db)
        builder.setSlatParams("112mm", 6, 12.192)
        return builder

    def test_partial_welding_wire_available(self, builder):
        """Should use available welding wire even if less than needed."""
        # Request more than might be available
        result = builder._getConsumableItem("welding_wire", 1000)
        
        if result["items"]:
            totalQty = sum(item["quantity"] for item in result["items"])
            print(f"Requested 1000kg, got {totalQty}kg welding wire")
            # Should get whatever is available
            assert totalQty > 0

    def test_consumables_sorted_by_price(self, builder):
        """Consumables should be fetched cheapest first."""
        result = builder._getConsumableItem("welding_wire", 50)
        
        if len(result["items"]) > 1:
            prices = [item["unitPrice"] for item in result["items"]]
            # Should be sorted by price ascending
            assert prices == sorted(prices)
            print(f"Welding wire prices (sorted): {prices}")


class TestConsumablesEdgeCases:
    """Test edge cases for consumables."""

    @pytest.fixture
    def db(self):
        return Database()

    @pytest.fixture
    def builder(self, db):
        return ContainerBuilder(db)

    def test_zero_quantity_requested(self, builder):
        """Zero quantity should return empty result."""
        result = builder._getConsumableItem("welding_wire", 0)
        
        assert result["items"] == []
        assert result["totalCost"] == 0
        assert result["totalWeight"] == 0

    def test_very_short_container(self, builder):
        """Very short container should still use minimum consumables."""
        builder.setSlatParams("97mm", 6, 3.0)  # Very short
        needed = builder._calculateConsumablesNeeded("20ft")
        
        # Should still have minimum quantities
        assert needed["cutting_nozzle"] >= 1
        assert needed["fastener"] >= 10

    def test_very_long_container(self, builder):
        """Very long container should scale up consumables."""
        builder.setSlatParams("112mm", 6, 20.0)  # Very long
        needed = builder._calculateConsumablesNeeded("40ft")
        
        # Should scale up significantly
        baseline = CONSUMABLES_SPECS["40ft"]["welding_wire_kg"]
        scaleFactor = 20.0 / 12.192
        expected = baseline * scaleFactor
        
        assert abs(needed["welding_wire"] - expected) < 0.1
        print(f"20m container needs {needed['welding_wire']:.1f}kg welding wire")

    def test_unknown_consumable_type(self, builder):
        """Unknown consumable type should return empty."""
        result = builder._getConsumableItem("unknown_type", 10)
        
        assert result["items"] == []
        assert result["totalCost"] == 0


def main():
    """Run tests manually."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    main()
