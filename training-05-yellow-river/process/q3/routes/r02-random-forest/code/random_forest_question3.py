from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
Q2_DIR = PROJECT_DIR / "question-2"
OUT_DIR = PROJECT_DIR / "q3"
DATA_DIR = OUT_DIR / "data" / "processed"
RESULTS_DIR = OUT_DIR / "results"
DOCS_DIR = OUT_DIR / "docs"
FIGURES_DIR = OUT_DIR / "figures"
QA_DIR = OUT_DIR / "qa"
MODELS_DIR = OUT_DIR / "models"
SECONDS_PER_DAY = 24 * 3600


@dataclass
class TreeNode:
    value: float
    feature: int | None = None
    threshold: float | None = None
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None


class SimpleDecisionTreeRegressor:
    def __init__(self, max_depth: int = 9, min_samples_leaf: int = 12, max_features: int | None = None, seed: int = 0):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.rng = np.random.default_rng(seed)
        self.root: TreeNode | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "SimpleDecisionTreeRegressor":
        self.n_features_ = x.shape[1]
        if self.max_features is None:
            self.max_features = max(1, int(np.sqrt(self.n_features_)))
        self.root = self._build(x, y, depth=0)
        return self

    def _best_split(self, x: np.ndarray, y: np.ndarray) -> tuple[int | None, float | None, float]:
        n_samples, n_features = x.shape
        base_sse = float(np.sum((y - y.mean()) ** 2))
        best_feature = None
        best_threshold = None
        best_sse = base_sse
        feature_ids = self.rng.choice(n_features, size=min(self.max_features or n_features, n_features), replace=False)
        for feature in feature_ids:
            col = x[:, feature]
            if np.all(col == col[0]):
                continue
            quantiles = np.linspace(0.10, 0.90, 17)
            thresholds = np.unique(np.quantile(col, quantiles))
            for threshold in thresholds:
                left_mask = col <= threshold
                left_n = int(left_mask.sum())
                right_n = n_samples - left_n
                if left_n < self.min_samples_leaf or right_n < self.min_samples_leaf:
                    continue
                y_left = y[left_mask]
                y_right = y[~left_mask]
                sse = float(np.sum((y_left - y_left.mean()) ** 2) + np.sum((y_right - y_right.mean()) ** 2))
                if sse < best_sse:
                    best_feature = int(feature)
                    best_threshold = float(threshold)
                    best_sse = sse
        return best_feature, best_threshold, best_sse

    def _build(self, x: np.ndarray, y: np.ndarray, depth: int) -> TreeNode:
        node = TreeNode(value=float(y.mean()))
        if depth >= self.max_depth or len(y) < 2 * self.min_samples_leaf:
            return node
        feature, threshold, split_sse = self._best_split(x, y)
        base_sse = float(np.sum((y - y.mean()) ** 2))
        if feature is None or threshold is None or split_sse >= base_sse * 0.995:
            return node
        mask = x[:, feature] <= threshold
        node.feature = feature
        node.threshold = threshold
        node.left = self._build(x[mask], y[mask], depth + 1)
        node.right = self._build(x[~mask], y[~mask], depth + 1)
        return node

    def _predict_one(self, row: np.ndarray) -> float:
        node = self.root
        while node is not None and node.feature is not None:
            if row[node.feature] <= (node.threshold or 0.0):
                node = node.left
            else:
                node = node.right
        return float(node.value if node is not None else 0.0)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.asarray([self._predict_one(row) for row in x], dtype=float)


