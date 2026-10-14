"""Train and validate the PM2.5 nowcast (SPEC 11.3-11.5).

M1 is a LightGBM L2 model (published P50); M1-Q are quantile models for P10/P90. Validation is
leave-one-station-out, with a 2 km spatial block CV and a 20% temporal hold-out as cross-checks.
Baselines B0 (CAMS) and B1 (IDW, p=2) are scored on exactly the same rows.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb
import numpy as np
import numpy.typing as npt
import optuna
import pandas as pd

from hirup_ml import metrics, registry
from hirup_ml.config import load_config, models_dir
from hirup_ml.dataset import Dataset
from hirup_pipelines import store
from hirup_pipelines.settings import TIMEZONE

log = logging.getLogger(__name__)
FloatArray = npt.NDArray[np.float64]
Folds = list[list[int]]


def monotone_constraints(names: Sequence[str]) -> list[int]:
    cfg = load_config()["monotone"]
    up, down = tuple(cfg["increasing_prefixes"]), tuple(cfg["decreasing_prefixes"])
    return [1 if n.startswith(up) else -1 if n.startswith(down) else 0 for n in names]


def fit(
    x: FloatArray,
    y: FloatArray,
    weight: FloatArray,
    names: Sequence[str],
    params: dict[str, Any],
    alpha: float | None = None,
) -> lgb.Booster:
    cfg = load_config()
    settings = {
        **params,
        "objective": "regression" if alpha is None else "quantile",
        "seed": int(cfg["seed"]),
        "deterministic": True,
        "force_col_wise": True,
        "num_threads": 0,
    }
    if alpha is None:
        settings["monotone_constraints"] = monotone_constraints(names)
    else:
        # LightGBM rejects monotone constraints for the quantile objective, so only the
        # published P50 (L2 model) is constrained; P10/P90 are clamped around it afterwards.
        settings["alpha"] = alpha
    rounds = int(settings.pop("n_estimators"))
    data = lgb.Dataset(x, label=y, weight=weight, feature_name=list(names), free_raw_data=False)
    return lgb.train(settings, data, num_boost_round=rounds)


def station_folds(ds: Dataset) -> Folds:
    """Leave-one-station-out: one fold per station that has labels."""
    return [[int(s)] for s in np.unique(ds.rows[:, 1])]


def block_folds(ds: Dataset) -> Folds:
    """Stations grouped into `block_m` squares, one fold per block (SPEC 11.4)."""
    size = float(load_config()["validation"]["block_m"])
    keys = [tuple(k) for k in np.floor(ds.xy / size).astype(int)]
    labelled = set(np.unique(ds.rows[:, 1]).tolist())
    blocks: dict[tuple[int, ...], list[int]] = {}
    for index, key in enumerate(keys):
        if index in labelled:
            blocks.setdefault(key, []).append(index)
    return list(blocks.values())


@dataclass
class Oof:
    """Out-of-fold predictions aligned with `Dataset.rows`."""

    mean: FloatArray
    quantiles: dict[float, FloatArray]
    idw: FloatArray  # baseline B1: IDW from the stations the fold could see
    fold: npt.NDArray[np.int64]


def cross_validate(
    ds: Dataset, folds: Folds, params: dict[str, Any], *, quantiles: Sequence[float] = ()
) -> Oof:
    base, y, weight = ds.base(), ds.y, ds.weights
    names = ds.feature_names
    idw_column = len(ds.static_names) + len(ds.shared)  # first fold column is idw_pm25
    oof = Oof(
        np.full(len(y), np.nan),
        {q: np.full(len(y), np.nan) for q in quantiles},
        np.full(len(y), np.nan),
        np.full(len(y), -1),
    )
    for number, holdout in enumerate(folds):
        x = np.column_stack([base, ds.fold(holdout)])
        test = np.isin(ds.rows[:, 1], holdout)
        train = ~test
        if not test.any() or not train.any():
            continue
        oof.mean[test] = fit(x[train], y[train], weight[train], names, params).predict(x[test])
        for q in quantiles:
            model = fit(x[train], y[train], weight[train], names, params, alpha=q)
            oof.quantiles[q][test] = model.predict(x[test])
        oof.idw[test] = x[test, idw_column]
        oof.fold[test] = number
    return oof


def tune(ds: Dataset, folds: Folds, n_trials: int) -> dict[str, Any]:
    """Optuna search scored by LOSO RMSE (SPEC 11.5)."""
    cfg = load_config()
    base = dict(cfg["lightgbm"])
    if n_trials <= 0:
        return base
    space = cfg["optuna"]["space"]
    n_train = len(ds.rows)

    def objective(trial: optuna.Trial) -> float:
        params = base | {
            "num_leaves": trial.suggest_int("num_leaves", *space["num_leaves"]),
            "min_data_in_leaf": trial.suggest_int(
                "min_data_in_leaf",
                space["min_data_in_leaf"][0],
                max(
                    space["min_data_in_leaf"][0] + 1,
                    min(space["min_data_in_leaf"][1], n_train // 20),
                ),
            ),
            "feature_fraction": trial.suggest_float("feature_fraction", *space["feature_fraction"]),
            "lambda_l2": trial.suggest_float("lambda_l2", *space["lambda_l2"], log=True),
        }
        return metrics.rmse(ds.y, cross_validate(ds, folds, params).mean)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="minimize", sampler=optuna.samplers.TPESampler(seed=int(cfg["seed"]))
    )
    study.enqueue_trial({k: base[k] for k in space})  # the default is always a candidate
    study.optimize(objective, n_trials=n_trials)
    return base | study.best_params


def conformal_offset(y: FloatArray, low: FloatArray, high: FloatArray, target: float) -> float:
    """Conformalized quantile regression: the amount to add to both ends of [P10, P90]."""
    ok = np.isfinite(y) & np.isfinite(low) & np.isfinite(high)
    scores = np.maximum(low[ok] - y[ok], y[ok] - high[ok])
    if not len(scores):
        return 0.0
    level = min(1.0, target * (1 + 1 / len(scores)))
    return float(np.quantile(scores, level))


def interval_report(ds: Dataset, oof: Oof) -> tuple[dict[str, Any], float]:
    """P10-P90 coverage, raw and after conformal adjustment. The adjusted figure is honest:
    each station is corrected with an offset learned from the other stations only."""
    cfg = load_config()["validation"]
    y, low, high = ds.y, oof.quantiles[0.1], oof.quantiles[0.9]
    target = float(cfg["target_coverage"])
    adjusted_low, adjusted_high = low.copy(), high.copy()
    for fold in np.unique(oof.fold[oof.fold >= 0]):
        inside = oof.fold == fold
        offset = conformal_offset(y[~inside], low[~inside], high[~inside], target)
        adjusted_low[inside], adjusted_high[inside] = low[inside] - offset, high[inside] + offset
    offset = conformal_offset(y, low, high, target) if cfg["conformal"] else 0.0
    report = {
        "target": target,
        "coverage_p10_p90_raw": metrics.coverage(y, low, high),
        "coverage_p10_p90_conformal": metrics.coverage(y, adjusted_low, adjusted_high),
        "conformal_offset_ug_m3": offset,
        "mean_width_ug_m3": float(np.nanmean(high - low) + 2 * offset),
        "pinball": {str(q): metrics.pinball(y, pred, q) for q, pred in oof.quantiles.items()},
    }
    return report, offset


def ispu_category(values: FloatArray) -> npt.NDArray[np.str_]:
    categories = load_config()["tiles"]["ispu"]["categories"]
    bounds = np.array([upper for _, upper, _ in categories[:-1]], dtype=float)
    names = np.array([name for name, _, _ in categories])
    return names[np.searchsorted(bounds, values, side="left")]


def road_class(ds: Dataset) -> npt.NDArray[np.str_]:
    """Dominant road class within 100 m of each station."""
    out = np.full(len(ds.stations), "none", dtype=object)
    for name in ("minor", "secondary", "primary", "trunk"):  # later classes take precedence
        column = f"road_{name}_100m"
        if column in ds.static_names:
            out[ds.static[:, ds.static_names.index(column)] > 0] = name
    return out.astype(str)


def error_analysis(ds: Dataset, oof: Oof) -> dict[str, Any]:
    """Model vs IDW error by road class, local hour, ISPU category and rush hour (SPEC 11.4)."""
    y = ds.y
    local_hour = ds.hours.tz_convert(TIMEZONE).hour.to_numpy()[ds.rows[:, 0]]
    first, last = load_config()["validation"]["rush_hours"]
    groups = {
        "road_class": road_class(ds)[ds.rows[:, 1]],
        "local_hour": local_hour.astype(str),
        "ispu_category": ispu_category(y),
        "rush_hour": np.where((local_hour >= first) & (local_hour < last), "06-09", "other"),
    }
    report: dict[str, Any] = {}
    for name, labels in groups.items():
        report[name] = {
            str(label): {
                "model": metrics.regression(y[labels == label], oof.mean[labels == label]),
                "idw": metrics.regression(y[labels == label], oof.idw[labels == label]),
            }
            for label in sorted(set(labels.tolist()), key=lambda v: (len(v), v))
        }
    return report


def compare(y: FloatArray, model: FloatArray, idw: FloatArray, cams: FloatArray) -> dict[str, Any]:
    """Model and baselines on the rows where all three exist."""
    common = np.isfinite(model) & np.isfinite(idw) & np.isfinite(cams) & np.isfinite(y)
    scores = {
        "lightgbm": metrics.regression(y[common], model[common]),
        "idw": metrics.regression(y[common], idw[common]),
        "cams": metrics.regression(y[common], cams[common]),
    }
    model_rmse, idw_rmse = scores["lightgbm"]["rmse"], scores["idw"]["rmse"]
    return scores | {
        "rmse_improvement_vs_idw": (
            metrics.improvement(float(model_rmse), float(idw_rmse))
            if model_rmse is not None and idw_rmse is not None
            else None
        ),
        "lightgbm_all_rows": metrics.regression(y, model),
    }


def temporal_holdout(ds: Dataset, params: dict[str, Any]) -> dict[str, Any]:
    """Train on the first 80% of the period, test on the last 20% (SPEC 11.4, 12.7 4a)."""
    fraction = float(load_config()["validation"]["temporal_holdout_fraction"])
    cut = int(len(ds.hours) * (1 - fraction))
    x, y, weight = ds.design(), ds.y, ds.weights
    test = ds.rows[:, 0] >= cut
    if not test.any() or not (~test).any():
        return {"skipped": "not enough hours for a temporal split"}
    model = fit(x[~test], y[~test], weight[~test], ds.feature_names, params)
    names = ds.feature_names
    return {
        "train_until": ds.hours[cut - 1].isoformat(),
        "test_from": ds.hours[cut].isoformat(),
        **compare(
            y[test],
            np.asarray(model.predict(x[test])),
            x[test, names.index("idw_pm25")],
            x[test, names.index("cams_pm25")],
        ),
    }


def source_holdout(ds: Dataset, params: dict[str, Any]) -> dict[str, Any] | None:
    """Stations listed in `holdout_station_ids` are never trained on (SPEC 12.7 4b)."""
    ids = set(load_config()["validation"]["holdout_station_ids"])
    held = [i for i, s in enumerate(ds.stations["station_id"]) if s in ids]
    if not held:
        return None
    x, y, weight = ds.design(held), ds.y, ds.weights
    test = np.isin(ds.rows[:, 1], held)
    model = fit(x[~test], y[~test], weight[~test], ds.feature_names, params)
    names = ds.feature_names
    return {
        "stations": sorted(ids & set(ds.stations["station_id"])),
        **compare(
            y[test],
            np.asarray(model.predict(x[test])),
            x[test, names.index("idw_pm25")],
            x[test, names.index("cams_pm25")],
        ),
    }


def shap_summary(model: lgb.Booster, x: FloatArray, names: Sequence[str]) -> dict[str, float]:
    """Mean |SHAP| per feature from LightGBM's exact TreeSHAP (`pred_contrib`)."""
    rng = np.random.default_rng(int(load_config()["seed"]))
    sample = x[rng.choice(len(x), size=min(len(x), 5000), replace=False)]
    contributions = np.asarray(model.predict(sample, pred_contrib=True))[:, :-1]
    importance = np.abs(contributions).mean(axis=0)
    order = np.argsort(importance)[::-1]
    return {names[i]: float(importance[i]) for i in order}


