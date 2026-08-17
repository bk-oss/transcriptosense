"""Test API schemas."""
import pytest
from src.api.schemas.transcription import TranscriptionResponse
from src.api.schemas.history import HistoryResponse, TranscriptionRecord, DeleteResponse


class TestTranscriptionSchema:
    """Test TranscriptionResponse schema."""
    
    def test_valid_transcription_response(self):
        """Test creating a valid TranscriptionResponse."""
        response = TranscriptionResponse(
            id=1,
            filename="test.wav",
            language="en",
            transcription="Hello world",
            model_used="whisper-small",
            file_size="1.5 MB",
            duration_sec=10.5,
            speakers_count=1,
            has_diarization=False
        )
        assert response.id == 1
        assert response.filename == "test.wav"
        assert response.language == "en"
        assert response.transcription == "Hello world"
    
    def test_transcription_response_minimal(self):
        """Test creating a minimal TranscriptionResponse."""
        response = TranscriptionResponse(
            filename="test.wav",
            language="en",
            transcription="Hello world"
        )
        assert response.filename == "test.wav"
        assert response.language == "en"
        assert response.transcription == "Hello world"
        assert response.model_used == "whisper-small"  # Default value
    
    def test_transcription_response_dict(self):
        """Test converting TranscriptionResponse to dict."""
        response = TranscriptionResponse(
            id=1,
            filename="test.wav",
            language="en",
            transcription="Hello world"
        )
        data = response.model_dump()
        assert data["filename"] == "test.wav"
        assert data["language"] == "en"


class TestTranscriptionRecord:
    """Test TranscriptionRecord schema."""
    
    def test_valid_record(self):
        """Test creating a valid TranscriptionRecord."""
        record = TranscriptionRecord(
            id=1,
            filename="test.wav",
            language="en",
            transcription="Hello world",
            model_used="whisper-small",
            file_size="1.5 MB",
            duration_sec=10.5,
            speakers_count=1,
            has_diarization=False,
            created_at="2024-01-01 10:00:00"
        )
        assert record.id == 1
        assert record.filename == "test.wav"


class TestHistoryResponse:
    """Test HistoryResponse schema."""
    
    def test_valid_history(self):
        """Test creating a valid HistoryResponse."""
        records = [
            TranscriptionRecord(
                id=1,
                filename="test1.wav",
                language="en",
                transcription="Text 1",
                created_at="2024-01-01 10:00:00"
            ),
            TranscriptionRecord(
                id=2,
                filename="test2.wav",
                language="fr",
                transcription="Text 2",
                created_at="2024-01-02 10:00:00"
            )
        ]
        history = HistoryResponse(total=2, records=records)
        assert history.total == 2
        assert len(history.records) == 2
    
    def test_empty_history(self):
        """Test creating an empty HistoryResponse."""
        history = HistoryResponse(total=0, records=[])
        assert history.total == 0
        assert len(history.records) == 0


class TestDeleteResponse:
    """Test DeleteResponse schema."""
    
    def test_delete_response(self):
        """Test creating a DeleteResponse."""
        response = DeleteResponse(
            success=True,
            message="Deleted successfully"
        )
        assert response.success is True
        assert response.message == "Deleted successfully"
