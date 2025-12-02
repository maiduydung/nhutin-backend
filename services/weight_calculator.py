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
        containerLength: float, slatType: str, db: Database
    ) -> tuple[float, bool]:
        """
        Calculate aluminum bar weight from constants.
        Returns: (weight_kg, has_enough_inventory)
        """
        # Get aluminum constants for slatType
        sizeMm = int(slatType.replace("mm", ""))
        constants = db.executeQuery(
            """
            SELECT density_kg_per_m, bars_per_container
            FROM aluminum_bar_constants
            WHERE size_mm = %s
            ORDER BY density_kg_per_m DESC
            """,
            (sizeMm,),
        )

        if not constants:
            raise ValueError(f"No aluminum constants found for slatType: {slatType}")

        # Try highest density first
        for density, bars in constants:
            weight = containerLength * float(density) * bars
            
            # Check if we have enough inventory
            inventory = db.executeQuery(
                """
                SELECT final_quantity
                FROM inventory_records ir
                JOIN items i ON ir.item_id = i.id
                WHERE i.type = 'aluminum'
                ORDER BY ir.record_date DESC
                LIMIT 1
                """
            )
            
            if inventory and inventory[0][0] >= weight:
                return weight, True

        # If no density works, use the lowest one anyway
        lowestDensity, bars = constants[-1]
        weight = containerLength * float(lowestDensity) * bars
        return weight, False

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
    
    # Test aluminum bars
    alumWeight, hasEnough = WeightCalculator.calculateAluminumBarWeight(
        6.096, "97mm", db
    )
    print(f"Aluminum bars (97mm, 6.096m): {alumWeight} kg, enough: {hasEnough}")
    
    # Test galvanized sheet
    weightPerM = WeightCalculator.calculateGalvanizedSheetWeightPerMeter(
        "Tôn mạ kẽm 0.95 x 1200"
    )
    print(f"Galvanized sheet weight per meter: {weightPerM} kg/m")
    
    db.close()


if __name__ == "__main__":
    main()