class SimpleRandomForestRegressor:
    def __init__(
        self,
        n_estimators: int = 120,
        max_depth: int = 9,
        min_samples_leaf: int = 12,
        max_features: int | None = None,
        sample_fraction: float = 0.85,
        seed: int = 20260808,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.sample_fraction = sample_fraction
        self.seed = seed
        self.trees: list[SimpleDecisionTreeRegressor] = []

    def fit(self, x: np.ndarray, y: np.ndarray) -> "SimpleRandomForestRegressor":
        rng = np.random.default_rng(self.seed)
        n = len(y)
        sample_size = max(2 * self.min_samples_leaf, int(n * self.sample_fraction))
        self.trees = []
        for idx in range(self.n_estimators):
            sample_ids = rng.integers(0, n, size=sample_size)
            tree = SimpleDecisionTreeRegressor(
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                max_features=self.max_features,
                seed=int(rng.integers(0, 2**31 - 1)),
            )
            tree.fit(x[sample_ids], y[sample_ids])
            self.trees.append(tree)
        return self

    def predict_all(self, x: np.ndarray) -> np.ndarray:
        return np.vstack([tree.predict(x) for tree in self.trees])

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.predict_all(x).mean(axis=0)


def load_daily_flux() -> pd.DataFrame:
    path = Q2_DIR / "data" / "processed" / "daily_flux_series.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    return pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)


def date_features(date: pd.Timestamp) -> list[float]:
    year_start = pd.Timestamp(datetime(date.year, 1, 1))
    year_end = pd.Timestamp(datetime(date.year + 1, 1, 1))
    d = (date - year_start).total_seconds() / (year_end - year_start).total_seconds()
    angle = 2 * np.pi * d
    trend = (date - pd.Timestamp("2016-01-01")).days / 365.25
    month = date.month
    one_hot = [1.0 if month == m else 0.0 for m in range(1, 13)]
    return [
        trend,
        trend**2,
        np.sin(angle),
        np.cos(angle),
        np.sin(2 * angle),
        np.cos(2 * angle),
        1.0 if 6 <= month <= 10 else 0.0,
        1.0 if 7 <= month <= 9 else 0.0,
        1.0 if month == 7 else 0.0,
        *one_hot,
    ]


def feature_names() -> list[str]:
    return [
        "trend_year",
        "trend_year_sq",
        "sin_annual",
        "cos_annual",
        "sin_semiannual",
        "cos_semiannual",
        "is_flood_jun_oct",
        "is_peak_jul_sep",
        "is_july",
        *[f"month_{m}" for m in range(1, 13)],
        "lag_1",
        "lag_3",
        "lag_7",
        "lag_14",
        "roll7_mean",
        "roll7_std",
        "roll7_max",
        "roll14_mean",
        "roll14_std",
    ]


def row_features(date: pd.Timestamp, history_y: list[float]) -> list[float]:
    last7 = np.asarray(history_y[-7:], dtype=float)
    last14 = np.asarray(history_y[-14:], dtype=float)
    return [
        *date_features(date),
        history_y[-1],
        history_y[-3],
        history_y[-7],
        history_y[-14],
        float(last7.mean()),
        float(last7.std()),
        float(last7.max()),
        float(last14.mean()),
        float(last14.std()),
    ]


def make_supervised(df: pd.DataFrame, target_col: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    y_all = np.log1p(df[target_col].to_numpy(dtype=float)).tolist()
    rows = []
    y = []
    meta = []
    for idx in range(14, len(df)):
        date = pd.Timestamp(df.loc[idx, "date"])
        rows.append(row_features(date, y_all[:idx]))
        y.append(y_all[idx])
        meta.append({"date": date, "year": date.year})
    return np.asarray(rows, dtype=float), np.asarray(y, dtype=float), pd.DataFrame(meta)


def recursive_forecast(
    forest: SimpleRandomForestRegressor,
    history_y: list[float],
    future_dates: pd.DatetimeIndex,
) -> dict[str, np.ndarray]:
    histories = {"low": list(history_y), "normal": list(history_y), "high": list(history_y)}
    preds = {"low": [], "normal": [], "high": []}
    for date in future_dates:
        for scenario, quantile in [("low", 0.30), ("normal", 0.50), ("high", 0.75)]:
            x = np.asarray([row_features(pd.Timestamp(date), histories[scenario])], dtype=float)
            tree_preds = forest.predict_all(x).ravel()
            pred = float(np.quantile(tree_preds, quantile))
            preds[scenario].append(pred)
            histories[scenario].append(pred)
    return {key: np.asarray(value, dtype=float) for key, value in preds.items()}


def validate_model(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    rows = []
    for year in [2018, 2019, 2020, 2021]:
        train = df[df["date"].dt.year < year].copy().reset_index(drop=True)
        test = df[df["date"].dt.year == year].copy().reset_index(drop=True)
        if len(train) < 380 or test.empty:
            continue
        x, y, _ = make_supervised(train, target_col)
        forest = SimpleRandomForestRegressor(n_estimators=90, max_depth=9, min_samples_leaf=12, seed=year)
        forest.fit(x, y)
        history_y = np.log1p(train[target_col].to_numpy(dtype=float)).tolist()
        pred_log = recursive_forecast(forest, history_y, pd.DatetimeIndex(test["date"]))["normal"]
        true = test[target_col].to_numpy(dtype=float)
        true_log = np.log1p(true)
        pred = np.expm1(pred_log).clip(min=0)
        rows.append(
            {
                "target": target_col,
                "heldout_year": year,
                "rmse_log": float(np.sqrt(np.mean((true_log - pred_log) ** 2))),
                "mae_log": float(np.mean(np.abs(true_log - pred_log))),
                "r2_log": float(1 - np.sum((true_log - pred_log) ** 2) / np.sum((true_log - true_log.mean()) ** 2)),
                "rmse_original": float(np.sqrt(np.mean((true - pred) ** 2))),
                "mae_original": float(np.mean(np.abs(true - pred))),
            }
        )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("target", as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            rmse_original=("rmse_original", "mean"),
            mae_original=("mae_original", "mean"),
        )
    )
    summary.insert(1, "heldout_year", "mean")
    return pd.concat([detail, summary], ignore_index=True)


def train_and_forecast(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    out = pd.DataFrame({"date": future_dates})
    importance_rows = []
    for target_col, stem, seed in [
        ("mean_flow_m3s", "flow", 301),
        ("mean_sediment_flux_kg_s", "sediment_flux", 907),
    ]:
        x, y, _ = make_supervised(df, target_col)
        forest = SimpleRandomForestRegressor(n_estimators=140, max_depth=10, min_samples_leaf=10, seed=seed)
        forest.fit(x, y)
        history_y = np.log1p(df[target_col].to_numpy(dtype=float)).tolist()
        forecast_logs = recursive_forecast(forest, history_y, future_dates)
        for scenario in ["low", "normal", "high"]:
            out[f"{scenario}_pred_mean_{stem}_raw"] = np.expm1(forecast_logs[scenario]).clip(min=0)
        baseline = forest.predict(x)
        base_rmse = float(np.sqrt(np.mean((y - baseline) ** 2)))
        rng = np.random.default_rng(seed + 77)
        names = feature_names()
        for feature_id, name in enumerate(names):
            x_perm = x.copy()
            rng.shuffle(x_perm[:, feature_id])
            rmse = float(np.sqrt(np.mean((y - forest.predict(x_perm)) ** 2)))
            importance_rows.append(
                {
                    "target": target_col,
                    "feature": name,
                    "permutation_importance": max(0.0, rmse - base_rmse),
                }
            )
    out["low_pred_mean_flow_m3s"] = out["low_pred_mean_flow_raw"]
    out["normal_pred_mean_flow_m3s"] = out["normal_pred_mean_flow_raw"]
    out["high_pred_mean_flow_m3s"] = out["high_pred_mean_flow_raw"]
    out["low_pred_mean_sediment_flux_kg_s"] = out["low_pred_mean_sediment_flux_raw"]
    out["normal_pred_mean_sediment_flux_kg_s"] = out["normal_pred_mean_sediment_flux_raw"]
    out["high_pred_mean_sediment_flux_kg_s"] = out["high_pred_mean_sediment_flux_raw"]
    drop_cols = [col for col in out.columns if col.endswith("_raw")]
    out = out.drop(columns=drop_cols)
    for scenario in ["low", "normal", "high"]:
        out[f"{scenario}_pred_water_volume_m3"] = out[f"{scenario}_pred_mean_flow_m3s"] * SECONDS_PER_DAY
        out[f"{scenario}_pred_sediment_mass_kg"] = out[f"{scenario}_pred_mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
        out[f"{scenario}_pred_water_volume_1e8_m3"] = out[f"{scenario}_pred_water_volume_m3"] / 1e8
        out[f"{scenario}_pred_sediment_mass_1e4_t"] = out[f"{scenario}_pred_sediment_mass_kg"] / 1e7
    out["pred_mean_flow_m3s"] = out["normal_pred_mean_flow_m3s"]
    out["pred_mean_sediment_flux_kg_s"] = out["normal_pred_mean_sediment_flux_kg_s"]
    out["pred_water_volume_m3"] = out["normal_pred_water_volume_m3"]
    out["pred_sediment_mass_kg"] = out["normal_pred_sediment_mass_kg"]
    out["pred_water_volume_1e8_m3"] = out["normal_pred_water_volume_1e8_m3"]
    out["pred_sediment_mass_1e4_t"] = out["normal_pred_sediment_mass_1e4_t"]
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    return out, pd.DataFrame(importance_rows)


def aggregate_scenarios(forecasts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows = []
    annual_rows = []
    for scenario in ["low", "normal", "high"]:
        monthly = (
            forecasts.groupby(["year", "month"], as_index=False)
            .agg(
                pred_mean_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "mean"),
                pred_mean_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "mean"),
                pred_water_volume_1e8_m3=(f"{scenario}_pred_water_volume_1e8_m3", "sum"),
                pred_sediment_mass_1e4_t=(f"{scenario}_pred_sediment_mass_1e4_t", "sum"),
            )
        )
        monthly.insert(0, "scenario", scenario)
        monthly_rows.append(monthly)
        annual = (
            forecasts.groupby("year", as_index=False)
            .agg(
                pred_water_volume_1e8_m3=(f"{scenario}_pred_water_volume_1e8_m3", "sum"),
                pred_sediment_mass_1e4_t=(f"{scenario}_pred_sediment_mass_1e4_t", "sum"),
                pred_mean_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "mean"),
                pred_mean_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "mean"),
                max_pred_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "max"),
                max_pred_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "max"),
            )
        )
        annual.insert(0, "scenario", scenario)
        annual_rows.append(annual)
    return pd.concat(monthly_rows, ignore_index=True), pd.concat(annual_rows, ignore_index=True)


