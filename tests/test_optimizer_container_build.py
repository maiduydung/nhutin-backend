"""
Tests for Optimizer container building integration.
Tests the edge case where containers need to be built from materials.

Updated for new container types:
- container_20ft, container_40ft: Include container item in BOM
- mooc_long, thung_xe_tai: NO container item, structure materials only
"""
import unittest
from unittest.mock import MagicMock, patch
from services.optimizer import Optimizer


class TestOptimizerContainerCheck(unittest.TestCase):
    """Test Optimizer container availability checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.optimizer = Optimizer(self.mockDb)

    def test_check_need_to_build_no_container_type(self):
        """Test _checkNeedToBuildContainer with no containerType."""
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(None, [])
        self.assertFalse(needBuild)
        self.assertEqual(size, "")
        self.assertFalse(usingPrebuilt)

    def test_check_need_to_build_20ft_available(self):
        """Test _checkNeedToBuildContainer when 20ft container is available."""
        variableItems = [
            {"type": "container", "name": "Vỏ container 20 feet"},
            {"type": "steel_box", "name": "Thép hộp"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "container_20ft", variableItems
        )
        
        self.assertFalse(needBuild)
        self.assertEqual(size, "20ft")
        self.assertTrue(usingPrebuilt)  # Using pre-built container

    def test_check_need_to_build_40ft_unavailable(self):
        """Test _checkNeedToBuildContainer when 40ft not available."""
        variableItems = [
            {"type": "container", "name": "Vỏ container 20 feet"},
            {"type": "steel_box", "name": "Thép hộp"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "container_40ft", variableItems
        )
        
        self.assertTrue(needBuild)
        self.assertEqual(size, "40ft")
        self.assertFalse(usingPrebuilt)  # Need to build

    def test_check_need_to_build_no_containers_at_all(self):
        """Test _checkNeedToBuildContainer when no containers in inventory."""
        variableItems = [
            {"type": "steel_box", "name": "Thép hộp"},
            {"type": "galvanized_sheet", "name": "Tôn mạ kẽm"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "container_20ft", variableItems
        )
        
        self.assertTrue(needBuild)
        self.assertEqual(size, "20ft")
        self.assertFalse(usingPrebuilt)

    def test_check_need_to_build_40ft_only_20ft_available(self):
        """Test requesting 40ft when only 20ft available."""
        variableItems = [
            {"type": "container", "name": "Container 20ft used"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "container_40ft", variableItems
        )
        
        self.assertTrue(needBuild)
        self.assertEqual(size, "40ft")
        self.assertFalse(usingPrebuilt)


class TestOptimizerMoocLongThungXeTai(unittest.TestCase):
    """Test container checking for mooc_long and thung_xe_tai types."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.optimizer = Optimizer(self.mockDb)

    def test_mooc_long_never_uses_container(self):
        """Test that mooc_long always builds structure, never uses container."""
        variableItems = [
            {"type": "container", "name": "Vỏ container 40 feet"},
            {"type": "container", "name": "Vỏ container 20 feet"},
            {"type": "steel_box", "name": "Thép hộp"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "mooc_long", variableItems
        )
        
        self.assertTrue(needBuild)  # Always build structure
        self.assertEqual(size, "40ft")  # Uses 40ft as scaling base
        self.assertFalse(usingPrebuilt)  # Never pre-built

    def test_thung_xe_tai_never_uses_container(self):
        """Test that thung_xe_tai always builds structure, never uses container."""
        variableItems = [
            {"type": "container", "name": "Vỏ container 40 feet"},
            {"type": "container", "name": "Vỏ container 20 feet"},
            {"type": "steel_box", "name": "Thép hộp"},
        ]
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "thung_xe_tai", variableItems
        )
        
        self.assertTrue(needBuild)  # Always build structure
        self.assertEqual(size, "40ft")  # Uses 40ft as scaling base
        self.assertFalse(usingPrebuilt)  # Never pre-built

    def test_mooc_long_with_no_inventory(self):
        """Test mooc_long with empty inventory."""
        variableItems = []
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "mooc_long", variableItems
        )
        
        self.assertTrue(needBuild)
        self.assertEqual(size, "40ft")
        self.assertFalse(usingPrebuilt)

    def test_thung_xe_tai_with_no_inventory(self):
        """Test thung_xe_tai with empty inventory."""
        variableItems = []
        
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "thung_xe_tai", variableItems
        )
        
        self.assertTrue(needBuild)
        self.assertEqual(size, "40ft")
        self.assertFalse(usingPrebuilt)


