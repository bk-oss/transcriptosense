"""Test preprocessing module."""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.ingestion.preprocess import resolve_ffmpeg_path, SpeechSegment


class TestFFmpegResolution:
    """Test ffmpeg path resolution."""
    
    def test_resolve_ffmpeg_cli_argument(self):
        """Test that CLI argument takes precedence."""
        result = resolve_ffmpeg_path(cli_ffmpeg="ffmpeg")
        assert result == "ffmpeg"
    
    def test_resolve_ffmpeg_env_var(self):
        """Test that env var is used when CLI arg is None."""
        with patch.dict(os.environ, {"FFMPEG_PATH": "ffmpeg"}):
            result = resolve_ffmpeg_path()
            assert result == "ffmpeg"
    
    def test_resolve_ffmpeg_default(self):
        """Test default fallback to system ffmpeg."""
        with patch.dict(os.environ, {}, clear=True):
            result = resolve_ffmpeg_path()
            assert result == "ffmpeg"
    
    def test_resolve_ffmpeg_invalid_path(self):
        """Test that invalid path raises FileNotFoundError."""
        invalid_path = "C:\\nonexistent\\path\\ffmpeg.exe"
        with pytest.raises(FileNotFoundError):
            resolve_ffmpeg_path(cli_ffmpeg=invalid_path)


class TestSpeechSegment:
    """Test SpeechSegment dataclass."""
    
    def test_create_segment(self):
        """Test creating a speech segment."""
        segment = SpeechSegment(start=0.0, end=1.5)
        assert segment.start == 0.0
        assert segment.end == 1.5
    
    def test_segment_duration(self):
        """Test calculating segment duration."""
        segment = SpeechSegment(start=5.0, end=10.0)
        duration = segment.end - segment.start
        assert duration == 5.0
    
    def test_multiple_segments(self):
        """Test creating multiple segments."""
        segments = [
            SpeechSegment(start=0.0, end=1.0),
            SpeechSegment(start=1.0, end=2.0),
            SpeechSegment(start=2.0, end=3.0)
        ]
        assert len(segments) == 3
        total_duration = sum(s.end - s.start for s in segments)
        assert total_duration == 3.0
