import json
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\jianmo\project 2\B")
OUT = Path(r"C:\Users\lenovo\.codex\visualizations\2026\07\24\019f9210-f095-7542-b3a8-eec90f062169\task-map-analysis.html")

tasks = pd.read_csv(ROOT / ".analysis" / "tasks.csv")
members = pd.read_excel(next(ROOT.glob("*.xlsx")))

task_rows = [
    [str(r.iloc[0]), round(float(r.iloc[2]), 6), round(float(r.iloc[1]), 6),
     round(float(r.iloc[3]), 1), int(r.iloc[4])]
    for _, r in tasks.iterrows()
]

member_coords = members.iloc[:, 1].astype(str).str.extract(
    r"([0-9.]+)\s+([0-9.]+)"
).astype(float)
member_rows = []
for idx, r in members.iterrows():
    lat, lon = member_coords.loc[idx]
    # Keep only members near the task study region.
    if 22.25 <= lat <= 24.10 and 112.45 <= lon <= 114.75:
        member_rows.append([
            str(r.iloc[0]), round(float(lon), 6), round(float(lat), 6),
            int(r.iloc[2]), round(float(r.iloc[4]), 1)
        ])

geo = json.loads((ROOT / ".analysis" / "prefectures.json").read_text(encoding="utf-8"))

def points(geometry):
    coords = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        for ring in coords:
            yield from ring
    elif geometry["type"] == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                yield from ring

def intersects_study(feature):
    if not str(feature["properties"].get("id", "")).startswith("44"):
        return False
    pts = list(points(feature["geometry"]))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) >= 112.45 and min(xs) <= 114.75 and max(ys) >= 22.25 and min(ys) <= 24.10

study_geo = {
    "type": "FeatureCollection",
    "features": [f for f in geo["features"] if intersects_study(f)],
}

