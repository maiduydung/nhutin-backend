"""
Test Runner for BOM Optimizer API
Captures input, output, and generates structured results for Reflex UI
"""

import json
import os
import requests
from datetime import datetime
from typing import Literal

# Configuration
LOCAL_URL = "http://localhost:7071/api/process_receipt"
PROD_URL = os.getenv("BOM_PROD_URL", "https://nhutin-bom-prod.azurewebsites.net/api/process_receipt")
PROD_KEY = os.getenv("BOM_PROD_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST CASES - Comprehensive coverage
# ═══════════════════════════════════════════════════════════════════════════════

TEST_CASES = [
    # ─────────────────────────────────────────────────────────────────────────────
    # CONTAINER 20FT TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "20ft_R2DX_97mm_500M_20pct",
        "description": "Container 20ft - Normal budget, R2DX model",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "20ft_R2DX_112mm_630M_20pct",
        "description": "Container 20ft - Higher budget, 112mm slat (may get warning)",
        "expectedResult": "warning",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 630000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "20ft_R2DX_350M_20pct_FAIL",
        "description": "Container 20ft - Budget too low (should fail)",
        "expectedResult": "fail",
        "failReason": "Fixed items exceed budget - R2DX floor alone costs ~250M",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 350000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "20ft_KSD_400M_20pct",
        "description": "Container 20ft - KSD model (cheaper floor)",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 400000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "20ft_KSD_450M_10pct",
        "description": "Container 20ft - Low margin (10%) - may get warning",
        "expectedResult": "warning",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.10
        }
    },
    {
        "name": "20ft_KSD_400M_40pct",
        "description": "Container 20ft - High margin (40%) - actually works for 20ft",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 400000000,
            "targetProfitMargin": 0.40
        }
    },
    {
        "name": "20ft_KMD_380M_22pct",
        "description": "Container 20ft - Budget KMD model",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 380000000,
            "targetProfitMargin": 0.22
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # CONTAINER 40FT TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "40ft_KSD_800M_15pct",
        "description": "Container 40ft - Normal budget",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 800000000,
            "targetProfitMargin": 0.15
        }
    },
    {
        "name": "40ft_R2DX_900M_15pct",
        "description": "Container 40ft - High budget R2DX",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 900000000,
            "targetProfitMargin": 0.15
        }
    },
    {
        "name": "40ft_R2DX_1200M_10pct",
        "description": "Container 40ft - Very high budget (may fail if inventory is low)",
        "expectedResult": "fail",
        "failReason": "High budget but may not have enough materials in inventory to spend that much",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 1200000000,
            "targetProfitMargin": 0.10
        }
    },
    {
        "name": "40ft_R2DX_400M_20pct_FAIL",
        "description": "Container 40ft - Budget too low (should fail)",
        "expectedResult": "fail",
        "failReason": "Budget too low to reach weight target for 40ft",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 400000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "40ft_KSD_750M_18pct",
        "description": "Container 40ft - 8mm thick aluminum",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 750000000,
            "targetProfitMargin": 0.18
        }
    },
    {
        "name": "40ft_KSD_800M_18pct",
        "description": "Container 40ft - Typical order",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 800000000,
            "targetProfitMargin": 0.18
        }
    },
    {
        "name": "40ft_R2DX_1000M_15pct",
        "description": "Container 40ft - Premium order",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 1000000000,
            "targetProfitMargin": 0.15
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # MOOC LONG TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "mooc_6m_KSD_450M_20pct",
        "description": "Mooc Long 6m - Small trailer",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 6.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "mooc_9m_R2DX_600M_20pct",
        "description": "Mooc Long 9m - Medium trailer",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 600000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "mooc_9m_R2DX_500M_25pct",
        "description": "Mooc Long 9m - High margin with R2DX (passes after container builder fix)",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.25
        }
    },
    {
        "name": "mooc_12m_KSD_550M_20pct",
        "description": "Mooc Long 12m - Standard",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 550000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "mooc_12m_R2DX_700M_18pct",
        "description": "Mooc Long 12m - R2DX model",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 700000000,
            "targetProfitMargin": 0.18
        }
    },
    {
        "name": "mooc_12m_KMD_450M_22pct",
        "description": "Mooc Long 12m - Budget KMD (passes after container builder fix)",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.22
        }
    },
    {
        "name": "mooc_15m_KSD_700M_20pct",
        "description": "Mooc Long 15m - Long trailer",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 700000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "mooc_15m_KMD_650M_25pct",
        "description": "Mooc Long 15m - High margin",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 650000000,
            "targetProfitMargin": 0.25
        }
    },
    {
        "name": "mooc_15m_R2DX_850M_16pct",
        "description": "Mooc Long 15m - Long haul premium",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 850000000,
            "targetProfitMargin": 0.16
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # THUNG XE TAI TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "truck_8m_KSD_480M_22pct",
        "description": "Thung Xe Tai 8m - Small truck",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 8.0,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 480000000,
            "targetProfitMargin": 0.22
        }
    },
    {
        "name": "truck_10m_KMD_550M_18pct",
        "description": "Thung Xe Tai 10m - Standard",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 10.0,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 550000000,
            "targetProfitMargin": 0.18
        }
    },
    {
        "name": "truck_12m_KSD_600M_20pct",
        "description": "Thung Xe Tai 12m - Medium truck",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 600000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "truck_12m_KSD_580M_20pct",
        "description": "Thung Xe Tai 12m - Standard order",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 580000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "truck_15m_KMD_650M_25pct",
        "description": "Thung Xe Tai 15m - Large truck",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 15.0,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 650000000,
            "targetProfitMargin": 0.25
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # EDGE CASES & STRESS TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "edge_very_low_budget_FAIL",
        "description": "Very low budget (200M) - should fail",
        "expectedResult": "fail",
        "failReason": "Budget too low for any configuration",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 200000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "edge_extreme_margin_FAIL",
        "description": "Extremely high margin (50%) - should fail",
        "expectedResult": "fail",
        "failReason": "50% margin leaves only 50% budget - impossible",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.50
        }
    },
    {
        "name": "edge_very_low_margin_5pct",
        "description": "Very low margin (5%) - may warn if can't hit exact margin",
        "expectedResult": "warning",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 550000000,
            "targetProfitMargin": 0.05
        }
    },
    {
        "name": "edge_very_high_budget_2B",
        "description": "Very high budget (2 Billion VND) - limited by inventory",
        "expectedResult": "fail",
        "failReason": "10% margin = 1.8B budget. Not enough materials in inventory to spend that much",
        "input": {
            "containerType": "container_40ft",
            "containerLength": 12.192,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 2000000000,
            "targetProfitMargin": 0.10
        }
    },
    {
        "name": "edge_min_length_5m",
        "description": "Minimum container length (5m - clamps to 6m)",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 5.0,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 400000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "edge_max_length_18m",
        "description": "Maximum container length (18m - clamps to 15m)",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 18.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 800000000,
            "targetProfitMargin": 0.18
        }
    },
    {
        "name": "edge_odd_length_7_5m",
        "description": "Odd container length (7.5m - interpolated)",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 7.5,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "edge_odd_length_10_5m",
        "description": "Odd container length (10.5m - interpolated)",
        "expectedResult": "pass",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 10.5,
            "itemModelType": "KMD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 580000000,
            "targetProfitMargin": 0.19
        }
    },
    {
        "name": "edge_odd_length_13_5m",
        "description": "Odd container length (13.5m - interpolated)",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 13.5,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 750000000,
            "targetProfitMargin": 0.17
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # MARGIN BOUNDARY TESTS
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "margin_15pct",
        "description": "Margin at 15%",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 600000000,
            "targetProfitMargin": 0.15
        }
    },
    {
        "name": "margin_20pct",
        "description": "Margin at 20%",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 550000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "margin_25pct",
        "description": "Margin at 25%",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 550000000,
            "targetProfitMargin": 0.25
        }
    },
    {
        "name": "margin_30pct",
        "description": "Margin at 30%",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 600000000,
            "targetProfitMargin": 0.30
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # IMPOSSIBLE CASES - Budget vs Weight Trade-offs
    # These cases should fail with clear error messages and diagnostic info
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "impossible_r2dx_15m_450M_20pct_FAIL",
        "description": "R2DX + 15m + 450M + 20% = Impossible (not enough budget for weight)",
        "expectedResult": "fail",
        "failReason": "R2DX (249M) + aluminum (100M) = 349M, leaves only 13M for 5700kg materials",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "impossible_r2dx_15m_450M_20pct_thung_FAIL",
        "description": "Same config for Thung Xe Tai - also impossible",
        "expectedResult": "fail",
        "failReason": "Same budget constraint issue as mooc_long",
        "input": {
            "containerType": "thung_xe_tai",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "impossible_ksd_160M_20pct_FAIL",
        "description": "KSD + 160M + 20% = Fixed items exceed budget",
        "expectedResult": "fail",
        "failReason": "KSD (157M) + aluminum (56M) + pump (12M) = 225M > 128M budget",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 160000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "impossible_r2dx_12m_350M_20pct_FAIL",
        "description": "R2DX + 12m + 350M + 20% = Budget too low for weight",
        "expectedResult": "fail",
        "failReason": "R2DX (249M) alone uses 89% of 280M budget",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 350000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "impossible_50pct_margin_FAIL",
        "description": "50% margin = only 50% budget - impossible with R2DX",
        "expectedResult": "fail",
        "failReason": "500M × 50% = 250M budget, R2DX alone is 249M",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "R2DX",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.50
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # WORKING CASES - Similar to impossible but with adjusted parameters
    # These should pass after fixing the parameters
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "fixed_r2dx_15m_700M_20pct",
        "description": "R2DX + 15m + 700M + 20% = Should work with higher budget",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 700000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "fixed_ksd_15m_650M_15pct",
        "description": "KSD + 15m + 650M + 15% = Should work with higher budget + lower margin",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 650000000,
            "targetProfitMargin": 0.15
        }
    },
    {
        "name": "fixed_r2dx_15m_850M_10pct",
        "description": "R2DX + 15m + 850M + 10% = Should work with much higher budget",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 850000000,
            "targetProfitMargin": 0.10
        }
    },
    {
        "name": "fixed_kmd_160M_20pct",
        "description": "KMD (cheapest) + 160M + 20% = Should work with cheapest floor",
        "expectedResult": "pass",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KMD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 350000000,
            "targetProfitMargin": 0.20
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # MODEL COMPARISON - Same config, different models
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "compare_kmd_12m_500M_20pct",
        "description": "KMD (cheapest floor) - 12m Mooc",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KMD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "compare_ksd_12m_500M_20pct",
        "description": "KSD (mid-range floor) - 12m Mooc",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "compare_r2dx_12m_500M_20pct",
        "description": "R2DX (premium floor) - 12m Mooc - passes after container builder fix",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 12.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # SLAT TYPE COMPARISON
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "slat_97mm_9m_500M",
        "description": "97mm slat (thinner) - should be lighter",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "KSD",
            "slatType": "97mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "slat_112mm_9m_500M",
        "description": "112mm slat (thicker) - should be heavier",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # THICKNESS COMPARISON
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "thick_6mm_9m_500M",
        "description": "6mm aluminum (thinner) - less aluminum weight",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "thick_8mm_9m_500M",
        "description": "8mm aluminum (thicker) - more aluminum weight",
        "expectedResult": "pass",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 9.0,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 500000000,
            "targetProfitMargin": 0.20
        }
    },
    
    # ─────────────────────────────────────────────────────────────────────────────
    # REAL WORLD ORDERS (from user's receipts)
    # ─────────────────────────────────────────────────────────────────────────────
    {
        "name": "realworld_mooc_15m_r2dx_450M_FAIL",
        "description": "Real order: Mooc Long 15m R2DX 450M 20% - user's failing case",
        "expectedResult": "fail",
        "failReason": "User's original failing case - insufficient budget for weight",
        "input": {
            "containerType": "mooc_long",
            "containerLength": 15.0,
            "itemModelType": "R2DX",
            "slatType": "112mm",
            "thickness": 6,
            "receiptPrice": 450000000,
            "targetProfitMargin": 0.20
        }
    },
    {
        "name": "realworld_20ft_ksd_160M_FAIL",
        "description": "Real order: Container 20ft KSD 160M 20% - user's failing case",
        "expectedResult": "fail",
        "failReason": "User's original failing case - fixed items exceed budget",
        "input": {
            "containerType": "container_20ft",
            "containerLength": 6.096,
            "itemModelType": "KSD",
            "slatType": "112mm",
            "thickness": 8,
            "receiptPrice": 160000000,
            "targetProfitMargin": 0.20
        }
    },
]


