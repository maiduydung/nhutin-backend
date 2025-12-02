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

    @staticmethod
    def calculateItemWeight(
        itemType: str, unit: str, quantity: float, itemName: str = ""
    ) -> float:
        """
        Calculate total weight for an item based on its type and unit.
        """
        if unit == "kg":
            return quantity
        
        if unit == "set":
            if "walking_floor" in itemType:
                # Should use config, but for safety calculate from type
                for modelType, config in WALKING_FLOORS.items():
                    if config["type"] == itemType:
                        return quantity * config["weight"]
                return 0.0
            return 0.0
        
        if unit == "m" and itemType == "galvanized_sheet":
            weightPerMeter = WeightCalculator.calculateGalvanizedSheetWeightPerMeter(
                itemName
            )
            return quantity * weightPerMeter
        
        return 0.0


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

