import argparse
from pathlib import Path
import warnings

import matplotlib.pyplot as plt
from matplotlib import colormaps, font_manager
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator, make_smoothing_spline
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.preprocessing import SplineTransformer


METHODS = ["linear", "pchip", "penalized_bspline", "gcv_smoothing_spline", "matern_gp"]
PENALTIES = np.logspace(-4, 4, 9)
LABELS = {
    "linear": "分段线性",
    "pchip": "PCHIP保形",
    "penalized_bspline": "惩罚B样条",
    "gcv_smoothing_spline": "GCV平滑样条",
    "matern_gp": "Matérn高斯过程",
}
COLORS = {
    "linear": "#4C4C4C",
    "pchip": "#0072B2",
    "penalized_bspline": "#CC79A7",
    "gcv_smoothing_spline": "#D55E00",
    "matern_gp": "#009E73",
}


def configure_plotting():
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "#F7F8FA"
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.2


def read_surveys(path):
    raw = pd.read_excel(path, header=None)
    surveys = {}
    for col in range(0, raw.shape[1], 2):
        date = pd.to_datetime(raw.iat[0, col], errors="coerce")
        if pd.isna(date):
            continue
        frame = pd.DataFrame(
            {
                "distance_m": pd.to_numeric(raw.iloc[2:, col], errors="coerce"),
                "bed_elevation_m": pd.to_numeric(raw.iloc[2:, col + 1], errors="coerce"),
            }
        ).dropna()
        surveys[date] = frame.groupby("distance_m", as_index=False)["bed_elevation_m"].mean().sort_values("distance_m").reset_index(drop=True)
    return surveys


def gp_model(x, y):
    span = x.max() - x.min()
    xn = ((x - x.min()) / span).reshape(-1, 1)
    kernel = ConstantKernel(1.0, (0.05, 20.0)) * Matern(length_scale=0.08, length_scale_bounds=(0.005, 1.5), nu=1.5) + WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-5, 0.5))
    model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, alpha=1e-8, n_restarts_optimizer=0, random_state=20260810)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(xn, y)
    return model, x.min(), span