def historical_abrupt_month_risk() -> dict[int, float]:
    path = Q2_DIR / "qa" / "abrupt_change_events.csv"
    if not path.exists():
        return {month: 0.0 for month in range(1, 13)}
    events = pd.read_csv(path, parse_dates=["date"])
    counts = events["date"].dt.month.value_counts().to_dict()
    max_count = max(counts.values()) if counts else 1
    return {month: counts.get(month, 0) / max_count for month in range(1, 13)}


def minmax(values: pd.Series) -> pd.Series:
    lo, hi = values.min(), values.max()
    if hi == lo:
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - lo) / (hi - lo)


def build_sampling_plan(forecasts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = forecasts.copy()
    work["log_sediment_flux"] = np.log1p(work["pred_mean_sediment_flux_kg_s"])
    work["high_log_sediment_flux"] = np.log1p(work["high_pred_mean_sediment_flux_kg_s"])
    work["change_strength"] = work["log_sediment_flux"].diff().abs().fillna(0)
    month_risk = historical_abrupt_month_risk()
    work["historical_abrupt_month_risk"] = work["month"].map(month_risk).astype(float)
    work["is_flood"] = work["month"].between(6, 10).astype(float)
    work["is_peak"] = work["month"].between(7, 9).astype(float)
    work["risk_score"] = (
        0.35 * minmax(work["log_sediment_flux"])
        + 0.10 * minmax(work["high_log_sediment_flux"])
        + 0.25 * minmax(work["change_strength"])
        + 0.15 * work["is_peak"]
        + 0.10 * work["is_flood"]
        + 0.05 * work["historical_abrupt_month_risk"]
    )
    selected: set[pd.Timestamp] = set()
    for _, row in work.iterrows():
        date = pd.Timestamp(row["date"])
        month = date.month
        interval = 10 if month <= 3 else 5 if month <= 5 else 2 if month <= 10 else 7
        if (date.day - 1) % interval == 0:
            selected.add(date)
    for year, group in work.groupby(work["date"].dt.year):
        for date in pd.DatetimeIndex(group.sort_values("risk_score", ascending=False).head(20)["date"]):
            selected.add(pd.Timestamp(date))
        for center in pd.DatetimeIndex(group.sort_values("risk_score", ascending=False).head(6)["date"]):
            for offset in [-1, 0, 1]:
                candidate = pd.Timestamp(center) + pd.Timedelta(days=offset)
                if candidate.year == year:
                    selected.add(candidate)
    plan = work[work["date"].isin(selected)].copy().sort_values("date")
    plan["sampling_level"] = np.where(
        plan["risk_score"] >= work["risk_score"].quantile(0.90),
        "high",
        np.where(plan["month"].between(6, 10), "flood_regular", "base_regular"),
    )
    plan = plan[
        [
            "date",
            "year",
            "month",
            "sampling_level",
            "risk_score",
            "pred_mean_flow_m3s",
            "pred_mean_sediment_flux_kg_s",
            "change_strength",
        ]
    ]
    monthly_counts = (
        plan.groupby(["year", "month"], as_index=False)
        .agg(samples=("date", "size"), high_risk_samples=("sampling_level", lambda s: int((s == "high").sum())))
    )
    return plan, monthly_counts


def get_font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2), text, font=font, fill=fill)