def runTest(testCase: dict, baseUrl: str, headers: dict = None) -> dict:
    """Run a single test case and return structured result"""
    headers = headers or {"Content-Type": "application/json", "Accept": "application/json"}
    
    startTime = datetime.now()
    try:
        response = requests.post(
            baseUrl,
            json=testCase["input"],
            headers=headers,
            timeout=60
        )
        endTime = datetime.now()
        durationMs = (endTime - startTime).total_seconds() * 1000
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "httpStatus": 200,
                "durationMs": round(durationMs),
                "response": data
            }
        else:
            return {
                "success": False,
                "httpStatus": response.status_code,
                "durationMs": round(durationMs),
                "error": response.text
            }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "httpStatus": None,
            "error": "Request timed out after 60 seconds"
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "httpStatus": None,
            "error": f"Connection failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "httpStatus": None,
            "error": str(e)
        }


def analyzeResult(testCase: dict, result: dict) -> dict:
    """
    Analyze the test result and generate UI guidance
    
    Returns structured data for Reflex UI to show user what to do
    """
    analysis = {
        "testName": testCase["name"],
        "description": testCase["description"],
        "expectedResult": testCase["expectedResult"],
        "input": testCase["input"],
        "result": result
    }
    
    # If request failed at HTTP level
    if not result["success"]:
        analysis["status"] = "error"
        analysis["uiGuidance"] = {
            "message": "Request failed - check server connection",
            "severity": "critical",
            "actions": []
        }
        return analysis
    
    response = result.get("response", {})
    apiStatus = response.get("status", "unknown")
    
    # Extract key metrics
    totalCost = response.get("totalCost", 0)
    totalWeight = response.get("totalWeight", 0)
    profitMargin = response.get("profitMargin", 0)
    constraints = response.get("constraints", {})
    
    weightOk = constraints.get("weightOk", False)
    marginOk = constraints.get("marginOk", False)
    weightRange = constraints.get("weightRange", [0, 0])
    marginRange = constraints.get("marginRange", [0, 0])
    
    targetWeight = (weightRange[0] + weightRange[1]) / 2 if weightRange else 0
    targetMargin = testCase["input"]["targetProfitMargin"] * 100
    
    # Determine status and generate UI guidance
    if apiStatus == "ok":
        analysis["status"] = "pass"
        analysis["uiGuidance"] = {
            "message": "Calculation successful ✓",
            "severity": "success",
            "summary": {
                "totalCost": totalCost,
                "totalWeight": totalWeight,
                "profitMargin": profitMargin,
                "itemCount": len(response.get("items", []))
            },
            "actions": []
        }
    elif apiStatus == "warning":
        analysis["status"] = "warning"
        actions = []
        
        # Check what's wrong and suggest fixes
        if not weightOk:
            weightDiff = totalWeight - targetWeight
            if weightDiff < 0:
                # Weight too low
                actions.append({
                    "action": "increase_weight",
                    "reason": f"Weight {totalWeight:,.0f}kg is below target {targetWeight:,.0f}kg",
                    "suggestions": [
                        "Increase container length",
                        "Use thicker aluminum (8mm instead of 6mm)",
                        "Choose heavier slat type (112mm instead of 97mm)"
                    ]
                })
            else:
                # Weight too high
                actions.append({
                    "action": "decrease_weight", 
                    "reason": f"Weight {totalWeight:,.0f}kg is above target {targetWeight:,.0f}kg",
                    "suggestions": [
                        "Decrease container length",
                        "Use thinner aluminum (6mm instead of 8mm)",
                        "Choose lighter slat type (97mm instead of 112mm)"
                    ]
                })
        
        if not marginOk:
            marginDiff = profitMargin - targetMargin
            if marginDiff < 0:
                # Margin too low (spending too much)
                actions.append({
                    "action": "increase_margin",
                    "reason": f"Margin {profitMargin:.1f}% is below target {targetMargin:.0f}%",
                    "suggestions": [
                        "Increase receipt price",
                        "Use cheaper walking floor model (KMD < KSD < R2DX)",
                        "Use thinner aluminum"
                    ]
                })
            else:
                # Margin too high (not spending enough)
                actions.append({
                    "action": "decrease_margin",
                    "reason": f"Margin {profitMargin:.1f}% is above target {targetMargin:.0f}%",
                    "suggestions": [
                        "Decrease target margin",
                        "Decrease receipt price",
                        "Use premium model (R2DX)"
                    ]
                })
        
        analysis["uiGuidance"] = {
            "message": "Calculation completed with warnings",
            "severity": "warning",
            "summary": {
                "totalCost": totalCost,
                "totalWeight": totalWeight,
                "profitMargin": profitMargin,
                "itemCount": len(response.get("items", []))
            },
            "actions": actions
        }
    else:
        # Failed - impossible case (items list is empty)
        analysis["status"] = "fail"
        errorMsg = response.get("error", "Unknown error")
        diagnostic = response.get("diagnostic", {})
        actions = []
        
        # Use diagnostic info if available for better guidance
        fixedCost = diagnostic.get("fixedItemsCost", totalCost)
        fixedWeight = diagnostic.get("fixedItemsWeight", totalWeight)
        maxBudget = diagnostic.get("maxBudget", constraints.get("weightRange", [0, 0])[1] if constraints else 0)
        
        # Parse error and suggest fixes
        if "exceed" in errorMsg.lower() and "budget" in errorMsg.lower():
            actions.append({
                "action": "increase_budget",
                "reason": errorMsg,
                "details": {
                    "fixedItemsCost": fixedCost,
                    "maxBudget": maxBudget,
                    "shortfall": fixedCost - maxBudget if fixedCost > maxBudget else 0
                },
                "suggestions": [
                    f"Increase receipt price to at least {fixedCost * 1.2:,.0f} VND (currently {testCase['input']['receiptPrice']:,.0f} VND)",
                    "Use cheaper walking floor model (KMD instead of R2DX, or KSD instead of R2DX)",
                    f"Decrease target margin from {testCase['input']['targetProfitMargin']*100:.0f}% to allow more spending"
                ]
            })
        elif "exceed" in errorMsg.lower() and "weight" in errorMsg.lower():
            actions.append({
                "action": "decrease_weight_or_length",
                "reason": errorMsg,
                "details": {
                    "fixedItemsWeight": fixedWeight,
                    "maxWeight": diagnostic.get("maxWeight", constraints.get("weightRange", [0, 0])[1] if constraints else 0)
                },
                "suggestions": [
                    "Decrease container length",
                    "Use lighter aluminum configuration (6mm instead of 8mm, 97mm instead of 112mm)"
                ]
            })
        elif "not enough materials" in errorMsg.lower():
            actions.append({
                "action": "check_inventory",
                "reason": errorMsg,
                "suggestions": [
                    "Check inventory levels",
                    "Order more materials",
                    "Reduce container length to lower weight requirement"
                ]
            })
        else:
            actions.append({
                "action": "review_parameters",
                "reason": errorMsg,
                "suggestions": [
                    "Review all input parameters",
                    "Contact support if issue persists"
                ]
            })
        
        analysis["uiGuidance"] = {
            "message": f"Calculation impossible: {errorMsg}",
            "severity": "error",
            "summary": {
                "totalCost": 0,
                "totalWeight": 0,
                "profitMargin": 0,
                "itemCount": 0
            },
            "diagnostic": diagnostic,
            "actions": actions
        }
    
    return analysis


