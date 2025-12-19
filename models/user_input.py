from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# Valid container types accepted by the API
ContainerType = Literal["container_20ft", "container_40ft", "mooc_long", "thung_xe_tai"]


class UserInput(BaseModel):
    """
    Minimal payload schema for /process_receipt requests.
    
    Container Types:
    - container_20ft: Standard 20ft container (6.096m), includes container item
    - container_40ft: Standard 40ft container (12.192m), includes container item
    - mooc_long: Trailer (default 15m), NO container item in BOM
    - thung_xe_tai: Truck body (default 15m), NO container item in BOM
    """

    containerType: ContainerType = Field(..., description="Container type: container_20ft, container_40ft, mooc_long, or thung_xe_tai")
    containerLength: float = Field(..., description="Container length in meters.")
    itemModelType: str = Field(..., min_length=1, description="Inventory model code, e.g., R2DX.")
    slatType: str = Field(..., min_length=1, description="Slat specification: 97mm or 112mm.")
    thickness: int = Field(default=6, description="Aluminum bar thickness: 6 or 8 (mm).")
    receiptPrice: float = Field(..., description="Receipt price in VND.")

    def toDict(self) -> dict[str, Any]:
        """
        Helper wrapper to convert the model into a plain dictionary.
        """
        return self.model_dump()


def main() -> None:
    """
    Quick sanity check for manual execution.
    Tests all 4 container types.
    """
    testPayloads = [
        {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 360000000,
        },
        {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 600000000,
        },
        {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 700000000,
        },
        {
            "containerType": "thung_xe_tai",
            "containerLength": 15.0,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
        },
    ]
    
    for payload in testPayloads:
        userInput = UserInput.model_validate(payload)
        print(f"✅ {payload['containerType']}: {userInput.toDict()}")


if __name__ == "__main__":
    main()
