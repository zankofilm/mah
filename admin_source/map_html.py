# -*- coding: utf-8 -*-
"""
تولید محتوای HTML نقشه (بر پایه Leaflet.js) که داخل QWebEngineView نمایش داده می‌شود.
دو حالت دارد:
  - حالت رسم محدوده (draw_mode=True): کاربر با کلیک، نقاط مرزی را مشخص می‌کند
  - حالت نمایش (draw_mode=False): نمایش محدوده + خیابان‌ها + اماکن ذخیره‌شده
"""

import json
from tile_server import get_tile_server_base_url
from place_types import get_place_type_meta

# مختصات تقریبی مرکز جوانرود، کرمانشاه
JAVANROOD_CENTER = (34.8114, 46.4911)

# آدرس‌های رسمی کیت توسعه Leaflet نشان (SDK)
NESHAN_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
NESHAN_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def _offline_grid_layer_js():
    """پس‌زمینه کاملاً محلی برای نقشه آفلاین؛ بدون درخواست تایل اینترنتی یا کش خراب."""
    return r"""
  var OfflineGridLayer = L.GridLayer.extend({
    createTile: function(coords) {
      var tile = document.createElement('canvas');
      tile.width = 256; tile.height = 256;
      var ctx = tile.getContext('2d');
      ctx.fillStyle = '#f3f6f9';
      ctx.fillRect(0, 0, 256, 256);
      ctx.strokeStyle = '#d9e1e8';
      ctx.lineWidth = 1;
      for (var i = 0; i <= 256; i += 64) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 256); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(256, i); ctx.stroke();
      }
      ctx.fillStyle = '#9aa7b4';
      ctx.font = '11px Tahoma, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('نقشه آفلاین داخلی', 128, 132);
      return tile;
    }
  });
  new OfflineGridLayer({maxZoom: 19, minZoom: 1, noWrap: false}).addTo(map);
"""


def _place_map_item(place):
    """داده استاندارد یک مکان برای تمام نقشه‌ها؛ آیکون و مسئول از یک مرجع مشترک می‌آیند."""
    meta = get_place_type_meta(place.get("subtype"))
    return {
        "id": place.get("id"),
        "name": place.get("name") or "بدون نام",
        "subtype": place.get("subtype") or meta["label"],
        "lat": place.get("lat"),
        "lon": place.get("lon"),
        "icon": meta["icon"],
        "managerRole": place.get("manager_role") or meta["role_label"],
        "managerLabel": place.get("manager_label") or "",
        "managerMobile": place.get("manager_mobile") or "",
    }


def build_draw_mode_html():
    """صفحه‌ای برای کشیدن محدوده شهر با کلیک روی نقشه آنلاین (نقشه نشان)."""
    lat, lon = JAVANROOD_CENTER
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>رسم محدوده جوانرود</title>
<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .place-type-icon {{
    background:#163a63; color:white; border:2px solid white; border-radius:50%;
    width:28px !important; height:28px !important; line-height:24px; text-align:center;
    font-size:16px; box-shadow:0 1px 5px rgba(0,0,0,.45);
  }}
  #toolbar {{
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: white; padding: 8px 12px; border-radius: 8px;
    font-family: Tahoma, sans-serif; direction: rtl; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  }}
  #toolbar button {{ margin-left: 6px; padding: 5px 10px; cursor: pointer; }}
  #status {{
    position: absolute; bottom: 10px; left: 10px; z-index: 1000;
    background: white; padding: 6px 10px; border-radius: 6px;
    font-family: Tahoma, sans-serif; direction: rtl; font-size: 12px; color: #888;
  }}
</style>
</head>
<body>
<div id="toolbar">
  <b>رسم محدوده شهر:</b> روی نقشه کلیک کنید تا نقاط مرزی اضافه شود.
  <button onclick="undoPoint()">حذف آخرین نقطه</button>
  <button onclick="clearPoints()">پاک کردن همه</button>
  <span id="count">نقاط: 0</span>
</div>
<div id="map"></div>
<div id="status">نقشه آنلاین: OpenStreetMap</div>
<script src="{NESHAN_LEAFLET_JS}"></script>
<script>
  var map = L.map('map').setView([{lat}, {lon}], 13);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);

  var points = [];
  var markers = [];
  var polygon = null;

  function updatePolygon() {{
    if (polygon) {{ map.removeLayer(polygon); }}
    if (points.length > 1) {{
      polygon = L.polygon(points, {{color: 'red'}}).addTo(map);
    }}
    document.getElementById('count').innerText = "نقاط: " + points.length;
  }}

  map.on('click', function(e) {{
    points.push([e.latlng.lat, e.latlng.lng]);
    var m = L.circleMarker(e.latlng, {{radius: 5, color: 'red', fillColor: 'red', fillOpacity: 1}}).addTo(map);
    markers.push(m);
    updatePolygon();
  }});

  function undoPoint() {{
    if (points.length > 0) {{
      points.pop();
      var m = markers.pop();
      map.removeLayer(m);
      updatePolygon();
    }}
  }}

  function clearPoints() {{
    points = [];
    markers.forEach(function(m) {{ map.removeLayer(m); }});
    markers = [];
    updatePolygon();
  }}

  function getPoints() {{
    return JSON.stringify(points);
  }}
</script>
</body>
</html>
"""
    return html


def build_zone_draw_html(existing_zones=None, boundary_points=None, mosques=None, offline=False,
                          schools=None, health_centers=None, places=None):
    """
    صفحه رسم یک منطقه/بلوک جدید.
    در حالت آفلاین از Leaflet محلی و تایل‌های ذخیره‌شده در دیتابیس استفاده می‌شود.
    """
    existing_zones = existing_zones or []
    mosques = mosques or []
    schools = schools or []
    health_centers = health_centers or []
    places = places or []
    tile_base = get_tile_server_base_url()
    lat, lon = JAVANROOD_CENTER
    if boundary_points:
        lats = [p[0] for p in boundary_points]
        lons = [p[1] for p in boundary_points]
        lat = sum(lats) / len(lats)
        lon = sum(lons) / len(lons)

    boundary_json = json.dumps(boundary_points or [])
    existing_zones_json = json.dumps([
        {
            "id": z.get("id"),
            "name": z["name"],
            "color": z["color"],
            "status": z.get("status") or "ناقص",
            "points": z["boundary_points"],
        }
        for z in existing_zones
    ], ensure_ascii=False)
    mosques_json = json.dumps([
        {"id": m.get("id"), "name": m.get("name"), "lat": m.get("lat"), "lon": m.get("lon"),
         "imamLabel": m.get("imam_label") or "", "imamMobile": m.get("imam_mobile") or ""}
        for m in mosques
    ], ensure_ascii=False)
    schools_json = json.dumps([
        {"id": s.get("id"), "name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"),
         "managerLabel": s.get("manager_label") or "", "managerMobile": s.get("manager_mobile") or ""}
        for s in schools
    ], ensure_ascii=False)
    health_centers_json = json.dumps([
        {"id": h.get("id"), "name": h.get("name"), "lat": h.get("lat"), "lon": h.get("lon"),
         "managerLabel": h.get("manager_label") or "", "managerMobile": h.get("manager_mobile") or ""}
        for h in health_centers
    ], ensure_ascii=False)
    places_json = json.dumps([_place_map_item(place) for place in places], ensure_ascii=False)

    if offline:
        css_link = f'<link rel="stylesheet" href="{tile_base}/vendor/leaflet.css" />'
        js_script = f'<script src="{tile_base}/vendor/leaflet.js"></script>'
        map_init = f"""
  var map = L.map('map').setView([{lat}, {lon}], 14);
  L.tileLayer('{tile_base}/tile/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (offline)',
      errorTileUrl: ''
  }}).addTo(map);
