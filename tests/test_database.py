"""
Tests for the Database service.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from services.database import Database


class TestDatabase:
    """Test cases for Database service."""

    @patch('services.database.psycopg2.connect')
    def test_getDbConnection_createsConnection(self, mockConnect):
        """Test that getDbConnection creates a connection."""
        mockConnect.return_value = MagicMock()
        
        result = Database.getDbConnection()
        
        mockConnect.assert_called_once()
        assert result is not None

    @patch('services.database.psycopg2.connect')
    def test_getDbConnection_usesCorrectParams(self, mockConnect):
        """Test that connection uses correct parameters."""
        mockConnect.return_value = MagicMock()
        
        Database.getDbConnection()
        
        callKwargs = mockConnect.call_args.kwargs
        assert "user" in callKwargs
        assert "password" in callKwargs
        assert "host" in callKwargs
        assert "port" in callKwargs
        assert "database" in callKwargs

    @patch('services.database.os.path.exists')
    def test_findSchemaFile_checksMultipleLocations(self, mockExists):
        """Test that _findSchemaFile checks multiple locations."""
        mockExists.return_value = False
        
        result = Database._findSchemaFile()
        
        # Should return None when file not found
        assert result is None
        # Should check multiple locations
        assert mockExists.call_count >= 2

    @patch('services.database.os.path.exists')
    def test_findSchemaFile_returnsPathWhenFound(self, mockExists):
        """Test that _findSchemaFile returns path when found."""
        mockExists.side_effect = [True]  # First location exists
        
        result = Database._findSchemaFile()
        
        assert result is not None
        assert "schema.psql" in result

    @patch.object(Database, '_findSchemaFile')
    @patch.object(Database, 'getDbConnection')
    def test_initSchema_skipsWhenNoSchemaFile(self, mockGetConn, mockFindSchema):
        """Test initSchema skips when schema file not found."""
        mockFindSchema.return_value = None
        
        result = Database.initSchema()
        
        assert result is False
        mockGetConn.assert_not_called()

    @patch.object(Database, '_findSchemaFile')
    @patch.object(Database, 'getDbConnection')
    @patch('builtins.open', mock_open(read_data="CREATE TABLE test;"))
    def test_initSchema_executesSchemaFile(self, mockGetConn, mockFindSchema):
        """Test initSchema executes schema SQL."""
        mockFindSchema.return_value = "schema.psql"
        mockConn = MagicMock()
        mockCursor = MagicMock()
        mockGetConn.return_value = mockConn
        mockConn.cursor.return_value = mockCursor
        
        result = Database.initSchema()
        
        assert result is True
        mockCursor.execute.assert_called_once()
        mockConn.commit.assert_called_once()
        mockCursor.close.assert_called_once()
        mockConn.close.assert_called_once()

    @patch.object(Database, '_findSchemaFile')
    @patch.object(Database, 'getDbConnection')
    @patch('builtins.open', mock_open(read_data="INVALID SQL;"))
    def test_initSchema_rollbacksOnError(self, mockGetConn, mockFindSchema):
        """Test initSchema rollbacks on error."""
        mockFindSchema.return_value = "schema.psql"
        mockConn = MagicMock()
        mockCursor = MagicMock()
        mockGetConn.return_value = mockConn
        mockConn.cursor.return_value = mockCursor
        mockCursor.execute.side_effect = Exception("SQL error")
        
        with pytest.raises(Exception):
            Database.initSchema()
        
        mockConn.rollback.assert_called_once()
        mockCursor.close.assert_called_once()
        mockConn.close.assert_called_once()


class TestDatabaseConnectionErrors:
    """Test database connection error handling."""

    @patch('services.database.psycopg2.connect')
    def test_getDbConnection_raisesOnFailure(self, mockConnect):
        """Test that connection errors propagate."""
        mockConnect.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            Database.getDbConnection()

