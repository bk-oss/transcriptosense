"""Test database module."""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

# Patch DB path before importing database module
TEST_DB_PATH = tempfile.mktemp(suffix=".db")

def setup_test_db():
    """Setup test database."""
    with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
        from src.api.services.database import init_db
        init_db()


def teardown_test_db():
    """Cleanup test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestDatabase:
    """Test database operations."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        setup_test_db()
        yield
        teardown_test_db()
    
    def test_save_and_retrieve_transcription(self):
        """Test saving and retrieving a transcription."""
        with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
            from src.api.services.database import save_transcription, get_transcription_by_id
            
            test_id = save_transcription(
                filename="test.wav",
                language="en",
                transcription="Hello world",
                model_used="whisper-small",
                file_size="1.5 MB",
                duration_sec=10.5,
                speakers_count=1,
                has_diarization=False
            )
            
            record = get_transcription_by_id(test_id)
            assert record is not None
            assert record["filename"] == "test.wav"
            assert record["language"] == "en"
            assert record["transcription"] == "Hello world"
            assert record["duration_sec"] == 10.5
    
    def test_get_all_transcriptions(self):
        """Test retrieving all transcriptions."""
        with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
            from src.api.services.database import save_transcription, get_all_transcriptions
            
            save_transcription("test1.wav", "en", "Text 1", duration_sec=5)
            save_transcription("test2.wav", "fr", "Text 2", duration_sec=10)
            
            records = get_all_transcriptions()
            assert len(records) >= 2
    
    def test_search_transcriptions(self):
        """Test searching transcriptions."""
        with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
            from src.api.services.database import save_transcription, search_transcriptions
            
            save_transcription("test1.wav", "en", "Hello world")
            save_transcription("test2.wav", "fr", "Bonjour monde")
            
            results = search_transcriptions("hello")
            assert len(results) >= 1
            assert results[0]["transcription"] == "Hello world"
    
    def test_delete_transcription(self):
        """Test deleting a transcription."""
        with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
            from src.api.services.database import save_transcription, delete_transcription, get_transcription_by_id
            
            test_id = save_transcription("test.wav", "en", "Test text")
            assert get_transcription_by_id(test_id) is not None
            
            success = delete_transcription(test_id)
            assert success is True
            assert get_transcription_by_id(test_id) is None
    
    def test_clear_all_transcriptions(self):
        """Test clearing all transcriptions."""
        with patch("src.api.services.database.DB_PATH", TEST_DB_PATH):
            from src.api.services.database import save_transcription, clear_all_transcriptions, get_all_transcriptions
            
            save_transcription("test1.wav", "en", "Text 1")
            save_transcription("test2.wav", "fr", "Text 2")
            
            count = clear_all_transcriptions()
            assert count >= 2
            
            records = get_all_transcriptions()
            assert len(records) == 0
