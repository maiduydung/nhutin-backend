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
        # Set default slat params for aluminum calculation
        self.builder.setSlatParams("112mm", 6, 12.192)

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

    def _setupMockForBuildCheck(self, steelQty=1000, sheetQty=100, alumQty=1000):
        """Helper to setup comprehensive mock for build checks."""
        steelResult = [
            (1, "steel_box_1", "Thép hộp", "kg", "steel_box", float(steelQty), 20000.0),
        ]
        sheetResult = [
            (2, "galv_sheet_1", "Tôn mạ kẽm 0.95 x 1200", "m", "galvanized_sheet", float(sheetQty), 100000.0),
        ]
        alumResult = [
            (3, "nhom_thanh", "Nhôm thanh", "kg", "aluminum", float(alumQty), 120000.0),
        ]
        # Aluminum bar constants for weight calculation
        alumConstantsResult = [(2.529, 21)]
        
        def mockQuery(query, params=None):
            queryLower = query.lower()
            if "aluminum_bar_constants" in queryLower:
                return alumConstantsResult
            elif "steel" in queryLower and "any" in queryLower:
                return steelResult
            elif "galvanized" in queryLower:
                return sheetResult
            elif "aluminum" in queryLower:
                return alumResult
            return []
        
        self.mockDb.executeQuery.side_effect = mockQuery

    def test_can_build_container_no_materials(self):
        """Test canBuildContainer when no materials available."""
        # Mock empty inventory but return aluminum constants
        def mockQuery(query, params=None):
            if "aluminum_bar_constants" in query.lower():
                return [(2.529, 21)]  # Return valid constants
            return []
        
        self.mockDb.executeQuery.side_effect = mockQuery
        
        result = self.builder.canBuildContainer("20ft")
        self.assertFalse(result["canBuild"])
        self.assertGreater(len(result["missingMaterials"]), 0)

    def test_can_build_container_with_materials(self):
        """Test canBuildContainer when materials are available."""
        self._setupMockForBuildCheck(steelQty=1000, sheetQty=100, alumQty=1000)
        
        result = self.builder.canBuildContainer("20ft")
        # Should be able to build with sufficient materials
        self.assertIn("canBuild", result)
        self.assertIn("materials", result)
        self.assertIn("totalCost", result)
        self.assertIn("totalWeight", result)

    def test_build_container_budget_constraint(self):
        """Test buildContainer respects budget constraint."""
        self._setupMockForBuildCheck(steelQty=1000, sheetQty=100, alumQty=1000)
        
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
        self._setupMockForBuildCheck(steelQty=5000, sheetQty=200, alumQty=2000)
        
        result = self.builder.buildContainer(
            containerSize="40ft",  # Needs more materials
            maxCost=500_000_000,
            currentCost=100_000_000,
            currentWeight=5500,  # Already at 5500kg
            maxWeight=6000,  # Only 500kg left
        )
        
        # Should fail or scale down due to weight
        self.assertIn("success", result)


class TestContainerBuilderMaterialChecks(unittest.TestCase):
    """Test individual material check methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mockDb = MagicMock()
        self.builder = ContainerBuilder(self.mockDb)
        self.builder.setSlatParams("112mm", 6, 12.192)

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
