# -*- coding: utf-8 -*-
"""موتور مستقل برآورد جمعیت بلوک‌ها و تجمیع داده‌های مکانی جمعیت."""
from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from geometry_utils import point_in_polygon


LAT_ALIASES = {"lat", "latitude", "y", "عرض", "عرض_جغرافیایی"}
LON_ALIASES = {"lon", "lng", "long", "longitude", "x", "طول", "طول_جغرافیایی"}
VALUE_ALIASES = {
    "population", "pop", "value", "count", "people", "persons", "جمعیت", "population_count",
    "worldpop", "ghsl", "ghs_pop",
}


@dataclass(frozen=True)
class PopulationEstimate:
    final_population: int
    minimum_population: int
    maximum_population: int
    households: int
    housing_population: int
    meter_population: int
    density_per_km2: float
    confidence: str
    source_count: int
    method_summary: str
    source_values: Dict[str, float]


def _safe_float(value, default=0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _safe_nonnegative(value, default=0.0) -> float:
    return max(0.0, _safe_float(value, default))


def estimate_population(
    *,
    worldpop: float = 0,
    ghsl: float = 0,
    residential_units: int = 0,
    occupied_units: int = 0,
    occupancy_rate: float = 0.90,
    household_size: float = 3.3,
    active_meters: int = 0,
    adjustment: int = 0,
    area_m2: float = 0,
) -> PopulationEstimate:
    """ترکیب وزنی منابع مستقل و تولید بازه عدم‌قطعیت و سطح اطمینان."""
    worldpop = _safe_nonnegative(worldpop)
    ghsl = _safe_nonnegative(ghsl)
    residential_units = int(_safe_nonnegative(residential_units))
    occupied_units = int(_safe_nonnegative(occupied_units))
    occupancy_rate = min(1.0, max(0.0, _safe_float(occupancy_rate, 0.90)))
    household_size = max(0.1, _safe_float(household_size, 3.3))
    active_meters = int(_safe_nonnegative(active_meters))
    adjustment = int(_safe_float(adjustment, 0))
    area_m2 = _safe_nonnegative(area_m2)

    households = occupied_units if occupied_units > 0 else int(round(residential_units * occupancy_rate))
    housing_population = int(round(households * household_size)) if households > 0 else 0
    meter_population = int(round(active_meters * household_size)) if active_meters > 0 else 0

    components: List[Tuple[str, float, float, float]] = []
    if worldpop > 0:
        components.append(("WorldPop", worldpop, 0.32, 0.22))
    if ghsl > 0:
        components.append(("GHSL", ghsl, 0.28, 0.25))
    if housing_population > 0:
        components.append(("واحد مسکونی", float(housing_population), 0.25, 0.18))
    if meter_population > 0:
        components.append(("کنتور فعال", float(meter_population), 0.15, 0.15))

    source_values = {name: round(value, 2) for name, value, _weight, _uncertainty in components}
    if not components:
        return PopulationEstimate(
            final_population=max(0, adjustment), minimum_population=max(0, adjustment),
            maximum_population=max(0, adjustment), households=households,
            housing_population=housing_population, meter_population=meter_population,
            density_per_km2=0.0, confidence="فاقد داده", source_count=0,
            method_summary="هیچ منبع قابل محاسبه‌ای ثبت نشده است.", source_values={},
        )

    weight_sum = sum(weight for _name, _value, weight, _uncertainty in components)
    weighted = sum(value * weight for _name, value, weight, _uncertainty in components) / weight_sum
    lower = sum(value * (1 - uncertainty) * weight for _name, value, weight, uncertainty in components) / weight_sum
    upper = sum(value * (1 + uncertainty) * weight for _name, value, weight, uncertainty in components) / weight_sum

    values = [value for _name, value, _weight, _uncertainty in components]
    variation = (pstdev(values) / mean(values)) if len(values) > 1 and mean(values) else 0.0
    if len(values) >= 3 and variation <= 0.18:
        confidence = "زیاد"
    elif len(values) >= 2 and variation <= 0.35:
        confidence = "متوسط"
    else:
        confidence = "کم"

    # اختلاف زیاد منابع باید در بازه خروجی دیده شود.
    if len(values) > 1:
        lower = min(lower, min(values) * 0.90)
        upper = max(upper, max(values) * 1.10)

    final_population = max(0, int(round(weighted + adjustment)))
    minimum_population = max(0, int(math.floor(lower + adjustment)))
    maximum_population = max(final_population, int(math.ceil(upper + adjustment)))
    density = (final_population / (area_m2 / 1_000_000.0)) if area_m2 > 0 else 0.0
    method = "ترکیب وزنی: " + "، ".join(name for name, *_rest in components)
    if adjustment:
        method += f"؛ اصلاح مدیریتی {adjustment:+d} نفر"

    return PopulationEstimate(
        final_population=final_population,
        minimum_population=minimum_population,
        maximum_population=maximum_population,
        households=households,
        housing_population=housing_population,
        meter_population=meter_population,
        density_per_km2=round(density, 1),
        confidence=confidence,
        source_count=len(components),
        method_summary=method,
        source_values=source_values,
    )


def _normalized_headers(fieldnames: Sequence[str]) -> Dict[str, str]:
    return {str(name).strip().lower().replace(" ", "_"): name for name in (fieldnames or [])}


def _find_header(mapping: Mapping[str, str], aliases: Iterable[str], requested: Optional[str] = None) -> Optional[str]:
    if requested:
        key = requested.strip().lower().replace(" ", "_")
        if key in mapping:
            return mapping[key]
    for alias in aliases:
        key = alias.strip().lower().replace(" ", "_")
        if key in mapping:
            return mapping[key]
    return None


def _zone_index(zones: Sequence[Mapping]) -> List[Tuple[int, Sequence[Sequence[float]], Tuple[float, float, float, float]]]:
    result = []
    for zone in zones:
        polygon = zone.get("boundary_points") or []
        if len(polygon) < 3:
            continue
        lats = [float(point[0]) for point in polygon]
        lons = [float(point[1]) for point in polygon]
        result.append((int(zone["id"]), polygon, (min(lats), min(lons), max(lats), max(lons))))
    return result


def _add_point_to_zones(lat: float, lon: float, value: float, index, totals, counts) -> None:
    if value <= 0 or not all(math.isfinite(v) for v in (lat, lon, value)):
        return
    for zone_id, polygon, bbox in index:
        min_lat, min_lon, max_lat, max_lon = bbox
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon and point_in_polygon(lat, lon, polygon):
            totals[zone_id] += value
            counts[zone_id] += 1
            break


def aggregate_csv(path: str, zones: Sequence[Mapping], value_field: Optional[str] = None) -> Dict[int, Dict[str, float]]:
    index = _zone_index(zones)
    totals = {zone_id: 0.0 for zone_id, _polygon, _bbox in index}
    counts = {zone_id: 0 for zone_id, _polygon, _bbox in index}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        mapping = _normalized_headers(reader.fieldnames or [])
        lat_key = _find_header(mapping, LAT_ALIASES)
        lon_key = _find_header(mapping, LON_ALIASES)
        value_key = _find_header(mapping, VALUE_ALIASES, value_field)
        if not (lat_key and lon_key and value_key):
            raise ValueError("ستون‌های مختصات و جمعیت پیدا نشدند. ستون‌های لازم: lat، lon و population.")
        for row in reader:
            lat = _safe_float(row.get(lat_key), math.nan)
            lon = _safe_float(row.get(lon_key), math.nan)
            value = _safe_float(row.get(value_key), 0.0)
            _add_point_to_zones(lat, lon, value, index, totals, counts)
    return {zone_id: {"value": round(totals[zone_id], 2), "cell_count": counts[zone_id]} for zone_id in totals}


def _geometry_centroid(geometry: Mapping) -> Optional[Tuple[float, float]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    if kind in {"Polygon", "MultiPolygon"}:
        points: List[Tuple[float, float]] = []
        containers = coords if kind == "MultiPolygon" else [coords]
        for polygon in containers or []:
            ring = polygon[0] if polygon else []
            for coord in ring:
                if len(coord) >= 2:
                    points.append((float(coord[1]), float(coord[0])))
        if points:
            return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
    return None


def aggregate_geojson(path: str, zones: Sequence[Mapping], value_field: Optional[str] = None) -> Dict[int, Dict[str, float]]:
    with open(path, "r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    index = _zone_index(zones)
    totals = {zone_id: 0.0 for zone_id, _polygon, _bbox in index}
    counts = {zone_id: 0 for zone_id, _polygon, _bbox in index}
    for feature in features:
        props = feature.get("properties") or {}
        mapping = _normalized_headers(list(props.keys()))
        key = _find_header(mapping, VALUE_ALIASES, value_field)
        if not key:
            continue
        centroid = _geometry_centroid(feature.get("geometry") or {})
        if centroid is None:
            continue
        lat, lon = centroid
        _add_point_to_zones(lat, lon, _safe_float(props.get(key), 0.0), index, totals, counts)
    return {zone_id: {"value": round(totals[zone_id], 2), "cell_count": counts[zone_id]} for zone_id in totals}


def aggregate_geotiff(path: str, zones: Sequence[Mapping]) -> Dict[int, Dict[str, float]]:
    """جمع سلول‌های GeoTIFF داخل بلوک؛ rasterio فقط هنگام استفاده لازم است."""
    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.warp import transform as warp_transform
    except Exception as exc:  # pragma: no cover - وابستگی اختیاری
        raise RuntimeError("برای فایل GeoTIFF کتابخانه اختیاری rasterio نصب نیست. از CSV/GeoJSON استفاده کنید یا rasterio را نصب کنید.") from exc

    index = _zone_index(zones)
    result: Dict[int, Dict[str, float]] = {}
    with rasterio.open(path) as src:
        for zone_id, polygon, bbox in index:
            min_lat, min_lon, max_lat, max_lon = bbox
            if src.crs and str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
                xs, ys = warp_transform("EPSG:4326", src.crs, [min_lon, max_lon], [min_lat, max_lat])
                left, right = min(xs), max(xs)
                bottom, top = min(ys), max(ys)
            else:
                left, right, bottom, top = min_lon, max_lon, min_lat, max_lat
            window = from_bounds(left, bottom, right, top, src.transform).round_offsets().round_lengths()
            data = src.read(1, window=window, masked=True)
            transform = src.window_transform(window)
            total = 0.0
            count = 0
            for row in range(data.shape[0]):
                for col in range(data.shape[1]):
                    value = data[row, col]
                    if getattr(value, "mask", False):
                        continue
                    value = _safe_float(value, 0.0)
                    if value <= 0:
                        continue
                    x, y = rasterio.transform.xy(transform, row, col, offset="center")
                    if src.crs and str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
                        lon_list, lat_list = warp_transform(src.crs, "EPSG:4326", [x], [y])
                        lon, lat = lon_list[0], lat_list[0]
                    else:
                        lon, lat = x, y
                    if point_in_polygon(lat, lon, polygon):
                        total += value
                        count += 1
            result[zone_id] = {"value": round(total, 2), "cell_count": count}
    return result


def aggregate_population_file(path: str, zones: Sequence[Mapping], value_field: Optional[str] = None) -> Dict[int, Dict[str, float]]:
    extension = os.path.splitext(path)[1].lower()
    if extension in {".csv", ".txt", ".tsv"}:
        return aggregate_csv(path, zones, value_field=value_field)
    if extension in {".json", ".geojson"}:
        return aggregate_geojson(path, zones, value_field=value_field)
    if extension in {".tif", ".tiff"}:
        return aggregate_geotiff(path, zones)
    raise ValueError("فرمت پشتیبانی نمی‌شود. فرمت‌های مجاز: CSV، GeoJSON و GeoTIFF.")
