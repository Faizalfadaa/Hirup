import copy
from typing import Any

import pytest
import yaml

from services.exposure.params import (
    DEFAULT_PATH,
    ExposureParams,
    UnverifiedParamsWarning,
    load_params,
)


@pytest.fixture(scope="session")
def params() -> ExposureParams:
    """The real contract file. Its values are still unverified, so loading warns."""
    with pytest.warns(UnverifiedParamsWarning):
        return load_params()


@pytest.fixture
def raw_params() -> dict[str, Any]:
    """A fresh, mutable copy of the contract file for negative tests."""
    data: dict[str, Any] = yaml.safe_load(DEFAULT_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(data)