fragment = """<div id="cumcm-task-map">
  <div class="viz-controls" aria-label="地图图层与显示方式">
    <label class="form-label">任务着色
      <select class="form-select" id="map-color">
        <option value="status">完成状态</option>
        <option value="price">任务价格</option>
      </select>
    </label>
    <label class="form-check form-switch">
      <input class="form-check-input" type="checkbox" id="map-members">
      <span class="form-check-label">显示会员</span>
    </label>
  </div>
  <div class="viz-row text-small" id="map-legend" aria-live="polite"></div>
  <svg id="task-map-svg" role="img" aria-label="珠三角任务完成状态、价格与会员空间分布图"></svg>
  <div class="card text-small" id="map-detail" aria-live="polite">选择地图上的任务查看任务编号、价格和完成状态。</div>
</div>
<style>
#cumcm-task-map{width:100%;color:var(--foreground)}
#cumcm-task-map .viz-controls{margin-bottom:.5rem}
#cumcm-task-map #map-legend{gap:1rem;margin:.25rem 0 .5rem}
#cumcm-task-map #task-map-svg{display:block;width:100%;height:auto;aspect-ratio:1.55/1;overflow:visible}
#cumcm-task-map .boundary{fill:color-mix(in srgb,var(--muted) 46%,transparent);stroke:var(--border);stroke-width:1}
#cumcm-task-map .city-label{fill:var(--muted-foreground);font-size:11px;text-anchor:middle;pointer-events:none}
#cumcm-task-map .task{cursor:pointer;stroke:var(--background);stroke-width:.55;opacity:.84}
#cumcm-task-map .task:focus,#cumcm-task-map .task:hover{stroke:var(--foreground);stroke-width:1.8;opacity:1}
#cumcm-task-map .member{fill:var(--viz-series-3);opacity:.22;pointer-events:none}
#cumcm-task-map #map-detail{margin-top:.6rem}
#cumcm-task-map .swatch{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.3rem;vertical-align:-.05rem}
@media(max-width:520px){#cumcm-task-map #task-map-svg{aspect-ratio:1/1}}
</style>
<script type="module">
import {geoMercator,geoPath,geoCentroid} from "https://esm.sh/d3-geo@3.1.1";
const root=document.getElementById("cumcm-task-map");
const svg=root.querySelector("#task-map-svg");
const colorSel=root.querySelector("#map-color");
const membersToggle=root.querySelector("#map-members");
const legend=root.querySelector("#map-legend");
const detail=root.querySelector("#map-detail");
const tasks=__TASKS__;
const members=__MEMBERS__;
const boundaries=__GEO__;
const NS="http://www.w3.org/2000/svg";
const css=n=>getComputedStyle(root).getPropertyValue(n).trim();
function el(name,attrs,parent){
  const n=document.createElementNS(NS,name);
  for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,v);
  (parent||svg).appendChild(n);return n;
}
function render(){
  const width=Math.max(320,Math.round(root.getBoundingClientRect().width||736));
  const height=Math.round(width/(width<520?1:1.55));
  svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
  svg.replaceChildren();
  const projection=geoMercator().fitExtent([[18,18],[width-18,height-18]],boundaries);
  const path=geoPath(projection);
  const bg=el("g",{},svg);
  boundaries.features.forEach(f=>{
    el("path",{d:path(f),class:"boundary"},bg);
    const c=projection(geoCentroid(f));
    if(c) {const tx=el("text",{x:c[0],y:c[1],class:"city-label"},bg);tx.textContent=f.properties["地名"]||f.properties.name;}
  });
  const memberLayer=el("g",{"aria-label":"会员位置"},svg);
  if(membersToggle.checked) members.forEach(m=>{
    const p=projection([m[1],m[2]]); if(p) el("circle",{cx:p[0],cy:p[1],r:1.5,class:"member"},memberLayer);
  });
  const statusColors=[css("--destructive"),css("--viz-series-2")];
  const priceMin=65,priceMax=85;
  const taskLayer=el("g",{"aria-label":"历史任务位置"},svg);
  tasks.forEach((t,i)=>{
    const p=projection([t[1],t[2]]); if(!p)return;
    let fill;
    if(colorSel.value==="status") fill=statusColors[t[4]];
    else {
      const u=(t[3]-priceMin)/(priceMax-priceMin);
      fill=`color-mix(in srgb,var(--viz-series-1) ${Math.round(25+75*u)}%,var(--muted))`;
    }
    const c=el("circle",{cx:p[0],cy:p[1],r:3.1,fill,class:"task",tabindex:"0","aria-label":`${t[0]}，${t[3]}元，${t[4]?"已完成":"未完成"}`},taskLayer);
    const show=()=>{detail.textContent=`任务 ${t[0]}｜经度 ${t[1]}，纬度 ${t[2]}｜标价 ${t[3]} 元｜${t[4]?"已完成":"未完成"}`};
    c.addEventListener("click",show);c.addEventListener("focus",show);
  });
  if(colorSel.value==="status"){
    legend.innerHTML=`<span><i class="swatch" style="background:var(--viz-series-2)"></i>已完成 522</span><span><i class="swatch" style="background:var(--destructive)"></i>未完成 313</span>${membersToggle.checked?'<span><i class="swatch" style="background:var(--viz-series-3)"></i>会员</span>':''}`;
  }else{
    legend.innerHTML=`<span><i class="swatch" style="background:color-mix(in srgb,var(--viz-series-1) 25%,var(--muted))"></i>65 元</span><span><i class="swatch" style="background:var(--viz-series-1)"></i>85 元</span>${membersToggle.checked?'<span><i class="swatch" style="background:var(--viz-series-3)"></i>会员</span>':''}`;
  }
}
colorSel.addEventListener("change",render);
membersToggle.addEventListener("change",render);
new ResizeObserver(render).observe(root);
render();
</script>
"""

fragment = fragment.replace("__TASKS__", json.dumps(task_rows, ensure_ascii=False, separators=(",", ":")))
fragment = fragment.replace("__MEMBERS__", json.dumps(member_rows, ensure_ascii=False, separators=(",", ":")))
fragment = fragment.replace("__GEO__", json.dumps(study_geo, ensure_ascii=False, separators=(",", ":")))
OUT.write_text(fragment, encoding="utf-8")
print(OUT)
print(f"tasks={len(task_rows)}, members={len(member_rows)}, cities={len(study_geo['features'])}, bytes={OUT.stat().st_size}")