"""
        mode_label = "حالت آفلاین"
    else:
        css_link = f'<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />'
        js_script = f'<script src="{NESHAN_LEAFLET_JS}"></script>'
        map_init = f"""
  var map = L.map('map').setView([{lat}, {lon}], 13);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
"""
        mode_label = "حالت آنلاین"

    return f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8" />
<title>رسم منطقه جدید</title>
{css_link}
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  #toolbar {{
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: white; padding: 8px 12px; border-radius: 8px;
    font-family: Tahoma, sans-serif; direction: rtl; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  }}
  #toolbar button {{ margin-left: 6px; padding: 5px 10px; cursor: pointer; }}
  #mode {{ color:#1565c0; margin-right:8px; font-weight:bold; }}
  .leaflet-popup-content {{ direction: rtl; font-family: Tahoma, sans-serif; }}
  .mosque-div-icon, .place-type-icon {{
    background:#0b7a45; color:white; border:2px solid white; border-radius:50%;
    width:28px !important; height:28px !important; line-height:24px; text-align:center;
    font-size:16px; box-shadow:0 1px 5px rgba(0,0,0,.45);
  }}
  .place-type-icon {{ background:#163a63; }}
  .zone-label-icon {{
    background: transparent !important; border: 0 !important;
  }}
  .zone-label-card {{
    --zone-color:#163a63; direction:rtl; display:flex; align-items:center; gap:8px;
    min-width:118px; max-width:210px; padding:7px 10px; border-radius:12px;
    background:rgba(255,255,255,.94); color:#172033;
    border:1px solid rgba(19,41,75,.16); border-right:4px solid var(--zone-color);
    box-shadow:0 4px 16px rgba(15,23,42,.20);
    font-family:Tahoma, sans-serif; white-space:nowrap;
    transform:translate(-50%,-50%); transition:opacity .18s ease, transform .18s ease;
    backdrop-filter:blur(6px);
  }}
  .zone-label-pin {{
    width:24px; height:24px; flex:0 0 24px; border-radius:8px;
    display:flex; align-items:center; justify-content:center;
    color:white; background:var(--zone-color); font-size:13px; font-weight:bold;
    box-shadow:0 2px 6px rgba(15,23,42,.20);
  }}
  .zone-label-text {{ overflow:hidden; text-overflow:ellipsis; font-weight:700; font-size:12px; }}
  .zone-label-caption {{ display:block; color:#64748b; font-size:9px; font-weight:400; margin-bottom:1px; }}
  .zone-label-card.is-compact {{ min-width:0; padding:5px 8px; border-radius:10px; }}
  .zone-label-card.is-compact .zone-label-pin,
  .zone-label-card.is-compact .zone-label-caption {{ display:none; }}
  .zone-label-card.is-hidden {{ opacity:0; pointer-events:none; }}
</style>
</head>
<body>
<div id="toolbar">
  <b>رسم منطقه جدید:</b> روی نقشه کلیک کنید تا نقاط مرزی اضافه شود.
  <button onclick="undoPoint()">حذف آخرین نقطه</button>
  <button onclick="clearPoints()">پاک کردن همه</button>
  <span id="count">نقاط: 0</span>
  <span id="mode">{mode_label}</span>
</div>
<div id="map"></div>
{js_script}
<script>
{map_init}
  var cityBoundary = {boundary_json};
  if (cityBoundary.length > 1) {{
    L.polygon(cityBoundary, {{color: '#555', weight: 2, dashArray: '6,4', fillOpacity: 0}}).addTo(map);
  }}

  function escHtml(value) {{
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }}

  var existingZones = {existing_zones_json};
  var existingZoneLabels = [];
  existingZones.forEach(function(z) {{
    if (!(z.points && z.points.length > 1)) return;

    var poly = L.polygon(z.points, {{
      color: z.color, weight: 2, fillColor: z.color, fillOpacity: 0.18
    }}).addTo(map);
    poly.bindPopup(
      '<div style="direction:rtl;font-family:Tahoma,sans-serif;min-width:150px">' +
      '<b style="font-size:14px">' + escHtml(z.name) + '</b><br>' +
      '<span style="color:#64748b">وضعیت: ' + escHtml(z.status || 'ناقص') + '</span>' +
      '</div>'
    );
    poly.on('mouseover', function() {{ poly.setStyle({{weight:4, fillOpacity:.28}}); }});
    poly.on('mouseout', function() {{ poly.setStyle({{weight:2, fillOpacity:.18}}); }});

    var labelHtml =
      '<div class="zone-label-card" style="--zone-color:' + escHtml(z.color || '#163a63') + '">' +
        '<span class="zone-label-pin">⌖</span>' +
        '<span class="zone-label-text"><span class="zone-label-caption">بلوک</span>' + escHtml(z.name) + '</span>' +
      '</div>';
    var labelIcon = L.divIcon({{
      className:'zone-label-icon', html:labelHtml, iconSize:[1,1], iconAnchor:[0,0]
    }});
    var label = L.marker(poly.getCenter(), {{
      icon:labelIcon, interactive:false, keyboard:false, zIndexOffset:700
    }}).addTo(map);
    existingZoneLabels.push(label);
  }});

  function updateExistingZoneLabels() {{
    var zoom = map.getZoom();
    existingZoneLabels.forEach(function(label) {{
      var el = label.getElement();
      if (!el) return;
      var card = el.querySelector('.zone-label-card');
      if (!card) return;
      card.classList.toggle('is-hidden', zoom < 13);
      card.classList.toggle('is-compact', zoom === 13);
    }});
  }}
  map.on('zoomend', updateExistingZoneLabels);
  map.whenReady(updateExistingZoneLabels);

  var places = {places_json};
  places.forEach(function(p) {{
    if (p.lat == null || p.lon == null) return;
    var icon = L.divIcon({{className:'place-type-icon', html:p.icon || '📍', iconSize:[28,28], iconAnchor:[14,14]}});
    var managerText = p.managerLabel ? '<br>' + p.managerRole + ': ' + p.managerLabel : '';
    var mobileText = p.managerMobile ? '<br>تلفن: ' + p.managerMobile : '';
    L.marker([p.lat,p.lon], {{icon:icon}}).addTo(map)
      .bindPopup('<b>' + (p.icon || '📍') + ' ' + p.name + '</b><br>' + p.subtype + managerText + mobileText);
  }});

  var mosques = {mosques_json};
  var mosqueIcon = L.divIcon({{className:'mosque-div-icon', html:'🕌', iconSize:[28,28], iconAnchor:[14,14]}});
  mosques.forEach(function(m) {{
    if (m.lat != null && m.lon != null) {{
      var imamText = m.imamLabel ? '<br>امام جماعت: ' + m.imamLabel : '';
      var imamMobileText = m.imamMobile ? '<br>تلفن: ' + m.imamMobile : '';
      L.marker([m.lat, m.lon], {{icon:mosqueIcon, keyboard:false}}).addTo(map)
        .bindPopup('<b>🕌 ' + m.name + '</b>' + imamText + imamMobileText + '<br>عرض: ' + Number(m.lat).toFixed(6) + '<br>طول: ' + Number(m.lon).toFixed(6));
    }}
  }});

  var schools = {schools_json};
  var schoolIcon = L.divIcon({{className:'mosque-div-icon', html:'🏫', iconSize:[28,28], iconAnchor:[14,14]}});
  schools.forEach(function(s) {{
    if (s.lat != null && s.lon != null) {{
      var managerText = s.managerLabel ? '<br>مدیر مدرسه: ' + s.managerLabel : '';
      var managerMobileText = s.managerMobile ? '<br>تلفن: ' + s.managerMobile : '';
      L.marker([s.lat, s.lon], {{icon:schoolIcon, keyboard:false}}).addTo(map)
        .bindPopup('<b>🏫 ' + s.name + '</b>' + managerText + managerMobileText + '<br>عرض: ' + Number(s.lat).toFixed(6) + '<br>طول: ' + Number(s.lon).toFixed(6));
    }}
  }});

  var healthCenters = {health_centers_json};
  var healthIcon = L.divIcon({{className:'mosque-div-icon', html:'🏥', iconSize:[28,28], iconAnchor:[14,14]}});
  healthCenters.forEach(function(h) {{
    if (h.lat != null && h.lon != null) {{
      var managerText = h.managerLabel ? '<br>مسؤول مرکز بهداشتی: ' + h.managerLabel : '';
      var managerMobileText = h.managerMobile ? '<br>تلفن: ' + h.managerMobile : '';
      L.marker([h.lat, h.lon], {{icon:healthIcon, keyboard:false}}).addTo(map)
        .bindPopup('<b>🏥 ' + h.name + '</b>' + managerText + managerMobileText + '<br>عرض: ' + Number(h.lat).toFixed(6) + '<br>طول: ' + Number(h.lon).toFixed(6));
    }}
  }});

  var points = [];
  var markers = [];
  var polygon = null;

  function updatePolygon() {{
    if (polygon) map.removeLayer(polygon);
    if (points.length > 1) polygon = L.polygon(points, {{color: 'red', weight:3, fillOpacity:.15}}).addTo(map);
    document.getElementById('count').innerText = 'نقاط: ' + points.length;
  }}
  map.on('click', function(e) {{
    points.push([e.latlng.lat, e.latlng.lng]);
    markers.push(L.circleMarker(e.latlng, {{radius:5, color:'red', fillColor:'red', fillOpacity:1}}).addTo(map));
    updatePolygon();
  }});
  function undoPoint() {{
    if (!points.length) return;
    points.pop();
    map.removeLayer(markers.pop());
    updatePolygon();
  }}
  function clearPoints() {{
    points = [];
    markers.forEach(function(marker) {{ map.removeLayer(marker); }});
    markers = [];
    updatePolygon();
  }}
  function getPoints() {{ return JSON.stringify(points); }}
</script>
</body>
</html>
"""

