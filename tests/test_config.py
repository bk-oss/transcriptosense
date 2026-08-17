"""Test configuration module."""
import pytest
from pathlib import Path
from config import CFG


def test_config_paths_exist():
    """Test that all required config paths exist or are creatable."""
    assert CFG.BASE_DIR.exists(), "Base directory should exist"
    assert CFG.DATA_RAW.exists(), "Data/raw directory should exist"
    assert CFG.DATA_PROCESSED.exists(), "Data/processed directory should exist"
    assert CFG.DATA_ANNOTATIONS.exists(), "Data/annotations directory should exist"
    assert CFG.MODELS_DIR.exists(), "Models directory should exist"
    assert CFG.OUT_TRANSCRIPTS.exists(), "Outputs/transcripts directory should exist"
    assert CFG.OUT_SUMMARIES.exists(), "Outputs/summaries directory should exist"
    assert CFG.OUT_EXPORTS.exists(), "Outputs/exports directory should exist"
    assert CFG.LOGS_DIR.exists(), "Logs directory should exist"


def test_config_base_dir_is_path():
    """Test that BASE_DIR is a Path object."""
    assert isinstance(CFG.BASE_DIR, Path)


def test_config_has_required_attributes():
    """Test that config has all required attributes."""
    required_attrs = [
        "BASE_DIR", "DATA_RAW", "DATA_PROCESSED", "DATA_ANNOTATIONS",
        "MODELS_DIR", "OUT_TRANSCRIPTS", "OUT_SUMMARIES", "OUT_EXPORTS", "LOGS_DIR"
    ]
    for attr in required_attrs:
        assert hasattr(CFG, attr), f"CFG should have {attr} attribute"