class TestOptimizerContainerHelpers(unittest.TestCase):
    """Test Optimizer container helper methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.optimizer = Optimizer(self.mockDb)

    def test_should_include_container_item_20ft(self):
        """Test _shouldIncludeContainerItem for container_20ft."""
        self.assertTrue(self.optimizer._shouldIncludeContainerItem("container_20ft"))

    def test_should_include_container_item_40ft(self):
        """Test _shouldIncludeContainerItem for container_40ft."""
        self.assertTrue(self.optimizer._shouldIncludeContainerItem("container_40ft"))

    def test_should_not_include_container_item_mooc_long(self):
        """Test _shouldIncludeContainerItem for mooc_long."""
        self.assertFalse(self.optimizer._shouldIncludeContainerItem("mooc_long"))

    def test_should_not_include_container_item_thung_xe_tai(self):
        """Test _shouldIncludeContainerItem for thung_xe_tai."""
        self.assertFalse(self.optimizer._shouldIncludeContainerItem("thung_xe_tai"))

    def test_prebuilt_container_weight_20ft(self):
        """Test _getPrebuiltContainerWeight for 20ft container."""
        weight = self.optimizer._getPrebuiltContainerWeight("container_20ft")
        self.assertEqual(weight, 1900)

    def test_prebuilt_container_weight_40ft(self):
        """Test _getPrebuiltContainerWeight for 40ft container."""
        weight = self.optimizer._getPrebuiltContainerWeight("container_40ft")
        self.assertEqual(weight, 2500)

    def test_prebuilt_container_weight_mooc_long(self):
        """Test _getPrebuiltContainerWeight for mooc_long (should be 0)."""
        weight = self.optimizer._getPrebuiltContainerWeight("mooc_long")
        self.assertEqual(weight, 0)

    def test_prebuilt_container_weight_thung_xe_tai(self):
        """Test _getPrebuiltContainerWeight for thung_xe_tai (should be 0)."""
        weight = self.optimizer._getPrebuiltContainerWeight("thung_xe_tai")
        self.assertEqual(weight, 0)

    def test_effective_max_weight_prebuilt_20ft(self):
        """Test _getEffectiveMaxWeight for pre-built 20ft container."""
        # 6720 - 1900 = 4820
        maxWeight = self.optimizer._getEffectiveMaxWeight("container_20ft", True)
        self.assertEqual(maxWeight, 4820)

    def test_effective_max_weight_prebuilt_40ft(self):
        """Test _getEffectiveMaxWeight for pre-built 40ft container."""
        # 6720 - 2500 = 4220
        maxWeight = self.optimizer._getEffectiveMaxWeight("container_40ft", True)
        self.assertEqual(maxWeight, 4220)

    def test_effective_max_weight_built_from_materials(self):
        """Test _getEffectiveMaxWeight when building from materials."""
        # When building, no container weight to subtract
        maxWeight = self.optimizer._getEffectiveMaxWeight("container_40ft", False)
        self.assertEqual(maxWeight, 6720)

    def test_effective_max_weight_mooc_long(self):
        """Test _getEffectiveMaxWeight for mooc_long."""
        maxWeight = self.optimizer._getEffectiveMaxWeight("mooc_long", False)
        self.assertEqual(maxWeight, 6720)

    def test_effective_max_weight_thung_xe_tai(self):
        """Test _getEffectiveMaxWeight for thung_xe_tai."""
        maxWeight = self.optimizer._getEffectiveMaxWeight("thung_xe_tai", False)
        self.assertEqual(maxWeight, 6720)


class TestOptimizerContainerBuildIntegration(unittest.TestCase):
    """Test Optimizer's integration with ContainerBuilder."""

    def setUp(self):
        """Set up test fixtures with comprehensive mocks."""
        self.mockDb = MagicMock()
        self.optimizer = Optimizer(self.mockDb)

    def test_optimize_with_available_container(self):
        """Test optimize when container is available in inventory.
        
        Note: This test requires proper database mocking which is complex.
        For full integration testing, use the main() function in optimizer.py.
        """
        # Skip this test as it requires complex DB mocking
        # The logic is tested via _checkNeedToBuildContainer tests
        self.skipTest("Requires complex DB mocking - tested via integration")

    def test_optimize_skips_container_when_building(self):
        """Test that variable items optimization skips containers when building."""
        # This tests the skipContainerBuild parameter
        variableItems = [
            {"id": 1, "code": "thephop", "type": "steel_box", "name": "Steel", "unit": "kg", 
             "availableQuantity": 1000, "unitPrice": 15000},
            {"id": 2, "code": "container_20ft", "type": "container", "name": "Container 20ft", "unit": "set",
             "availableQuantity": 5, "unitPrice": 50000000},
        ]
        
        # Test with skipContainerBuild=True
        result = self.optimizer._optimizeVariableItems(
            variableItems=variableItems,
            fixedWeight=1000,
            fixedCost=300_000_000,
            receiptPrice=600_000_000,
            skipContainerBuild=True,
        )
        
        # Container should not be in selected items when skipContainerBuild=True
        containerInResult = any(
            "container" in item.get("name", "").lower()
            for item in result
        )
        self.assertFalse(containerInResult, "Container should be skipped when building from materials")


class TestOptimizerEdgeCases(unittest.TestCase):
    """Test edge cases in container building."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.optimizer = Optimizer(self.mockDb)

    def test_container_type_parsing_40ft(self):
        """Test container type parsing for 40ft."""
        needBuild, size, _ = self.optimizer._checkNeedToBuildContainer(
            "container_40ft", []
        )
        self.assertEqual(size, "40ft")

    def test_container_type_parsing_20ft(self):
        """Test container type parsing for 20ft."""
        needBuild, size, _ = self.optimizer._checkNeedToBuildContainer(
            "container_20ft", []
        )
        self.assertEqual(size, "20ft")

    def test_container_type_parsing_with_extra_text(self):
        """Test container type parsing with invalid type returns empty."""
        needBuild, size, _ = self.optimizer._checkNeedToBuildContainer(
            "container_40ft_special", []
        )
        # Invalid type should return empty string
        self.assertEqual(size, "")

    def test_invalid_container_type(self):
        """Test with invalid container type (no size)."""
        needBuild, size, usingPrebuilt = self.optimizer._checkNeedToBuildContainer(
            "some_invalid_type", []
        )
        self.assertFalse(needBuild)
        self.assertEqual(size, "")
        self.assertFalse(usingPrebuilt)


def main():
    """Run tests."""
    unittest.main()


if __name__ == "__main__":
    main()
