from config import WALKING_FLOORS
from services.database import Database
from config import logger


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
        Calculate aluminum bar weight from constants based on slatType and thickness.
        
        Args:
            containerLength: Container length in meters
            slatType: Slat size ("97mm" or "112mm")
            thickness: Bar thickness (6 or 8 mm)
            db: Database connection
        
        Returns: (weight_kg, density_kg_per_m, bars_per_container)
        """
        sizeMm = int(slatType.replace("mm", ""))
        
        # Query for exact match of size_mm and thickness_mm
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
            # Fallback: try any thickness for this size
            logger.warning(
                f"No exact match for slatType={slatType}, thickness={thickness}mm. "
                f"Trying fallback..."
            )
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
            raise ValueError(
                f"No aluminum constants found for slatType={slatType}, thickness={thickness}mm"
            )

        density = float(result[0][0])
        bars = int(result[0][1])
        weight = containerLength * density * bars
        
        logger.info(
            f"Aluminum calculation: {containerLength}m × {density} kg/m × {bars} bars = {weight:.2f} kg "
            f"(slatType={slatType}, thickness={thickness}mm)"
        )
        
        return weight, density, bars

    @staticmethod
    def calculateGalvanizedSheetWeightPerMeter(itemName: str) -> float:
        """
        Calculate weight per meter for galvanized sheet.
        Formula: Thickness (mm) × Width (mm) × Density (kg/m³) / 1,000,000
        """
        # Extract dimensions from name like "Tôn mạ kẽm 0.95 x 1200"
        import re
        pattern = r"(\d+\.?\d*)\s*x\s*(\d+)"
        match = re.search(pattern, itemName)
        
        if not match:
            logger.warning(f"Could not parse dimensions from: {itemName}")
            return 0.0
        
        thickness = float(match.group(1))
        width = float(match.group(2))
        
        weightPerMeter = (
            thickness * width * WeightCalculator.GALVANIZED_STEEL_DENSITY / 1_000_000
        )
        return weightPerMeter

    # Weight constants for non-kg items (approximate values)
    # Container weight is 0 because it's the packaging, not cargo
    # The weight constraint applies to cargo that goes INTO the container
    CONTAINER_WEIGHT = {
        "20ft": 0,  # Not counted - it's the packaging
        "40ft": 0,  # Not counted - it's the packaging
    }
    HYDRAULIC_PUMP_WEIGHT = 50  # kg per unit (approximate)
    
    @staticmethod
    def calculateItemWeight(
        itemType: str, unit: str, quantity: float, itemName: str = ""
    ) -> float:
        """
        Calculate total weight for an item based on its type and unit.
        Supports: kg (direct), set (walking floors, containers), m (galvanized sheets)
        """
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
            # Detect container size from name
            if "40" in itemName.lower():
                return quantity * WeightCalculator.CONTAINER_WEIGHT["40ft"]
            return quantity * WeightCalculator.CONTAINER_WEIGHT["20ft"]
        
        # Galvanized sheets (per meter)
        if unit == "m" and itemType == "galvanized_sheet":
            weightPerMeter = WeightCalculator.calculateGalvanizedSheetWeightPerMeter(
                itemName
            )
            return quantity * weightPerMeter
        
        # Hydraulic pump (per piece - "cái" or "pcs")
        if itemType == "hydraulic_pump":
            return quantity * WeightCalculator.HYDRAULIC_PUMP_WEIGHT
        
        # Default: treat as kg if unknown
        logger.warning(f"Unknown weight calculation for type={itemType}, unit={unit}")
        return quantity if unit in ["kg", "pcs", "cái"] else 0.0


def main():
    """Test weight calculations."""
    from services.database import Database
    
    db = Database()
    
    # Test walking floor
    weight, itemType = WeightCalculator.calculateWalkingFloorWeight("R2DX")
    print(f"R2DX weight: {weight} kg, type: {itemType}")
    
    # Test aluminum bars with different slat/thickness combos
    print("\n--- Aluminum Bar Weight Tests ---")
    testCases = [
        (12.192, "97mm", 6),   # 40ft, 97mm, 6mm thick
        (12.192, "112mm", 6),  # 40ft, 112mm, 6mm thick
        (12.192, "112mm", 8),  # 40ft, 112mm, 8mm thick
        (6.096, "97mm", 6),    # 20ft, 97mm, 6mm thick
    ]
    for length, slatType, thickness in testCases:
        alumWeight, density, bars = WeightCalculator.calculateAluminumBarWeight(
            length, slatType, thickness, db
        )
        print(f"  {length}m, {slatType}, {thickness}mm: {alumWeight:.2f} kg")
    
    # Test galvanized sheet
    weightPerM = WeightCalculator.calculateGalvanizedSheetWeightPerMeter(
        "Tôn mạ kẽm 0.95 x 1200"
    )
    print(f"\nGalvanized sheet weight per meter: {weightPerM} kg/m")
    
    db.close()


if __name__ == "__main__":
    main()

