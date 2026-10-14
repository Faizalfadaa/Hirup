import numpy as np
import pytest

from hirup_ml import baseline, dataset, metrics, registry, train
from hirup_ml.config import models_dir
from hirup_pipelines import store


def test_metrics():
    y = np.array([10.0, 20.0, 30.0, np.nan])
    pred = np.array([12.0, 18.0, 33.0, 5.0])
    scores = metrics.regression(y, pred)
    assert scores["n"] == 3
    assert scores["rmse"] == pytest.approx(np.sqrt((4 + 4 + 9) / 3))
    assert scores["bias"] == pytest.approx(1.0)
    assert metrics.coverage(y, pred - 2.5, pred + 2.5) == pytest.approx(2 / 3)
    assert metrics.pinball(np.array([10.0]), np.array([8.0]), 0.9) == pytest.approx(1.8)
    assert metrics.improvement(8.0, 10.0) == pytest.approx(0.2)
    assert metrics.regression(np.array([np.nan]), np.array([1.0]))["rmse"] is None


def test_fold_features_never_see_the_held_out_station(toy):
    ds = dataset.load()
    assert ds.labels.shape == (240, 8)
    assert ds.feature_names[-len(dataset.FOLD_COLUMNS) :] == list(dataset.FOLD_COLUMNS)
    plain, held = ds.fold(), ds.fold([0])
    rows_of_1 = ds.rows[:, 1] == 1
    # Removing station 0 changes what station 1 sees, and its station count drops by one.
    count = list(dataset.FOLD_COLUMNS).index("n_stations")
    assert (plain[rows_of_1, count] == 7).all()
    assert (held[rows_of_1, count] == 6).all()
    assert not np.allclose(plain[rows_of_1, 0], held[rows_of_1, 0])
    # Poisoning station 0's own readings must not move its own IDW feature (leave-one-out).
    before = ds.fold()[ds.rows[:, 1] == 0, 0]
    ds.inputs[:, 0] += 1000
    assert np.allclose(ds.fold()[ds.rows[:, 1] == 0, 0], before)


def test_monotone_constraints_follow_the_config():
    names = ["road_trunk_100m", "ndvi_mean_300m", "ndvi_max_300m", "temp"]
    assert train.monotone_constraints(names) == [1, -1, 0, 0]


def test_conformal_offset_reaches_the_target_coverage():
    rng = np.random.default_rng(0)
    y = rng.normal(50, 10, 2000)
    low, high = np.full(2000, 48.0), np.full(2000, 52.0)  # far too narrow
    offset = train.conformal_offset(y, low, high, 0.8)
    assert metrics.coverage(y, low - offset, high + offset) == pytest.approx(0.8, abs=0.01)


def test_promotion_rules():
    def entry(rmse, idw=10.0):
        return {"model_version": "m", "metrics": {"loso_rmse": rmse, "idw_loso_rmse": idw}}

    assert registry.promotion_decision(entry(11.0), None)[0] is False  # gate G2
    assert registry.promotion_decision(entry(8.0), None)[0] is True
    assert registry.promotion_decision(entry(8.3), entry(8.0))[0] is True  # within 5%
    assert registry.promotion_decision(entry(8.5), entry(8.0))[0] is False
    registry.register(entry(8.0) | {"model_version": "a"})
    registry.register(entry(7.0) | {"model_version": "b"})
    registry.register(entry(9.9) | {"model_version": "c"})
    assert [e["is_active"] for e in registry.entries()] == [False, True, False]


def test_train_end_to_end_on_toy_data(toy):
    report = baseline.run()
    assert report["idw_loso"]["n"] == 240 * 8
    assert report["idw_interval_ratio"]["p10"] < 1 < report["idw_interval_ratio"]["p90"]

    entry = train.train(dataset.load(), n_trials=2)
    scores = entry["metrics"]
    # The toy signal is a road effect IDW cannot see, so the model must win and be promoted.
    assert scores["loso_rmse"] < scores["idw_loso_rmse"]
    assert scores["rmse_improvement_vs_idw"] > 0.1
    assert entry["is_active"] is True
    assert 0.5 < scores["coverage_p10_p90"] <= 1.0
    folder = models_dir() / entry["model_version"]
    for name in ("mean.txt", "q10.txt", "q90.txt", "meta.json", "oof.parquet", "shap_summary.json"):
        assert (folder / name).is_file()
    validation = store.read_json(folder / "validation.json")
    assert set(validation["error_analysis"]) == {
        "road_class",
        "local_hour",
        "ispu_category",
        "rush_hour",
    }
    assert validation["temporal_holdout"]["lightgbm"]["n"] == 48 * 8
    assert validation["source_holdout"] is None
    model = registry.load_active()
    assert model is not None
    assert model.feature_names == dataset.load().feature_names
    assert registry.next_version() != entry["model_version"]


def test_training_refuses_too_few_stations(toy):
    ds = dataset.load()
    ds.rows = ds.rows[ds.rows[:, 1] < 2]
    with pytest.raises(RuntimeError, match="LOSO needs at least"):
        train.train(ds, n_trials=0)
