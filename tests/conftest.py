import pandas as pd
import pathlib
import pytest


@pytest.fixture
def sample_ohlcv():
    """Read 15 dummy 5-minute candles for fast offline tests."""
    path = pathlib.Path(__file__).parent / "ohlcv_sol_5m.csv"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df
