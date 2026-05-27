import pandas as pd

from src.predictor import Predictor


class FixedPredictor(Predictor):
    def __init__(self, value):
        self.value = value

    def predict_next_close(self, daily_df):
        return self.value


class BrokenPredictor(Predictor):
    def predict_next_close(self, daily_df):
        raise RuntimeError("model failure")


def _df():
    return pd.DataFrame({"close": [100, 101, 102]})


def test_approves_when_prediction_above_price():
    assert FixedPredictor(110).approves_buy(_df(), 100) is True


def test_rejects_when_prediction_below_price():
    assert FixedPredictor(90).approves_buy(_df(), 100) is False


def test_failure_defaults_to_approve():
    # 예측 실패 시 게이트는 통과(전략 판단에 맡김)
    assert BrokenPredictor().approves_buy(_df(), 100) is True