def save_line_figure(monthly: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 720
    left, right, top, bottom = 105, 45, 88, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw_centered(draw, (width / 2, 38), "Random Forest Forecast Monthly Flux", get_font(28, True), (31, 41, 55))
    draw.text((left, top - 32), "index (max=100)", font=get_font(16), fill=(55, 65, 81))
    labels = [f"{int(y)}-{int(m):02d}" for y, m in zip(monthly["year"], monthly["month"])]
    water = (monthly["pred_water_volume_1e8_m3"] / monthly["pred_water_volume_1e8_m3"].max() * 100).tolist()
    sediment = (monthly["pred_sediment_mass_1e4_t"] / monthly["pred_sediment_mass_1e4_t"].max() * 100).tolist()
    y_max = 115
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 52, y - 8), f"{value:.0f}", font=get_font(14), fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    step = plot_w / (len(labels) - 1)
    for i, label in enumerate(labels):
        if i % 2 == 0:
            draw_centered(draw, (left + i * step, top + plot_h + 28), label, get_font(14), (55, 65, 81))
    for values, color in [(water, (37, 99, 235)), (sediment, (220, 38, 38))]:
        points = [(left + i * step, top + plot_h - value / y_max * plot_h) for i, value in enumerate(values)]
        draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
    image.save(path)


