import pytest
from config import ConfigManager


@pytest.fixture(autouse=True)
def reset_config_cache():
    ConfigManager._cache = None
    yield
    ConfigManager._cache = None
