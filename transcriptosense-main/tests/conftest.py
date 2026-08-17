"""Shared pytest configuration and fixtures."""
import pytest
import sys
from pathlib import Path

# Add the project root to sys.path so we can import modules
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root():
    """Provide the project root path."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide the test data directory."""
    test_dir = PROJECT_ROOT / "tests" / "data"
    test_dir.mkdir(exist_ok=True)
    return test_dir


@pytest.fixture
def sample_transcription_data():
    """Provide sample transcription data for tests."""
    return {
        "filename": "test_audio.wav",
        "language": "en",
        "transcription": "This is a test transcription",
        "model_used": "whisper-small",
        "file_size": "2.5 MB",
        "duration_sec": 15.0,
        "speakers_count": 1,
        "has_diarization": False
    }


@pytest.fixture
def sample_history_record():
    """Provide sample history record data for tests."""
    return {
        "id": 1,
        "filename": "test.wav",
        "language": "en",
        "transcription": "Hello world, this is a test",
        "model_used": "whisper-small",
        "file_size": "1.5 MB",
        "duration_sec": 10.5,
        "speakers_count": 1,
        "has_diarization": False,
        "created_at": "2024-01-01 10:00:00"
    }
