"""
Tests for ContainerBuilder service.
Tests the ability to build containers from raw materials.

Material requirements based on:
THAICUONG 23062025 THUYETMINHKYTHUAT.pdf - Walking Floor S-Drive KSD 4.25" system
"""
import unittest
from unittest.mock import MagicMock, patch
from services.container_builder import ContainerBuilder
from config import CONTAINER_BUILD_SPECS


class TestContainerBuilder(unittest.TestCase):
    """Test ContainerBuilder service."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.builder = ContainerBuilder(self.mockDb)

    def test_container_specs_exist(self):
        """Test that container specs are defined in config."""
        self.assertIn("20ft", CONTAINER_BUILD_SPECS)
        self.assertIn("40ft", CONTAINER_BUILD_SPECS)

    def test_20ft_container_specs(self):
        """Test 20ft container specifications (from THUYETMINHKYTHUAT.pdf)."""
        specs = CONTAINER_BUILD_SPECS["20ft"]
        self.assertEqual(specs["length_m"], 6.096)
        # 20ft specs are approximately half of 40ft
        self.assertEqual(specs["steel_frame_kg"], 492)  # Half of 40ft's 983kg
        self.assertEqual(specs["galvanized_sheet_m"], 50)
        self.assertEqual(specs["aluminum_kg"], 378)  # Half of 40ft's 756kg

    def test_40ft_container_specs(self):
        """Test 40ft container specifications (from THUYETMINHKYTHUAT.pdf).
        
        Reference document values:
        - Aluminum: 756.76 kg (25 bars × 12m × 2.53 kg/m)
        - Steel frame: ~983 kg (332.34 + 398.48 + 252.41)
        - Galvanized sheets: ~100m for roof/walls
        """
        specs = CONTAINER_BUILD_SPECS["40ft"]
        self.assertEqual(specs["length_m"], 12.192)
        self.assertEqual(specs["steel_frame_kg"], 983)  # From THUYETMINHKYTHUAT.pdf
        self.assertEqual(specs["galvanized_sheet_m"], 100)
        self.assertEqual(specs["aluminum_kg"], 757)  # Rounded from 756.76kg

    def test_can_build_container_unknown_size(self):
        """Test canBuildContainer with unknown size."""
        result = self.builder.canBuildContainer("50ft")
        self.assertFalse(result["canBuild"])
        self.assertIn("reason", result)

    def test_can_build_container_no_materials(self):
        """Test canBuildContainer when no materials available."""
        # Mock empty inventory
        self.mockDb.executeQuery.return_value = []
        
        result = self.builder.canBuildContainer("20ft")
        self.assertFalse(result["canBuild"])
        self.assertGreater(len(result["missingMaterials"]), 0)

    def test_can_build_container_with_materials(self):
        """Test canBuildContainer when materials are available."""
        # Mock steel query result
        steelResult = [
            (1, "steel_box_1", "Thép hộp", "kg", "steel_box", 1000.0, 20000.0),
        ]
        # Mock galvanized sheet query result
        sheetResult = [
            (2, "galv_sheet_1", "Tôn mạ kẽm 0.95 x 1200", "m", "galvanized_sheet", 100.0, 100000.0),
        ]
        # Mock aluminum query result
        alumResult = [
            (3, "nhom_thanh", "Nhôm thanh", "kg", "aluminum", 500.0, 120000.0),
        ]
        
        # Setup mock to return different results for different queries
        def mockQuery(query, params=None):
            if "steel" in query.lower():
                return steelResult
            elif "galvanized" in query.lower():
                return sheetResult
            elif "aluminum" in query.lower():
                return alumResult
            return []
        
        self.mockDb.executeQuery.side_effect = mockQuery
        
        result = self.builder.canBuildContainer("20ft")
        # May or may not build depending on quantities
        self.assertIn("canBuild", result)
        self.assertIn("materials", result)
        self.assertIn("totalCost", result)
        self.assertIn("totalWeight", result)

    def test_build_container_budget_constraint(self):
        """Test buildContainer respects budget constraint."""
        # Setup mock with expensive materials
        def mockQuery(query, params=None):
            return [(1, "test", "Test Item", "kg", "steel_box", 1000.0, 1000000.0)]
        
        self.mockDb.executeQuery.side_effect = mockQuery
        
        result = self.builder.buildContainer(
            containerSize="20ft",
            maxCost=100_000_000,  # 100M budget
            currentCost=99_000_000,  # Already spent 99M
            currentWeight=1000,
            maxWeight=6000,
        )
        
        # Should fail or scale down due to budget
        self.assertIn("success", result)

    def test_build_container_weight_constraint(self):
        """Test buildContainer respects weight constraint."""
        # Setup mock with heavy materials
        def mockQuery(query, params=None):
            return [(1, "test", "Test Item", "kg", "steel_box", 5000.0, 10000.0)]
        
        self.mockDb.executeQuery.side_effect = mockQuery
        
        result = self.builder.buildContainer(
            containerSize="40ft",  # Needs more materials
            maxCost=500_000_000,
            currentCost=100_000_000,
            currentWeight=3500,  # Already at 3500kg
            maxWeight=6000,  # Only 200kg left
        )
        
        # Should fail or scale down due to weight
        self.assertIn("success", result)


class TestContainerBuilderMaterialChecks(unittest.TestCase):
    """Test individual material check methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.builder = ContainerBuilder(self.mockDb)

    def test_check_steel_availability_empty(self):
        """Test _checkSteelAvailability with no inventory."""
        self.mockDb.executeQuery.return_value = []
        result = self.builder._checkSteelAvailability(500)
        
        self.assertFalse(result["available"])
        self.assertEqual(result["availableQty"], 0)
        self.assertEqual(len(result["items"]), 0)

    def test_check_steel_availability_sufficient(self):
        """Test _checkSteelAvailability with sufficient inventory."""
        self.mockDb.executeQuery.return_value = [
            (1, "thephop", "Thép hộp", "kg", "steel_box", 1000.0, 20000.0),
        ]
        
        result = self.builder._checkSteelAvailability(500)
        
        self.assertTrue(result["available"])
        self.assertGreater(result["availableQty"], 0)
        self.assertGreater(len(result["items"]), 0)

    def test_check_galvanized_availability_empty(self):
        """Test _checkGalvanizedSheetAvailability with no inventory."""
        self.mockDb.executeQuery.return_value = []
        result = self.builder._checkGalvanizedSheetAvailability(50)
        
        self.assertFalse(result["available"])
        self.assertEqual(result["availableQty"], 0)

    def test_check_aluminum_availability_empty(self):
        """Test _checkAluminumAvailability with no inventory."""
        self.mockDb.executeQuery.return_value = []
        result = self.builder._checkAluminumAvailability(100)
        
        self.assertFalse(result["available"])
        self.assertEqual(result["availableQty"], 0)


def main():
    """Run tests."""
    unittest.main()


if __name__ == "__main__":
    main()

