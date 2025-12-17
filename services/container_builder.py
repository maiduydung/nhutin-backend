"""
Container Builder Service.
Handles building containers from raw materials (aluminum, steel, sheets)
when pre-built containers are not available in inventory.

Material requirements are based on:
THAICUONG 23062025 THUYETMINHKYTHUAT.pdf - Walking Floor S-Drive KSD 4.25" system
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger, CONTAINER_BUILD_SPECS, CONTAINER_MATERIAL_TYPES


class ContainerBuilder:
    """Builds containers from raw materials when pre-built containers unavailable."""

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()
        # Use specs from config.py
        self.specs = CONTAINER_BUILD_SPECS
        self.materialTypes = CONTAINER_MATERIAL_TYPES
        # Slat parameters (set via setters before building)
        self.slatType = "112mm"
        self.thickness = 6
        self.containerLength = 12.192

    def setSlatParams(self, slatType: str, thickness: int, containerLength: float):
        """Set slat parameters for aluminum calculation."""
        self.slatType = slatType
        self.thickness = thickness
        self.containerLength = containerLength

    def _calculateAluminumNeeded(self) -> float:
        """Calculate aluminum needed based on slat params (dynamic, not fixed)."""
        weight, density, bars = self.weightCalculator.calculateAluminumBarWeight(
            self.containerLength, self.slatType, self.thickness, self.db
        )
        return weight

    def canBuildContainer(self, containerSize: str) -> dict[str, Any]:
        """
        Check if we can build a container from available materials.
        Uses flexible material substitution - if not enough steel, uses aluminum instead.
        
        Material requirements based on THUYETMINHKYTHUAT.pdf:
        - Aluminum bars: For walking floor slats (21 bars × 12m)
        - Steel frame: Structural frame (hộp, vuông, mạ kẽm)
        - Steel plates: Floor/wall reinforcement (not always in inventory)
        - Galvanized sheets: Roof and wall panels
        
        Args:
            containerSize: "20ft" or "40ft"
        
        Returns:
            Dict with keys: canBuild, materials, totalCost, totalWeight, missingMaterials
        """
        if containerSize not in self.specs:
            logger.error(f"Unknown container size: {containerSize}")
            return {"canBuild": False, "reason": f"Unknown size: {containerSize}"}

        specs = self.specs[containerSize]
        materials = []
        totalCost = 0.0
        totalWeight = 0.0
        steelShortfall = 0.0
        
        # Total steel needed = steel_frame + steel_plate (if available)
        # But since we may not have steel_plate in inventory, use steel_frame as primary
        steelNeeded = specs["steel_frame_kg"]

        # Check steel availability (use any steel type: steel_box, steel_square)
        steelResult = self._checkSteelAvailability(steelNeeded)
        materials.extend(steelResult["items"])
        totalCost += steelResult["totalCost"]
        totalWeight += steelResult["totalWeight"]
        
        # Calculate steel shortfall (to be compensated with aluminum)
        if steelResult["availableQty"] < steelNeeded:
            steelShortfall = steelNeeded - steelResult["availableQty"]
            logger.info(
                f"Steel shortfall: {steelShortfall:.0f} kg "
                f"(needed {steelNeeded}, got {steelResult['availableQty']:.0f}). "
                f"Will compensate with aluminum."
            )

        # Check galvanized sheet availability
        sheetResult = self._checkGalvanizedSheetAvailability(specs["galvanized_sheet_m"])
        materials.extend(sheetResult["items"])
        totalCost += sheetResult["totalCost"]
        totalWeight += sheetResult["totalWeight"]

        # Check aluminum availability (including compensation for steel shortfall)
        # Calculate aluminum dynamically based on slat params (not fixed from specs)
        baseAluminumNeeded = self._calculateAluminumNeeded()
        totalAluminumNeeded = baseAluminumNeeded + steelShortfall
        alumResult = self._checkAluminumAvailability(totalAluminumNeeded)
        materials.extend(alumResult["items"])
        totalCost += alumResult["totalCost"]
        totalWeight += alumResult["totalWeight"]

        # Calculate if we have enough materials overall
        # We need at least 50% of total required weight to build (lower threshold due to material flexibility)
        requiredWeight = steelNeeded + baseAluminumNeeded
        # Add estimated galvanized sheet weight (approx 9 kg/m for typical sheets)
        requiredWeight += specs["galvanized_sheet_m"] * 9
        
        canBuild = totalWeight >= requiredWeight * 0.5  # 50% minimum threshold
        
        missingMaterials = []
        if not canBuild:
            missingMaterials.append({
                "type": "total_materials",
                "needed": requiredWeight,
                "available": totalWeight,
                "percentage": round(totalWeight / requiredWeight * 100, 1) if requiredWeight > 0 else 0,
            })

        return {
            "canBuild": canBuild,
            "containerSize": containerSize,
            "materials": materials,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(totalWeight, 2),
            "missingMaterials": missingMaterials,
            "steelShortfallCompensatedWithAluminum": steelShortfall > 0,
        }

    def buildContainer(
        self,
        containerSize: str,
        maxCost: float,
        currentCost: float,
        currentWeight: float,
        maxWeight: float,
    ) -> dict[str, Any]:
        """
        Attempt to build a container from available materials.
        
        Args:
            containerSize: "20ft" or "40ft"
            maxCost: Maximum allowed total cost
            currentCost: Current cost from fixed + variable items
            currentWeight: Current weight from fixed + variable items
            maxWeight: Maximum allowed weight (6000kg)
        
        Returns:
            Dict with: success, items (list of materials used), totalCost, totalWeight
        """
        buildCheck = self.canBuildContainer(containerSize)

        if not buildCheck["canBuild"]:
            logger.warning(
                f"Cannot build {containerSize} container. "
                f"Missing: {buildCheck['missingMaterials']}"
            )
            return {
                "success": False,
                "reason": "Missing materials",
                "missingMaterials": buildCheck["missingMaterials"],
                "items": [],
                "totalCost": 0,
                "totalWeight": 0,
            }

        # Check if building would exceed budget
        budgetRemaining = maxCost - currentCost
        if buildCheck["totalCost"] > budgetRemaining:
            # Try to build with reduced materials (scale down)
            scaleFactor = budgetRemaining / buildCheck["totalCost"]
            if scaleFactor < 0.1:  # Need at least 10% of materials (more aggressive)
                logger.warning(
                    f"Insufficient budget to build container. "
                    f"Need: {buildCheck['totalCost']:,.0f}, Available: {budgetRemaining:,.0f}"
                )
                return {
                    "success": False,
                    "reason": "Insufficient budget",
                    "items": [],
                    "totalCost": 0,
                    "totalWeight": 0,
                }
            logger.info(f"Scaling container build to {scaleFactor:.0%} due to budget")
            return self._buildScaledContainer(
                containerSize, scaleFactor, maxCost, currentCost, currentWeight, maxWeight
            )

        # Check if building would exceed weight
        weightRemaining = maxWeight - currentWeight
        if buildCheck["totalWeight"] > weightRemaining:
            scaleFactor = weightRemaining / buildCheck["totalWeight"]
            if scaleFactor < 0.5:
                logger.warning(
                    f"Insufficient weight capacity to build container. "
                    f"Need: {buildCheck['totalWeight']:.0f}kg, Available: {weightRemaining:.0f}kg"
                )
                return {
                    "success": False,
                    "reason": "Insufficient weight capacity",
                    "items": [],
                    "totalCost": 0,
                    "totalWeight": 0,
                }
            logger.info(f"Scaling container build to {scaleFactor:.0%} due to weight")
            return self._buildScaledContainer(
                containerSize, scaleFactor, maxCost, currentCost, currentWeight, maxWeight
            )

        logger.info(
            f"Building {containerSize} container from materials: "
            f"Cost={buildCheck['totalCost']:,.0f}, Weight={buildCheck['totalWeight']:.0f}kg"
        )

        return {
            "success": True,
            "containerSize": containerSize,
            "items": buildCheck["materials"],
            "totalCost": buildCheck["totalCost"],
            "totalWeight": buildCheck["totalWeight"],
            "builtFromMaterials": True,
        }

    def _buildScaledContainer(
        self,
        containerSize: str,
        scaleFactor: float,
        maxCost: float,
        currentCost: float,
        currentWeight: float,
        maxWeight: float,
    ) -> dict[str, Any]:
        """Build a container with scaled-down materials. Uses flexible substitution."""
        specs = self.specs[containerSize]
        materials = []
        totalCost = 0.0
        totalWeight = 0.0

        # Scale requirements (use steel_frame_kg as primary steel requirement)
        scaledSteelKg = specs["steel_frame_kg"] * scaleFactor
        scaledSheetM = specs["galvanized_sheet_m"] * scaleFactor
        # Calculate aluminum dynamically based on slat params
        baseAluminumKg = self._calculateAluminumNeeded()
        scaledAlumKg = baseAluminumKg * scaleFactor

        # Get scaled materials - steel first
        steelResult = self._checkSteelAvailability(scaledSteelKg)
        materials.extend(steelResult["items"])
        totalCost += steelResult["totalCost"]
        totalWeight += steelResult["totalWeight"]
        
        # Calculate steel shortfall for aluminum compensation
        steelShortfall = max(0, scaledSteelKg - steelResult["availableQty"])

        # Get sheets
        sheetResult = self._checkGalvanizedSheetAvailability(scaledSheetM)
        materials.extend(sheetResult["items"])
        totalCost += sheetResult["totalCost"]
        totalWeight += sheetResult["totalWeight"]

        # Get aluminum (including steel compensation)
        totalAlumNeeded = scaledAlumKg + steelShortfall
        alumResult = self._checkAluminumAvailability(totalAlumNeeded)
        materials.extend(alumResult["items"])
        totalCost += alumResult["totalCost"]
        totalWeight += alumResult["totalWeight"]

        if not materials:
            return {
                "success": False,
                "reason": "No materials available for scaled build",
                "items": [],
                "totalCost": 0,
                "totalWeight": 0,
            }

        return {
            "success": True,
            "containerSize": containerSize,
            "items": materials,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(totalWeight, 2),
            "builtFromMaterials": True,
            "scaled": True,
            "scaleFactor": scaleFactor,
        }

    def _checkSteelAvailability(self, neededKg: float) -> dict[str, Any]:
        """Check steel inventory and return available items."""
        steelTypes = ["steel_box", "steel_i", "steel_square", "steel_u", "steel_pipe", "steel_plate"]
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type,
                ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = ANY(%s) AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """,
            (steelTypes,),
        )

        if not result:
            return {"available": False, "availableQty": 0, "items": [], "totalCost": 0, "totalWeight": 0}

        items = []
        collectedKg = 0.0
        totalCost = 0.0

        # Sort by unit price (cheapest first)
        rows = sorted(result, key=lambda r: float(r[6]) if r[6] else float("inf"))

        for row in rows:
            if collectedKg >= neededKg:
                break

            availableQty = float(row[5])
            unitPrice = float(row[6])
            neededFromThis = min(neededKg - collectedKg, availableQty)

            if neededFromThis <= 0:
                continue

            items.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "quantity": round(neededFromThis, 2),
                "unitPrice": unitPrice,
                "totalValue": round(neededFromThis * unitPrice, 2),
                "weight": round(neededFromThis, 2),  # Steel: kg = weight
                "forContainerBuild": True,
            })

            collectedKg += neededFromThis
            totalCost += neededFromThis * unitPrice

        # Return whatever steel is available (aluminum will compensate shortfall)
        return {
            "available": collectedKg > 0,
            "availableQty": collectedKg,
            "items": items,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(collectedKg, 2),
        }

    def _checkGalvanizedSheetAvailability(self, neededMeters: float) -> dict[str, Any]:
        """Check galvanized sheet inventory."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type,
                ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'galvanized_sheet' AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """
        )

        if not result:
            return {"available": False, "availableQty": 0, "items": [], "totalCost": 0, "totalWeight": 0}

        items = []
        collectedMeters = 0.0
        totalCost = 0.0
        totalWeight = 0.0

        for row in result:
            if collectedMeters >= neededMeters:
                break

            availableQty = float(row[5])
            unitPrice = float(row[6])
            itemName = row[2]
            neededFromThis = min(neededMeters - collectedMeters, availableQty)

            if neededFromThis <= 0:
                continue

            weightPerMeter = self.weightCalculator.calculateGalvanizedSheetWeightPerMeter(itemName)
            itemWeight = neededFromThis * weightPerMeter

            items.append({
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "unit": row[3],
                "type": row[4],
                "quantity": round(neededFromThis, 2),
                "unitPrice": unitPrice,
                "totalValue": round(neededFromThis * unitPrice, 2),
                "weight": round(itemWeight, 2),
                "forContainerBuild": True,
            })

            collectedMeters += neededFromThis
            totalCost += neededFromThis * unitPrice
            totalWeight += itemWeight

        # Return whatever sheets are available
        return {
            "available": collectedMeters > 0,
            "availableQty": collectedMeters,
            "items": items,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(totalWeight, 2),
        }

    def _checkAluminumAvailability(self, neededKg: float) -> dict[str, Any]:
        """Check aluminum inventory for container building."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type,
                ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity 
                     ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'aluminum' AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """
        )

        if not result:
            return {"available": False, "availableQty": 0, "items": [], "totalCost": 0, "totalWeight": 0}

        row = result[0]
        availableQty = float(row[5])
        unitPrice = float(row[6])
        actualQty = min(neededKg, availableQty)

        if actualQty <= 0:
            return {"available": False, "availableQty": 0, "items": [], "totalCost": 0, "totalWeight": 0}

        items = [{
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "unit": row[3],
            "type": row[4],
            "quantity": round(actualQty, 2),
            "unitPrice": unitPrice,
            "totalValue": round(actualQty * unitPrice, 2),
            "weight": round(actualQty, 2),  # Aluminum: kg = weight
            "forContainerBuild": True,
        }]

        # Return whatever aluminum is available
        return {
            "available": actualQty > 0,
            "availableQty": actualQty,
            "items": items,
            "totalCost": round(actualQty * unitPrice, 2),
            "totalWeight": round(actualQty, 2),
        }


