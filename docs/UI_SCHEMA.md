# BOM Optimizer API Response Schema for Reflex UI

This document defines the API response schema and UI guidance structure for the Nhu Tin BOM Optimizer.

## API Response Schema

### Success Response (status: "ok")

```json
{
  "status": "ok",
  "items": [
    {
      "id": 123,
      "name": "Sàn đùn R2DX 2.438M",
      "quantity": 1,
      "unit": "Cái",
      "unitPrice": 250000000,
      "totalPrice": 250000000,
      "weight": 751.0,
      "category": "walking_floor"
    }
  ],
  "totalCost": 450000000,
  "totalWeight": 3500.0,
  "profitMargin": 20.0,
  "constraints": {
    "weightOk": true,
    "marginOk": true,
    "weightRange": [3000, 4000],
    "marginRange": [15.0, 25.0]
  }
}
```

### Warning Response (status: "warning")

When constraints are close but not perfectly met:

```json
{
  "status": "warning",
  "items": [...],
  "totalCost": 450000000,
  "totalWeight": 4200.0,
  "profitMargin": 18.5,
  "constraints": {
    "weightOk": false,
    "marginOk": true,
    "weightRange": [3000, 4000],
    "marginRange": [15.0, 25.0]
  }
}
```

### Failed Response (status: "failed")

When optimization is impossible:

```json
{
  "status": "failed",
  "error": "Fixed items (380,000,000 VND) exceed max budget (280,000,000 VND)",
  "items": [],
  "totalCost": 0,
  "totalWeight": 0,
  "profitMargin": 0,
  "constraints": {
    "weightOk": false,
    "marginOk": false,
    "weightRange": [3000, 4000],
    "marginRange": [15.0, 25.0]
  }
}
```

---

## UI Guidance Schema

The test runner generates structured guidance for the Reflex UI to help users understand what actions to take.

### Guidance Structure

```json
{
  "uiGuidance": {
    "message": "Human-readable status message",
    "severity": "success | warning | error | critical",
    "summary": {
      "totalCost": 450000000,
      "totalWeight": 3500.0,
      "profitMargin": 20.0,
      "itemCount": 15
    },
    "actions": [
      {
        "action": "action_type",
        "reason": "Why this action is needed",
        "suggestions": [
          "Specific suggestion 1",
          "Specific suggestion 2"
        ]
      }
    ]
  }
}
```

### Severity Levels

| Severity | Description | UI Treatment |
|----------|-------------|--------------|
| `success` | Calculation successful, all constraints met | Green checkmark, proceed to generate BOM |
| `warning` | Calculation completed but some constraints not met | Yellow warning, show suggestions |
| `error` | Calculation failed, configuration is impossible | Red error, must change parameters |
| `critical` | System error (connection failed, timeout) | Red critical, contact support |

### Action Types

#### `increase_weight`
**When:** Weight is below target range
**UI:** Show weight slider/input with suggestion to increase
**Suggestions:**
- Increase container length
- Use thicker aluminum (8mm instead of 6mm)
- Choose heavier slat type (112mm instead of 97mm)

#### `decrease_weight`
**When:** Weight is above target range
**UI:** Show weight slider/input with suggestion to decrease
**Suggestions:**
- Decrease container length
- Use thinner aluminum (6mm instead of 8mm)
- Choose lighter slat type (97mm instead of 112mm)

#### `increase_margin`
**When:** Profit margin is below target
**UI:** Show margin adjustment or price input
**Suggestions:**
- Increase receipt price
- Use cheaper walking floor model (KMD < KSD < R2DX)
- Use thinner aluminum

#### `decrease_margin`
**When:** Profit margin is above target (spending too little)
**UI:** Show margin adjustment
**Suggestions:**
- Decrease target margin
- Decrease receipt price
- Use premium model (R2DX)

#### `increase_budget`
**When:** Fixed items exceed available budget
**UI:** Show price input with minimum required
**Suggestions:**
- Increase receipt price significantly
- Use cheaper walking floor model (KMD instead of R2DX)
- Decrease target margin to allow more spending

#### `check_inventory`
**When:** Not enough materials in inventory
**UI:** Show inventory warning
**Suggestions:**
- Check inventory levels
- Order more materials
- Reduce container length to lower weight requirement

