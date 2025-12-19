"""
Weight Target Calculator.
Calculates target weight range based on container length using linear interpolation.
"""
from config import logger


# Length (m) → Target Weight (kg) guideposts
WEIGHT_GUIDEPOSTS = [
    (6.0, 3500),   # 6m → 3.5 tons
    (9.0, 4500),   # 9m → 4.5 tons
    (12.0, 7000),  # 12m → 7 tons
    (15.0, 8000),  # 15m → 8 tons
]

WEIGHT_TOLERANCE = 500  # ±500kg soft limit
MARGIN_TOLERANCE = 0.05  # 5% breathing room below target margin


def calculateTargetWeight(containerLength: float) -> int:
    """
    Calculate target weight based on container length using linear interpolation.
    
    Args:
        containerLength: Length in meters
    
    Returns:
        Target weight in kg
    """
    # Handle edge cases
    if containerLength <= WEIGHT_GUIDEPOSTS[0][0]:
        return WEIGHT_GUIDEPOSTS[0][1]
    if containerLength >= WEIGHT_GUIDEPOSTS[-1][0]:
        return WEIGHT_GUIDEPOSTS[-1][1]
    
    # Find the two guideposts to interpolate between
    for i in range(len(WEIGHT_GUIDEPOSTS) - 1):
        length1, weight1 = WEIGHT_GUIDEPOSTS[i]
        length2, weight2 = WEIGHT_GUIDEPOSTS[i + 1]
        
        if length1 <= containerLength <= length2:
            # Linear interpolation
            ratio = (containerLength - length1) / (length2 - length1)
            targetWeight = weight1 + ratio * (weight2 - weight1)
            return int(round(targetWeight))
    
    # Fallback (shouldn't reach here)
    return WEIGHT_GUIDEPOSTS[-1][1]


def getWeightRange(containerLength: float) -> tuple[int, int, int]:
    """
    Get target weight and acceptable range for a container length.
    
    Args:
        containerLength: Length in meters
    
    Returns:
        (targetWeight, minWeight, maxWeight) in kg
    """
    target = calculateTargetWeight(containerLength)
    minWeight = target - WEIGHT_TOLERANCE
    maxWeight = target + WEIGHT_TOLERANCE
    
    logger.info(
        f"Weight target for {containerLength}m: {target}kg "
        f"(range: {minWeight}-{maxWeight}kg)"
    )
    
    return target, minWeight, maxWeight


def getMarginRange(targetMargin: float) -> tuple[float, float]:
    """
    Get acceptable profit margin range.
    
    Args:
        targetMargin: User's target profit margin (e.g., 0.20 for 20%)
    
    Returns:
        (minMargin, maxMargin) - acceptable range
    """
    maxMargin = targetMargin
    minMargin = max(0.0, targetMargin - MARGIN_TOLERANCE)
    return minMargin, maxMargin


def main():
    """Test weight calculations."""
    testLengths = [5.0, 6.0, 7.5, 9.0, 10.0, 12.0, 13.5, 15.0, 16.0]
    
    print("Container Length → Target Weight")
    print("-" * 40)
    for length in testLengths:
        target, minW, maxW = getWeightRange(length)
        print(f"  {length:5.1f}m → {target:,} kg (range: {minW:,}-{maxW:,})")


if __name__ == "__main__":
    main()