def main():
    """Test container builder with different slat/thickness combinations."""
    db = Database()
    builder = ContainerBuilder(db)

    # Test different slat/thickness combinations for 40ft
    testCases = [
        ("40ft", "97mm", 6, 12.192),   # 40ft, 97mm, 6mm
        ("40ft", "112mm", 6, 12.192),  # 40ft, 112mm, 6mm
        ("40ft", "112mm", 8, 12.192),  # 40ft, 112mm, 8mm
        ("20ft", "97mm", 6, 6.096),    # 20ft, 97mm, 6mm
    ]

    for containerSize, slatType, thickness, length in testCases:
        print("=" * 60)
        print(f"Testing: {containerSize}, {slatType}, {thickness}mm thick")
        
        # Set slat params
        builder.setSlatParams(slatType, thickness, length)
        
        # Check build capability
        result = builder.canBuildContainer(containerSize)
        print(f"  Can build: {result['canBuild']}")
        print(f"  Total cost: {result['totalCost']:,.0f} VND")
        print(f"  Total weight: {result['totalWeight']:.0f} kg")
        
        # Find aluminum item to check quantity
        for item in result.get("materials", []):
            if item.get("type") == "aluminum":
                print(f"  Aluminum: {item['quantity']:.2f} kg")
        
        if result.get("missingMaterials"):
            print(f"  Missing: {result['missingMaterials']}")

    db.close()


if __name__ == "__main__":
    main()

