# TranscriptoSense Tests

This directory contains unit and integration tests for the TranscriptoSense project.

## Test Structure

- `test_config.py` - Configuration module tests
- `test_database.py` - Database operations tests
- `test_schemas.py` - Pydantic schema validation tests
- `test_preprocess.py` - Audio preprocessing utilities tests
- `test_routes.py` - API endpoint tests
- `conftest.py` - Shared pytest fixtures
- `pytest.ini` - Pytest configuration

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run a specific test file
```bash
pytest tests/test_config.py
```

### Run a specific test class
```bash
pytest tests/test_database.py::TestDatabase
```

### Run a specific test function
```bash
pytest tests/test_database.py::TestDatabase::test_save_and_retrieve_transcription
```

### Run tests matching a pattern
```bash
pytest -k "database"
```

### Run with coverage report
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

### Run only fast tests (skip slow tests)
```bash
pytest -m "not slow"
```

## Test Coverage

Current test coverage includes:

1. **Configuration (test_config.py)** - Path existence and attribute validation
2. **Database (test_database.py)** - CRUD operations, search, deletion
3. **Schemas (test_schemas.py)** - Pydantic model validation
4. **Preprocessing (test_preprocess.py)** - FFmpeg path resolution, data classes
5. **API Routes (test_routes.py)** - HTTP endpoints, error handling

## Writing New Tests

When adding new tests:

1. Use descriptive test names starting with `test_`
2. Group related tests in test classes
3. Use fixtures for common setup/teardown
4. Mock external dependencies (API calls, file I/O)
5. Add docstrings to explain test purpose
6. Use proper assertions with meaningful messages

Example:
```python
def test_some_feature(sample_transcription_data):
    """Test that some feature works correctly."""
    # Arrange
    expected = "value"
    
    # Act
    result = some_function(sample_transcription_data)
    
    # Assert
    assert result == expected, "Feature should return expected value"
```
