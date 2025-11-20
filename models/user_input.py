from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserInput(BaseModel):
    """
    Minimal payload schema for /process_receipt requests.
    """

    containerType: str = Field(..., min_length=1, description="Container category (container_20ft, container_40ft, etc.)")
    containerLength: float = Field(..., description="Container length in meters.")
    itemModelType: str = Field(..., min_length=1, description="Inventory model code, e.g., R2DX.")
    slatType: str = Field(..., min_length=1, description="Slat specification such as 97mm or 122mm.")

    def toDict(self) -> dict[str, Any]:
        """
        Helper wrapper to convert the model into a plain dictionary.
        """
        return self.model_dump()


def main() -> None:
    """
    Quick sanity check for manual execution.
    """
    samplePayload = {
        "containerType": "container_20ft",
        "containerLength": 6.06,
        "itemModelType": "R2DX",
        "slatType": "97mm",
    }
    userInput = UserInput.model_validate(samplePayload)
    print(userInput.toDict())


if __name__ == "__main__":
    main()