#### `review_parameters`
**When:** General configuration error
**UI:** Show all parameters for review
**Suggestions:**
- Review all input parameters
- Contact support if issue persists

---

## Input Parameters Reference

| Parameter | Type | Description | Valid Values |
|-----------|------|-------------|--------------|
| `containerType` | string | Type of container/body | `container_20ft`, `container_40ft`, `mooc_long`, `thung_xe_tai` |
| `containerLength` | float | Length in meters | 5.0 - 18.0 |
| `itemModelType` | string | Walking floor model | `R2DX` (premium), `KSD` (standard), `KMD` (budget) |
| `slatType` | string | Aluminum slat width | `97mm`, `112mm` |
| `thickness` | int | Aluminum thickness | `6`, `8` |
| `receiptPrice` | int | Total receipt price in VND | 200,000,000 - 2,000,000,000 |
| `targetProfitMargin` | float | Target profit margin | 0.05 - 0.50 (5% - 50%) |

### Model Pricing (approximate)

| Model | Price Range | Weight | Best For |
|-------|-------------|--------|----------|
| R2DX | ~250M VND | ~751 kg | Premium orders, high budget |
| KSD | ~157M VND | ~503 kg | Standard orders |
| KMD | ~124M VND | ~502 kg | Budget orders |

### Weight Targets by Length

| Length | Target Weight | Range (±500kg) |
|--------|---------------|----------------|
| 6m / 20ft | 3,500 kg | 3,000 - 4,000 kg |
| 9m | 4,500 kg | 4,000 - 5,000 kg |
| 12m / 40ft | 7,000 kg | 6,500 - 7,500 kg |
| 15m | 8,000 kg | 7,500 - 8,500 kg |

---

## Reflex UI Component Mapping

### Success State
```python
def render_success(response):
    return rx.vstack(
        rx.icon("check-circle", color="green"),
        rx.heading("Calculation Successful"),
        rx.text(f"Total Cost: {format_currency(response.totalCost)}"),
        rx.text(f"Total Weight: {response.totalWeight:,.0f} kg"),
        rx.text(f"Profit Margin: {response.profitMargin:.1f}%"),
        rx.button("Generate BOM", on_click=State.generate_bom)
    )
```

### Warning State
```python
def render_warning(response, guidance):
    return rx.vstack(
        rx.icon("alert-triangle", color="orange"),
        rx.heading("Calculation Completed with Warnings"),
        rx.text(guidance.message),
        rx.foreach(
            guidance.actions,
            lambda action: rx.box(
                rx.text(action.reason, weight="bold"),
                rx.unordered_list(
                    rx.foreach(action.suggestions, rx.list_item)
                )
            )
        ),
        rx.button("Accept Anyway", variant="outline"),
        rx.button("Adjust Parameters", on_click=State.show_adjustments)
    )
```

### Error State
```python
def render_error(response, guidance):
    return rx.vstack(
        rx.icon("x-circle", color="red"),
        rx.heading("Calculation Failed"),
        rx.text(guidance.message, color="red"),
        rx.foreach(
            guidance.actions,
            lambda action: rx.callout(
                action.reason,
                icon="alert-circle",
                rx.unordered_list(
                    rx.foreach(action.suggestions, rx.list_item)
                )
            )
        ),
        rx.button("Adjust Parameters", on_click=State.reset_form)
    )
```

---

## Test Result File Structure

The test runner generates a JSON file with the following structure:

```json
{
  "metadata": {
    "environment": "local | prod",
    "endpoint": "http://localhost:7071/api/process_receipt",
    "startedAt": "2025-12-25T10:00:00",
    "completedAt": "2025-12-25T10:05:00",
    "totalTests": 45
  },
  "summary": {
    "passed": 38,
    "warnings": 3,
    "failed": 4,
    "errors": 0
  },
  "tests": [
    {
      "testName": "20ft_R2DX_97mm_500M_20pct",
      "description": "Container 20ft - Normal budget, R2DX model",
      "expectedResult": "pass",
      "input": { ... },
      "result": {
        "success": true,
        "httpStatus": 200,
        "durationMs": 1234,
        "response": { ... }
      },
      "status": "pass",
      "uiGuidance": { ... }
    }
  ]
}
```

This file can be passed to an LLM to:
1. Update UI components based on common failure patterns
2. Improve error messages and suggestions
3. Add new action types for edge cases
4. Validate the schema doesn't break existing UI code

