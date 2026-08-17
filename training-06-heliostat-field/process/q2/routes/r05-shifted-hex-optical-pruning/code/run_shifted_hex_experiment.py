#!/usr/bin/env python3
"""Focused shifted-hex search with real-ray pruning and validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, proxy_metrics_from_xy, validation_states
from shifted_hex_model import ShiftedHexDesign, generate_layout, geometry_checks, local_improvement


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--r03-run", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--random-designs", type=int, default=120)
    parser.add_argument("--screen-samples", type=int, default=16)
    parser.add_argument("--verify-samples", type=int, default=32)
    parser.add_argument("--final-samples", type=int, default=256)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def setup(output):
    for folder in ("results", "figures", "validation", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("shifted-hex")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in [logging.StreamHandler(), logging.FileHandler(output / "logs" / "run.log", encoding="utf-8")]:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def ray_design(d):
    return Design(d.tower_x, d.tower_y, d.width, d.height, d.center_z, 100.0, math.sqrt(3) * d.spacing / 2 - (d.width + 5), d.spacing - (d.width + 5), 520.0, d.rotation)


def evaluate(d, xy, samples, seed, radius, states=None, store=False, logger=None):
    rows, mirror = evaluate_field(ray_design(d), xy, samples, seed, radius, states, store, logger)
    monthly, annual = aggregate_time_rows(rows, d.area * len(xy))
    return rows, monthly, annual, mirror


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_row(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    return {key: float(value) for key, value in row.items() if value not in (None, "")}


def fields(d):
    return {"tower_y_m": d.tower_y, "width_m": d.width, "height_m": d.height, "center_z_m": d.center_z, "clearance_m": d.clearance, "rotation_deg": math.degrees(d.rotation), "offset_u": d.offset_u, "offset_v": d.offset_v}


def candidate_designs(seed, random_count):
    designs = []
    # Explicitly preserve the known high-unit-power neighborhood.
    for tower_y in (-45.0, -60.0):
        for height in np.arange(5.90, 6.081, 0.03):
            for rotation_deg, offset_u, offset_v in [(0, 0, 0), (15, 0.25, 0.5), (30, 0.5, 0.25), (45, 0.75, 0.5)]:
                designs.append(ShiftedHexDesign(0, tower_y, 6.3, float(height), max(3.1, float(height) / 2), 0.05, math.radians(rotation_deg), offset_u, offset_v))
    rng = np.random.default_rng(seed)
    for _ in range(random_count):
        width = rng.uniform(6.15, 6.45)
        height = width - rng.uniform(0.25, 0.50)
        designs.append(ShiftedHexDesign(0, rng.uniform(-75, -40), width, height, max(3.1, height / 2), 0.05, rng.uniform(0, math.pi / 3), rng.random(), rng.random()))
    return designs


def proxy_screen(designs, factor, states):
    output = []
    for index, d in enumerate(designs, 1):
        xy = generate_layout(d)
        metrics = proxy_metrics_from_xy(ray_design(d), xy, factor)
        output.append({"design_id": index, **fields(d), "mirror_count": len(xy), "total_area_m2": d.area * len(xy), **{f"proxy_{k}": v for k, v in metrics.items() if k not in ("mirror_count", "total_area_m2")}, "design": d, "xy": xy})
    return output


def unique_rank(rows, count, keys):
    chosen, seen = [], set()
    for key, reverse in keys:
        for row in sorted(rows, key=lambda value: value[key], reverse=reverse):
            signature = (round(row["tower_y_m"], 3), round(row["width_m"], 3), round(row["height_m"], 3), round(row["rotation_deg"], 2), round(row["offset_u"], 2), round(row["offset_v"], 2))
            if signature not in seen:
                chosen.append(row)
                seen.add(signature)
            if len(chosen) >= count:
                return chosen
    return chosen


def serial(rows):
    return [{k: v for k, v in row.items() if k not in ("design", "xy", "mirror", "annual")} for row in rows]


def ray_screen(rows, args, baseline_reduced, baseline_full, logger):
    result = []
    scale = baseline_full / baseline_reduced
    for index, row in enumerate(rows, 1):
        _, _, annual, _ = evaluate(row["design"], row["xy"], args.screen_samples, args.seed, args.neighbor_radius, validation_states())
        item = {**row, **{f"screen_{k}": v for k, v in annual.items()}, "estimated_full_power_mw": annual["field_power_mw"] * scale}
        result.append(item)
        logger.info("Screen %d/%d id=%s N=%d P_est=%.3f unit=%.4f", index, len(rows), row["design_id"], len(row["xy"]), item["estimated_full_power_mw"], annual["unit_area_power_kw_m2"])
    return result


def full_verify(rows, samples, args, logger, label):
    result = []
    for index, row in enumerate(rows, 1):
        _, _, annual, mirror = evaluate(row["design"], row["xy"], samples, args.seed, args.neighbor_radius, all_states(), True, logger)
        result.append({**row, "annual": annual, "mirror": mirror})
        logger.info("%s %d/%d id=%s P=%.3f unit=%.4f", label, index, len(rows), row.get("design_id", "local"), annual["field_power_mw"], annual["unit_area_power_kw_m2"])
    return result


def select_feasible(rows, threshold):
    feasible = [row for row in rows if row["annual"]["field_power_mw"] >= threshold]
    return max(feasible or rows, key=lambda row: row["annual"]["unit_area_power_kw_m2"] if feasible else row["annual"]["field_power_mw"])


def refine_neighbors(best):
    d = best["design"]
    values = [d]
    for delta in (-0.04, -0.02, 0.02, 0.04, 0.06):
        height = min(d.width, d.height + delta)
        values.append(replace(d, height=height, center_z=max(3.1, height / 2)))
    for delta in (-5, -2.5, 2.5, 5):
        values.append(replace(d, tower_y=d.tower_y + delta))
    for delta in (-math.radians(5), math.radians(5)):
        values.append(replace(d, rotation=(d.rotation + delta) % (math.pi / 3)))
    for du, dv in [(-0.15, 0), (0.15, 0), (0, -0.15), (0, 0.15)]:
        values.append(replace(d, offset_u=(d.offset_u + du) % 1, offset_v=(d.offset_v + dv) % 1))
    return [{"design_id": f"local-{i}", **fields(value), "design": value, "xy": generate_layout(value)} for i, value in enumerate(values)]


def prune_candidates(best, args, logger):
    order = np.argsort(best["mirror"][:, 0])
    rows = []
    for removed in (0, 5, 10, 15, 20, 25, 30):
        xy = np.delete(best["xy"], order[:removed], axis=0) if removed else np.array(best["xy"], copy=True)
        _, _, annual, _ = evaluate(best["design"], xy, args.screen_samples, args.seed, args.neighbor_radius, validation_states())
        rows.append({"removed": removed, "mirror_count": len(xy), **annual, "design": best["design"], "xy": xy})
        logger.info("Prune screen removed=%d P_reduced=%.3f unit=%.4f", removed, annual["field_power_mw"], annual["unit_area_power_kw_m2"])
    scale = best["annual"]["field_power_mw"] / rows[0]["field_power_mw"]
    for row in rows:
        row["estimated_full_power_mw"] = row["field_power_mw"] * scale
    feasible = [row for row in rows if row["estimated_full_power_mw"] >= 60.35]
    return sorted(feasible or rows, key=lambda row: row["unit_area_power_kw_m2"], reverse=True)[:2], rows


def plots(output, proxy, full32, prune, before_xy, final_xy, d, r03, final):
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8.7, 5.5), constrained_layout=True)
    p = np.array([r["proxy_field_power_mw"] for r in proxy]); u = np.array([r["proxy_unit_area_power_kw_m2"] for r in proxy]); a = np.array([r["total_area_m2"] for r in proxy]) / 1000
    mark = ax.scatter(p, u, c=a, s=20, cmap="viridis", alpha=.7); ax.axvline(60, color="#c43c39", linestyle="--"); ax.set(xlabel="校准代理功率 / MW", ylabel="代理单位面积功率 / (kW/m2)", title="平移旋转六角点阵候选初筛"); ax.grid(True); fig.colorbar(mark, ax=ax, label="总镜面面积 / 10^3 m2"); fig.savefig(output / "figures" / "fig01-proxy-search.png", dpi=190); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.7, 5.5), constrained_layout=True)
    for row in full32: ax.scatter(row["annual"]["field_power_mw"], row["annual"]["unit_area_power_kw_m2"], s=60)
    ax.axvline(60, color="#c43c39", linestyle="--"); ax.set(xlabel="32光线完整年功率 / MW", ylabel="单位面积功率 / (kW/m2)", title="真实光线候选复核"); ax.grid(True); fig.savefig(output / "figures" / "fig02-real-ray-candidates.png", dpi=190); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
    for ax, xy, title in [(axes[0], before_xy, "A  删镜前"), (axes[1], final_xy, "B  最终镜场")]: ax.scatter(xy[:,0],xy[:,1],s=2,color="#3b8c6e"); ax.add_patch(plt.Circle((0,0),350,fill=False,color="#333")); ax.add_patch(plt.Circle((d.tower_x,d.tower_y),100,fill=False,linestyle="--",color="#c43c39")); ax.scatter([d.tower_x],[d.tower_y],marker="^",s=70,color="#c46a1a"); ax.set_aspect("equal"); ax.set(xlim=(-370,370),ylim=(-370,370),xlabel="x / m",ylabel="y / m",title=title); ax.grid(True,linewidth=.4)
    fig.savefig(output / "figures" / "fig03-layout-before-after.png", dpi=190); plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(10.5,4.6),constrained_layout=True); axes[0].plot([r["removed"] for r in prune],[r["estimated_full_power_mw"] for r in prune],marker="o"); axes[0].axhline(60.35,color="#c43c39",linestyle="--"); axes[0].set(xlabel="删除镜数",ylabel="估计完整年功率 / MW",title="A  低贡献删镜"); axes[0].grid(True); axes[1].bar(["r03","r05"],[r03["unit_area_power_kw_m2"],final["unit_area_power_kw_m2"]],color=["#7d99af","#3b8c6e"]); axes[1].set(ylabel="单位面积功率 / (kW/m2)",title="B  正式结果比较"); axes[1].grid(True,axis="y"); fig.savefig(output / "figures" / "fig04-pruning-comparison.png",dpi=190); plt.close(fig)


def main():
    args = parse_args(); logger = setup(args.output)
    r03 = read_row(args.r03_run / "results" / "annual_metrics.csv")
    positions = np.genfromtxt(args.r03_run / "results" / "heliostat_positions.csv", delimiter=",", names=True, encoding="utf-8-sig")
    r03_xy = np.column_stack([positions["x_m"], positions["y_m"]])
    reference = Design(0,-60,6.8,6.35,3.175,100,math.sqrt(3)*11.8/2-11.8,0,520,0)
    calibration = r03["unit_area_power_kw_m2"] / proxy_metrics_from_xy(reference, r03_xy)["unit_area_power_kw_m2"]
    base_hex = ShiftedHexDesign(0,-60,6.8,6.35,3.175,0,0,0,0)
    _,_,base_reduced,_ = evaluate(base_hex,r03_xy,args.screen_samples,args.seed,args.neighbor_radius,validation_states())
    proxy = proxy_screen(candidate_designs(args.seed,args.random_designs),calibration,all_states()); write_csv(args.output/"results"/"proxy_screen.csv",serial(proxy)); logger.info("Proxy complete designs=%d",len(proxy))
    eligible = [r for r in proxy if r["proxy_field_power_mw"] >= 58.5]
    chosen = unique_rank(eligible,12,[("proxy_field_power_mw",True),("proxy_unit_area_power_kw_m2",True)])
    screen = ray_screen(chosen,args,base_reduced["field_power_mw"],r03["field_power_mw"],logger); write_csv(args.output/"results"/"reduced_ray_screen.csv",serial(screen))
    full_input = unique_rank(screen,4,[("estimated_full_power_mw",True),("screen_unit_area_power_kw_m2",True)])
    full32 = full_verify(full_input,args.verify_samples,args,logger,"Full32"); write_csv(args.output/"results"/"full32_candidates.csv",[{**serial([r])[0],**{f"annual_{k}":v for k,v in r["annual"].items()}} for r in full32])
    best32 = select_feasible(full32,60.0)
    local = refine_neighbors(best32)
    local_screen = ray_screen(local,args,base_reduced["field_power_mw"],r03["field_power_mw"],logger)
    local_candidates = unique_rank([r for r in local_screen if r["estimated_full_power_mw"]>=60.0] or local_screen,3,[("screen_unit_area_power_kw_m2",True),("estimated_full_power_mw",True)])
    full64 = full_verify(local_candidates,64,args,logger,"Full64"); write_csv(args.output/"results"/"full64_refinement.csv",[{**serial([r])[0],**{f"annual_{k}":v for k,v in r["annual"].items()}} for r in full64])
    best64 = select_feasible(full64,60.35)
    prune_input, prune_all = prune_candidates(best64,args,logger); write_csv(args.output/"results"/"pruning_screen.csv",serial(prune_all))
    prune64 = full_verify(prune_input,64,args,logger,"Prune64"); best_pruned = select_feasible(prune64,60.25)
    local_xy,moves = local_improvement(best_pruned["design"],best_pruned["xy"],best_pruned["mirror"][:,0],all_states())
    _,_,moved_annual,_ = evaluate(best_pruned["design"],local_xy,64,args.seed,args.neighbor_radius,all_states())
    if moved_annual["field_power_mw"]>=60.25 and moved_annual["unit_area_power_kw_m2"]>best_pruned["annual"]["unit_area_power_kw_m2"]: final_xy=local_xy; moved=True
    else: final_xy=best_pruned["xy"]; moved=False
    convergence=[]; final_rows=final_monthly=final_annual=final_mirror=None
    for samples in sorted(set([32,64,128,args.final_samples])):
        rows,monthly,annual,mirror=evaluate(best_pruned["design"],final_xy,samples,args.seed,args.neighbor_radius,all_states(),samples==args.final_samples,logger); convergence.append({"samples":samples,**annual})
        if samples==args.final_samples: final_rows,final_monthly,final_annual,final_mirror=rows,monthly,annual,mirror
    checks=geometry_checks(best_pruned["design"],final_xy); checks.update({"annual_power_constraint_satisfied":final_annual["field_power_mw"]>=60,"annual_power_mw":final_annual["field_power_mw"],"unit_area_power_kw_m2":final_annual["unit_area_power_kw_m2"],"local_moves_proposed":moves,"local_field_accepted":moved,"final_samples":args.final_samples})
    result={**fields(best_pruned["design"]),"mirror_count":len(final_xy),"total_area_m2":best_pruned["design"].area*len(final_xy),**final_annual,"local_moves":moves,"local_field_accepted":moved}
    write_csv(args.output/"results"/"annual_metrics.csv",[result]); write_csv(args.output/"results"/"monthly_metrics.csv",final_monthly); write_csv(args.output/"results"/"time_metrics.csv",final_rows); write_csv(args.output/"results"/"ray_convergence.csv",convergence); write_csv(args.output/"results"/"final_positions.csv",[{"mirror_id":i,"x_m":p[0],"y_m":p[1],"z_m":best_pruned["design"].center_z} for i,p in enumerate(final_xy,1)]); write_csv(args.output/"results"/"mirror_annual_metrics.csv",[{"mirror_id":i,"x_m":p[0],"y_m":p[1],"annual_optical_efficiency":m[0],"annual_cosine_efficiency":m[1],"annual_atmospheric_efficiency":m[2],"annual_shadow_blocking_efficiency":m[3],"annual_truncation_efficiency":m[4]} for i,(p,m) in enumerate(zip(final_xy,final_mirror),1)])
    (args.output/"results"/"design.json").write_text(json.dumps({**asdict(best_pruned["design"]),**result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (args.output/"validation"/"checks.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    plots(args.output,proxy,full32,prune_all,best64["xy"],final_xy,best_pruned["design"],r03,final_annual)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE,HERE.with_name("shifted_hex_model.py")]}; (args.output/"validation"/"code_hashes.json").write_text(json.dumps(hashes,indent=2)+"\n",encoding="utf-8")
    logger.info("FINAL %s",json.dumps(result,ensure_ascii=False))


if __name__ == "__main__": main()
