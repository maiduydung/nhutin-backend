"""
Container Builder Service.
Builds containers from raw materials when pre-built containers unavailable.
"""
from typing import Any
from services.database import Database
from services.weight_calculator import WeightCalculator
from config import logger, CONTAINER_BUILD_SPECS


class ContainerBuilder:
    """Builds containers from raw materials."""

    def __init__(self, db: Database):
        self.db = db
        self.weightCalculator = WeightCalculator()
        self.slatType = "112mm"
        self.thickness = 6
        self.containerLength = 12.192

    def setSlatParams(self, slatType: str, thickness: int, containerLength: float):
        """Set slat parameters for aluminum calculation."""
        self.slatType = slatType
        self.thickness = thickness
        self.containerLength = containerLength

    def _calculateAluminumNeeded(self) -> float:
        """Calculate aluminum needed based on slat params."""
        weight, _, _ = self.weightCalculator.calculateAluminumBarWeight(
            self.containerLength, self.slatType, self.thickness, self.db
        )
        return weight

    def canBuildContainer(self, containerSize: str) -> dict[str, Any]:
        """Check if we can build a container from available materials."""
        if containerSize not in CONTAINER_BUILD_SPECS:
            return {"canBuild": False, "reason": f"Unknown size: {containerSize}"}

        specs = CONTAINER_BUILD_SPECS[containerSize]
        materials = []
        totalCost = 0.0
        totalWeight = 0.0

        # Get steel
        steelResult = self._getSteelMaterials(specs["steel_frame_kg"])
        materials.extend(steelResult["items"])
        totalCost += steelResult["totalCost"]
        totalWeight += steelResult["totalWeight"]
        steelShortfall = max(0, specs["steel_frame_kg"] - steelResult["totalWeight"])

        # Get galvanized sheets
        sheetResult = self._getGalvanizedSheets(specs["galvanized_sheet_m"])
        materials.extend(sheetResult["items"])
        totalCost += sheetResult["totalCost"]
        totalWeight += sheetResult["totalWeight"]

        # Get aluminum (includes steel compensation)
        aluminumNeeded = self._calculateAluminumNeeded() + steelShortfall
        alumResult = self._getAluminum(aluminumNeeded)
        materials.extend(alumResult["items"])
        totalCost += alumResult["totalCost"]
        totalWeight += alumResult["totalWeight"]

        # Need at least 50% of materials
        requiredWeight = specs["steel_frame_kg"] + self._calculateAluminumNeeded()
        canBuild = totalWeight >= requiredWeight * 0.5

        return {
            "canBuild": canBuild,
            "materials": materials,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(totalWeight, 2),
        }

    def buildContainer(
        self,
        containerSize: str,
        maxCost: float,
        currentCost: float,
        currentWeight: float,
        maxWeight: float,
    ) -> dict[str, Any]:
        """Build a container from available materials."""
        buildCheck = self.canBuildContainer(containerSize)

        if not buildCheck["canBuild"]:
            logger.warning(f"Cannot build {containerSize} container")
            return {"success": False, "items": [], "totalCost": 0, "totalWeight": 0}

        budgetRemaining = maxCost - currentCost
        weightRemaining = maxWeight - currentWeight

        # Check if building fits constraints
        if buildCheck["totalCost"] > budgetRemaining:
            scaleFactor = budgetRemaining / buildCheck["totalCost"]
            if scaleFactor < 0.1:
                logger.warning("Insufficient budget for container build")
                return {"success": False, "items": [], "totalCost": 0, "totalWeight": 0}
            return self._buildScaled(containerSize, scaleFactor, weightRemaining)

        if buildCheck["totalWeight"] > weightRemaining:
            scaleFactor = weightRemaining / buildCheck["totalWeight"]
            if scaleFactor < 0.5:
                logger.warning("Insufficient weight capacity for container build")
                return {"success": False, "items": [], "totalCost": 0, "totalWeight": 0}
            return self._buildScaled(containerSize, scaleFactor, weightRemaining)

        return {
            "success": True,
            "items": buildCheck["materials"],
            "totalCost": buildCheck["totalCost"],
            "totalWeight": buildCheck["totalWeight"],
        }

    def _buildScaled(
        self, containerSize: str, scaleFactor: float, maxWeight: float
    ) -> dict[str, Any]:
        """Build container with scaled-down materials."""
        specs = CONTAINER_BUILD_SPECS[containerSize]
        materials = []
        totalCost = 0.0
        totalWeight = 0.0

        # Scaled steel
        steelResult = self._getSteelMaterials(specs["steel_frame_kg"] * scaleFactor)
        materials.extend(steelResult["items"])
        totalCost += steelResult["totalCost"]
        totalWeight += steelResult["totalWeight"]

        # Scaled sheets
        sheetResult = self._getGalvanizedSheets(specs["galvanized_sheet_m"] * scaleFactor)
        materials.extend(sheetResult["items"])
        totalCost += sheetResult["totalCost"]
        totalWeight += sheetResult["totalWeight"]

        # Scaled aluminum
        alumResult = self._getAluminum(self._calculateAluminumNeeded() * scaleFactor)
        materials.extend(alumResult["items"])
        totalCost += alumResult["totalCost"]
        totalWeight += alumResult["totalWeight"]

        return {
            "success": len(materials) > 0,
            "items": materials,
            "totalCost": round(totalCost, 2),
            "totalWeight": round(totalWeight, 2),
            "scaled": True,
            "scaleFactor": scaleFactor,
        }

    def _getSteelMaterials(self, neededKg: float) -> dict[str, Any]:
        """Get steel materials from inventory."""
        steelTypes = ["steel_box", "steel_i", "steel_square", "steel_u", "steel_pipe", "steel_plate"]
        
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type, ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = ANY(%s) AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """,
            (steelTypes,),
        )

        if not result:
            return {"items": [], "totalCost": 0, "totalWeight": 0}

        items = []
        collectedKg = 0.0
        totalCost = 0.0
        rows = sorted(result, key=lambda r: float(r[6]) if r[6] else float("inf"))

        for row in rows:
            if collectedKg >= neededKg:
                break
            availableQty = float(row[5])
            unitPrice = float(row[6])
            needed = min(neededKg - collectedKg, availableQty)
            if needed <= 0:
                continue

            items.append({
                "id": row[0], "code": row[1], "name": row[2], "unit": row[3],
                "type": row[4], "quantity": round(needed, 2), "unitPrice": unitPrice,
                "totalValue": round(needed * unitPrice, 2), "weight": round(needed, 2),
                "forContainerBuild": True,
            })
            collectedKg += needed
            totalCost += needed * unitPrice

        return {"items": items, "totalCost": round(totalCost, 2), "totalWeight": round(collectedKg, 2)}

    def _getGalvanizedSheets(self, neededMeters: float) -> dict[str, Any]:
        """Get galvanized sheets from inventory."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type, ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'galvanized_sheet' AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """
        )

        if not result:
            return {"items": [], "totalCost": 0, "totalWeight": 0}

        items = []
        collectedMeters = 0.0
        totalCost = 0.0
        totalWeight = 0.0

        for row in result:
            if collectedMeters >= neededMeters:
                break
            availableQty = float(row[5])
            unitPrice = float(row[6])
            needed = min(neededMeters - collectedMeters, availableQty)
            if needed <= 0:
                continue

            weightPerMeter = self.weightCalculator.calculateGalvanizedSheetWeightPerMeter(row[2])
            weight = needed * weightPerMeter

            items.append({
                "id": row[0], "code": row[1], "name": row[2], "unit": row[3],
                "type": row[4], "quantity": round(needed, 2), "unitPrice": unitPrice,
                "totalValue": round(needed * unitPrice, 2), "weight": round(weight, 2),
                "forContainerBuild": True,
            })
            collectedMeters += needed
            totalCost += needed * unitPrice
            totalWeight += weight

        return {"items": items, "totalCost": round(totalCost, 2), "totalWeight": round(totalWeight, 2)}

    def _getAluminum(self, neededKg: float) -> dict[str, Any]:
        """Get aluminum from inventory."""
        result = self.db.executeQuery(
            """
            SELECT DISTINCT ON (i.id)
                i.id, i.code, i.name, i.unit, i.type, ir.final_quantity,
                CASE WHEN ir.final_quantity > 0 
                     THEN ir.final_value::numeric / ir.final_quantity ELSE 0 END as unit_price
            FROM items i
            JOIN inventory_records ir ON i.id = ir.item_id
            WHERE i.type = 'aluminum' AND ir.final_quantity > 0
            ORDER BY i.id, ir.record_date DESC
            """
        )

        if not result:
            return {"items": [], "totalCost": 0, "totalWeight": 0}

        row = result[0]
        availableQty = float(row[5])
        unitPrice = float(row[6])
        actualQty = min(neededKg, availableQty)

        if actualQty <= 0:
            return {"items": [], "totalCost": 0, "totalWeight": 0}

        return {
            "items": [{
                "id": row[0], "code": row[1], "name": row[2], "unit": row[3],
                "type": row[4], "quantity": round(actualQty, 2), "unitPrice": unitPrice,
                "totalValue": round(actualQty * unitPrice, 2), "weight": round(actualQty, 2),
                "forContainerBuild": True,
            }],
            "totalCost": round(actualQty * unitPrice, 2),
            "totalWeight": round(actualQty, 2),
        }
