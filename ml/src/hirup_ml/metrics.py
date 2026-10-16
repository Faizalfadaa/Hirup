"""Regression and quantile metrics (SPEC 11.4)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def regression(y: FloatArray, pred: FloatArray) -> dict[str, float | None]:
    ok = np.isfinite(y) & np.isfinite(pred)
    y, pred = y[ok], pred[ok]
    if not len(y):
        return {"n": 0, "rmse": None, "mae": None, "r2": None, "bias": None}
    error = pred - y
    total = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": len(y),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "r2": float(1 - np.sum(error**2) / total) if total > 0 else None,
        "bias": float(np.mean(error)),
    }


def rmse(y: FloatArray, pred: FloatArray) -> float:
    value = regression(y, pred)["rmse"]
    return float("nan") if value is None else float(value)


def pinball(y: FloatArray, pred: FloatArray, alpha: float) -> float:
    ok = np.isfinite(y) & np.isfinite(pred)
    diff = y[ok] - pred[ok]
    return (
        float(np.mean(np.maximum(alpha * diff, (alpha - 1) * diff))) if ok.any() else float("nan")
    )


def coverage(y: FloatArray, low: FloatArray, high: FloatArray) -> float:
    ok = np.isfinite(y) & np.isfinite(low) & np.isfinite(high)
    return float(np.mean((y[ok] >= low[ok]) & (y[ok] <= high[ok]))) if ok.any() else float("nan")


def improvement(model_rmse: float, baseline_rmse: float) -> float | None:
    """Relative RMSE reduction against a baseline; positive means the model is better."""
    if not np.isfinite(model_rmse) or not np.isfinite(baseline_rmse) or baseline_rmse <= 0:
        return None
    return float(1 - model_rmse / baseline_rmse)
