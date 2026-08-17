#!/usr/bin/env python3
"""Targeted real-ray refinement around the best shifted-hex candidates."""

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

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, validation_states
from shifted_hex_model import ShiftedHexDesign, generate_layout, geometry_checks, local_improvement


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--r03-run", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--final-samples", type=int, default=256)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def logger_for(output):
    for folder in ("results", "figures", "validation", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("targeted-shifted-hex")
    logger.handlers.clear(); logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in [logging.StreamHandler(), logging.FileHandler(output / "logs" / "run.log", encoding="utf-8")]:
        handler.setFormatter(formatter); logger.addHandler(handler)
    return logger


def ray_design(d):
    return Design(d.tower_x,d.tower_y,d.width,d.height,d.center_z,100,math.sqrt(3)*d.spacing/2-(d.width+5),d.spacing-(d.width+5),520,d.rotation)


def evaluate(d,xy,samples,seed,radius,states=None,store=False,logger=None):
    rows,mirror=evaluate_field(ray_design(d),xy,samples,seed,radius,states,store,logger)
    monthly,annual=aggregate_time_rows(rows,d.area*len(xy))
    return rows,monthly,annual,mirror


def write_csv(path,rows):
    if not rows:return
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def read_row(path):
    with path.open("r",encoding="utf-8-sig",newline="") as handle: row=next(csv.DictReader(handle))
    return {k:float(v) for k,v in row.items() if v not in (None,"")}


def design_fields(d):
    return {"tower_y_m":d.tower_y,"width_m":d.width,"height_m":d.height,"center_z_m":d.center_z,"clearance_m":d.clearance,"rotation_deg":math.degrees(d.rotation),"offset_u":d.offset_u,"offset_v":d.offset_v}


def candidates():
    result=[]
    for tower_y in (-55.0,-60.0):
        for width in (6.15,6.20,6.25,6.30):
            for difference in (0.0,0.05,0.10,0.15):
                height=width-difference
                result.append(ShiftedHexDesign(0,tower_y,width,height,max(3.1,height/2),0.05,0,0,0))
    return result


def evaluate_list(items,samples,args,logger,label,states=None,store=True):
    output=[]
    for index,item in enumerate(items,1):
        d=item["design"];xy=item["xy"]
        _,_,annual,mirror=evaluate(d,xy,samples,args.seed,args.neighbor_radius,states or all_states(),store,logger if states is None else None)
        output.append({**item,"annual":annual,"mirror":mirror})
        logger.info("%s %d/%d id=%s P=%.3f unit=%.4f",label,index,len(items),item["id"],annual["field_power_mw"],annual["unit_area_power_kw_m2"])
    return output


def public_rows(rows):
    return [{"id":r["id"],**design_fields(r["design"]),"mirror_count":len(r["xy"]),"total_area_m2":r["design"].area*len(r["xy"]),**{f"annual_{k}":v for k,v in r["annual"].items()}} for r in rows]


def select(rows,threshold,count=1):
    feasible=[r for r in rows if r["annual"]["field_power_mw"]>=threshold]
    ordered=sorted(feasible or rows,key=lambda r:r["annual"]["unit_area_power_kw_m2"] if feasible else r["annual"]["field_power_mw"],reverse=True)
    return ordered[:count]


def make_plots(output,screen,full32,pruning,d,xy,r03,final):
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],"axes.unicode_minus":False})
    fig,ax=plt.subplots(figsize=(8.5,5.4),constrained_layout=True);ax.scatter([r["annual"]["field_power_mw"] for r in full32],[r["annual"]["unit_area_power_kw_m2"] for r in full32],c=[r["design"].height for r in full32],cmap="viridis",s=65);ax.axvline(60,color="#c43c39",linestyle="--");ax.set(xlabel="64光线完整年功率 / MW",ylabel="单位面积功率 / (kW/m2)",title="近方形镜面区域真实光线细搜");ax.grid(True);fig.savefig(output/"figures"/"fig01-targeted-candidates.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.5,5.2),constrained_layout=True);ax.plot([r["removed"] for r in pruning],[r["annual"]["field_power_mw"] for r in pruning],marker="o");ax.axhline(60.10,color="#c43c39",linestyle="--");ax.set(xlabel="删除镜数",ylabel="64光线完整年功率 / MW",title="低贡献镜面筛除");ax.grid(True);fig.savefig(output/"figures"/"fig02-pruning.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,6.5),constrained_layout=True);ax.scatter(xy[:,0],xy[:,1],s=2,color="#3b8c6e");ax.add_patch(plt.Circle((0,0),350,fill=False,color="#333"));ax.add_patch(plt.Circle((d.tower_x,d.tower_y),100,fill=False,linestyle="--",color="#c43c39"));ax.scatter([d.tower_x],[d.tower_y],marker="^",s=75,color="#c46a1a");ax.set_aspect("equal");ax.set(xlim=(-370,370),ylim=(-370,370),xlabel="x / m",ylabel="y / m",title="r05 最终平移六角镜场");ax.grid(True,linewidth=.4);fig.savefig(output/"figures"/"fig03-final-layout.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.8,5),constrained_layout=True);ax.bar(["r03","r05"],[r03["unit_area_power_kw_m2"],final["unit_area_power_kw_m2"]],color=["#7d99af","#3b8c6e"]);ax.set(ylabel="单位面积功率 / (kW/m2)",title="正式256光线结果比较");ax.grid(True,axis="y");fig.savefig(output/"figures"/"fig04-r03-r05-comparison.png",dpi=190);plt.close(fig)


def main():
    args=parse_args();logger=logger_for(args.output);r03=read_row(args.r03_run/"results"/"annual_metrics.csv")
    items=[{"id":f"target-{i+1}","design":d,"xy":generate_layout(d)} for i,d in enumerate(candidates())]
    screen=evaluate_list(items,16,args,logger,"Reduced16",validation_states(),False)
    write_csv(args.output/"results"/"reduced_screen.csv",public_rows(screen))
    top=sorted(screen,key=lambda r:r["annual"]["field_power_mw"],reverse=True)[:6]
    full32=evaluate_list(top,64,args,logger,"Full64");write_csv(args.output/"results"/"initial64_candidates.csv",public_rows(full32))
    top64=select(full32,60.10,2);full64=evaluate_list(top64,128,args,logger,"Full128");write_csv(args.output/"results"/"refinement128_candidates.csv",public_rows(full64))
    base=select(full64,60.10,1)[0];order=np.argsort(base["mirror"][:,0]);prune_items=[]
    for removed in (0,5,10,15):
        xy=np.delete(base["xy"],order[:removed],axis=0) if removed else np.array(base["xy"],copy=True)
        prune_items.append({"id":f"prune-{removed}","removed":removed,"design":base["design"],"xy":xy})
    pruning=evaluate_list(prune_items,64,args,logger,"Prune64");write_csv(args.output/"results"/"pruning_candidates.csv",[{**row,"removed":item["removed"]} for row,item in zip(public_rows(pruning),pruning)])
    prune_top=select(pruning,60.10,2);prune64=evaluate_list(prune_top,128,args,logger,"Prune128");chosen=select(prune64,60.10,1)[0]
    moved_xy,moves=local_improvement(chosen["design"],chosen["xy"],chosen["mirror"][:,0],all_states());_,_,moved_annual,_=evaluate(chosen["design"],moved_xy,64,args.seed,args.neighbor_radius,all_states())
    if moved_annual["field_power_mw"]>=60.10 and moved_annual["unit_area_power_kw_m2"]>chosen["annual"]["unit_area_power_kw_m2"]: final_xy=moved_xy;moved=True
    else: final_xy=chosen["xy"];moved=False
    convergence=[];final_rows=final_monthly=final_annual=final_mirror=None
    for samples in sorted(set([32,64,128,args.final_samples])):
        rows,monthly,annual,mirror=evaluate(chosen["design"],final_xy,samples,args.seed,args.neighbor_radius,all_states(),samples==args.final_samples,logger);convergence.append({"samples":samples,**annual})
        if samples==args.final_samples:final_rows,final_monthly,final_annual,final_mirror=rows,monthly,annual,mirror
    result={**design_fields(chosen["design"]),"mirror_count":len(final_xy),"total_area_m2":chosen["design"].area*len(final_xy),**final_annual,"local_moves":moves,"local_field_accepted":moved}
    checks=geometry_checks(chosen["design"],final_xy);checks.update({"annual_power_constraint_satisfied":final_annual["field_power_mw"]>=60,"annual_power_mw":final_annual["field_power_mw"],"unit_area_power_kw_m2":final_annual["unit_area_power_kw_m2"],"final_samples":args.final_samples,"local_moves_proposed":moves,"local_field_accepted":moved})
    write_csv(args.output/"results"/"annual_metrics.csv",[result]);write_csv(args.output/"results"/"monthly_metrics.csv",final_monthly);write_csv(args.output/"results"/"time_metrics.csv",final_rows);write_csv(args.output/"results"/"ray_convergence.csv",convergence);write_csv(args.output/"results"/"final_positions.csv",[{"mirror_id":i,"x_m":p[0],"y_m":p[1],"z_m":chosen["design"].center_z} for i,p in enumerate(final_xy,1)]);write_csv(args.output/"results"/"mirror_annual_metrics.csv",[{"mirror_id":i,"x_m":p[0],"y_m":p[1],"annual_optical_efficiency":m[0],"annual_cosine_efficiency":m[1],"annual_atmospheric_efficiency":m[2],"annual_shadow_blocking_efficiency":m[3],"annual_truncation_efficiency":m[4]} for i,(p,m) in enumerate(zip(final_xy,final_mirror),1)])
    (args.output/"results"/"design.json").write_text(json.dumps({**asdict(chosen["design"]),**result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8");(args.output/"validation"/"checks.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");(args.output/"validation"/"code_hashes.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE,HERE.with_name("shifted_hex_model.py")]},indent=2)+"\n",encoding="utf-8")
    make_plots(args.output,screen,full32,pruning,chosen["design"],final_xy,r03,final_annual);logger.info("FINAL %s",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
