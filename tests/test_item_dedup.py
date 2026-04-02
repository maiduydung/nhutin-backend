"""
Tests for item deduplication across optimizer phases.

The optimizer adds items in multiple phases (Phase 1: fixed/container build,
Phase 2: weight filling, Phase 3: margin tuning, Phase 4: micro-adjust).
The same item can be picked up by different phases, resulting in duplicate
entries in the final BOM. _mergeItemsById() consolidates these.
"""
import pytest
from services.optimizer import OptimizerV2
from services.database import Database


class TestMergeItemsById:
    """Unit tests for _mergeItemsById static method."""

    def test_no_duplicates_unchanged(self):
        """Items with unique IDs should pass through unchanged."""
        items = [
            {"id": 1, "code": "A", "quantity": 10, "weight": 100, "totalValue": 5000},
            {"id": 2, "code": "B", "quantity": 5, "weight": 50, "totalValue": 3000},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert len(merged) == 2
        assert merged[0]["quantity"] == 10
        assert merged[1]["quantity"] == 5

    def test_duplicates_merged(self):
        """Items with same ID should have quantity, weight, totalValue summed."""
        items = [
            {"id": 1, "code": "steel_u", "quantity": 6, "weight": 6.0, "totalValue": 5143636},
            {"id": 2, "code": "nhom", "quantity": 100, "weight": 253.0, "totalValue": 10000000},
            {"id": 1, "code": "steel_u", "quantity": 6, "weight": 6.0, "totalValue": 5143636},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert len(merged) == 2

        steelItem = next(i for i in merged if i["id"] == 1)
        assert steelItem["quantity"] == 12
        assert steelItem["weight"] == 12.0
        assert steelItem["totalValue"] == 10287272

    def test_three_duplicates_merged(self):
        """Three entries for the same item across three phases."""
        items = [
            {"id": 5, "code": "X", "quantity": 2, "weight": 20, "totalValue": 1000},
            {"id": 5, "code": "X", "quantity": 3, "weight": 30, "totalValue": 1500},
            {"id": 5, "code": "X", "quantity": 1, "weight": 10, "totalValue": 500},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert len(merged) == 1
        assert merged[0]["quantity"] == 6
        assert merged[0]["weight"] == 60
        assert merged[0]["totalValue"] == 3000

    def test_empty_list(self):
        """Empty input should return empty output."""
        assert OptimizerV2._mergeItemsById([]) == []

    def test_single_item(self):
        """Single item should pass through unchanged."""
        items = [{"id": 1, "code": "A", "quantity": 5, "weight": 10, "totalValue": 500}]
        merged = OptimizerV2._mergeItemsById(items)
        assert len(merged) == 1
        assert merged[0]["quantity"] == 5

    def test_preserves_non_numeric_fields(self):
        """Merged item should keep code, name, unit, type from first occurrence."""
        items = [
            {"id": 1, "code": "steel_u", "name": "Thep U120", "unit": "Cay",
             "type": "steel_u", "quantity": 3, "weight": 3.0, "totalValue": 2000000},
            {"id": 1, "code": "steel_u", "name": "Thep U120", "unit": "Cay",
             "type": "steel_u", "quantity": 4, "weight": 4.0, "totalValue": 2500000},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert merged[0]["code"] == "steel_u"
        assert merged[0]["name"] == "Thep U120"
        assert merged[0]["unit"] == "Cay"
        assert merged[0]["type"] == "steel_u"

    def test_preserves_order_of_first_occurrence(self):
        """Merged list should maintain order of first occurrence of each ID."""
        items = [
            {"id": 3, "code": "C", "quantity": 1, "weight": 10, "totalValue": 100},
            {"id": 1, "code": "A", "quantity": 2, "weight": 20, "totalValue": 200},
            {"id": 2, "code": "B", "quantity": 3, "weight": 30, "totalValue": 300},
            {"id": 1, "code": "A", "quantity": 4, "weight": 40, "totalValue": 400},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert len(merged) == 3
        assert [i["id"] for i in merged] == [3, 1, 2]
        assert merged[1]["quantity"] == 6  # 2 + 4

    def test_weight_rounding(self):
        """Merged weight should be rounded to 2 decimal places."""
        items = [
            {"id": 1, "code": "A", "quantity": 1, "weight": 1.005, "totalValue": 100},
            {"id": 1, "code": "A", "quantity": 1, "weight": 2.007, "totalValue": 200},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert merged[0]["weight"] == 3.01  # rounded

    def test_handles_missing_weight_key(self):
        """Items without weight key should default to 0."""
        items = [
            {"id": 1, "code": "A", "quantity": 1, "weight": 5.0, "totalValue": 100},
            {"id": 1, "code": "A", "quantity": 1, "totalValue": 200},
        ]
        merged = OptimizerV2._mergeItemsById(items)
        assert merged[0]["weight"] == 5.0
        assert merged[0]["totalValue"] == 300


class TestNoDuplicateItemsIntegration:
    """Integration tests: optimizer output should never have duplicate IDs."""

    @pytest.fixture
    def optimizer(self):
        db = Database()
        return OptimizerV2(db)

    def _assertNoDuplicateIds(self, result):
        """Helper: assert no duplicate item IDs in result."""
        if result["status"] == "error":
            return  # error results have empty items

        items = result["items"]
        ids = [item["id"] for item in items]
        duplicates = [itemId for itemId in ids if ids.count(itemId) > 1]
        assert len(duplicates) == 0, (
            f"Duplicate item IDs found: {set(duplicates)}. "
            f"Items: {[(i['id'], i['code'], i['quantity']) for i in items]}"
        )

    def test_mooc_long_no_duplicates(self, optimizer):
        """Mooc long builds container from materials + weight fills — high duplicate risk."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=1_200_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )
        self._assertNoDuplicateIds(result)

    def test_thung_xe_tai_build_no_duplicates(self, optimizer):
        """Thung xe tai with container build — same risk as mooc long."""
        result = optimizer.optimize(
            containerLength=9.5,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=600_000_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
            buildContainer=True,
        )
        self._assertNoDuplicateIds(result)

    def test_thung_xe_tai_skip_build_no_duplicates(self, optimizer):
        """Thung xe tai without container build — fewer phases but still check."""
        result = optimizer.optimize(
            containerLength=9.5,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=378_700_000,
            containerType="thung_xe_tai",
            targetProfitMargin=0.20,
            buildContainer=False,
        )
        self._assertNoDuplicateIds(result)

    def test_container_20ft_no_duplicates(self, optimizer):
        """20ft container — may use pre-built or build from materials."""
        result = optimizer.optimize(
            containerLength=6.096,
            itemModelType="KMD",
            slatType="97mm",
            receiptPrice=500_000_000,
            containerType="container_20ft",
            targetProfitMargin=0.15,
        )
        self._assertNoDuplicateIds(result)

    def test_container_40ft_no_duplicates(self, optimizer):
        """40ft container — builds from materials, high duplicate risk."""
        result = optimizer.optimize(
            containerLength=12.192,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=1_000_000_000,
            containerType="container_40ft",
            targetProfitMargin=0.15,
        )
        self._assertNoDuplicateIds(result)

    def test_relaxed_mode_no_duplicates(self, optimizer):
        """Relaxed/best-effort mode should also have no duplicates."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="R2DX",
            slatType="112mm",
            receiptPrice=450_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
            relaxedMode=True,
        )
        self._assertNoDuplicateIds(result)

    def test_high_budget_triggers_phase4_no_duplicates(self, optimizer):
        """High budget with tight margin triggers Phase 4 micro-adjust — another duplicate risk."""
        result = optimizer.optimize(
            containerLength=12.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=800_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.15,
        )
        self._assertNoDuplicateIds(result)

    def test_item_totals_consistent_after_merge(self, optimizer):
        """Verify totalValue and weight are consistent with quantity * unitPrice."""
        result = optimizer.optimize(
            containerLength=15.0,
            itemModelType="KSD",
            slatType="112mm",
            receiptPrice=1_200_000_000,
            containerType="mooc_long",
            targetProfitMargin=0.20,
        )

        if result["status"] == "error":
            return

        for item in result["items"]:
            # totalValue should be close to quantity * unitPrice
            if "unitPrice" in item and item.get("quantity", 0) > 0:
                expected = item["quantity"] * item["unitPrice"]
                assert abs(item["totalValue"] - expected) < 1, (
                    f"Item {item['code']}: totalValue={item['totalValue']} != "
                    f"qty({item['quantity']}) * unitPrice({item['unitPrice']}) = {expected}"
                )


def main():
    """Run tests manually."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    main()