def pspline_predict(x, y, xp, penalty):
    xmin = x.min()
    span = x.max() - xmin
    xn = ((x - xmin) / span).reshape(-1, 1)
    xpn = ((xp - xmin) / span).reshape(-1, 1)
    n_knots = int(np.clip(len(x) // 5, 10, 28))
    basis = SplineTransformer(n_knots=n_knots, degree=3, knots="quantile", extrapolation="linear", include_bias=True)
    design = basis.fit_transform(xn)
    target = basis.transform(xpn)
    difference = np.diff(np.eye(design.shape[1]), n=2, axis=0)
    system = design.T @ design + penalty * (difference.T @ difference) + 1e-10 * np.eye(design.shape[1])
    coefficient = np.linalg.solve(system, design.T @ y)
    return target @ coefficient


def select_pspline_penalty(x, y, folds=4):
    scores = []
    for penalty in PENALTIES:
        errors = []
        for test in blocked_folds(len(x), folds=folds, block_size=3):
            train = np.ones(len(x), dtype=bool)
            train[test] = False
            estimate = pspline_predict(x[train], y[train], x[test], penalty)
            errors.extend(estimate - y[test])
        scores.append(np.sqrt(np.mean(np.asarray(errors) ** 2)))
    return float(PENALTIES[int(np.argmin(scores))])


def predict(method, x, y, xp, return_std=False, penalty=None):
    if method == "linear":
        yp = np.interp(xp, x, y)
        return (yp, np.zeros_like(yp)) if return_std else yp
    if method == "pchip":
        yp = PchipInterpolator(x, y, extrapolate=False)(xp)
        return (yp, np.zeros_like(yp)) if return_std else yp
    if method == "penalized_bspline":
        if penalty is None:
            penalty = select_pspline_penalty(x, y)
        yp = pspline_predict(x, y, xp, penalty)
        return (yp, np.zeros_like(yp)) if return_std else yp
    if method == "gcv_smoothing_spline":
        yp = make_smoothing_spline(x, y, lam=None)(xp)
        return (yp, np.zeros_like(yp)) if return_std else yp
    model, xmin, span = gp_model(x, y)
    xpn = ((xp - xmin) / span).reshape(-1, 1)
    if return_std:
        return model.predict(xpn, return_std=True)
    return model.predict(xpn)


def blocked_folds(n, folds=5, block_size=3):
    interior = np.arange(1, n - 1)
    blocks = [interior[i : i + block_size] for i in range(0, len(interior), block_size)]
    return [np.concatenate(blocks[k::folds]) for k in range(folds) if blocks[k::folds]]


def cross_validate(surveys):
    rows = []
    failures = []
    for date, frame in surveys.items():
        x = frame.distance_m.to_numpy(float)
        y = frame.bed_elevation_m.to_numpy(float)
        for fold, test in enumerate(blocked_folds(len(x)), start=1):
            train = np.ones(len(x), dtype=bool)
            train[test] = False
            for method in METHODS:
                try:
                    penalty = select_pspline_penalty(x[train], y[train]) if method == "penalized_bspline" else np.nan
                    estimate = predict(method, x[train], y[train], x[test], penalty=penalty)
                    for index, actual, fitted in zip(test, y[test], estimate):
                        rows.append(
                            {
                                "survey_date": date.date(),
                                "fold": fold,
                                "method": method,
                                "distance_m": x[index],
                                "actual_m": actual,
                                "predicted_m": fitted,
                                "error_m": fitted - actual,
                                "abs_error_m": abs(fitted - actual),
                                "selected_penalty": penalty,
                            }
                        )
                except Exception as exc:
                    failures.append({"survey_date": date.date(), "fold": fold, "method": method, "error": repr(exc)})
    return pd.DataFrame(rows), pd.DataFrame(failures)


def fit_full(surveys, grid):
    rows = []
    diagnostics = []
    gp_bounds = []
    for date, frame in surveys.items():
        x = frame.distance_m.to_numpy(float)
        y = frame.bed_elevation_m.to_numpy(float)
        for method in METHODS:
            penalty = select_pspline_penalty(x, y) if method == "penalized_bspline" else np.nan
            if method == "matern_gp":
                fitted, std = predict(method, x, y, grid, return_std=True)
                gp_bounds.append(pd.DataFrame({"survey_date": date.date(), "distance_m": grid, "mean_m": fitted, "std_m": std}))
            else:
                fitted = predict(method, x, y, grid, penalty=penalty)
            roughness = np.trapz(np.gradient(np.gradient(fitted, grid), grid) ** 2, grid)
            diagnostics.append(
                {
                    "survey_date": date.date(),
                    "method": method,
                    "min_bed_elevation_m": fitted.min(),
                    "thalweg_distance_m": grid[np.argmin(fitted)],
                    "max_bed_elevation_m": fitted.max(),
                    "section_integral_m2": np.trapz(fitted, grid),
                    "roughness_integral": roughness,
                    "max_abs_slope": np.max(np.abs(np.gradient(fitted, grid))),
                    "below_observed_min_m": max(0.0, y.min() - fitted.min()),
                    "above_observed_max_m": max(0.0, fitted.max() - y.max()),
                    "selected_penalty": penalty,
                }
            )
            rows.append(pd.DataFrame({"survey_date": date.date(), "method": method, "distance_m": grid, "bed_elevation_m": fitted}))
    return pd.concat(rows, ignore_index=True), pd.DataFrame(diagnostics), pd.concat(gp_bounds, ignore_index=True)


def summarize_cv(predictions):
    def metrics(group):
        error = group.error_m.to_numpy()
        return pd.Series({"n": len(error), "rmse_m": np.sqrt(np.mean(error**2)), "mae_m": np.mean(np.abs(error)), "bias_m": np.mean(error), "max_abs_error_m": np.max(np.abs(error))})
    overall = predictions.groupby("method", sort=False).apply(metrics, include_groups=False).reset_index()
    by_date = predictions.groupby(["survey_date", "method"], sort=False).apply(metrics, include_groups=False).reset_index()
    return overall, by_date


def save_fit_facets(surveys, fitted, output):
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), sharey=True)
    for ax, (date, frame) in zip(axes.flat, surveys.items()):
        date_value = date.date()
        ax.scatter(frame.distance_m, frame.bed_elevation_m, s=9, color="#111111", alpha=0.55, label="实测点", zorder=5)
        subset = fitted[fitted.survey_date == date_value]
        for method in METHODS:
            curve = subset[subset.method == method]
            ax.plot(curve.distance_m, curve.bed_elevation_m, color=COLORS[method], lw=1.25, label=LABELS[method])
        ax.set_title(date.strftime("%Y-%m-%d"), fontsize=11)
        ax.set_xlabel("起点距离（m）")
        ax.set_ylabel("河底高程（m）")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.002), ncol=5, frameon=False)
    fig.suptitle("附件2：5 m网格四类连续断面重建", fontsize=16, y=0.995)
    fig.tight_layout(rect=(0, 0.04, 1, 0.965))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_cv_performance(overall, output):
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    x = np.arange(len(overall))
    width = 0.34
    ax.bar(x - width / 2, overall.rmse_m, width, label="RMSE", color="#2878B5")
    ax.bar(x + width / 2, overall.mae_m, width, label="MAE", color="#F2A104")
    for i, row in overall.reset_index(drop=True).iterrows():
        ax.text(i - width / 2, row.rmse_m + 0.015, f"{row.rmse_m:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, row.mae_m + 0.015, f"{row.mae_m:.3f}", ha="center", fontsize=9)
    ax.set_xticks(x, [LABELS[m] for m in overall.method])
    ax.set(title="连续3点空间区块留出验证", ylabel="高程误差（m）")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_error_distribution(predictions, output):
    data = [predictions.loc[predictions.method == method, "abs_error_m"].to_numpy() for method in METHODS]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    parts = ax.violinplot(data, showmeans=True, showmedians=True, showextrema=False)
    for body, method in zip(parts["bodies"], METHODS):
        body.set_facecolor(COLORS[method])
        body.set_alpha(0.65)
    ax.set_xticks(range(1, len(METHODS) + 1), [LABELS[m] for m in METHODS])
    ax.set(title="空间区块留出绝对误差分布", ylabel="绝对误差（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_differences(fitted, dates, grid, output):
    linear = fitted[fitted.method == "linear"].pivot(index="survey_date", columns="distance_m", values="bed_elevation_m").loc[dates, grid]
    comparison_methods = METHODS[1:]
    fig, axes = plt.subplots(len(comparison_methods), 1, figsize=(14, 11), sharex=True, sharey=True)
    vmax = 0
    matrices = []
    for method in comparison_methods:
        current = fitted[fitted.method == method].pivot(index="survey_date", columns="distance_m", values="bed_elevation_m").loc[dates, grid]
        matrix = current.to_numpy() - linear.to_numpy()
        matrices.append(matrix)
        vmax = max(vmax, np.nanquantile(np.abs(matrix), 0.99))
    vmax = max(vmax, 0.05)
    for ax, method, matrix in zip(axes, comparison_methods, matrices):
        image = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax, extent=[grid.min(), grid.max(), len(dates) - 0.5, -0.5])
        ax.set_yticks(range(len(dates)), labels=[str(d) for d in dates])
        ax.set_ylabel(LABELS[method])
        ax.grid(False)
    axes[-1].set_xlabel("起点距离（m）")
    fig.suptitle("各方法相对分段线性的拟合高程差", fontsize=16)
    colorbar = fig.colorbar(image, ax=axes, pad=0.012, shrink=0.9)
    colorbar.set_label("高程差（m）")
    fig.subplots_adjust(left=0.12, right=0.89, top=0.92, bottom=0.08, hspace=0.18)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_deep_channel(surveys, fitted, gp_bounds, output):
    date = max(surveys, key=lambda d: surveys[d].bed_elevation_m.max() - surveys[d].bed_elevation_m.min())
    frame = surveys[date]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    focus = (frame.distance_m >= 1500) & (frame.distance_m <= 2200)
    ax.scatter(frame.loc[focus, "distance_m"], frame.loc[focus, "bed_elevation_m"], color="#111111", s=25, label="实测点", zorder=5)
    subset = fitted[(fitted.survey_date == date.date()) & (fitted.distance_m >= 1500) & (fitted.distance_m <= 2200)]
    for method in METHODS:
        curve = subset[subset.method == method]
        ax.plot(curve.distance_m, curve.bed_elevation_m, color=COLORS[method], lw=2, label=LABELS[method])
    band = gp_bounds[(gp_bounds.survey_date == date.date()) & (gp_bounds.distance_m >= 1500) & (gp_bounds.distance_m <= 2200)]
    ax.fill_between(band.distance_m, band.mean_m - 1.96 * band.std_m, band.mean_m + 1.96 * band.std_m, color=COLORS["matern_gp"], alpha=0.15, label="GP条件95%带")
    ax.set(title=f"主槽局部拟合比较：{date:%Y-%m-%d}", xlabel="起点距离（m）", ylabel="河底高程（m）")
    ax.legend(ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--grid-step-m", type=float, default=5.0)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    for name in ["results", "figures", "validation", "logs"]:
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    configure_plotting()
    surveys = read_surveys(args.input)
    lower = max(frame.distance_m.min() for frame in surveys.values())
    upper = min(frame.distance_m.max() for frame in surveys.values())
    grid = np.arange(np.ceil(lower / args.grid_step_m) * args.grid_step_m, upper + 1e-9, args.grid_step_m)
    predictions, failures = cross_validate(surveys)
    fitted, diagnostics, gp_bounds = fit_full(surveys, grid)
    overall, by_date = summarize_cv(predictions)

    fitted.to_csv(run_dir / "results" / "fitted_common_grid.csv", index=False, encoding="utf-8-sig")
    diagnostics.to_csv(run_dir / "results" / "fit_diagnostics.csv", index=False, encoding="utf-8-sig")
    gp_bounds.to_csv(run_dir / "results" / "gp_uncertainty.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(run_dir / "validation" / "blocked_cv_predictions.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(run_dir / "validation" / "blocked_cv_summary.csv", index=False, encoding="utf-8-sig")
    by_date.to_csv(run_dir / "validation" / "blocked_cv_by_survey.csv", index=False, encoding="utf-8-sig")
    failures.to_csv(run_dir / "logs" / "fit_failures.csv", index=False, encoding="utf-8-sig")

    dates = [date.date() for date in surveys]
    save_fit_facets(surveys, fitted, run_dir / "figures" / "method_fit_facets.png")
    save_cv_performance(overall, run_dir / "figures" / "method_cv_performance.png")
    save_error_distribution(predictions, run_dir / "figures" / "method_cv_error_distribution.png")
    save_differences(fitted, dates, grid, run_dir / "figures" / "method_difference_from_linear.png")
    save_deep_channel(surveys, fitted, gp_bounds, run_dir / "figures" / "deep_channel_method_comparison.png")

    checks = pd.DataFrame(
        [
            {"check": "survey_count", "value": len(surveys), "passed": len(surveys) == 9},
            {"check": "grid_step_m", "value": args.grid_step_m, "passed": args.grid_step_m == 5.0},
            {"check": "grid_values_finite", "value": int(np.isfinite(fitted.bed_elevation_m).sum()), "passed": bool(np.isfinite(fitted.bed_elevation_m).all())},
            {"check": "cv_failures", "value": len(failures), "passed": len(failures) == 0},
            {"check": "all_methods_present", "value": predictions.method.nunique(), "passed": predictions.method.nunique() == len(METHODS)},
        ]
    )
    checks.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")
    (run_dir / "logs" / "run_summary.txt").write_text(
        f"surveys={len(surveys)}\ngrid={lower:.1f},{upper:.1f},{args.grid_step_m:.1f}\ncv_predictions={len(predictions)}\nfailures={len(failures)}\nquality_checks={int(checks.passed.sum())}/{len(checks)}\n",
        encoding="utf-8",
    )
    if not checks.passed.all():
        raise RuntimeError("Quality checks failed")


if __name__ == "__main__":
    main()