def build_all_zones_view_html(zones, boundary_points=None, offline=False, mosques=None,
                               schools=None, health_centers=None):
    """
    نمایش نقشه کلی با تمام مناطق/بلوک‌ها به رنگ‌های خودشان روی هم.
    zones: لیستی از دیکشنری {"name", "color", "boundary_points", "streets":[...], "places":[...]}
    boundary_points: محدوده کلی شهر (اختیاری)
    """
    tile_base = get_tile_server_base_url()
    zones = zones or []
    boundary_points = boundary_points or []
    mosques = mosques or []
    schools = schools or []
    health_centers = health_centers or []

    all_lats, all_lons = [], []
    for z in zones:
        for p in z.get("boundary_points", []):
            all_lats.append(p[0]); all_lons.append(p[1])
    for p in boundary_points:
        all_lats.append(p[0]); all_lons.append(p[1])

    if all_lats:
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
    else:
        center_lat, center_lon = JAVANROOD_CENTER

    boundary_json = json.dumps(boundary_points)
    zones_json = json.dumps([
        {
            "id": z.get("id"),
            "name": z["name"],
            "color": z["color"],
            "status": z.get("status") or "ناقص",
            "area_m2": z.get("area_m2") or 0,
            "points": z.get("boundary_points", []),
            "streets": [
                {"name": s.get("name") or "بدون نام", "type": s.get("highway_type", ""), "geom": s.get("geometry", [])}
                for s in z.get("streets", [])
            ],
            "places": [_place_map_item(p) for p in z.get("places", [])],
            "mosques": [
                {"id": m.get("id"), "name": m.get("name"), "lat": m.get("lat"), "lon": m.get("lon")}
                for m in z.get("mosques", [])
            ],
        }
        for z in zones
    ], ensure_ascii=False)
    mosques_json = json.dumps([
        {
            "id": m.get("id"), "name": m.get("name"), "lat": m.get("lat"), "lon": m.get("lon"),
            "zones": m.get("zones", []),
            "imamLabel": m.get("imam_label") or "", "imamMobile": m.get("imam_mobile") or "",
        }
        for m in mosques
    ], ensure_ascii=False)
    schools_json = json.dumps([
        {"id": s.get("id"), "name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"),
         "managerLabel": s.get("manager_label") or "", "managerMobile": s.get("manager_mobile") or ""}
        for s in schools
    ], ensure_ascii=False)
    health_centers_json = json.dumps([
        {"id": h.get("id"), "name": h.get("name"), "lat": h.get("lat"), "lon": h.get("lon"),
         "managerLabel": h.get("manager_label") or "", "managerMobile": h.get("manager_mobile") or ""}
        for h in health_centers
    ], ensure_ascii=False)

    if offline:
        map_init_js = f"""
  var map = L.map('map', {{
      zoomControl: false,
      scrollWheelZoom: true,
      doubleClickZoom: true,
      boxZoom: true,
      keyboard: true,
      touchZoom: true,
      dragging: true,
      minZoom: 9,
      maxZoom: 19,
      wheelPxPerZoomLevel: 60
  }}).setView([{center_lat}, {center_lon}], 13);
  L.control.zoom({{
      position: 'topright',
      zoomInTitle: 'بزرگ‌نمایی',
      zoomOutTitle: 'کوچک‌نمایی'
  }}).addTo(map);
  L.tileLayer('{tile_base}/tile/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (offline)',
      errorTileUrl: ''
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{tile_base}/vendor/leaflet.css" />'
        js_script = f'<script src="{tile_base}/vendor/leaflet.js"></script>'
        status_text = "نقشه کلی: آفلاین داخلی (داده‌های ذخیره‌شده)"
    else:
        map_init_js = f"""
  var map = L.map('map', {{
      zoomControl: false,
      scrollWheelZoom: true,
      doubleClickZoom: true,
      boxZoom: true,
      keyboard: true,
      touchZoom: true,
      dragging: true,
      minZoom: 9,
      maxZoom: 19,
      wheelPxPerZoomLevel: 60
  }}).setView([{center_lat}, {center_lon}], 13);
  L.control.zoom({{
      position: 'topright',
      zoomInTitle: 'بزرگ‌نمایی',
      zoomOutTitle: 'کوچک‌نمایی'
  }}).addTo(map);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />'
        js_script = f'<script src="{NESHAN_LEAFLET_JS}"></script>'
        status_text = "نقشه کلی: آنلاین (OpenStreetMap)"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>نقشه کلی مناطق جوانرود</title>
{css_link}
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  #map {{ cursor: grab; }}
  #map:active {{ cursor: grabbing; }}
  .leaflet-popup-content {{ direction: rtl; font-family: Tahoma, sans-serif; }}
  .leaflet-top.leaflet-right {{ top: 12px; right: 12px; }}
  .leaflet-control-zoom {{ border: 1px solid rgba(19,41,75,.20) !important; box-shadow: 0 6px 20px rgba(15,23,42,.22) !important; }}
  .leaflet-control-zoom a {{
    width: 38px !important; height: 38px !important; line-height: 36px !important;
    color: #13294b !important; background: rgba(255,255,255,.97) !important;
    font-size: 24px !important; font-weight: 700 !important;
  }}
  .leaflet-control-zoom a:hover {{ background: #eef4fb !important; color: #0b63ce !important; }}
  #status {{
    position: absolute; bottom: 10px; left: 10px; z-index: 1000;
    background: white; padding: 6px 10px; border-radius: 6px;
    font-family: Tahoma, sans-serif; direction: rtl; font-size: 12px; color: #888;
  }}
  #zone-panel {{
    position:absolute; top:12px; left:12px; z-index:1000; width:250px; max-height:calc(100% - 70px);
    display:flex; flex-direction:column; overflow:hidden; direction:rtl;
    background:rgba(255,255,255,.96); border:1px solid rgba(19,41,75,.12); border-radius:16px;
    box-shadow:0 10px 30px rgba(15,23,42,.22); font-family:Tahoma,sans-serif;
    backdrop-filter:blur(8px);
  }}
  .zone-panel-head {{ padding:12px 13px 9px; border-bottom:1px solid #e8edf3; }}
  .zone-panel-title {{ display:flex; align-items:center; justify-content:space-between; font-size:14px; font-weight:700; color:#13294b; }}
  .zone-count {{ padding:2px 7px; border-radius:999px; background:#eef3f8; color:#64748b; font-size:10px; }}
  #zone-search {{
    width:100%; box-sizing:border-box; margin-top:9px; padding:8px 10px; border:1px solid #d9e1ea;
    border-radius:10px; outline:none; direction:rtl; font-family:Tahoma,sans-serif; font-size:11px;
  }}
  #zone-search:focus {{ border-color:#7f96ad; box-shadow:0 0 0 3px rgba(19,41,75,.08); }}
  #legend-items {{ padding:7px; overflow:auto; }}
  .zone-list-item {{
    width:100%; display:flex; align-items:center; gap:8px; padding:8px 9px; margin:2px 0;
    border:0; border-radius:10px; background:transparent; cursor:pointer; direction:rtl; text-align:right;
    font-family:Tahoma,sans-serif; color:#26364a; transition:background .15s ease, transform .15s ease;
  }}
  .zone-list-item:hover {{ background:#f2f6fa; transform:translateX(-2px); }}
  .zone-list-item.active {{ background:#e9f0f7; color:#13294b; font-weight:700; }}
  .legend-swatch {{ width:11px; height:28px; flex:0 0 11px; border-radius:6px; box-shadow:inset 0 0 0 1px rgba(0,0,0,.08); }}
  .zone-list-name {{ flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }}
  .zone-list-arrow {{ color:#94a3b8; font-size:12px; }}
  .zone-panel-foot {{ display:flex; gap:6px; padding:8px; border-top:1px solid #e8edf3; }}
  .zone-panel-foot button {{
    flex:1; padding:7px; border:0; border-radius:9px; background:#13294b; color:white; cursor:pointer;
    font-family:Tahoma,sans-serif; font-size:10px;
  }}
  .zone-empty {{ padding:16px 10px; text-align:center; color:#94a3b8; font-size:11px; }}
  .zone-label-icon {{ background:transparent !important; border:0 !important; }}
  .zone-label-card {{
    --zone-color:#163a63; direction:rtl; display:flex; align-items:center; gap:8px;
    min-width:122px; max-width:220px; padding:7px 10px; border-radius:12px; cursor:pointer;
    background:rgba(255,255,255,.94); color:#172033; border:1px solid rgba(19,41,75,.15);
    border-right:4px solid var(--zone-color); box-shadow:0 4px 16px rgba(15,23,42,.20);
    font-family:Tahoma,sans-serif; white-space:nowrap; transform:translate(-50%,-50%);
    transition:opacity .18s ease, transform .18s ease, box-shadow .18s ease; backdrop-filter:blur(6px);
  }}
  .zone-label-card:hover, .zone-label-card.active {{
    transform:translate(-50%,-50%) scale(1.04); box-shadow:0 8px 24px rgba(15,23,42,.28);
  }}
  .zone-label-card.active {{ border-color:var(--zone-color); }}
  .zone-label-pin {{
    width:25px; height:25px; flex:0 0 25px; border-radius:8px; display:flex; align-items:center;
    justify-content:center; color:white; background:var(--zone-color); font-size:13px; font-weight:bold;
  }}
  .zone-label-text {{ overflow:hidden; text-overflow:ellipsis; font-weight:700; font-size:12px; }}
  .zone-label-caption {{ display:block; color:#64748b; font-size:9px; font-weight:400; margin-bottom:1px; }}
  .zone-label-card.is-compact {{ min-width:0; padding:5px 8px; border-radius:10px; }}
  .zone-label-card.is-compact .zone-label-pin, .zone-label-card.is-compact .zone-label-caption {{ display:none; }}
  .zone-label-card.is-hidden {{ opacity:0; pointer-events:none; }}
  @media (max-width:760px) {{ #zone-panel {{ width:210px; }} }}
  .mosque-div-icon, .place-type-icon {{
    background:#0b7a45; color:white; border:2px solid white; border-radius:50%;
    width:28px !important; height:28px !important; line-height:24px; text-align:center;
    font-size:16px; box-shadow:0 1px 5px rgba(0,0,0,.45);
  }}
  .place-type-icon {{ background:#163a63; }}
</style>
</head>
<body>
<div id="map"></div>
<div id="zone-panel">
  <div class="zone-panel-head">
    <div class="zone-panel-title"><span>بلوک‌های شهر</span><span id="zone-count" class="zone-count">۰</span></div>
    <input id="zone-search" type="text" placeholder="جست‌وجوی نام بلوک..." autocomplete="off" />
  </div>
  <div id="legend-items"></div>
  <div class="zone-panel-foot"><button type="button" onclick="showAllZones()">نمایش همه بلوک‌ها</button></div>
</div>
<div id="status">{status_text}</div>
{js_script}
<script>
{map_init_js}
  map.scrollWheelZoom.enable();
  map.doubleClickZoom.enable();
  map.boxZoom.enable();
  map.keyboard.enable();
  if (map.touchZoom) map.touchZoom.enable();
  var mapElement = map.getContainer();
  mapElement.setAttribute('tabindex', '0');
  mapElement.addEventListener('mousedown', function() {{ mapElement.focus(); }});
  mapElement.addEventListener('wheel', function(event) {{ event.stopPropagation(); }}, {{passive:true}});
  var boundary = {boundary_json};
  if (boundary.length > 1) {{
    L.polygon(boundary, {{color: '#333', weight: 2, dashArray: '6,4', fillOpacity: 0}}).addTo(map);
  }}

  function escHtml(value) {{
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }}
  function toFaDigits(value) {{
    return String(value).replace(/\\d/g, function(d) {{ return '۰۱۲۳۴۵۶۷۸۹'[Number(d)]; }});
  }}

  var zones = {zones_json};
  var zoneLayers = [];
  var activeZoneIndex = null;
  var allZonesGroup = L.featureGroup().addTo(map);

  function zonePopup(z) {{
    var area = Number(z.area_m2 || 0) / 10000;
    return '<div style="direction:rtl;font-family:Tahoma,sans-serif;min-width:190px">' +
      '<div style="font-size:15px;font-weight:700;color:#13294b;margin-bottom:7px">' + escHtml(z.name) + '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:5px 8px;font-size:11px;color:#475569">' +
      '<span>وضعیت</span><b>' + escHtml(z.status || 'ناقص') + '</b>' +
      '<span>مساحت</span><b>' + area.toFixed(2) + ' هکتار</b>' +
      '<span>خیابان‌ها</span><b>' + toFaDigits(z.streets.length) + '</b>' +
      '<span>اماکن</span><b>' + toFaDigits(z.places.length) + '</b>' +
      '<span>مساجد</span><b>' + toFaDigits(z.mosques.length) + '</b>' +
      '</div></div>';
  }}

  zones.forEach(function(z, index) {{
    var poly = null;
    var label = null;
    if (z.points && z.points.length > 1) {{
      poly = L.polygon(z.points, {{
        color:z.color, weight:2, fillColor:z.color, fillOpacity:.18
      }}).addTo(allZonesGroup);
      poly.bindPopup(zonePopup(z), {{maxWidth:280}});

      var labelHtml =
        '<div class="zone-label-card" data-zone-index="' + index + '" style="--zone-color:' + escHtml(z.color || '#163a63') + '">' +
          '<span class="zone-label-pin">⌖</span>' +
          '<span class="zone-label-text"><span class="zone-label-caption">بلوک</span>' + escHtml(z.name) + '</span>' +
        '</div>';
      label = L.marker(poly.getCenter(), {{
        icon:L.divIcon({{className:'zone-label-icon',html:labelHtml,iconSize:[1,1],iconAnchor:[0,0]}}),
        keyboard:false, zIndexOffset:800
      }}).addTo(map);

      poly.on('click', function() {{ selectZone(index, false); }});
      poly.on('mouseover', function() {{ if (activeZoneIndex !== index) poly.setStyle({{weight:4,fillOpacity:.28}}); }});
      poly.on('mouseout', function() {{ if (activeZoneIndex !== index) poly.setStyle({{weight:2,fillOpacity:.18}}); }});
      label.on('click', function() {{ selectZone(index, false); }});
    }}

    z.streets.forEach(function(street) {{
      if (street.geom && street.geom.length > 1) {{
        var line = L.polyline(street.geom, {{color:z.color,weight:3,opacity:.72}}).addTo(map);
        line.bindPopup('<div style="direction:rtl;font-family:Tahoma,sans-serif"><b>' + escHtml(street.name) + '</b><br>نوع: ' + escHtml(street.type) + '<br>بلوک: ' + escHtml(z.name) + '</div>');
      }}
    }});
    z.places.forEach(function(p) {{
      if (p.lat != null && p.lon != null) {{
        var icon = L.divIcon({{className:'place-type-icon',html:p.icon || '📍',iconSize:[28,28],iconAnchor:[14,14]}});
        var managerText = p.managerLabel ? '<br>' + escHtml(p.managerRole) + ': ' + escHtml(p.managerLabel) : '';
        var mobileText = p.managerMobile ? '<br>تلفن: ' + escHtml(p.managerMobile) : '';
        L.marker([p.lat,p.lon], {{icon:icon}}).addTo(map)
          .bindPopup('<div style="direction:rtl;font-family:Tahoma,sans-serif"><b>' + escHtml(p.icon || '📍') + ' ' + escHtml(p.name) + '</b><br>' + escHtml(p.subtype) + managerText + mobileText + '<br>بلوک: ' + escHtml(z.name) + '</div>');
      }}
    }});
    zoneLayers.push({{zone:z,polygon:poly,label:label}});
  }});

  function updateZoneLabels() {{
    var zoom = map.getZoom();
    zoneLayers.forEach(function(item) {{
      if (!item.label) return;
      var el = item.label.getElement();
      if (!el) return;
      var card = el.querySelector('.zone-label-card');
      if (!card) return;
      card.classList.toggle('is-hidden', zoom < 13);
      card.classList.toggle('is-compact', zoom === 13);
    }});
  }}

  function renderZoneList(filterText) {{
    var list = document.getElementById('legend-items');
    list.innerHTML = '';
    var query = String(filterText || '').trim().toLowerCase();
    var visibleCount = 0;
    zones.forEach(function(z,index) {{
      if (query && String(z.name || '').toLowerCase().indexOf(query) === -1) return;
      visibleCount += 1;
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'zone-list-item' + (activeZoneIndex === index ? ' active' : '');
      button.setAttribute('data-zone-index', index);
      button.innerHTML = '<span class="legend-swatch" style="background:' + escHtml(z.color) + '"></span>' +
        '<span class="zone-list-name">' + escHtml(z.name) + '</span><span class="zone-list-arrow">‹</span>';
      button.onclick = function() {{ selectZone(index, true); }};
      list.appendChild(button);
    }});
    if (!visibleCount) list.innerHTML = '<div class="zone-empty">بلوک مطابق جست‌وجو پیدا نشد</div>';
    document.getElementById('zone-count').textContent = toFaDigits(visibleCount);
  }}

  function selectZone(index, fit) {{
    activeZoneIndex = index;
    zoneLayers.forEach(function(item,i) {{
      if (item.polygon) item.polygon.setStyle({{
        weight:i === index ? 5 : 2,
        fillOpacity:i === index ? .34 : .07,
        opacity:i === index ? 1 : .45
      }});
      if (item.label && item.label.getElement()) {{
        var card = item.label.getElement().querySelector('.zone-label-card');
        if (card) card.classList.toggle('active', i === index);
      }}
    }});
    var selected = zoneLayers[index];
    if (selected && selected.polygon) {{
      if (fit) map.fitBounds(selected.polygon.getBounds(), {{padding:[70,70],maxZoom:16}});
      selected.polygon.openPopup();
    }}
    renderZoneList(document.getElementById('zone-search').value);
  }}

  function showAllZones() {{
    activeZoneIndex = null;
    zoneLayers.forEach(function(item) {{
      if (item.polygon) item.polygon.setStyle({{weight:2,fillOpacity:.18,opacity:1}});
      if (item.label && item.label.getElement()) {{
        var card = item.label.getElement().querySelector('.zone-label-card');
        if (card) card.classList.remove('active');
      }}
    }});
    if (allZonesGroup.getLayers().length) map.fitBounds(allZonesGroup.getBounds(), {{padding:[35,35],maxZoom:15}});
    map.closePopup();
    renderZoneList(document.getElementById('zone-search').value);
  }}

  document.getElementById('zone-search').addEventListener('input', function() {{ renderZoneList(this.value); }});
  map.on('zoomend', updateZoneLabels);
  map.whenReady(function() {{
    renderZoneList('');
    updateZoneLabels();
    if (allZonesGroup.getLayers().length) map.fitBounds(allZonesGroup.getBounds(), {{padding:[35,35],maxZoom:15}});
  }});
  // هر مسجد فقط یک بار روی نقشه نمایش داده می‌شود؛ نام بلوک‌های مرتبط در پنجره آن آمده است.
  var mosques = {mosques_json};
  var mosqueIcon = L.divIcon({{className:'mosque-div-icon', html:'🕌', iconSize:[28,28], iconAnchor:[14,14]}});
  mosques.forEach(function(m) {{
    if (m.lat != null && m.lon != null) {{
      var zoneText = (m.zones && m.zones.length) ? m.zones.join('، ') : 'هنوز داخل بلوکی ثبت نشده';
      var imamText = m.imamLabel ? '<br>امام جماعت: ' + m.imamLabel : '';
      var imamMobileText = m.imamMobile ? '<br>تلفن: ' + m.imamMobile : '';
      L.marker([m.lat,m.lon], {{icon:mosqueIcon}}).addTo(map)
       .bindPopup('<b>🕌 ' + m.name + '</b>' + imamText + imamMobileText + '<br>بلوک: ' + zoneText + '<br>مختصات: ' + Number(m.lat).toFixed(6) + '، ' + Number(m.lon).toFixed(6));
    }}
  }});

  var schools = {schools_json};
  var schoolIcon = L.divIcon({{className:'mosque-div-icon', html:'🏫', iconSize:[28,28], iconAnchor:[14,14]}});
  schools.forEach(function(s) {{
    if (s.lat != null && s.lon != null) {{
      var managerText = s.managerLabel ? '<br>مدیر مدرسه: ' + s.managerLabel : '';
      var managerMobileText = s.managerMobile ? '<br>تلفن: ' + s.managerMobile : '';
      L.marker([s.lat, s.lon], {{icon:schoolIcon}}).addTo(map)
       .bindPopup('<b>🏫 ' + s.name + '</b>' + managerText + managerMobileText + '<br>مختصات: ' + Number(s.lat).toFixed(6) + '، ' + Number(s.lon).toFixed(6));
    }}
  }});

  var healthCenters = {health_centers_json};
  var healthIcon = L.divIcon({{className:'mosque-div-icon', html:'🏥', iconSize:[28,28], iconAnchor:[14,14]}});
  healthCenters.forEach(function(h) {{
    if (h.lat != null && h.lon != null) {{
      var managerText = h.managerLabel ? '<br>مسؤول مرکز بهداشتی: ' + h.managerLabel : '';
      var managerMobileText = h.managerMobile ? '<br>تلفن: ' + h.managerMobile : '';
      L.marker([h.lat, h.lon], {{icon:healthIcon}}).addTo(map)
       .bindPopup('<b>🏥 ' + h.name + '</b>' + managerText + managerMobileText + '<br>مختصات: ' + Number(h.lat).toFixed(6) + '، ' + Number(h.lon).toFixed(6));
    }}
  }});

</script>
</body>
</html>
"""
    return html


def build_place_editor_html(zone, places, offline=False):
    """
    نمایش نقشه یک منطقه با اماکن موجود، به‌همراه قابلیت کلیک روی نقشه برای
    انتخاب مختصات یک مکان جدید (مسجد/مدرسه/... که در OSM ثبت نشده و باید
    به‌صورت دستی اضافه شود).

    zone: {"name", "color", "boundary_points"}
    places: [{"id", "name", "subtype", "lat", "lon"}, ...] — اماکن موجود (فقط نمایشی)
    """
    tile_base = get_tile_server_base_url()
    places = places or []
    boundary_points = zone.get("boundary_points", [])

    if boundary_points:
        lats = [p[0] for p in boundary_points]
        lons = [p[1] for p in boundary_points]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        center_lat, center_lon = JAVANROOD_CENTER

    boundary_json = json.dumps(boundary_points)
    zone_color = zone.get("color", "#13294b")
    places_json = json.dumps([_place_map_item(place) for place in places], ensure_ascii=False)

    if offline:
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 15);
  L.tileLayer('{tile_base}/tile/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (offline)',
      errorTileUrl: ''
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{tile_base}/vendor/leaflet.css" />'
        js_script = f'<script src="{tile_base}/vendor/leaflet.js"></script>'
    else:
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 15);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />'
        js_script = f'<script src="{NESHAN_LEAFLET_JS}"></script>'

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>افزودن مکان جدید</title>
{css_link}
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .leaflet-popup-content {{ direction: rtl; font-family: Tahoma, sans-serif; }}
  .place-type-icon {{
    background:#163a63; color:white; border:2px solid white; border-radius:50%;
    width:28px !important; height:28px !important; line-height:24px; text-align:center;
    font-size:16px; box-shadow:0 1px 5px rgba(0,0,0,.45);
  }}
  #toolbar {{
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: white; padding: 8px 12px; border-radius: 8px;
    font-family: Tahoma, sans-serif; direction: rtl; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    font-size: 13px;
  }}
</style>
</head>
<body>
<div id="toolbar">برای افزودن مکان جدید، روی نقطه مورد نظر روی نقشه کلیک کنید.</div>
<div id="map"></div>
{js_script}
<script>
{map_init_js}
  var boundary = {boundary_json};
  if (boundary.length > 1) {{
    L.polygon(boundary, {{color: '{zone_color}', weight: 2, fillColor: '{zone_color}', fillOpacity: 0.12}}).addTo(map);
    map.fitBounds(L.polygon(boundary).getBounds(), {{padding: [20, 20]}});
  }}

  // نمایش اماکن موجود با آیکون اختصاصی (فقط جهت مرجع، غیرقابل انتخاب)
  var places = {places_json};
  places.forEach(function(p) {{
    if (p.lat != null && p.lon != null) {{
      var icon = L.divIcon({{className:'place-type-icon', html:p.icon || '📍', iconSize:[28,28], iconAnchor:[14,14]}});
      var managerText = p.managerLabel ? '<br>' + p.managerRole + ': ' + p.managerLabel : '';
      var mobileText = p.managerMobile ? '<br>تلفن: ' + p.managerMobile : '';
      L.marker([p.lat, p.lon], {{icon:icon}}).addTo(map)
        .bindPopup('<b>' + (p.icon || '📍') + ' ' + p.name + '</b><br>' + p.subtype + managerText + mobileText);
    }}
  }});

  var newMarker = null;

  map.on('click', function(e) {{
    if (newMarker) {{ map.removeLayer(newMarker); }}
    newMarker = L.marker([e.latlng.lat, e.latlng.lng], {{
        icon: L.divIcon({{className: '', html: '<div style="background:#c9a227;width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>', iconSize: [16,16]}})
    }}).addTo(map);
    document.title = "NEW_PLACE_COORDS:" + e.latlng.lat + "," + e.latlng.lng;
  }});
</script>
</body>
</html>
"""
    return html


def build_zone_meeting_map_html(
    zone, places, selected_place_id=None, offline=False, mosques=None,
    schools=None, health_centers=None,
    selected_source_type=None, selected_source_id=None, allow_selection=True,
):
    """نقشه بلوک برای نمایش/انتخاب محل جلسه از میان اماکن OSM، مساجد مرجع،
    مدارس و مراکز بهداشتی ثبت‌شده."""
    tile_base = get_tile_server_base_url()
    places = places or []
    mosques = mosques or []
    schools = schools or []
    health_centers = health_centers or []
    boundary_points = zone.get("boundary_points", [])

    if boundary_points:
        lats = [p[0] for p in boundary_points]
        lons = [p[1] for p in boundary_points]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        center_lat, center_lon = JAVANROOD_CENTER

    if selected_source_type is None and selected_place_id is not None:
        selected_source_type = "place"
        selected_source_id = str(selected_place_id)
    selected_source_type = selected_source_type or None
    selected_source_id = str(selected_source_id) if selected_source_id is not None else None

    boundary_json = json.dumps(boundary_points)
    zone_color = zone.get("color", "#13294b")
    points = []
    for place in places:
        item = _place_map_item(place)
        item.update({"sourceType": "place", "sourceId": str(place.get("id"))})
        item["imamLabel"] = item.pop("managerLabel", "")
        item["imamMobile"] = item.pop("managerMobile", "")
        points.append(item)
    for mosque in mosques:
        points.append({
            "sourceType": "mosque",
            "sourceId": str(mosque.get("id")),
            "name": mosque.get("name") or "مسجد بدون نام",
            "subtype": "مسجد مرجع",
            "lat": mosque.get("lat"),
            "lon": mosque.get("lon"),
            "imamLabel": mosque.get("imam_label") or "",
            "imamMobile": mosque.get("imam_mobile") or "",
            "icon": "🕌", "managerRole": "امام جماعت",
        })
    for school in schools:
        points.append({
            "sourceType": "school",
            "sourceId": str(school.get("id")),
            "name": school.get("name") or "مدرسه بدون نام",
            "subtype": "مدرسه",
            "lat": school.get("lat"),
            "lon": school.get("lon"),
            "imamLabel": school.get("manager_label") or "",
            "imamMobile": school.get("manager_mobile") or "",
            "icon": "🏫", "managerRole": "مدیر مدرسه",
        })
    for hc in health_centers:
        points.append({
            "sourceType": "health_center",
            "sourceId": str(hc.get("id")),
            "name": hc.get("name") or "مرکز بهداشتی بدون نام",
            "subtype": "مرکز بهداشتی",
            "lat": hc.get("lat"),
            "lon": hc.get("lon"),
            "imamLabel": hc.get("manager_label") or "",
            "imamMobile": hc.get("manager_mobile") or "",
            "icon": "🏥", "managerRole": "مسؤول مرکز بهداشتی",
        })
    points_json = json.dumps(points, ensure_ascii=False)
    selected_type_json = json.dumps(selected_source_type, ensure_ascii=False)
    selected_id_json = json.dumps(selected_source_id, ensure_ascii=False)
    allow_selection_js = "true" if allow_selection else "false"

    if offline:
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 15);
  L.tileLayer('{tile_base}/tile/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (offline)',
      errorTileUrl: ''
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{tile_base}/vendor/leaflet.css" />'
        js_script = f'<script src="{tile_base}/vendor/leaflet.js"></script>'
    else:
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 15);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />'
        js_script = f'<script src="{NESHAN_LEAFLET_JS}"></script>'

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>نقشه منطقه — محل جلسات</title>
{css_link}
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .leaflet-popup-content {{ direction: rtl; font-family: Tahoma, sans-serif; }}
  .place-popup button {{
    margin-top: 6px; padding: 4px 10px; cursor: pointer;
    background: #13294b; color: white; border: none; border-radius: 4px;
  }}
  .facility-div-icon {{
    background:#0b7a45; color:white; border:2px solid white; border-radius:50%;
    width:28px !important; height:28px !important; line-height:24px; text-align:center;
    font-size:16px; box-shadow:0 1px 5px rgba(0,0,0,.45);
  }}
  .facility-div-icon.facility-selected {{
    background:#c9a227; width:34px !important; height:34px !important;
    line-height:30px; font-size:19px;
  }}
</style>
</head>
<body>
<div id="map"></div>
{js_script}
<script>
{map_init_js}
  var boundary = {boundary_json};
  if (boundary.length > 1) {{
    var zoneLayer = L.polygon(boundary, {{color: '{zone_color}', weight: 2, fillColor: '{zone_color}', fillOpacity: 0.12}}).addTo(map);
    map.fitBounds(zoneLayer.getBounds(), {{padding: [20, 20]}});
  }}

  var selectedType = {selected_type_json};
  var selectedId = {selected_id_json};
  var allowSelection = {allow_selection_js};
  var points = {points_json};

  function esc(value) {{
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }}

  points.forEach(function(p) {{
    if (p.lat == null || p.lon == null) return;
    var isSelected = (p.sourceType === selectedType && String(p.sourceId) === String(selectedId));
    var marker;
    if (p.icon) {{
      var size = isSelected ? 34 : 28;
      var divIcon = L.divIcon({{
        className: 'facility-div-icon' + (isSelected ? ' facility-selected' : ''),
        html: p.icon, iconSize: [size, size], iconAnchor: [size/2, size/2]
      }});
      marker = L.marker([p.lat, p.lon], {{icon: divIcon, zIndexOffset: isSelected ? 1000 : 500}}).addTo(map);
    }} else {{
      var baseColor = '#13294b';
      marker = L.circleMarker([p.lat, p.lon], {{
        radius: isSelected ? 10 : 7,
        color: isSelected ? '#c9a227' : baseColor,
        fillColor: isSelected ? '#c9a227' : baseColor,
        fillOpacity: 0.92,
        weight: isSelected ? 3 : 1
      }}).addTo(map);
    }}

    var popup = "<div class='place-popup'><b>" + esc(p.name) + "</b><br/>" + esc(p.subtype);
    if (p.managerRole && p.imamLabel) {{
      popup += "<br/>" + esc(p.managerRole) + ": " + esc(p.imamLabel);
      if (p.imamMobile) {{ popup += "<br/>تلفن: " + esc(p.imamMobile); }}
    }}
    if (isSelected) {{
      popup += "<br/><i>(محل انتخاب‌شده برای جلسات)</i>";
    }} else if (allowSelection) {{
      popup += "<br/><button onclick=\\\"selectSource('" + esc(p.sourceType) + "','" + esc(p.sourceId) + "')\\\">انتخاب به‌عنوان محل جلسات</button>";
    }}
    popup += "</div>";
    marker.bindPopup(popup);
  }});

  function selectSource(sourceType, sourceId) {{
    document.title = "SELECT_SOURCE:" + sourceType + ":" + encodeURIComponent(sourceId);
  }}
</script>
</body>
</html>
"""
    return html

def build_view_mode_html(boundary_points, streets=None, places=None, mosques=None, offline=False,
                          schools=None, health_centers=None):
    """
    صفحه نمایش نقشه با محدوده، خیابان‌ها و اماکن.
    boundary_points: [(lat, lon), ...]
    streets: [{"name":..., "geometry":[(lat,lon),...], "highway_type":...}, ...]
    places: [{"name":..., "lat":..., "lon":..., "subtype":...}, ...]
    schools/health_centers: [{"id":..., "name":..., "lat":..., "lon":..., "manager_label":..., "manager_mobile":...}, ...]
    offline: اگر True باشد، از تایل‌های محلی OpenStreetMap (دیتابیس) استفاده می‌شود.
             اگر False باشد، از نقشه آنلاین فارسی نشان (Neshan) استفاده می‌شود.
    """
    tile_base = get_tile_server_base_url()
    streets = streets or []
    places = places or []
    mosques = mosques or []
    schools = schools or []
    health_centers = health_centers or []

    if boundary_points:
        lats = [p[0] for p in boundary_points]
        lons = [p[1] for p in boundary_points]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        center_lat, center_lon = JAVANROOD_CENTER

    boundary_json = json.dumps(boundary_points)
    streets_json = json.dumps([
        {"name": s.get("name") or "بدون نام", "type": s.get("highway_type", ""), "geom": s.get("geometry", [])}
        for s in streets
    ], ensure_ascii=False)
    places_json = json.dumps([_place_map_item(place) for place in places], ensure_ascii=False)
    mosques_json = json.dumps([
        {"id": m.get("id"), "name": m.get("name"), "lat": m.get("lat"), "lon": m.get("lon"),
         "aliases": m.get("aliases", []), "zones": m.get("zones", []),
         "imamLabel": m.get("imam_label") or "", "imamMobile": m.get("imam_mobile") or ""}
        for m in mosques
    ], ensure_ascii=False)
    schools_json = json.dumps([
        {"id": s.get("id"), "name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"),
         "managerLabel": s.get("manager_label") or "", "managerMobile": s.get("manager_mobile") or ""}
        for s in schools
    ], ensure_ascii=False)
    health_centers_json = json.dumps([
        {"id": h.get("id"), "name": h.get("name"), "lat": h.get("lat"), "lon": h.get("lon"),
         "managerLabel": h.get("manager_label") or "", "managerMobile": h.get("manager_mobile") or ""}
        for h in health_centers
    ], ensure_ascii=False)

    if offline:
        # حالت آفلاین واقعی: بدون هیچ درخواست شبکه؛ نمایش مرزها، معابر و اماکن ذخیره‌شده.
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 14);
  L.tileLayer('{tile_base}/tile/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors (offline)',
      errorTileUrl: ''
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{tile_base}/vendor/leaflet.css" />'
        js_script = f'<script src="{tile_base}/vendor/leaflet.js"></script>'
        status_text = "نقشه: آفلاین داخلی (بدون اتصال اینترنت)"
    else:
        # حالت آنلاین: نقشه فارسی نشان
        map_init_js = f"""
  var map = L.map('map').setView([{center_lat}, {center_lon}], 14);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
"""
        css_link = f'<link rel="stylesheet" href="{NESHAN_LEAFLET_CSS}" />'
        js_script = f'<script src="{NESHAN_LEAFLET_JS}"></script>'
        status_text = "نقشه: آنلاین (نشان)"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>نقشه جوانرود</title>
{css_link}
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  .leaflet-popup-content {{ direction: rtl; font-family: Tahoma, sans-serif; }}
  .mosque-div-icon, .place-type-icon {{
    background:#0b7a45; color:white; border:2px solid white; border-radius:50%;
    width:30px !important; height:30px !important; line-height:26px; text-align:center;
    font-size:17px; box-shadow:0 1px 6px rgba(0,0,0,.5);
  }}
  .place-type-icon {{ background:#163a63; }}
  #status {{
    position: absolute; bottom: 10px; left: 10px; z-index: 1000;
    background: white; padding: 6px 10px; border-radius: 6px;
    font-family: Tahoma, sans-serif; direction: rtl; font-size: 12px; color: #888;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div id="status">{status_text}</div>
{js_script}
<script>
{map_init_js}
  var boundary = {boundary_json};
  if (boundary.length > 1) {{
    L.polygon(boundary, {{color: 'red', fillOpacity: 0.05}}).addTo(map);
  }}

  var streets = {streets_json};
  streets.forEach(function(s) {{
    if (s.geom && s.geom.length > 1) {{
      var line = L.polyline(s.geom, {{color: '#1f78b4', weight: 3}}).addTo(map);
      line.bindPopup("<b>" + s.name + "</b><br/>نوع: " + s.type);
    }}
  }});

  var places = {places_json};
  places.forEach(function(p) {{
    if (p.lat != null && p.lon != null) {{
      var icon = L.divIcon({{className:'place-type-icon', html:p.icon || '📍', iconSize:[30,30], iconAnchor:[15,15]}});
      var managerText = p.managerLabel ? '<br>' + p.managerRole + ': ' + p.managerLabel : '';
      var mobileText = p.managerMobile ? '<br>تلفن: ' + p.managerMobile : '';
      L.marker([p.lat, p.lon], {{icon:icon, zIndexOffset:900}}).addTo(map)
        .bindPopup('<b>' + (p.icon || '📍') + ' ' + p.name + '</b><br>' + p.subtype + managerText + mobileText);
    }}
  }});

  var mosqueMarkerById = {{}};
  var mosques = {mosques_json};
  var mosqueIcon = L.divIcon({{className:'mosque-div-icon', html:'🕌', iconSize:[30,30], iconAnchor:[15,15]}});
  mosques.forEach(function(m) {{
    if (m.lat != null && m.lon != null) {{
      var zoneText = (m.zones && m.zones.length) ? m.zones.join('، ') : '—';
      var aliasesText = (m.aliases && m.aliases.length) ? '<br>نام قبلی: ' + m.aliases.join('، ') : '';
      var imamText = m.imamLabel ? '<br>امام جماعت: ' + m.imamLabel : '';
      var imamMobileText = m.imamMobile ? '<br>تلفن: ' + m.imamMobile : '';
      var marker = L.marker([m.lat, m.lon], {{icon:mosqueIcon, zIndexOffset:1000}}).addTo(map);
      marker.bindPopup('<b>🕌 ' + m.name + '</b>' + aliasesText + imamText + imamMobileText + '<br>بلوک: ' + zoneText + '<br>عرض: ' + Number(m.lat).toFixed(6) + '<br>طول: ' + Number(m.lon).toFixed(6));
      mosqueMarkerById[m.id] = marker;
    }}
  }});

  var schools = {schools_json};
  var schoolIcon = L.divIcon({{className:'mosque-div-icon', html:'🏫', iconSize:[30,30], iconAnchor:[15,15]}});
  schools.forEach(function(s) {{
    if (s.lat != null && s.lon != null) {{
      var managerText = s.managerLabel ? '<br>مدیر مدرسه: ' + s.managerLabel : '';
      var managerMobileText = s.managerMobile ? '<br>تلفن: ' + s.managerMobile : '';
      L.marker([s.lat, s.lon], {{icon:schoolIcon, zIndexOffset:1000}}).addTo(map)
        .bindPopup('<b>🏫 ' + s.name + '</b>' + managerText + managerMobileText + '<br>عرض: ' + Number(s.lat).toFixed(6) + '<br>طول: ' + Number(s.lon).toFixed(6));
    }}
  }});

  var healthCenters = {health_centers_json};
  var healthIcon = L.divIcon({{className:'mosque-div-icon', html:'🏥', iconSize:[30,30], iconAnchor:[15,15]}});
  healthCenters.forEach(function(h) {{
    if (h.lat != null && h.lon != null) {{
      var managerText = h.managerLabel ? '<br>مسؤول مرکز بهداشتی: ' + h.managerLabel : '';
      var managerMobileText = h.managerMobile ? '<br>تلفن: ' + h.managerMobile : '';
      L.marker([h.lat, h.lon], {{icon:healthIcon, zIndexOffset:1000}}).addTo(map)
        .bindPopup('<b>🏥 ' + h.name + '</b>' + managerText + managerMobileText + '<br>عرض: ' + Number(h.lat).toFixed(6) + '<br>طول: ' + Number(h.lon).toFixed(6));
    }}
  }});

  function focusMosque(id) {{
    var marker = mosqueMarkerById[id];
    if (marker) {{ map.setView(marker.getLatLng(), 17); marker.openPopup(); }}
  }}
</script>
</body>
</html>
"""
    return html
