"""Test API routes and endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.api.main import app


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health check endpoint returns OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.1.0"


class TestHistoryEndpoints:
    """Test history endpoints."""
    
    def test_get_history_empty(self, client):
        """Test getting history when empty."""
        with patch("src.api.services.database.get_all_transcriptions") as mock_get:
            mock_get.return_value = []
            response = client.get("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["records"] == []
    
    def test_get_history_with_records(self, client):
        """Test getting history with records."""
        mock_record = {
            "id": 1,
            "filename": "test.wav",
            "language": "en",
            "transcription": "Hello world",
            "model_used": "whisper-small",
            "file_size": "1.5 MB",
            "duration_sec": 10.5,
            "speakers_count": 1,
            "has_diarization": False,
            "created_at": "2024-01-01 10:00:00"
        }
        
        with patch("src.api.services.database.get_all_transcriptions") as mock_get:
            mock_get.return_value = [mock_record]
            response = client.get("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["records"]) == 1
    
    def test_search_history_short_query(self, client):
        """Test search with query too short."""
        response = client.get("/api/history/search?q=a")
        assert response.status_code == 400
    
    def test_search_history_valid_query(self, client):
        """Test search with valid query."""
        mock_record = {
            "id": 1,
            "filename": "test.wav",
            "language": "en",
            "transcription": "Hello world",
            "created_at": "2024-01-01 10:00:00"
        }
        
        with patch("src.api.services.database.search_transcriptions") as mock_search:
            mock_search.return_value = [mock_record]
            response = client.get("/api/history/search?q=hello")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
    
    def test_get_transcription_by_id_found(self, client):
        """Test getting a specific transcription."""
        mock_record = {
            "id": 1,
            "filename": "test.wav",
            "language": "en",
            "transcription": "Hello world",
            "model_used": "whisper-small",
            "file_size": "1.5 MB",
            "duration_sec": 10.5,
            "speakers_count": 1,
            "has_diarization": False,
            "created_at": "2024-01-01 10:00:00"
        }
        
        with patch("src.api.services.database.get_transcription_by_id") as mock_get:
            mock_get.return_value = mock_record
            response = client.get("/api/history/1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["filename"] == "test.wav"
    
    def test_get_transcription_by_id_not_found(self, client):
        """Test getting a non-existent transcription."""
        with patch("src.api.services.database.get_transcription_by_id") as mock_get:
            mock_get.return_value = None
            response = client.get("/api/history/999")
            assert response.status_code == 404
    
    def test_delete_transcription_found(self, client):
        """Test deleting a transcription."""
        with patch("src.api.services.database.delete_transcription") as mock_delete:
            mock_delete.return_value = True
            response = client.delete("/api/history/1")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_delete_transcription_not_found(self, client):
        """Test deleting non-existent transcription."""
        with patch("src.api.services.database.delete_transcription") as mock_delete:
            mock_delete.return_value = False
            response = client.delete("/api/history/999")
            assert response.status_code == 404
    
    def test_clear_all_transcriptions(self, client):
        """Test clearing all transcriptions."""
        with patch("src.api.services.database.clear_all_transcriptions") as mock_clear:
            mock_clear.return_value = 5
            response = client.delete("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "5" in data["message"]
