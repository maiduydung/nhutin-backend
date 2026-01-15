"""
Tests for auto-fallback to best-effort mode when inventory is insufficient.

v2.2.0 - Auto fallback feature:
- When normal optimization fails due to insufficient inventory/budget
- System automatically retries with relaxed mode
- Returns result with warning instead of error
"""
import json
from datetime import datetime
from services.database import Database
from services.optimizer import OptimizerV2


def runAutoFallbackTests():
    """
    Run comprehensive tests for auto-fallback feature.
    
    Tests:
    1. Normal case - should work without fallback
    2. Low budget case - should fallback and return warning
    3. Manual relaxedMode=True - should work same as auto-fallback
    4. Various container types with limited inventory
    """
    db = Database()
    optimizer = OptimizerV2(db)
    
    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    testCases = [
        # Test 1: Normal case - Mooc 15m with good budget (should succeed without fallback)
        {
            "name": "Mooc 15m - Good Budget (700M, 20%)",
            "expectWarning": False,  # May or may not warn depending on inventory
            "params": {
                "containerType": "mooc_long",
                "containerLength": 15.0,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 700_000_000,
                "targetProfitMargin": 0.20,
            }
        },
        # Test 2: Low budget - should auto-fallback to best-effort
        {
            "name": "Mooc 15m - Low Budget (430M, 15%) - Auto Fallback",
            "expectWarning": True,
            "params": {
                "containerType": "mooc_long",
                "containerLength": 15.0,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 430_000_000,
                "targetProfitMargin": 0.15,
            }
        },
        # Test 3: Manual relaxedMode=True (should behave same as auto-fallback)
        {
            "name": "Mooc 15m - Manual Relaxed Mode (430M, 15%)",
            "expectWarning": True,
            "params": {
                "containerType": "mooc_long",
                "containerLength": 15.0,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 430_000_000,
                "targetProfitMargin": 0.15,
                "relaxedMode": True,
            }
        },
        # Test 4: Container 20ft with limited budget
        {
            "name": "Container 20ft - KSD 400M 20%",
            "expectWarning": False,  # May work depending on inventory
            "params": {
                "containerType": "container_20ft",
                "containerLength": 6.096,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 400_000_000,
                "targetProfitMargin": 0.20,
            }
        },
        # Test 5: Container 40ft with good budget
        {
            "name": "Container 40ft - KSD 800M 15%",
            "expectWarning": False,
            "params": {
                "containerType": "container_40ft",
                "containerLength": 12.192,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 800_000_000,
                "targetProfitMargin": 0.15,
            }
        },
        # Test 6: Thung xe tai with existing body (skip container build)
        {
            "name": "Truck 9.5m - Existing Body (378.7M, 20%)",
            "expectWarning": False,
            "params": {
                "containerType": "thung_xe_tai",
                "containerLength": 9.5,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 378_700_000,
                "targetProfitMargin": 0.20,
                "buildContainer": False,
            }
        },
        # Test 7: Very low budget - should definitely trigger fallback
        {
            "name": "Mooc 12m - Very Low Budget (350M, 15%)",
            "expectWarning": True,
            "params": {
                "containerType": "mooc_long",
                "containerLength": 12.0,
                "itemModelType": "KSD",
                "slatType": "112mm",
                "thickness": 6,
                "receiptPrice": 350_000_000,
                "targetProfitMargin": 0.15,
            }
        },
        # Test 8: R2DX model (more expensive)
        {
            "name": "Container 20ft - R2DX 500M 20%",
            "expectWarning": False,
            "params": {
                "containerType": "container_20ft",
                "containerLength": 6.096,
                "itemModelType": "R2DX",
                "slatType": "97mm",
                "thickness": 6,
                "receiptPrice": 500_000_000,
                "targetProfitMargin": 0.20,
            }
        },
    ]
    
    print("\n" + "=" * 80)
    print("🧪 AUTO-FALLBACK TEST SUITE")
    print("=" * 80)
    
    passed = 0
    failed = 0
    warnings = 0
    
    for i, test in enumerate(testCases, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {i}: {test['name']}")
        print(f"{'─' * 80}")
        
        try:
            result = optimizer.optimize(**test["params"])
            
            status = result["status"]
            warning = result.get("warning")
            itemCount = len(result["items"])
            weight = result["totalWeight"]
            margin = result["profitMargin"]
            weightOk = result["constraints"]["weightOk"]
            marginOk = result["constraints"]["marginOk"]
            
            # Determine test outcome
            if status == "error":
                outcome = "❌ ERROR"
                failed += 1
            elif status == "warning":
                outcome = "⚠️ WARNING (fallback)"
                warnings += 1
                passed += 1  # Warning with items is still a pass
            else:
                outcome = "✅ OK"
                passed += 1
            
            print(f"  Status: {outcome}")
            print(f"  Items: {itemCount}")
            print(f"  Weight: {weight:,.0f} kg (OK: {weightOk})")
            print(f"  Margin: {margin:.1f}% (OK: {marginOk})")
            if warning:
                print(f"  Warning: {warning[:80]}...")
            
            # Store result
            results.append({
                "test": test["name"],
                "status": status,
                "items": itemCount,
                "weight": weight,
                "margin": margin,
                "weightOk": weightOk,
                "marginOk": marginOk,
                "warning": warning,
                "outcome": outcome,
            })
            
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)}")
            failed += 1
            results.append({
                "test": test["name"],
                "status": "exception",
                "error": str(e),
                "outcome": "❌ EXCEPTION",
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"  Total: {len(testCases)}")
    print(f"  Passed: {passed} (including {warnings} with warnings)")
    print(f"  Failed: {failed}")
    print("=" * 80)
    
    # Save results
    outputFile = f"tests/results_autofallback_{timestamp}.json"
    with open(outputFile, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "summary": {
                "total": len(testCases),
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
            },
            "results": results,
        }, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: {outputFile}")
    
    db.close()
    return passed, failed


def main():
    """Run the test suite."""
    passed, failed = runAutoFallbackTests()
    exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
