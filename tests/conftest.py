"""
Pytest configuration and fixtures for Nhu Tin tests.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


@pytest.fixture
def mockDbConnection():
    """Fixture that provides a mock database connection."""
    with patch('services.database.Database.getDbConnection') as mockConn:
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        mockConn.return_value = connection
        yield {
            "connection": connection,
            "cursor": cursor,
            "patcher": mockConn
        }


@pytest.fixture
def sampleInventoryData():
    """Fixture that provides sample inventory data as DataFrame."""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "code": ["NL001", "NL002", "TP001"],
        "name": ["Nguyên liệu A", "Nguyên liệu B", "Thành phẩm X"],
        "type": ["NGUYÊN LIỆU", "NGUYÊN LIỆU", "THÀNH PHẨM"],
        "unit": ["KG", "LIT", "CÁI"],
        "initial_quantity": [100, 50, 200],
        "initial_value": [1000000, 500000, 2000000],
        "imported_quantity": [20, 10, 0],
        "imported_value": [200000, 100000, 0],
        "exported_quantity": [15, 5, 50],
        "exported_value": [150000, 50000, 500000],
        "final_quantity": [105, 55, 150],
        "final_value": [1050000, 550000, 1500000],
        "record_date": ["2024-01-15"] * 3
    })


@pytest.fixture
def sampleSummaryStats():
    """Fixture that provides sample summary statistics."""
    return {
        "totalItems": 100,
        "itemsByType": {
            "NGUYÊN LIỆU": 60,
            "THÀNH PHẨM": 30,
            "BAO BÌ": 10
        },
        "latestSnapshot": {
            "date": "2024-01-15",
            "totalQuantity": 5000,
            "totalValue": 50000000,
            "itemsCount": 100
        },
        "allTime": {
            "totalImported": 10000,
            "totalImportedValue": 100000000,
            "totalExported": 8000,
            "totalExportedValue": 80000000
        }
    }


@pytest.fixture
def sampleTopItems():
    """Fixture that provides sample top items data."""
    return pd.DataFrame({
        "code": ["A001", "A002", "A003", "A004", "A005"],
        "name": ["Top Item 1", "Top Item 2", "Top Item 3", "Top Item 4", "Top Item 5"],
        "type": ["TYPE_A", "TYPE_A", "TYPE_B", "TYPE_B", "TYPE_C"],
        "final_quantity": [500, 400, 300, 200, 100],
        "final_value": [5000000, 4000000, 3000000, 2000000, 1000000],
        "record_date": ["2024-01-15"] * 5
    })


@pytest.fixture
def sampleTypeDistribution():
    """Fixture that provides sample type distribution data."""
    return pd.DataFrame({
        "type": ["NGUYÊN LIỆU", "THÀNH PHẨM", "BAO BÌ"],
        "item_count": [60, 30, 10],
        "total_quantity": [3000, 1500, 500],
        "total_value": [30000000, 15000000, 5000000]
    })


@pytest.fixture
def mockOpenAiClient():
    """Fixture that provides a mock OpenAI client."""
    with patch('app.openaiClient') as mockClient:
        mockResponse = MagicMock()
        mockResponse.choices = [MagicMock()]
        mockResponse.choices[0].message.content = "This is a test response from the AI."
        mockClient.chat.completions.create.return_value = mockResponse
        yield mockClient

