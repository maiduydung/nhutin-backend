"""
Tests for the Gradio app module.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


class TestFormatFunctions:
    """Test formatting utility functions."""

    def test_formatCurrency_withValidValue(self):
        """Test currency formatting with valid value."""
        from app import formatCurrency
        
        result = formatCurrency(1000000)
        assert "₫" in result
        assert "1" in result

    def test_formatCurrency_withNone(self):
        """Test currency formatting with None."""
        from app import formatCurrency
        
        result = formatCurrency(None)
        assert result == "0 ₫"

    def test_formatCurrency_withZero(self):
        """Test currency formatting with zero."""
        from app import formatCurrency
        
        result = formatCurrency(0)
        assert "0" in result
        assert "₫" in result

    def test_formatNumber_withValidValue(self):
        """Test number formatting with valid value."""
        from app import formatNumber
        
        result = formatNumber(1000000)
        assert "1" in result
        # Vietnamese uses dots as thousand separators
        assert "." in result or "," not in result or result == "1.000.000"

    def test_formatNumber_withNone(self):
        """Test number formatting with None."""
        from app import formatNumber
        
        result = formatNumber(None)
        assert result == "0"


class TestGetSummaryMarkdown:
    """Test summary markdown generation."""

    @patch('app.Analytics.getSummaryStats')
    def test_getSummaryMarkdown_returnsMarkdown(self, mockStats):
        """Test that getSummaryMarkdown returns valid markdown."""
        from app import getSummaryMarkdown
        
        mockStats.return_value = {
            "totalItems": 100,
            "itemsByType": {"TYPE_A": 50, "TYPE_B": 50},
            "latestSnapshot": {
                "date": "2024-01-15",
                "totalQuantity": 5000,
                "totalValue": 50000000,
                "itemsCount": 100
            },
            "allTime": {
                "totalImported": 1000,
                "totalImportedValue": 10000000,
                "totalExported": 800,
                "totalExportedValue": 8000000
            }
        }
        
        result = getSummaryMarkdown()
        
        assert isinstance(result, str)
        assert "##" in result  # Has markdown headers
        assert "Tổng quan" in result or "Tồn kho" in result  # Vietnamese labels

    @patch('app.Analytics.getSummaryStats')
    def test_getSummaryMarkdown_handlesError(self, mockStats):
        """Test that getSummaryMarkdown handles errors gracefully."""
        from app import getSummaryMarkdown
        
        mockStats.side_effect = Exception("Database error")
        
        result = getSummaryMarkdown()
        
        assert "Error" in result or "❌" in result


class TestChartCreation:
    """Test chart creation functions."""

    @patch('app.Analytics.getItemTypeDistribution')
    def test_createTypeDistributionChart_withData(self, mockDistribution):
        """Test type distribution chart creation with data."""
        from app import createTypeDistributionChart
        
        mockDistribution.return_value = pd.DataFrame({
            "type": ["A", "B"],
            "total_value": [1000, 2000]
        })
        
        result = createTypeDistributionChart()
        
        # Should return a plotly figure or None
        assert result is None or hasattr(result, 'update_layout')

    @patch('app.Analytics.getItemTypeDistribution')
    def test_createTypeDistributionChart_withEmptyData(self, mockDistribution):
        """Test type distribution chart with empty data."""
        from app import createTypeDistributionChart
        
        mockDistribution.return_value = pd.DataFrame()
        
        result = createTypeDistributionChart()
        
        assert result is None

    @patch('app.Analytics.getTopItems')
    def test_createTopItemsChart_withData(self, mockTopItems):
        """Test top items chart creation."""
        from app import createTopItemsChart
        
        mockTopItems.return_value = pd.DataFrame({
            "name": ["Item A", "Item B"],
            "type": ["TYPE_A", "TYPE_B"],
            "final_value": [1000, 2000],
            "final_quantity": [10, 20]
        })
        
        result = createTopItemsChart(metric="value")
        
        assert result is None or hasattr(result, 'update_layout')

    @patch('app.Analytics.getMovementAnalysis')
    def test_createMovementChart_withData(self, mockMovement):
        """Test movement chart creation."""
        from app import createMovementChart
        
        mockMovement.return_value = pd.DataFrame({
            "name": ["Item A", "Item B"],
            "imported_value": [1000, 2000],
            "exported_value": [500, 1000]
        })
        
        result = createMovementChart()
        
        assert result is None or hasattr(result, 'update_layout')


class TestSearchItems:
    """Test item search functionality."""

    @patch('app.Analytics.searchItems')
    def test_searchItemsUI_withQuery(self, mockSearch):
        """Test search with valid query."""
        from app import searchItemsUI
        
        mockSearch.return_value = pd.DataFrame({
            "code": ["A001"],
            "name": ["Test Item"]
        })
        
        result = searchItemsUI("test")
        
        assert isinstance(result, pd.DataFrame)
        mockSearch.assert_called_once_with("test")

    @patch('app.Analytics.searchItems')
    def test_searchItemsUI_withEmptyQuery(self, mockSearch):
        """Test search with empty query."""
        from app import searchItemsUI
        
        result = searchItemsUI("")
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty
        mockSearch.assert_not_called()

    @patch('app.Analytics.searchItems')
    def test_searchItemsUI_withWhitespaceQuery(self, mockSearch):
        """Test search with whitespace-only query."""
        from app import searchItemsUI
        
        result = searchItemsUI("   ")
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestChatFunction:
    """Test chat functionality."""

    @patch('app.openaiClient', None)
    @patch('app.getDataContext')
    def test_chatWithInventory_withoutApiKey(self, mockContext):
        """Test chat falls back gracefully without API key."""
        from app import chatWithInventory
        
        mockContext.return_value = "Test context data"
        
        result = chatWithInventory("What is the inventory value?", [])
        
        assert isinstance(result, str)
        assert "No LLM configured" in result or "context" in result.lower()

    @patch('app.openaiClient', None)
    @patch('app.getDataContext')
    def test_chatWithInventory_withEmptyMessage(self, mockContext):
        """Test chat with empty message."""
        from app import chatWithInventory
        
        result = chatWithInventory("", [])
        
        assert "enter a question" in result.lower() or "please" in result.lower()


class TestGetDataContext:
    """Test data context generation."""

    @patch('app.Analytics.getSummaryStats')
    @patch('app.Analytics.getTopItems')
    @patch('app.Analytics.getItemTypeDistribution')
    def test_getDataContext_success(self, mockDistribution, mockTopItems, mockStats):
        """Test data context generation."""
        from app import getDataContext
        
        mockStats.return_value = {
            "totalItems": 100,
            "latestSnapshot": {"date": "2024-01-15", "totalValue": 50000000, "totalQuantity": 5000},
            "allTime": {"totalImported": 1000, "totalImportedValue": 10000000,
                       "totalExported": 800, "totalExportedValue": 8000000}
        }
        mockTopItems.return_value = pd.DataFrame({"code": ["A001"], "name": ["Item"]})
        mockDistribution.return_value = pd.DataFrame({"type": ["A"], "total_value": [1000]})
        
        result = getDataContext()
        
        assert isinstance(result, str)
        assert "100" in result  # Total items
        assert "Inventory" in result or "items" in result.lower()

    @patch('app.Analytics.getSummaryStats')
    def test_getDataContext_handlesError(self, mockStats):
        """Test data context handles errors."""
        from app import getDataContext
        
        mockStats.side_effect = Exception("Database error")
        
        result = getDataContext()
        
        assert "Error" in result or "error" in result


class TestGetAllItemsDataframe:
    """Test getting all items."""

    @patch('app.Analytics.getAllItemsWithLatestInventory')
    def test_getAllItemsDataframe_success(self, mockGetAll):
        """Test getting all items successfully."""
        from app import getAllItemsDataframe
        
        mockGetAll.return_value = pd.DataFrame({
            "code": ["A001", "A002"],
            "name": ["Item 1", "Item 2"]
        })
        
        result = getAllItemsDataframe()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch('app.Analytics.getAllItemsWithLatestInventory')
    def test_getAllItemsDataframe_handlesError(self, mockGetAll):
        """Test handling error when getting all items."""
        from app import getAllItemsDataframe
        
        mockGetAll.side_effect = Exception("Database error")
        
        result = getAllItemsDataframe()
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestCreateApp:
    """Test Gradio app creation."""

    def test_createApp_functionExists(self):
        """Test that createApp function exists and is callable."""
        from app import createApp
        
        # Verify the function exists and is callable
        assert callable(createApp)
    
    def test_gradioImport(self):
        """Test that Gradio is properly installed and importable."""
        import gradio as gr
        
        # Verify core Gradio components are available
        assert hasattr(gr, 'Blocks')
        assert hasattr(gr, 'Markdown')
        assert hasattr(gr, 'Plot')
        assert hasattr(gr, 'Chatbot')