def run(n_trials: int | None = None) -> dict[str, Any]:
    """Train, validate, save and (if it earns it) promote a model. Returns the registry entry."""
    from hirup_ml import dataset

    cfg = load_config()
    ds = dataset.load()
    return train(ds, int(cfg["optuna"]["n_trials"]) if n_trials is None else n_trials)


def train(ds: Dataset, n_trials: int) -> dict[str, Any]:
    cfg = load_config()
    labelled = np.unique(ds.rows[:, 1])
    if len(labelled) < int(cfg["validation"]["min_stations"]):
        raise RuntimeError(
            f"Only {len(labelled)} station(s) have labels; LOSO needs at least "
            f"{cfg['validation']['min_stations']}. Serve the IDW + CAMS fallback instead (gate G0)."
        )
    quantiles = [float(q) for q in cfg["quantiles"]]
    folds = station_folds(ds)
    held_ids = set(cfg["validation"]["holdout_station_ids"])
    held = [i for i, s in enumerate(ds.stations["station_id"]) if s in held_ids]
    params = tune(ds, folds, n_trials)
    log.info("parameters: %s", params)

    oof = cross_validate(ds, folds, params, quantiles=quantiles)
    y, names = ds.y, ds.feature_names
    cams = ds.base()[:, names.index("cams_pm25")]
    loso = compare(y, oof.mean, oof.idw, cams)
    intervals, offset = interval_report(ds, oof)
    block = cross_validate(ds, block_folds(ds), params)
    holdout = temporal_holdout(ds, params)
    validation: dict[str, Any] = {
        "loso": loso,
        "intervals": intervals,
        "spatial_block_cv": compare(y, block.mean, block.idw, cams),
        "temporal_holdout": holdout,
        "source_holdout": source_holdout(ds, params),
        "error_analysis": error_analysis(ds, oof),
    }

    # Final models see every station except the source hold-out.
    x, weight = ds.design(held), ds.weights
    keep = ~np.isin(ds.rows[:, 1], held)
    final = {"mean": fit(x[keep], y[keep], weight[keep], names, params)}
    for q in quantiles:
        final[f"q{round(q * 100):02d}"] = fit(
            x[keep], y[keep], weight[keep], names, params, alpha=q
        )

    version = registry.next_version()
    target = models_dir() / version
    target.mkdir(parents=True, exist_ok=True)
    for name, model in final.items():
        model.save_model(str(target / f"{name}.txt"))
    shap = shap_summary(final["mean"], x[keep], names)
    loso_rmse = loso["lightgbm"]["rmse"]
    meta = {
        "model_version": version,
        "feature_names": names,
        "params": params,
        "quantiles": quantiles,
        "conformal_offset_ug_m3": offset,
        "loso_rmse": loso_rmse,
        "idw_interval_ratio": idw_interval_ratio(y, oof.idw),
        "seed": int(cfg["seed"]),
    }
    store.write_json(meta, target / "meta.json")
    store.write_json(validation, target / "validation.json")
    store.write_json(shap, target / "shap_summary.json")
    frame = pd.DataFrame(
        {
            "station_id": ds.stations["station_id"].to_numpy()[ds.rows[:, 1]],
            "ts": ds.hours[ds.rows[:, 0]],
            "y": y,
            "pred": oof.mean,
            "idw": oof.idw,
            "cams": cams,
            "fold": oof.fold,
            **{f"q{round(q * 100):02d}": pred for q, pred in oof.quantiles.items()},
        }
    )
    store.write_parquet(frame, target / "oof.parquet")

    entry = {
        "model_version": version,
        "trained_at": datetime.now(UTC).isoformat(),
        "data_window": {"start": ds.hours[0].isoformat(), "end": ds.hours[-1].isoformat()},
        "n_stations": len(labelled),
        "n_rows": len(y),
        "n_features": len(names),
        "metrics": {
            "loso_rmse": loso_rmse,
            "loso_mae": loso["lightgbm"]["mae"],
            "loso_r2": loso["lightgbm"]["r2"],
            "loso_bias": loso["lightgbm"]["bias"],
            "idw_loso_rmse": loso["idw"]["rmse"],
            "cams_rmse": loso["cams"]["rmse"],
            "rmse_improvement_vs_idw": loso["rmse_improvement_vs_idw"],
            "coverage_p10_p90": intervals["coverage_p10_p90_conformal"],
            "coverage_p10_p90_raw": intervals["coverage_p10_p90_raw"],
            "temporal_holdout_rmse": (holdout.get("lightgbm") or {}).get("rmse"),
            "block_cv_rmse": validation["spatial_block_cv"]["lightgbm"]["rmse"],
        },
        "params": params,
        "top_features": list(shap)[:10],
        "path": f"ml/models/{version}",
        "is_active": False,
    }
    return registry.register(entry)


def idw_interval_ratio(y: FloatArray, idw: FloatArray) -> dict[str, float] | None:
    """P10/P90 of observed / IDW at held-out stations: the fallback raster's uncertainty band."""
    ok = np.isfinite(y) & np.isfinite(idw) & (idw > 0)
    if ok.sum() < 30:
        return None
    ratio = y[ok] / idw[ok]
    return {"p10": float(np.quantile(ratio, 0.1)), "p90": float(np.quantile(ratio, 0.9))}
