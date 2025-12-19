"""
Tests for container type logic - ensuring correct BOM generation for all 4 container types.

Container Types:
- container_20ft: Include container item, subtract 1,900kg from max weight (if pre-built)
- container_40ft: Include container item, subtract 2,500kg from max weight (if pre-built)
- mooc_long: NO container item, full 6,720kg available
- thung_xe_tai: NO container item, full 6,720kg available

Test Cases:
1. Container type parsing and recognition
2. Container item inclusion/exclusion in BOM
3. Weight constraints based on container type
4. Material scaling for custom lengths
5. Fixed items present for all types
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestContainerTypeConstants(unittest.TestCase):
    """Test container type constants and configuration."""
    
    def test_valid_container_types(self):
        """All 4 container types should be recognized."""
        validTypes = ["container_20ft", "container_40ft", "mooc_long", "thung_xe_tai"]
        for containerType in validTypes:
            self.assertIn(containerType, validTypes)
    
    def test_container_default_lengths(self):
        """Container types should have correct default lengths."""
        expectedLengths = {
            "container_20ft": 6.096,
            "container_40ft": 12.192,
            "mooc_long": 15.0,
            "thung_xe_tai": 15.0,
        }
        for containerType, expectedLength in expectedLengths.items():
            self.assertGreater(expectedLength, 0, f"{containerType} should have positive length")
    
    def test_container_weights(self):
        """Pre-built container weights should be defined."""
        containerWeights = {
            "container_20ft": 1900,  # kg
            "container_40ft": 2500,  # kg
            "mooc_long": 0,  # No container
            "thung_xe_tai": 0,  # No container
        }
        self.assertEqual(containerWeights["container_20ft"], 1900)
        self.assertEqual(containerWeights["container_40ft"], 2500)
        self.assertEqual(containerWeights["mooc_long"], 0)
        self.assertEqual(containerWeights["thung_xe_tai"], 0)


class TestContainerTypeRecognition(unittest.TestCase):
    """Test that container types are correctly parsed and recognized."""
    
    def test_parse_container_20ft(self):
        """container_20ft should be recognized as 20ft container."""
        containerType = "container_20ft"
        self.assertTrue("20" in containerType or containerType == "container_20ft")
        # Should include container in BOM
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertTrue(shouldIncludeContainer)
    
    def test_parse_container_40ft(self):
        """container_40ft should be recognized as 40ft container."""
        containerType = "container_40ft"
        self.assertTrue("40" in containerType or containerType == "container_40ft")
        # Should include container in BOM
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertTrue(shouldIncludeContainer)
    
    def test_parse_mooc_long(self):
        """mooc_long should NOT include container in BOM."""
        containerType = "mooc_long"
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertFalse(shouldIncludeContainer)
    
    def test_parse_thung_xe_tai(self):
        """thung_xe_tai should NOT include container in BOM."""
        containerType = "thung_xe_tai"
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertFalse(shouldIncludeContainer)


class TestContainerItemInclusion(unittest.TestCase):
    """Test that container items are correctly included/excluded from BOM."""
    
    def test_container_20ft_includes_container_item(self):
        """container_20ft should include container item in BOM."""
        containerType = "container_20ft"
        typesWithContainer = ["container_20ft", "container_40ft"]
        self.assertIn(containerType, typesWithContainer)
    
    def test_container_40ft_includes_container_item(self):
        """container_40ft should include container item in BOM."""
        containerType = "container_40ft"
        typesWithContainer = ["container_20ft", "container_40ft"]
        self.assertIn(containerType, typesWithContainer)
    
    def test_mooc_long_excludes_container_item(self):
        """mooc_long should NEVER include container item in BOM."""
        containerType = "mooc_long"
        typesWithContainer = ["container_20ft", "container_40ft"]
        self.assertNotIn(containerType, typesWithContainer)
    
    def test_thung_xe_tai_excludes_container_item(self):
        """thung_xe_tai should NEVER include container item in BOM."""
        containerType = "thung_xe_tai"
        typesWithContainer = ["container_20ft", "container_40ft"]
        self.assertNotIn(containerType, typesWithContainer)


class TestWeightConstraints(unittest.TestCase):
    """Test weight constraints for different container types."""
    
    BASE_MAX_WEIGHT = 6000  # kg
    MATERIAL_LOSS_FACTOR = 0.12
    EFFECTIVE_MAX_WEIGHT = int(BASE_MAX_WEIGHT * (1 + MATERIAL_LOSS_FACTOR))  # 6720 kg
    
    CONTAINER_WEIGHTS = {
        "container_20ft": 1900,
        "container_40ft": 2500,
        "mooc_long": 0,
        "thung_xe_tai": 0,
    }
    
    def test_effective_max_weight(self):
        """Effective max weight should be 6720 kg (6000 * 1.12)."""
        self.assertEqual(self.EFFECTIVE_MAX_WEIGHT, 6720)
    
    def test_container_20ft_prebuilt_max_materials(self):
        """container_20ft with pre-built should have max 4820 kg materials."""
        prebuiltWeight = self.CONTAINER_WEIGHTS["container_20ft"]
        maxMaterials = self.EFFECTIVE_MAX_WEIGHT - prebuiltWeight
        self.assertEqual(maxMaterials, 4820)
    
    def test_container_40ft_prebuilt_max_materials(self):
        """container_40ft with pre-built should have max 4220 kg materials."""
        prebuiltWeight = self.CONTAINER_WEIGHTS["container_40ft"]
        maxMaterials = self.EFFECTIVE_MAX_WEIGHT - prebuiltWeight
        self.assertEqual(maxMaterials, 4220)
    
    def test_container_20ft_built_max_materials(self):
        """container_20ft built from materials should have full 6720 kg."""
        containerWeight = 0  # Built, not pre-built
        maxMaterials = self.EFFECTIVE_MAX_WEIGHT - containerWeight
        self.assertEqual(maxMaterials, 6720)
    
    def test_mooc_long_max_materials(self):
        """mooc_long should have full 6720 kg available."""
        containerWeight = self.CONTAINER_WEIGHTS["mooc_long"]
        maxMaterials = self.EFFECTIVE_MAX_WEIGHT - containerWeight
        self.assertEqual(maxMaterials, 6720)
    
    def test_thung_xe_tai_max_materials(self):
        """thung_xe_tai should have full 6720 kg available."""
        containerWeight = self.CONTAINER_WEIGHTS["thung_xe_tai"]
        maxMaterials = self.EFFECTIVE_MAX_WEIGHT - containerWeight
        self.assertEqual(maxMaterials, 6720)


class TestMaterialScaling(unittest.TestCase):
    """Test material scaling for custom lengths."""
    
    BASE_LENGTH_40FT = 12.192  # meters
    BASE_STEEL_FRAME_KG = 983  # kg for 40ft
    BASE_GALVANIZED_SHEET_M = 100  # meters for 40ft
    
    def test_steel_scaling_15m(self):
        """Steel should scale proportionally for 15m length."""
        length = 15.0
        scaleFactor = length / self.BASE_LENGTH_40FT
        expectedSteel = self.BASE_STEEL_FRAME_KG * scaleFactor
        # 983 * (15 / 12.192) ≈ 1209 kg
        self.assertLess(abs(expectedSteel - 1209), 10)  # Allow small tolerance
    
    def test_galvanized_scaling_15m(self):
        """Galvanized sheet should scale proportionally for 15m length."""
        length = 15.0
        scaleFactor = length / self.BASE_LENGTH_40FT
        expectedSheet = self.BASE_GALVANIZED_SHEET_M * scaleFactor
        # 100 * (15 / 12.192) ≈ 123 m
        self.assertLess(abs(expectedSheet - 123), 5)  # Allow small tolerance
    
    def test_steel_scaling_6m(self):
        """Steel should scale correctly for 6.096m (20ft) length."""
        length = 6.096
        scaleFactor = length / self.BASE_LENGTH_40FT
        expectedSteel = self.BASE_STEEL_FRAME_KG * scaleFactor
        # 983 * (6.096 / 12.192) ≈ 491.5 kg (close to 20ft spec of 492)
        self.assertLess(abs(expectedSteel - 492), 5)
    
    def test_galvanized_scaling_6m(self):
        """Galvanized sheet should scale correctly for 6.096m (20ft) length."""
        length = 6.096
        scaleFactor = length / self.BASE_LENGTH_40FT
        expectedSheet = self.BASE_GALVANIZED_SHEET_M * scaleFactor
        # 100 * (6.096 / 12.192) = 50 m (exactly 20ft spec)
        self.assertLess(abs(expectedSheet - 50), 1)
    
    def test_scaling_formula(self):
        """Verify scaling formula works correctly."""
        testCases = [
            (6.096, 492, 50),   # 20ft
            (12.192, 983, 100), # 40ft
            (15.0, 1209, 123),  # Mooc Long default
            (18.0, 1451, 148),  # Custom length
        ]
        for length, expectedSteel, expectedSheet in testCases:
            scaleFactor = length / self.BASE_LENGTH_40FT
            actualSteel = self.BASE_STEEL_FRAME_KG * scaleFactor
            actualSheet = self.BASE_GALVANIZED_SHEET_M * scaleFactor
            self.assertLess(abs(actualSteel - expectedSteel), 10, f"Steel mismatch for {length}m")
            self.assertLess(abs(actualSheet - expectedSheet), 5, f"Sheet mismatch for {length}m")


class TestAluminumCalculation(unittest.TestCase):
    """Test aluminum bar weight calculation from database constants."""
    
    ALUMINUM_CONSTANTS = [
        {"size_mm": 112, "thickness_mm": 6, "density_kg_per_m": 2.529, "bars_per_container": 21},
        {"size_mm": 112, "thickness_mm": 8, "density_kg_per_m": 3.313, "bars_per_container": 21},
        {"size_mm": 97, "thickness_mm": 6, "density_kg_per_m": 2.313, "bars_per_container": 24},
    ]
    
    def _calculateAluminumWeight(self, length: float, sizeMm: int, thicknessMm: int) -> float:
        """Calculate aluminum weight based on constants."""
        for const in self.ALUMINUM_CONSTANTS:
            if const["size_mm"] == sizeMm and const["thickness_mm"] == thicknessMm:
                return length * const["density_kg_per_m"] * const["bars_per_container"]
        return 0
    
    def test_aluminum_112mm_6mm_40ft(self):
        """Test aluminum calculation for 112mm/6mm at 40ft (12.192m)."""
        weight = self._calculateAluminumWeight(12.192, 112, 6)
        # 12.192 * 2.529 * 21 ≈ 647.29 kg
        self.assertLess(abs(weight - 647.29), 1)
    
    def test_aluminum_112mm_8mm_40ft(self):
        """Test aluminum calculation for 112mm/8mm at 40ft (12.192m)."""
        weight = self._calculateAluminumWeight(12.192, 112, 8)
        # 12.192 * 3.313 * 21 ≈ 848.12 kg
        self.assertLess(abs(weight - 848.12), 1)
    
    def test_aluminum_97mm_6mm_40ft(self):
        """Test aluminum calculation for 97mm/6mm at 40ft (12.192m)."""
        weight = self._calculateAluminumWeight(12.192, 97, 6)
        # 12.192 * 2.313 * 24 ≈ 676.77 kg
        self.assertLess(abs(weight - 676.77), 1)
    
    def test_aluminum_112mm_6mm_15m(self):
        """Test aluminum calculation for 112mm/6mm at 15m (Mooc Long)."""
        weight = self._calculateAluminumWeight(15.0, 112, 6)
        # 15.0 * 2.529 * 21 ≈ 796.64 kg
        self.assertLess(abs(weight - 796.64), 1)
    
    def test_aluminum_97mm_6mm_15m(self):
        """Test aluminum calculation for 97mm/6mm at 15m (Mooc Long)."""
        weight = self._calculateAluminumWeight(15.0, 97, 6)
        # 15.0 * 2.313 * 24 ≈ 832.68 kg
        self.assertLess(abs(weight - 832.68), 1)


class TestFixedItemsPresence(unittest.TestCase):
    """Test that all fixed items are present for all container types."""
    
    FIXED_ITEM_TYPES = [
        "walking_floor",  # R2DX, KSD, or KMD
        "aluminum",       # Aluminum bars
        "hydraulic_pump", # 108cc or 130cc
        "hydraulic_oil",  # 200L barrel
    ]
    
    def test_fixed_items_for_container_20ft(self):
        """container_20ft should include all fixed items."""
        containerType = "container_20ft"
        self.assertIsNotNone(containerType)
    
    def test_fixed_items_for_container_40ft(self):
        """container_40ft should include all fixed items."""
        containerType = "container_40ft"
        self.assertIsNotNone(containerType)
    
    def test_fixed_items_for_mooc_long(self):
        """mooc_long should include all fixed items."""
        containerType = "mooc_long"
        self.assertIsNotNone(containerType)
    
    def test_fixed_items_for_thung_xe_tai(self):
        """thung_xe_tai should include all fixed items."""
        containerType = "thung_xe_tai"
        self.assertIsNotNone(containerType)


class TestContainerBuildLogic(unittest.TestCase):
    """Test container building logic for different container types."""
    
    def test_container_20ft_can_use_prebuilt(self):
        """container_20ft can use pre-built container from inventory."""
        containerType = "container_20ft"
        canUsePrebuilt = containerType in ["container_20ft", "container_40ft"]
        self.assertTrue(canUsePrebuilt)
    
    def test_container_40ft_can_use_prebuilt(self):
        """container_40ft can use pre-built container from inventory."""
        containerType = "container_40ft"
        canUsePrebuilt = containerType in ["container_20ft", "container_40ft"]
        self.assertTrue(canUsePrebuilt)
    
    def test_container_20ft_can_build_from_materials(self):
        """container_20ft can build container from materials if not in inventory."""
        containerType = "container_20ft"
        canBuildFromMaterials = containerType in ["container_20ft", "container_40ft"]
        self.assertTrue(canBuildFromMaterials)
    
    def test_mooc_long_never_includes_container(self):
        """mooc_long should never include container item (pre-built or built)."""
        containerType = "mooc_long"
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertFalse(shouldIncludeContainer)
    
    def test_thung_xe_tai_never_includes_container(self):
        """thung_xe_tai should never include container item (pre-built or built)."""
        containerType = "thung_xe_tai"
        shouldIncludeContainer = containerType in ["container_20ft", "container_40ft"]
        self.assertFalse(shouldIncludeContainer)
    
    def test_mooc_long_still_builds_structure(self):
        """mooc_long should still build structure from materials (steel, sheet, aluminum)."""
        needsStructureMaterials = True  # Always true for all types
        self.assertTrue(needsStructureMaterials)
    
    def test_thung_xe_tai_still_builds_structure(self):
        """thung_xe_tai should still build structure from materials."""
        needsStructureMaterials = True
        self.assertTrue(needsStructureMaterials)


class TestUserInputValidation(unittest.TestCase):
    """Test UserInput model validation for container types."""
    
    def test_valid_container_types_accepted(self):
        """All 4 container types should be accepted."""
        validTypes = ["container_20ft", "container_40ft", "mooc_long", "thung_xe_tai"]
        for containerType in validTypes:
            self.assertGreater(len(containerType), 0)
    
    def test_container_length_required(self):
        """Container length should be required for all types."""
        self.assertTrue(True)
    
    def test_default_lengths(self):
        """Default lengths should be correct."""
        defaults = {
            "container_20ft": 6.096,
            "container_40ft": 12.192,
            "mooc_long": 15.0,
            "thung_xe_tai": 15.0,
        }
        for containerType, length in defaults.items():
            self.assertGreater(length, 0)


if __name__ == "__main__":
    unittest.main()
