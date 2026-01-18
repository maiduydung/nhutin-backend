"""
Weight Calculator Service.
Calculates weight for different item types.
"""
import re
from config import (
    logger,
    WALKING_FLOORS,
    CONTAINER_EMPTY_WEIGHTS,
    HYDRAULIC_PUMP_WEIGHT_KG,
    CONSUMABLE_WEIGHTS,
)
from services.database import Database


class WeightCalculator:
    """Calculates weight for different item types."""

    GALVANIZED_STEEL_DENSITY = 7850  # kg/m³

    @staticmethod
    def calculateWalkingFloorWeight(itemModelType: str) -> tuple[float, str]:
        """
        Get walking floor weight and type from config.
        Returns: (weight_kg, item_type)
        """
        if itemModelType not in WALKING_FLOORS:
            raise ValueError(f"Unknown walking floor type: {itemModelType}")
        
        config = WALKING_FLOORS[itemModelType]
        return config["weight"], config["type"]

    @staticmethod
    def calculateAluminumBarWeight(
        containerLength: float, slatType: str, thickness: int, db: Database
    ) -> tuple[float, float, int]:
        """
        Calculate aluminum bar weight from constants.
        Returns: (weight_kg, density_kg_per_m, bars_per_container)
        """
        sizeMm = int(slatType.replace("mm", ""))
        
        result = db.executeQuery(
            """
            SELECT density_kg_per_m, bars_per_container
            FROM aluminum_bar_constants
            WHERE size_mm = %s AND thickness_mm = %s
            LIMIT 1
            """,
            (sizeMm, thickness),
        )

        if not result:
            logger.warning(f"No exact match for {slatType}/{thickness}mm, using fallback")
            result = db.executeQuery(
                """
                SELECT density_kg_per_m, bars_per_container
                FROM aluminum_bar_constants
                WHERE size_mm = %s
                ORDER BY thickness_mm ASC
                LIMIT 1
                """,
                (sizeMm,),
            )
            
        if not result:
            raise ValueError(f"No aluminum constants for {slatType}/{thickness}mm")

        density = float(result[0][0])
        bars = int(result[0][1])
        weight = containerLength * density * bars
        
        return weight, density, bars

    @staticmethod
    def calculateGalvanizedSheetWeightPerMeter(itemName: str) -> float:
        """
        Calculate weight per meter for galvanized sheet.
        Formula: Thickness (mm) × Width (mm) × Density / 1,000,000
        """
        pattern = r"(\d+\.?\d*)\s*x\s*(\d+)"
        match = re.search(pattern, itemName)
        
        if not match:
            logger.warning(f"Could not parse dimensions from: {itemName}")
            return 0.0
        
        thickness = float(match.group(1))
        width = float(match.group(2))
        
        return thickness * width * WeightCalculator.GALVANIZED_STEEL_DENSITY / 1_000_000

    @staticmethod
    def calculateItemWeight(
        itemType: str, unit: str, quantity: float, itemName: str = ""
    ) -> float:
        """Calculate total weight for an item based on type and unit."""
        # Direct weight in kg
        if unit == "kg":
            return quantity
        
        # Walking floor sets
        if unit == "set" and "walking_floor" in itemType:
            for modelType, config in WALKING_FLOORS.items():
                if config["type"] == itemType:
                    return quantity * config["weight"]
            return 0.0
        
        # Container sets
        if unit == "set" and itemType == "container":
            if "40" in itemName.lower():
                return quantity * CONTAINER_EMPTY_WEIGHTS.get("container_40ft", 2500)
            return quantity * CONTAINER_EMPTY_WEIGHTS.get("container_20ft", 1900)
        
        # Galvanized sheets (per meter)
        if unit == "m" and itemType == "galvanized_sheet":
            weightPerMeter = WeightCalculator.calculateGalvanizedSheetWeightPerMeter(itemName)
            return quantity * weightPerMeter
        
        # Hydraulic pump
        if itemType == "hydraulic_pump":
            return quantity * HYDRAULIC_PUMP_WEIGHT_KG
        
        # Consumables (welding_wire, cutting_nozzle, fastener, gear_pump)
        if itemType in CONSUMABLE_WEIGHTS:
            return quantity * CONSUMABLE_WEIGHTS[itemType]
        
        # Items sold by pieces (Con, pcs, cái) - typically light accessories
        if unit in ["Con", "pcs", "cái"]:
            return 0.0  # Don't count towards weight
        
        # Default: treat as kg if unknown
        return quantity if unit == "kg" else 0.0
