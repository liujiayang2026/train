import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const questionDir = path.resolve(import.meta.dirname, "..");
const projectDir = path.resolve(questionDir, "..");
const taskPath = path.join(projectDir, ".analysis", "tasks.csv");
const rawDir = path.join(questionDir, "data", "raw");
const outputPath = path.join(rawDir, "worldpop-2017-grid-population.csv");
const cachePath = path.join(rawDir, "worldpop-2017-grid-cache.json");
const gridStep = 0.02;
const concurrency = 4;
const limitArgumentIndex = process.argv.indexOf("--limit");
const runLimit = limitArgumentIndex >= 0 ? Number(process.argv[limitArgumentIndex + 1]) : Infinity;

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const rows = lines.slice(1).map((line) => line.split(",").map((value) => value.replace(/^"|"$/g, "")));
  return rows.map((row) => ({
    taskId: row[0],
    lat: Number(row[1]),
    lon: Number(row[2]),
  }));
}

function gridKey(lat, lon) {
  const latIndex = Math.round(lat / gridStep);
  const lonIndex = Math.round(lon / gridStep);
  return `${latIndex}:${lonIndex}`;
}

function gridFeature(key) {
  const [latIndex, lonIndex] = key.split(":").map(Number);
  const centerLat = latIndex * gridStep;
  const centerLon = lonIndex * gridStep;
  const half = gridStep / 2;
  return {
    centerLat,
    centerLon,
    west: centerLon - half,
    east: centerLon + half,
    south: centerLat - half,
    north: centerLat + half,
  };
}

function gridAreaKm2(cell) {
  const earthRadiusKm = 6371.0088;
  const dLon = (cell.east - cell.west) * Math.PI / 180;
  const sinLat = Math.sin(cell.north * Math.PI / 180) - Math.sin(cell.south * Math.PI / 180);
  return earthRadiusKm ** 2 * Math.abs(dLon * sinLat);
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, attempts = 6) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const { stdout } = await execFileAsync("curl.exe", [
        "--silent",
        "--show-error",
        "--fail",
        "--max-time",
        "60",
        "--user-agent",
        "CUMCM academic population analysis/1.0",
        url,
      ], {
        maxBuffer: 4 * 1024 * 1024,
      });
      return JSON.parse(stdout);
    } catch (error) {
      lastError = error;
      await sleep(Math.min(15000, 1000 * 2 ** (attempt - 1)));
    }
  }
  throw lastError;
}

async function fetchSample(lat, lon) {
  const params = new URLSearchParams({
    dataset: "wpgppop",
    year: "2017",
    lat: String(lat),
    lon: String(lon),
  });
  let result = await fetchJson(`https://api.worldpop.org/v1/services/sample?${params}`);
  if (result.status === "finished" && result.data) {
    return Number(result.data.total_population);
  }
  const taskId = result.taskid;
  if (!taskId) {
    throw new Error(`WorldPop response did not include a task id: ${JSON.stringify(result)}`);
  }
  for (let poll = 0; poll < 120; poll += 1) {
    await sleep(1500);
    result = await fetchJson(`https://api.worldpop.org/v1/tasks/${taskId}`);
    if (result.status === "finished") {
      if (result.error || !result.data) {
        throw new Error(`WorldPop task failed: ${JSON.stringify(result)}`);
      }
      return Number(result.data.total_population);
    }
  }
  throw new Error(`WorldPop task timed out: ${taskId}`);
}

async function fetchPopulation(cell) {
  const samplePoints = [
    [cell.centerLat, cell.centerLon],
  ];
  const samples = await Promise.all(samplePoints.map(([lat, lon]) => fetchSample(lat, lon)));
  return {
    samples,
    meanPixelPopulation: samples.reduce((sum, value) => sum + value, 0) / samples.length,
  };
}

function worldPopPixelAreaKm2(latitude) {
  const earthRadiusKm = 6371.0088;
  const pixelDegrees = 1 / 1200;
  const south = (latitude - pixelDegrees / 2) * Math.PI / 180;
  const north = (latitude + pixelDegrees / 2) * Math.PI / 180;
  const dLon = pixelDegrees * Math.PI / 180;
  return earthRadiusKm ** 2 * Math.abs(dLon * (Math.sin(north) - Math.sin(south)));
}

async function main() {
  await fs.mkdir(rawDir, { recursive: true });
  const tasks = parseCsv(await fs.readFile(taskPath, "utf8"));
  const allKeys = [...new Set(tasks.map((task) => gridKey(task.lat, task.lon)))].sort();
  let cache = {};
  try {
    cache = JSON.parse(await fs.readFile(cachePath, "utf8"));
  } catch {
    cache = {};
  }

  const pendingKeys = allKeys.filter((key) => !Number.isFinite(cache[key]?.population_density_per_km2));
  const uniqueKeys = pendingKeys.slice(0, runLimit);
  let cursor = 0;
  let completed = 0;
  async function worker(workerId) {
    while (cursor < uniqueKeys.length) {
      const index = cursor;
      cursor += 1;
      const key = uniqueKeys[index];
      if (Number.isFinite(cache[key]?.population_density_per_km2)) {
        completed += 1;
        continue;
      }
      const cell = gridFeature(key);
      const population = await fetchPopulation(cell);
      const pixelArea = worldPopPixelAreaKm2(cell.centerLat);
      cache[key] = {
        ...cell,
        area_km2: gridAreaKm2(cell),
        sample_pixel_populations: population.samples,
        mean_pixel_population: population.meanPixelPopulation,
        pixel_area_km2: pixelArea,
        population_density_per_km2: population.meanPixelPopulation / pixelArea,
        source: "WorldPop Global 2000-2020, wpgppop, 2017",
      };
      completed += 1;
      if (completed % 5 === 0 || completed === uniqueKeys.length) {
        await fs.writeFile(cachePath, JSON.stringify(cache, null, 2), "utf8");
        process.stdout.write(`worker ${workerId}: ${completed}/${uniqueKeys.length}\n`);
      }
    }
  }

  await Promise.all(Array.from({ length: concurrency }, (_, index) => worker(index + 1)));
  await fs.writeFile(cachePath, JSON.stringify(cache, null, 2), "utf8");

  const completedKeys = allKeys.filter((key) => Number.isFinite(cache[key]?.population_density_per_km2));
  const header = [
    "grid_key",
    "center_latitude",
    "center_longitude",
    "west",
    "east",
    "south",
    "north",
    "area_km2",
    "mean_sampled_pixel_population_2017",
    "population_density_per_km2",
    "source_url",
  ];
  const rows = completedKeys.map((key) => {
    const item = cache[key];
    return [
      key,
      item.centerLat,
      item.centerLon,
      item.west,
      item.east,
      item.south,
      item.north,
      item.area_km2,
      item.mean_pixel_population,
      item.population_density_per_km2,
      "https://api.worldpop.org/v1/services",
    ].join(",");
  });
  await fs.writeFile(outputPath, `${header.join(",")}\n${rows.join("\n")}\n`, "utf8");
  process.stdout.write(`saved ${completedKeys.length}/${allKeys.length} population grids to ${outputPath}\n`);
}

await main();
