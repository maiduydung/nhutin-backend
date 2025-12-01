"""
Tests for the Analytics service.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from services.analytics import Analytics


class TestAnalytics:
    """Test cases for Analytics service."""

    @patch('services.analytics.Database.getDbConnection')
    def test_getSummaryStats_returnsExpectedStructure(self, mockGetConnection):
        """Test that getSummaryStats returns expected keys."""
        from datetime import date
        
        # Setup mock
        mockConn = MagicMock()
        mockCursor = MagicMock()
        mockGetConnection.return_value = mockConn
        mockConn.cursor.return_value = mockCursor
        
        # Mock cursor responses in order
        mockCursor.fetchone.side_effect = [
            (100,),  # Total items count
            (date(2024, 1, 1), 5000, 100000, 50),  # Latest snapshot (date object)
            (1000, 50000000, 800, 40000000),  # All-time stats
        ]
        mockCursor.fetchall.return_value = [("NGUYÊN LIỆU", 50), ("THÀNH PHẨM", 30)]
        
        # Execute
        result = Analytics.getSummaryStats()
        
        # Assert structure
        assert "totalItems" in result
        assert "itemsByType" in result
        assert "latestSnapshot" in result
        assert "allTime" in result
        
        mockConn.cursor.assert_called_once()
        mockCursor.close.assert_called_once()
        mockConn.close.assert_called_once()

    @patch('services.analytics.Database.getDbConnection')
    def test_getTopItems_returnsDataFrame(self, mockGetConnection):
        """Test that getTopItems returns a DataFrame."""
        # Setup mock connection
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        # Mock pandas read_sql to return empty DataFrame
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({
                "code": ["A001", "A002"],
                "name": ["Item 1", "Item 2"],
                "type": ["TYPE_A", "TYPE_B"],
                "final_quantity": [100, 200],
                "final_value": [10000, 20000],
                "record_date": ["2024-01-01", "2024-01-01"]
            })
            
            result = Analytics.getTopItems(limit=10, metric="value")
            
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2
            mockConn.close.assert_called_once()

    @patch('services.analytics.Database.getDbConnection')
    def test_getTopItems_byQuantity(self, mockGetConnection):
        """Test getTopItems with quantity metric."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame()
            
            Analytics.getTopItems(limit=5, metric="quantity")
            
            # Check that quantity ordering is in the query
            callArgs = mockReadSql.call_args
            query = callArgs[0][0]
            assert "final_quantity" in query

    @patch('services.analytics.Database.getDbConnection')
    def test_getItemTypeDistribution_returnsDataFrame(self, mockGetConnection):
        """Test that getItemTypeDistribution returns a DataFrame."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({
                "type": ["A", "B"],
                "item_count": [10, 20],
                "total_quantity": [100, 200],
                "total_value": [1000, 2000]
            })
            
            result = Analytics.getItemTypeDistribution()
            
            assert isinstance(result, pd.DataFrame)
            assert "type" in result.columns
            assert "total_value" in result.columns

    @patch('services.analytics.Database.getDbConnection')
    def test_searchItems_withQuery(self, mockGetConnection):
        """Test searchItems with a search query."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({
                "code": ["TEST001"],
                "name": ["Test Item"],
                "type": ["TEST"],
                "unit": ["KG"],
                "final_quantity": [50],
                "final_value": [5000],
                "record_date": ["2024-01-01"]
            })
            
            result = Analytics.searchItems("test")
            
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
            
            # Verify search pattern is passed correctly
            callArgs = mockReadSql.call_args
            params = callArgs[1]["params"]
            assert "%test%" in params

    @patch('services.analytics.Database.getDbConnection')
    def test_getPriceHistory_withoutItemCode(self, mockGetConnection):
        """Test getPriceHistory without specific item code."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({
                "code": ["A001"],
                "name": ["Item"],
                "price": [100.0],
                "source": ["import"],
                "effective_at": ["2024-01-01"]
            })
            
            result = Analytics.getPriceHistory()
            
            assert isinstance(result, pd.DataFrame)

    @patch('services.analytics.Database.getDbConnection')
    def test_getPriceHistory_withItemCode(self, mockGetConnection):
        """Test getPriceHistory with specific item code."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame()
            
            Analytics.getPriceHistory(itemCode="A001", limit=50)
            
            callArgs = mockReadSql.call_args
            params = callArgs[1]["params"]
            assert "A001" in params

    def test_executeCustomQuery_rejectsInsert(self):
        """Test that INSERT queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            Analytics.executeCustomQuery("INSERT INTO items VALUES (1, 'test')")

    def test_executeCustomQuery_rejectsDelete(self):
        """Test that DELETE queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            Analytics.executeCustomQuery("DELETE FROM items WHERE id = 1")

    def test_executeCustomQuery_rejectsDrop(self):
        """Test that DROP queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            Analytics.executeCustomQuery("DROP TABLE items")

    def test_executeCustomQuery_rejectsUpdate(self):
        """Test that UPDATE queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            Analytics.executeCustomQuery("UPDATE items SET name = 'test'")

    def test_executeCustomQuery_rejectsNonSelect(self):
        """Test that non-SELECT queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            Analytics.executeCustomQuery("TRUNCATE TABLE items")

    @patch('services.analytics.Database.getDbConnection')
    def test_executeCustomQuery_allowsSelect(self, mockGetConnection):
        """Test that valid SELECT queries are allowed."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({"count": [10]})
            
            result = Analytics.executeCustomQuery("SELECT COUNT(*) FROM items")
            
            assert isinstance(result, pd.DataFrame)

    @patch('services.analytics.Database.getDbConnection')
    def test_getInventoryTrends_defaultDays(self, mockGetConnection):
        """Test getInventoryTrends with default 30 days."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame({
                "record_date": ["2024-01-01"],
                "total_quantity": [100],
                "total_value": [10000],
                "imports": [50],
                "import_value": [5000],
                "exports": [30],
                "export_value": [3000]
            })
            
            result = Analytics.getInventoryTrends()
            
            assert isinstance(result, pd.DataFrame)
            callArgs = mockReadSql.call_args
            params = callArgs[1]["params"]
            assert params == (30,)

    @patch('services.analytics.Database.getDbConnection')
    def test_getInventoryTrends_customDays(self, mockGetConnection):
        """Test getInventoryTrends with custom days."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        
        with patch('services.analytics.pd.read_sql') as mockReadSql:
            mockReadSql.return_value = pd.DataFrame()
            
            Analytics.getInventoryTrends(days=90)
            
            callArgs = mockReadSql.call_args
            params = callArgs[1]["params"]
            assert params == (90,)


class TestAnalyticsErrorHandling:
    """Test error handling in Analytics service."""

    @patch('services.analytics.Database.getDbConnection')
    def test_getSummaryStats_handlesException(self, mockGetConnection):
        """Test that getSummaryStats properly raises on error."""
        mockConn = MagicMock()
        mockCursor = MagicMock()
        mockGetConnection.return_value = mockConn
        mockConn.cursor.return_value = mockCursor
        mockCursor.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            Analytics.getSummaryStats()

    @patch('services.analytics.pd.read_sql')
    @patch('services.analytics.Database.getDbConnection')
    def test_getTopItems_returnsEmptyOnError(self, mockGetConnection, mockReadSql):
        """Test that getTopItems returns empty DataFrame on error."""
        mockConn = MagicMock()
        mockGetConnection.return_value = mockConn
        mockReadSql.side_effect = Exception("Query failed")
        
        result = Analytics.getTopItems()
        
        assert isinstance(result, pd.DataFrame)
        assert result.empty