def save_sampling_figure(monthly_counts: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 720
    left, right, top, bottom = 105, 45, 88, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw_centered(draw, (width / 2, 38), "Random Forest Monthly Sampling Counts", get_font(28, True), (31, 41, 55))
    draw.text((left, top - 32), "samples", font=get_font(16), fill=(55, 65, 81))
    labels = [f"{int(y)}-{int(m):02d}" for y, m in zip(monthly_counts["year"], monthly_counts["month"])]
    values = monthly_counts["samples"].tolist()
    y_max = max(values) * 1.2
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 52, y - 8), f"{value:.0f}", font=get_font(14), fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    group_w = plot_w / len(values)
    bar_w = min(34, group_w * 0.62)
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + i * group_w + (group_w - bar_w) / 2
        h = value / y_max * plot_h
        y = top + plot_h - h
        color = (220, 38, 38) if "-07" in label or "-08" in label or "-09" in label else (37, 99, 235)
        draw.rounded_rectangle((x, y, x + bar_w, top + plot_h), radius=3, fill=color)
        if i % 2 == 0:
            draw_centered(draw, (x + bar_w / 2, top + plot_h + 28), label, get_font(14), (55, 65, 81))
    image.save(path)


def dataframe_to_markdown(df: pd.DataFrame, floatfmt: str = ".5g") -> str:
    headers = list(df.columns)
    rows = []
    for _, row in df.iterrows():
        vals = []
        for value in row:
            if isinstance(value, pd.Timestamp):
                vals.append(value.strftime("%Y-%m-%d"))
            elif isinstance(value, (float, np.floating)):
                vals.append(format(float(value), floatfmt))
            else:
                vals.append(str(value))
        rows.append(vals)
    widths = [max(len(str(h)), *(len(row[i]) for row in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    lines = [
        "| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |",
    ]
    lines.extend("| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(row)) + " |" for row in rows)
    return "\n".join(lines)


def write_report(validation: pd.DataFrame, annual: pd.DataFrame, monthly: pd.DataFrame, monthly_counts: pd.DataFrame) -> None:
    lines = [
        "# q3 随机森林预测版本",
        "",
        "本版本在独立 `q3` 文件夹中运行，使用纯 numpy 实现的随机森林回归模型。预测对象为 `ln(1+Q_t)` 和 `ln(1+F_t)`，特征包括趋势项、周期项、月份指示变量、汛期指标、滞后项和滚动统计量。",
        "",
        "## 验证结果",
        "",
        dataframe_to_markdown(validation[validation["heldout_year"].eq("mean")]),
        "",
        "## 年度预测",
        "",
        dataframe_to_markdown(annual),
        "",
        "## 月度预测图",
        "",
        "![rf forecast](../figures/rf-forecast-monthly-flux.png)",
        "",
        "## 采样方案",
        "",
        dataframe_to_markdown(monthly_counts),
        "",
        "![rf sampling](../figures/rf-sampling-monthly-counts.png)",
        "",
    ]
    (DOCS_DIR / "q3-random-forest-analysis.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for directory in [DATA_DIR, RESULTS_DIR, DOCS_DIR, FIGURES_DIR, QA_DIR, MODELS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    daily = load_daily_flux()
    validation = pd.concat(
        [validate_model(daily, "mean_flow_m3s"), validate_model(daily, "mean_sediment_flux_kg_s")],
        ignore_index=True,
    )
    forecasts, importance = train_and_forecast(daily)
    monthly, annual = aggregate_scenarios(forecasts)
    normal_monthly = monthly[monthly["scenario"] == "normal"].drop(columns=["scenario"]).reset_index(drop=True)
    plan, monthly_counts = build_sampling_plan(forecasts)

    forecasts.to_csv(DATA_DIR / "rf_predicted_daily_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(RESULTS_DIR / "rf_forecast_monthly_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    annual.to_csv(RESULTS_DIR / "rf_forecast_annual_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    plan.to_csv(RESULTS_DIR / "rf_sampling_plan_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly_counts.to_csv(RESULTS_DIR / "rf_sampling_monthly_counts_2022_2023.csv", index=False, encoding="utf-8-sig")
    validation.to_csv(QA_DIR / "rf_forecast_validation.csv", index=False, encoding="utf-8-sig")
    importance.to_csv(QA_DIR / "rf_feature_importance.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "model": "pure_numpy_random_forest_regressor",
                "n_estimators": 140,
                "max_depth": 10,
                "min_samples_leaf": 10,
                "target_transform": "log1p",
            }
        ]
    ).to_csv(QA_DIR / "rf_model_settings.csv", index=False, encoding="utf-8-sig")
    save_line_figure(normal_monthly, FIGURES_DIR / "rf-forecast-monthly-flux.png")
    save_sampling_figure(monthly_counts, FIGURES_DIR / "rf-sampling-monthly-counts.png")
    write_report(validation, annual, normal_monthly, monthly_counts)

    print("Validation mean:")
    print(validation[validation["heldout_year"].eq("mean")].to_string(index=False))
    print("\nAnnual forecast:")
    print(annual.to_string(index=False))
    print("\nSampling counts by year:")
    print(plan.groupby("year").size().rename("samples").reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