def runAllTests(env: Literal["local", "prod"] = "local") -> dict:
    """Run all test cases and generate structured output"""
    
    if env == "local":
        baseUrl = LOCAL_URL
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
    else:
        baseUrl = PROD_URL
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-functions-key": PROD_KEY
        }
    
    print(f"\n{'═' * 80}")
    print(f"  BOM OPTIMIZER TEST SUITE - {env.upper()} ENVIRONMENT")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  Endpoint: {baseUrl}")
    print(f"{'═' * 80}\n")
    
    results = {
        "metadata": {
            "environment": env,
            "endpoint": baseUrl,
            "startedAt": datetime.now().isoformat(),
            "totalTests": len(TEST_CASES)
        },
        "summary": {
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "errors": 0
        },
        "tests": []
    }
    
    for i, testCase in enumerate(TEST_CASES, 1):
        print(f"[{i:02d}/{len(TEST_CASES)}] {testCase['name']}...", end=" ", flush=True)
        
        result = runTest(testCase, baseUrl, headers)
        analysis = analyzeResult(testCase, result)
        results["tests"].append(analysis)
        
        # Update summary
        status = analysis["status"]
        if status == "pass":
            results["summary"]["passed"] += 1
            print("✅ PASS")
        elif status == "warning":
            results["summary"]["warnings"] += 1
            print("⚠️ WARN")
        elif status == "fail":
            results["summary"]["failed"] += 1
            print("❌ FAIL")
        else:
            results["summary"]["errors"] += 1
            print("💥 ERROR")
    
    results["metadata"]["completedAt"] = datetime.now().isoformat()
    
    # Print summary
    s = results["summary"]
    print(f"\n{'═' * 80}")
    print(f"  TEST SUMMARY")
    print(f"{'─' * 80}")
    print(f"  ✅ Passed:   {s['passed']}")
    print(f"  ⚠️ Warnings: {s['warnings']}")
    print(f"  ❌ Failed:   {s['failed']}")
    print(f"  💥 Errors:   {s['errors']}")
    print(f"{'─' * 80}")
    print(f"  Total:      {len(TEST_CASES)}")
    print(f"{'═' * 80}\n")
    
    return results


def saveResults(results: dict, filename: str = None):
    """Save results to JSON file"""
    if filename is None:
        env = results["metadata"]["environment"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tests/results_{env}_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {filename}")
    return filename


if __name__ == "__main__":
    import sys
    
    env = sys.argv[1] if len(sys.argv) > 1 else "local"
    
    if env not in ["local", "prod"]:
        print("Usage: python test_runner.py [local|prod]")
        sys.exit(1)
    
    results = runAllTests(env)
    saveResults(results)

