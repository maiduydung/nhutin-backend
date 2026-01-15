from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ContainerType = Literal["container_20ft", "container_40ft", "mooc_long", "thung_xe_tai"]


class UserInput(BaseModel):
    """
    Payload schema for /process_receipt requests.
    
    Container Types:
    - container_20ft: Standard 20ft container (6.096m)
    - container_40ft: Standard 40ft container (12.192m)
    - mooc_long: Trailer (default 15m), NO container item in BOM
    - thung_xe_tai: Truck body (user-specified length), NO container item in BOM
    """

    containerType: ContainerType = Field(
        ..., 
        description="Container type: container_20ft, container_40ft, mooc_long, or thung_xe_tai"
    )
    containerLength: float = Field(..., description="Container length in meters.")
    itemModelType: str = Field(..., min_length=1, description="Walking floor model: R2DX, KSD, or KMD")
    slatType: str = Field(..., min_length=1, description="Slat specification: 97mm or 112mm")
    thickness: int = Field(default=6, description="Aluminum bar thickness: 6 or 8 (mm)")
    receiptPrice: float = Field(..., gt=0, description="Receipt price in VND")
    targetProfitMargin: float = Field(
        default=0.20,
        ge=0.05,
        le=0.50,
        description="Target profit margin (0.05-0.50, default 0.20 = 20%)"
    )
    buildContainer: bool = Field(
        default=True,
        description="Whether to build container structure from materials. "
                    "Only applicable for thung_xe_tai. Set to False if user "
                    "already has a truck body and only needs walking floor installed."
    )
    existingContainerWeight: float = Field(
        default=0,
        ge=0,
        description="Weight of user's existing container/truck body in kg. "
                    "Only used when buildContainer=False. Typical truck body: 1500-2500 kg."
    )
    relaxedMode: bool = Field(
        default=False,
        description="When True, optimizer will do best-effort filling even when strict "
                    "constraints cannot be met (e.g., insufficient inventory to reach weight "
                    "target). Returns result with warning status instead of failing."
    )

    def toDict(self) -> dict[str, Any]:
        return self.model_dump()


def main() -> None:
    """Quick sanity check."""
    testPayloads = [
        {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "receiptPrice": 400_000_000,
            "targetProfitMargin": 0.20,
        },
        {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "receiptPrice": 700_000_000,
            # Uses default margin
        },
    ]
    
    for payload in testPayloads:
        userInput = UserInput.model_validate(payload)
        print(f"✅ {payload['containerType']}: margin={userInput.targetProfitMargin}")


if __name__ == "__main__":
    main()
