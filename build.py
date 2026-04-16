#!/usr/bin/env python3
"""
Airport Code Site Generator
Reads airports_refined.csv and generates a full static site.
"""

import csv
import json
import math
import os
import re
import time

CSV_PATH = '/Users/simon/Desktop/airports_refined.csv'
RUNWAY_CSV = '/Users/simon/Desktop/runways.csv'
FREQ_CSV = '/Users/simon/Desktop/frequencies.csv'
OUT_DIR = '/Users/simon/airport-site'

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def flag_emoji(cc):
    if not cc or len(cc) != 2:
        return ''
    cc = cc.upper()
    return chr(0x1F1E6 + ord(cc[0]) - ord('A')) + chr(0x1F1E6 + ord(cc[1]) - ord('A'))

def type_label(t):
    return {'large_airport': 'Large Airport', 'medium_airport': 'Medium Airport', 'small_airport': 'Small Airport'}.get(t, t.replace('_', ' ').title())

def type_badge_class(t):
    return {'large_airport': 'badge-large', 'medium_airport': 'badge-medium', 'small_airport': 'badge-small'}.get(t, 'badge-small')

def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def fmt_coord(val, pos_label, neg_label):
    v = float(val)
    label = pos_label if v >= 0 else neg_label
    return f"{abs(v):.4f}°{label}"

def fmt_elevation(elev):
    if not elev:
        return 'N/A'
    try:
        ft = int(elev)
        m = round(ft * 0.3048)
        return f"{ft:,} ft ({m:,} m)"
    except:
        return elev

# ─── Country name fixes (source data has some names in Indonesian) ────────────
COUNTRY_NAME_MAP = {
    'A.S': 'United States',
    'Afrika Selatan': 'South Africa',
    'Antartika': 'Antarctica',
    'Antigua dan Barbuda': 'Antigua and Barbuda',
    'Arab Saudi': 'Saudi Arabia',
    'Belanda': 'Netherlands',
    'Bosnia dan Herzegovina': 'Bosnia and Herzegovina',
    'Emiriah Arab Bersatu': 'United Arab Emirates',
    'Filipina': 'Philippines',
    'Guiana Perancis': 'French Guiana',
    'Jerman': 'Germany',
    'Kepulauan Cayman': 'Cayman Islands',
    'Kepulauan Cocos (Keeling)': 'Cocos (Keeling) Islands',
    'Kepulauan Cook': 'Cook Islands',
    'Kepulauan Falkland': 'Falkland Islands',
    'Kepulauan Faroe': 'Faroe Islands',
    'Kepulauan Mariana Utara': 'Northern Mariana Islands',
    'Kepulauan Marshall': 'Marshall Islands',
    'Kepulauan Solomon': 'Solomon Islands',
    'Kepulauan Terpencil A.S.': 'U.S. Minor Outlying Islands',
    'Kepulauan Turks dan Caicos': 'Turks and Caicos Islands',
    'Kepulauan Virgin A.S': 'US Virgin Islands',
    'Kepulauan Virgin A.S.': 'US Virgin Islands',
    'Kepulauan Virgin British': 'British Virgin Islands',
    'Korea Selatan': 'South Korea',
    'Korea Utara': 'North Korea',
    'Macedonia Utara': 'North Macedonia',
    'Mesir': 'Egypt',
    'Perancis': 'France',
    'Pulau Krismas': 'Christmas Island',
    'Pulau Norfolk': 'Norfolk Island',
    'Republik Afrika Tengah': 'Central African Republic',
    'Republik Dominica': 'Dominican Republic',
    'Rusia': 'Russia',
    'Sahara Barat': 'Western Sahara',
    'Saint Kitts dan Nevis': 'Saint Kitts and Nevis',
    'Saint Pierre dan Miquelon': 'Saint Pierre and Miquelon',
    'Saint Vincent dan Grenadines': 'Saint Vincent and the Grenadines',
    'Samoa Amerika': 'American Samoa',
    'Sao Tome dan Principe': 'Sao Tome and Principe',
    'Sepanyol': 'Spain',
    'Singapura': 'Singapore',
    'Sudan Selatan': 'South Sudan',
    'Surinam': 'Suriname',
    'Trinidad dan Tobago': 'Trinidad and Tobago',
    'Wallis dan Futuna': 'Wallis and Futuna',
    'Wilayah Lautan Hindi British': 'British Indian Ocean Territory',
    'Yaman': 'Yemen',
}

# ─── Load airports ───────────────────────────────────────────────────────────

print("Loading airports...")
airports = []
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lat = float(row['latitude'])
            lon = float(row['longitude'])
        except:
            continue
        airports.append({
            'iata': row['iata_code'].strip().upper(),
            'icao': row['icao_code'].strip().upper(),
            'name': re.sub(r'^\(Duplicate\)', '', row['name'].strip()).strip(),
            'city': row['city'].strip(),
            'country_code': row['country_code'].strip().upper(),
            'country_name': COUNTRY_NAME_MAP.get(row['country_name'].strip(), row['country_name'].strip()),
            'region': row['region'].strip(),
            'type': row['type'].strip(),
            'lat': lat,
            'lon': lon,
            'elevation': row['elevation_ft'].strip(),
            'wikipedia': row['wikipedia'].strip(),
        })

print(f"  Loaded {len(airports)} airports")

# ─── Load runways ─────────────────────────────────────────────────────────────

print("Loading runways...")
runways_by_icao = {}
with open(RUNWAY_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        icao = row['airport_ident'].strip().upper()
        if row.get('closed', '0') == '1':
            continue
        try:
            length = int(row['length_ft']) if row['length_ft'] else 0
        except:
            length = 0
        le = row['le_ident'].strip()
        he = row['he_ident'].strip()
        name = f"{le}/{he}" if le and he else (le or he or 'Runway')
        surface = row['surface'].strip().split('-')[0].title() if row['surface'] else 'Unknown'
        width = row['width_ft'].strip()
        runways_by_icao.setdefault(icao, []).append({
            'name': name,
            'length_ft': length,
            'surface': surface,
            'width_ft': width,
        })

# Sort runways by length desc
for icao in runways_by_icao:
    runways_by_icao[icao].sort(key=lambda r: r['length_ft'], reverse=True)

print(f"  Loaded runways for {len(runways_by_icao)} airports")

# ─── Load frequencies ─────────────────────────────────────────────────────────

print("Loading frequencies...")
freqs_by_icao = {}
with open(FREQ_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        icao = row['airport_ident'].strip().upper()
        freqs_by_icao.setdefault(icao, []).append({
            'type': row['type'].strip(),
            'description': row['description'].strip(),
            'mhz': row['frequency_mhz'].strip(),
        })
print(f"  Loaded frequencies for {len(freqs_by_icao)} airports")

# Index by IATA
by_iata = {a['iata']: a for a in airports}

# ─── Pre-compute nearby airports (5 nearest within 600km) ───────────────────

print("Computing nearby airports...")
t0 = time.time()
for i, a in enumerate(airports):
    dists = []
    for j, b in enumerate(airports):
        if i == j:
            continue
        # Quick bounding box check
        if abs(b['lat'] - a['lat']) > 6 or abs(b['lon'] - a['lon']) > 8:
            continue
        d = haversine(a['lat'], a['lon'], b['lat'], b['lon'])
        if d <= 600:
            dists.append((d, b['iata'], b['name'], b['city']))
    dists.sort()
    a['nearby'] = dists[:5]
    if i % 500 == 0:
        print(f"  {i}/{len(airports)} ({time.time()-t0:.0f}s)")

print(f"  Done in {time.time()-t0:.0f}s")

# ─── airports.json for search & carbon calculator ────────────────────────────

print("Writing airports.json...")
airports_json = [
    {'iata': a['iata'], 'name': a['name'], 'city': a['city'], 'country': a['country_name'], 'lat': round(a['lat'], 4), 'lon': round(a['lon'], 4)}
    for a in airports
]
os.makedirs(OUT_DIR, exist_ok=True)
with open(f"{OUT_DIR}/airports.json", 'w') as f:
    json.dump(airports_json, f, separators=(',', ':'))

# ─── Shared CSS & SVG logo ───────────────────────────────────────────────────

NAV_LOGO_SVG = '''<svg width="32" height="32" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="34" height="34" rx="9" fill="#1a56db"/><path d="M24.5 8.5C25.3 9.3 25.3 10.6 24.5 11.4L19.8 16.1L22 25L19.5 27.5L16 19L11.5 23.5L12 26L10 28L8 24L4 22L6 20L8.5 20.5L13 16L5.5 12.5L8 10L17 12.2L21.6 7.5C22.4 6.7 23.7 6.7 24.5 8.5Z" fill="white"/></svg>'''

SHARED_CSS = '''
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --navy: #0f1f3d;
      --blue: #1a56db;
      --blue-light: #e8f0fe;
      --sky: #38bdf8;
      --text: #1e293b;
      --muted: #64748b;
      --border: #e2e8f0;
      --bg: #f8fafc;
      --white: #ffffff;
      --green: #10b981;
    }
    body { font-family: \'Outfit\', sans-serif; background: var(--bg); color: var(--text); font-size: 15px; line-height: 1.6; }
    nav { background: var(--navy); padding: 0 24px; display: flex; align-items: center; justify-content: space-between; height: 60px; position: sticky; top: 0; z-index: 100; }
    .nav-logo { color: #fff; font-size: 22px; font-weight: 800; letter-spacing: -0.3px; text-decoration: none; display: flex; align-items: center; gap: 8px; line-height: 1; }
    .nav-logo svg { flex-shrink: 0; }
    .nav-logo .tld { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.5); letter-spacing: 0; }
    .nav-search { display: flex; align-items: center; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 6px 14px; gap: 8px; width: 280px; position: relative; }
    .nav-search input { background: none; border: none; outline: none; color: #fff; font-size: 14px; width: 100%; font-family: \'Outfit\', sans-serif; }
    .nav-search input::placeholder { color: rgba(255,255,255,0.4); }
    #search-results { position: absolute; top: calc(100% + 6px); left: 0; right: 0; background: #fff; border: 1px solid var(--border); border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); z-index: 200; overflow: hidden; display: none; }
    #search-results a { display: flex; align-items: center; gap: 10px; padding: 10px 14px; text-decoration: none; color: var(--text); font-size: 13px; border-bottom: 1px solid var(--border); transition: background 0.15s; }
    #search-results a:last-child { border-bottom: none; }
    #search-results a:hover { background: var(--bg); }
    #search-results .sr-code { background: var(--blue-light); color: var(--blue); font-weight: 700; font-size: 12px; padding: 2px 7px; border-radius: 5px; min-width: 38px; text-align: center; }
    #search-results .sr-name { font-weight: 600; }
    #search-results .sr-city { color: var(--muted); font-size: 11px; }
    .nav-links { display: flex; gap: 24px; }
    .nav-links a { color: rgba(255,255,255,0.7); text-decoration: none; font-size: 13px; font-weight: 500; transition: color 0.2s; }
    .nav-links a:hover { color: #fff; }
    .hero { background: linear-gradient(135deg, var(--navy) 0%, #1a3a6b 100%); color: #fff; padding: 48px 0 56px; position: relative; overflow: hidden; }
    .hero::before { content: \'✈\'; position: absolute; right: -20px; top: -20px; font-size: 220px; opacity: 0.04; transform: rotate(25deg); }
    .hero-inner { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
    .breadcrumb { font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 20px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .breadcrumb a { color: rgba(255,255,255,0.5); text-decoration: none; }
    .breadcrumb a:hover { color: rgba(255,255,255,0.8); }
    .breadcrumb span.sep { color: rgba(255,255,255,0.3); }
    .hero-top { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 24px; }
    .hero-title { display: flex; align-items: flex-start; gap: 24px; }
    .iata-badge { background: var(--blue); border: 2px solid rgba(255,255,255,0.2); border-radius: 12px; padding: 14px 20px; text-align: center; min-width: 100px; flex-shrink: 0; }
    .iata-badge .code { font-size: 40px; font-weight: 800; letter-spacing: 2px; color: #fff; line-height: 1; }
    .iata-badge .label { font-size: 10px; color: rgba(255,255,255,0.6); text-transform: uppercase; letter-spacing: 1px; margin-top: 6px; }
    .hero-name { padding-top: 4px; }
    .hero-name h1 { font-size: 38px; font-weight: 800; line-height: 1.1; color: #fff; }
    .hero-name .location { display: flex; align-items: center; gap: 6px; color: rgba(255,255,255,0.65); font-size: 15px; margin-top: 6px; }
    .hero-badges { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
    .badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; letter-spacing: 0.3px; }
    .badge-large { background: rgba(16,185,129,0.2); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.3); }
    .badge-medium { background: rgba(56,189,248,0.15); color: #7dd3fc; border: 1px solid rgba(56,189,248,0.3); }
    .badge-small { background: rgba(245,158,11,0.15); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }
    .hero-stats { display: flex; gap: 32px; margin-top: 32px; padding-top: 28px; border-top: 1px solid rgba(255,255,255,0.1); flex-wrap: wrap; }
    .hero-stat .value { font-size: 22px; font-weight: 700; color: #fff; }
    .hero-stat .label { font-size: 11px; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 2px; }
    .main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; display: grid; grid-template-columns: 1fr 320px; gap: 24px; }
    @media (max-width: 768px) {
      .main { grid-template-columns: 1fr; }
      .nav-links { display: none; }
      .nav-search { width: 160px; min-width: 0; flex-shrink: 1; }
      .nav-logo { flex-shrink: 0; }
      .hero-home { padding: 48px 16px; }
      .hero-home h1 { font-size: 36px; }
      .search-big { margin: 0 4px; }
      .hero { padding: 16px 0 20px; }
      .hero-top { flex-direction: column; align-items: center; }
      .hero-top > div { width: 100%; }
      .hero-title { flex-direction: column; gap: 12px; align-items: center; }
      .iata-badge { min-width: unset; width: 100%; padding: 12px 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; border-radius: 10px; }
      .iata-badge .code { font-size: 40px; }
      .iata-badge .label { margin-top: 0; }
      .hero-name { text-align: center; width: 100%; }
      .hero-name h1 { font-size: 24px; text-align: center; }
      .hero-name .location { font-size: 13px; justify-content: center; }
      .hero-badges { justify-content: center; }
      .hero-stats { gap: 0; display: grid; grid-template-columns: 1fr 1fr; margin-top: 20px; padding-top: 16px; }
      .hero-stat { padding: 12px 0; text-align: center; }
      .hero-stat .value { font-size: 18px; }
    }
    .card { background: var(--white); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 20px; }
    .card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; background: var(--blue); }
    .card-header h2 { font-size: 14px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; }
    .card-body { padding: 20px; }
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
    .info-item { padding: 14px 16px; border-bottom: 1px solid var(--border); border-right: 1px solid var(--border); }
    .info-item:nth-child(even) { border-right: none; }
    .info-item:nth-last-child(-n+2) { border-bottom: none; }
    .info-item .key { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px; }
    .info-item .val { font-size: 15px; font-weight: 600; color: var(--text); }
    .info-item .val a { color: var(--blue); text-decoration: none; }
    .info-item .val a:hover { text-decoration: underline; }
    .weather-widget { display: flex; align-items: center; gap: 20px; padding: 16px; background: linear-gradient(135deg, #e0f2fe, #f0f9ff); border-radius: 10px; margin-bottom: 16px; min-height: 100px; }
    .weather-icon { font-size: 48px; line-height: 1; }
    .weather-main .temp { font-size: 32px; font-weight: 700; color: var(--text); }
    .weather-main .desc { font-size: 14px; color: var(--muted); text-transform: capitalize; }
    .weather-details { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
    .weather-detail { font-size: 13px; color: var(--muted); }
    .weather-detail strong { color: var(--text); font-weight: 600; }
    .nearby-list { list-style: none; }
    .nearby-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border); }
    .nearby-item:last-child { border-bottom: none; }
    .nearby-code { background: var(--blue-light); color: var(--blue); font-weight: 700; font-size: 13px; padding: 3px 8px; border-radius: 6px; min-width: 44px; text-align: center; text-decoration: none; }
    .nearby-code:hover { background: #ccdcfb; }
    .nearby-info { flex: 1; margin: 0 12px; }
    .nearby-info .name { font-size: 13px; font-weight: 600; color: var(--text); }
    .nearby-info .city { font-size: 11px; color: var(--muted); }
    .nearby-dist { font-size: 12px; color: var(--muted); white-space: nowrap; }
    .carbon-form { display: flex; flex-direction: column; gap: 12px; }
    .carbon-form label { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .carbon-form input, .carbon-form select { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; font-family: \'Outfit\', sans-serif; color: var(--text); outline: none; transition: border-color 0.2s; }
    .carbon-form input:focus, .carbon-form select:focus { border-color: var(--blue); }
    .carbon-btn { background: var(--blue); color: #fff; border: none; padding: 11px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: \'Outfit\', sans-serif; transition: background 0.2s; }
    .carbon-btn:hover { background: #1447c0; }
    .carbon-result { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px; text-align: center; display: none; }
    .carbon-result .co2 { font-size: 24px; font-weight: 800; color: var(--green); }
    .carbon-result .co2-label { font-size: 12px; color: var(--muted); margin-top: 2px; }
    .sidebar-card { background: var(--white); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 20px; }
    .sidebar-card .card-header { padding: 14px 16px; }
    .sidebar-card .card-body { padding: 16px; }
    .codes-display { display: flex; gap: 12px; }
    .code-box { flex: 1; text-align: center; padding: 16px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; }
    .code-box .code-val { font-size: 28px; font-weight: 800; color: var(--navy); letter-spacing: 1px; }
    .code-box .code-type { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }
    footer { background: var(--navy); color: rgba(255,255,255,0.5); text-align: center; padding: 24px; font-size: 13px; margin-top: 40px; }
    footer a { color: rgba(255,255,255,0.5); text-decoration: none; margin: 0 12px; }
    footer a:hover { color: #fff; }
    #cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #1a2535; color: rgba(255,255,255,0.85); font-size: 13px; padding: 14px 20px; display: flex; align-items: center; justify-content: center; gap: 16px; flex-wrap: wrap; z-index: 9999; border-top: 1px solid rgba(255,255,255,0.1); }
    #cookie-banner a { color: var(--sky); text-decoration: underline; }
    #cookie-accept { background: var(--sky); color: #fff; border: none; border-radius: 6px; padding: 7px 18px; font-size: 13px; font-family: \'Outfit\', sans-serif; font-weight: 600; cursor: pointer; white-space: nowrap; }
'''

def nav_html(root=''):
    return f'''<nav>
  <a href="/" class="nav-logo">
    {NAV_LOGO_SVG}
    <span style="white-space:nowrap">Airport-<span style="color:var(--sky)">Code</span><span class="tld">.com</span></span>
  </a>
  <div class="nav-links">
    <a href="/az">A–Z</a>
    <a href="/countries">By Country</a>
  </div>
</nav>'''

def footer_html():
    return '''<footer>
  <div style="margin-bottom:10px">
    <a href="/az">A–Z Index</a>
    <a href="/countries">By Country</a>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    <a href="/terms">Terms</a>
    <a href="/privacy">Privacy</a>
  </div>
  <div>© 2025 airport-code.com</div>
</footer>
<div id="cookie-banner" style="display:none">
  <span>This site stores preferences locally in your browser. See our <a href="/privacy">Privacy Policy</a>.</span>
  <button id="cookie-accept" onclick="document.getElementById(\'cookie-banner\').style.display=\'none\';localStorage.setItem(\'cookie-ok\',\'1\')">Accept</button>
</div>
<script>if(!localStorage.getItem(\'cookie-ok\')){document.getElementById(\'cookie-banner\').style.display=\'flex\';}</script>'''

def static_page(title, meta_desc, content_html, slug=''):
    canonical = f"https://airport-code.com/{slug}/" if slug else "https://airport-code.com/"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>{title} | Airport Code</title>
  <meta name="description" content="{meta_desc}">
  <meta property="og:title" content="{title} | Airport Code">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="{canonical}">
  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    .page-content {{ max-width:800px; margin:0 auto; padding:40px 24px; }}
    .page-content h1 {{ font-size:32px; font-weight:800; color:var(--navy); margin-bottom:8px; }}
    .page-content h2 {{ font-size:20px; font-weight:700; color:var(--navy); margin:28px 0 10px; }}
    .page-content p {{ color:var(--text); line-height:1.7; margin-bottom:14px; }}
    .page-content a {{ color:var(--blue); }}
    .page-content ul {{ padding-left:20px; margin-bottom:14px; }}
    .page-content ul li {{ margin-bottom:6px; line-height:1.7; color:var(--text); }}
  </style>
</head>
<body>
{nav_html('/')}
<div class="page-content">
{content_html}
</div>
{footer_html()}
{SEARCH_JS}
</body>
</html>'''

SEARCH_JS = '''
<script>
(function(){
  let db = null;
  const input = document.getElementById('navSearchInput');
  const results = document.getElementById('search-results');
  if (!input) return;

  async function loadDB() {
    if (db) return;
    const root = document.querySelector('meta[name="site-root"]')?.content || '/';
    const r = await fetch(root + 'airports.json');
    db = await r.json();
  }

  input.addEventListener('focus', loadDB);
  input.addEventListener('input', async function() {
    const q = this.value.trim().toUpperCase();
    if (q.length < 2) { results.style.display = 'none'; return; }
    await loadDB();
    const matches = db.filter(a =>
      a.iata.startsWith(q) ||
      a.name.toUpperCase().includes(q) ||
      a.city.toUpperCase().includes(q)
    ).slice(0, 7);
    if (!matches.length) { results.style.display = 'none'; return; }
    const root = document.querySelector('meta[name="site-root"]')?.content || '/';
    results.innerHTML = matches.map(a =>
      `<a href="${root}${a.iata.toLowerCase()}/index.html">
        <span class="sr-code">${a.iata}</span>
        <div><div class="sr-name">${a.name}</div><div class="sr-city">${a.city}, ${a.country}</div></div>
      </a>`
    ).join('');
    results.style.display = 'block';
  });

  document.addEventListener('click', function(e) {
    if (!input.contains(e.target) && !results.contains(e.target)) results.style.display = 'none';
  });
})();
</script>
'''

WEATHER_ICONS = {
    0: ('☀️','Clear sky'), 1: ('🌤️','Mostly clear'), 2: ('⛅','Partly cloudy'), 3: ('☁️','Overcast'),
    45: ('🌫️','Foggy'), 48: ('🌫️','Icy fog'),
    51: ('🌦️','Light drizzle'), 53: ('🌦️','Moderate drizzle'), 55: ('🌧️','Heavy drizzle'),
    61: ('🌧️','Light rain'), 63: ('🌧️','Moderate rain'), 65: ('🌧️','Heavy rain'),
    71: ('🌨️','Light snow'), 73: ('🌨️','Moderate snow'), 75: ('❄️','Heavy snow'),
    80: ('🌦️','Rain showers'), 81: ('🌧️','Heavy showers'), 82: ('⛈️','Violent showers'),
    95: ('⛈️','Thunderstorm'), 96: ('⛈️','Thunderstorm with hail'), 99: ('⛈️','Heavy thunderstorm'),
}

def weather_js(lat, lon):
    return f'''
<script>
(function(){{
  const lat = {lat}, lon = {lon};
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${{lat}}&longitude=${{lon}}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,apparent_temperature,visibility,weather_code&wind_speed_unit=kmh&timezone=auto`;
  const icons = {json.dumps(WEATHER_ICONS)};
  fetch(url).then(r=>r.json()).then(d=>{{
    const c = d.current;
    const [icon, desc] = icons[c.weather_code] || ['🌡️','Unknown'];
    const tempC = Math.round(c.temperature_2m);
    const tempF = Math.round(tempC * 9/5 + 32);
    const feelsC = Math.round(c.apparent_temperature);
    const windDir = ['N','NE','E','SE','S','SW','W','NW'][Math.round(c.wind_direction_10m/45)%8];
    document.getElementById('wx-icon').textContent = icon;
    document.getElementById('wx-temp').innerHTML = `${{tempC}}°C <span style="font-size:16px;font-weight:400;color:#64748b">/ ${{tempF}}°F</span>`;
    document.getElementById('wx-desc').textContent = desc;
    document.getElementById('wx-humidity').innerHTML = `💧 Humidity: <strong>${{c.relative_humidity_2m}}%</strong>`;
    document.getElementById('wx-wind').innerHTML = `💨 Wind: <strong>${{Math.round(c.wind_speed_10m)}} km/h ${{windDir}}</strong>`;
    document.getElementById('wx-feels').innerHTML = `🌡️ Feels like: <strong>${{feelsC}}°C</strong>`;
    const vis = c.visibility ? (c.visibility >= 1000 ? `${{(c.visibility/1000).toFixed(0)}} km` : `${{c.visibility}} m`) : '—';
    document.getElementById('wx-visibility').innerHTML = `👁️ Visibility: <strong>${{vis}}</strong>`;
  }}).catch(()=>{{
    document.getElementById('wx-widget').innerHTML = '<p style="color:#94a3b8;font-size:13px;text-align:center;padding:20px 0">Weather data unavailable</p>';
  }});
}})();
</script>'''

def time_js(lat, lon):
    # Rough UTC offset from longitude
    utc_offset = round(lon / 15)
    return f'''
<script>
(function(){{
  const lat={lat}, lon={lon};
  // Fetch timezone from Open-Meteo (included in weather call anyway)
  let tz = 'UTC';
  fetch(`https://api.open-meteo.com/v1/forecast?latitude=${{lat}}&longitude=${{lon}}&current=temperature_2m&timezone=auto`)
    .then(r=>r.json()).then(d=>{{ tz = d.timezone || 'UTC'; tick(); }}).catch(()=>tick());
  function tick(){{
    const now = new Date();
    const s = now.toLocaleTimeString('en-GB', {{timeZone: tz, hour:'2-digit', minute:'2-digit', second:'2-digit'}});
    document.getElementById('localTime').textContent = s;
    const tzShort = tz.split('/').pop().replace('_',' ');
    document.getElementById('localTZ').textContent = tzShort;
  }}
  tick();
  setInterval(tick, 1000);
}})();
</script>'''

def carbon_js(lat, lon, iata):
    return f'''
<script>
const ORIGIN = {{lat:{lat}, lon:{lon}, iata:"{iata}"}};
let airportDB = null;
let selectedDestIata = null;
async function loadAirportDB(){{
  if (airportDB) return;
  const root = document.querySelector('meta[name="site-root"]')?.content || '/';
  const r = await fetch(root + 'airports.json');
  airportDB = await r.json();
}}
function haversine(lat1,lon1,lat2,lon2){{
  const R=6371,dLat=(lat2-lat1)*Math.PI/180,dLon=(lon2-lon1)*Math.PI/180;
  const a=Math.sin(dLat/2)**2+Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
}}
(async function initCarbonSearch(){{
  await loadAirportDB();
  const inp = document.getElementById('destInput');
  const sug = document.getElementById('carbonSuggest');
  inp.addEventListener('input', function(){{
    const q = this.value.toUpperCase().trim();
    selectedDestIata = null;
    if (q.length < 2) {{ sug.style.display='none'; return; }}
    const matches = airportDB.filter(a =>
      a.iata.startsWith(q) ||
      a.name.toUpperCase().includes(q) ||
      a.city.toUpperCase().includes(q)
    ).slice(0,8);
    if (!matches.length) {{ sug.style.display='none'; return; }}
    sug.innerHTML = matches.map(a =>
      `<div onclick="selectDest('${{a.iata}}','${{a.name.replace(/'/g,"\\\\'")}}')"
        style="padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid #f1f5f9;display:flex;gap:10px;align-items:center"
        onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background=''"
      ><span style="font-weight:700;color:var(--blue);min-width:36px">${{a.iata}}</span>
       <span style="color:#334155">${{a.name}}</span>
       <span style="color:#94a3b8;font-size:11px;margin-left:auto">${{a.city}}</span></div>`
    ).join('');
    sug.style.display='block';
  }});
  document.addEventListener('click', e => {{ if (!inp.contains(e.target) && !sug.contains(e.target)) sug.style.display='none'; }});
}})();
function selectDest(iata, name){{
  document.getElementById('destInput').value = iata + ' – ' + name;
  document.getElementById('carbonSuggest').style.display='none';
  selectedDestIata = iata;
}}
async function calcCarbon(){{
  const classMult = parseFloat(document.getElementById('classSelect').value);
  const tripMult = parseFloat(document.querySelector('input[name="trip"]:checked').value);
  const resultEl = document.getElementById('carbonResult');
  const co2El = document.getElementById('co2Val');
  const noteEl = document.getElementById('carbonNote');
  const dest = selectedDestIata || document.getElementById('destInput').value.toUpperCase().trim().split(/[\s–-]/)[0];
  if (!dest || dest.length < 2) return;
  await loadAirportDB();
  const destAirport = airportDB.find(a => a.iata === dest);
  if (!destAirport) {{
    co2El.textContent = '?';
    noteEl.textContent = `Airport "${{dest}}" not found. Search by name or code above.`;
    resultEl.style.display = 'block';
    return;
  }}
  const distKm = haversine(ORIGIN.lat, ORIGIN.lon, destAirport.lat, destAirport.lon);
  const co2 = Math.round(distKm * 0.115 * classMult * tripMult);
  co2El.textContent = co2.toLocaleString() + ' kg';
  const classNames = {{'1':'Economy','1.5':'Business','2.5':'First Class'}};
  const tripName = tripMult===1?'one-way':'return';
  noteEl.textContent = `${{ORIGIN.iata}} → ${{dest}} · approx ${{Math.round(distKm).toLocaleString()}} km · ${{classNames[String(classMult)]}} ${{tripName}} flight.`;
  resultEl.style.display = 'block';
}}
</script>'''

def departures_js(icao, lat, lon):
    if not icao or icao == 'N/A':
        return ''
    return f'''
<script>
(function(){{
  const lat={lat}, lon={lon}, icao="{icao}";
  const pad=1.2;
  const url=`https://opensky-network.org/api/states/all?lamin=${{lat-pad}}&lomin=${{lon-pad}}&lamax=${{lat+pad}}&lomax=${{lon+pad}}`;
  const container=document.getElementById('flights-container');
  fetch(url).then(r=>r.json()).then(d=>{{
    const states=(d.states||[]).filter(s=>!s[8]&&s[1]&&s[1].trim()); // not on ground, has callsign
    if(!states.length){{
      container.innerHTML='<p style="color:#94a3b8;font-size:13px;text-align:center;padding:12px">No aircraft currently overhead.</p>';
      return;
    }}
    states.sort((a,b)=>(b[9]||0)-(a[9]||0));
    const shown=states.slice(0,8);
    const rows=shown.map(s=>{{
      const callsign=(s[1]||'').trim();
      const country=s[2]||'—';
      const alt=s[13]?Math.round(s[13]*3.281).toLocaleString()+' ft':'—';
      const spd=s[9]?Math.round(s[9]*1.944)+' kts':'—';
      const hdg=s[10]!=null?Math.round(s[10])+'°':'—';
      return `<tr style="border-bottom:1px solid #f0f0f0">
        <td style="padding:10px 16px;font-weight:700;color:#1e293b;font-size:13px">${{callsign}}</td>
        <td style="padding:10px 16px;font-size:13px;color:#64748b">${{country}}</td>
        <td style="padding:10px 16px;font-size:13px;font-weight:600">${{alt}}</td>
        <td style="padding:10px 16px;font-size:13px">${{spd}}</td>
        <td style="padding:10px 16px;font-size:13px;color:#64748b">${{hdg}}</td>
      </tr>`;
    }}).join('');
    document.getElementById('flights-container').outerHTML=`<table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f8fafc">
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Callsign</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Origin</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Altitude</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Speed</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Heading</th>
      </tr></thead>
      <tbody>${{rows}}</tbody>
    </table>`;
  }}).catch(()=>{{
    container.innerHTML='<p style="color:#94a3b8;font-size:13px;text-align:center;padding:12px">Flight data temporarily unavailable.</p>';
  }});
}})();
</script>'''

# ─── Individual airport page ──────────────────────────────────────────────────

def airport_page(a):
    iata = escape_html(a['iata'])
    icao = escape_html(a['icao']) if a['icao'] else 'N/A'
    name = escape_html(a['name'])
    city = escape_html(a['city'])
    country = escape_html(a['country_name'])
    cc = a['country_code']
    flag = flag_emoji(cc)
    ttype = type_label(a['type'])
    badge_cls = type_badge_class(a['type'])
    lat = a['lat']
    lon = a['lon']
    elev = fmt_elevation(a['elevation'])
    lat_str = fmt_coord(lat, 'N', 'S')
    lon_str = fmt_coord(lon, 'E', 'W')
    wiki = a['wikipedia']
    wiki_link = f'<a href="{wiki}" target="_blank" rel="noopener">Wikipedia ↗</a>' if wiki else 'N/A'

    # Runways
    runways = runways_by_icao.get(a['icao'], [])
    max_len = max((r['length_ft'] for r in runways), default=1) or 1
    runway_html = ''
    for r in runways[:6]:
        pct = round(r['length_ft'] / max_len * 100)
        length_m = round(r['length_ft'] * 0.3048)
        runway_html += f'''
        <div style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
            <span style="font-weight:600">{escape_html(r["name"])}</span>
            <span style="color:#64748b">{r["length_ft"]:,} ft ({length_m:,} m) · {escape_html(r["surface"])}</span>
          </div>
          <div style="height:10px;background:#e2e8f0;border-radius:5px;overflow:hidden">
            <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#1a56db,#38bdf8);border-radius:5px"></div>
          </div>
        </div>'''

    if not runway_html:
        runway_html = '<p style="color:#94a3b8;font-size:13px">No runway data available.</p>'

    # Frequencies
    freqs = freqs_by_icao.get(a['icao'], [])
    freq_rows = ''
    for fr in freqs:
        freq_rows += f'''
        <tr style="border-bottom:1px solid #f5f5f5">
          <td style="padding:10px 16px;font-weight:600;font-size:13px;color:var(--text)">{escape_html(fr["type"])}</td>
          <td style="padding:10px 16px;font-size:13px;color:var(--muted)">{escape_html(fr["description"])}</td>
          <td style="padding:10px 16px;font-weight:700;font-size:13px;color:var(--blue);text-align:right">{escape_html(fr["mhz"])} MHz</td>
        </tr>'''

    nearby_html = ''
    for dist_km, n_iata, n_name, n_city in a['nearby']:
        n_name_e = escape_html(n_name)
        n_city_e = escape_html(n_city)
        dist_str = f"{int(dist_km)} km"
        nearby_html += f'''
          <li class="nearby-item">
            <a href="/{n_iata.lower()}/index.html" style="display:flex;align-items:center;flex:1;gap:12px;text-decoration:none;color:inherit;">
              <span class="nearby-code">{n_iata}</span>
              <div class="nearby-info"><div class="name">{n_name_e}</div><div class="city">{n_city_e}</div></div>
            </a>
            <span class="nearby-dist">{dist_str}</span>
          </li>'''

    if not nearby_html:
        nearby_html = '<li style="padding:14px 0;color:#94a3b8;font-size:13px;">No nearby airports found within 600 km</li>'

    if freq_rows:
        freq_card_html = f'''<div class="card">
      <div class="card-header"><span>📻</span><h2>Radio Frequencies</h2></div>
      <div class="card-body" style="padding:0">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr style="background:#f8fafc">
            <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Type</th>
            <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Description</th>
            <th style="padding:10px 16px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid #e2e8f0">Frequency</th>
          </tr></thead>
          <tbody>{freq_rows}
          </tbody>
        </table>
      </div>
    </div>'''
    else:
        freq_card_html = ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>{iata} – {name} | Airport Code</title>
  <meta name="description" content="{iata} is the IATA airport code for {name} in {city}, {country}. Find location, weather, runways and nearby airports.">
  <meta property="og:title" content="{iata} – {name} | Airport Code">
  <meta property="og:description" content="{iata} is the IATA airport code for {name} in {city}, {country}. Find location, weather, runways and nearby airports.">
  <meta property="og:url" content="https://airport-code.com/{a['iata'].lower()}/">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{iata} – {name} | Airport Code">
  <meta name="twitter:description" content="{iata} is the IATA airport code for {name} in {city}, {country}.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <link rel="canonical" href="https://airport-code.com/{a['iata'].lower()}/">
  <style>{SHARED_CSS}</style>
</head>
<body>

{nav_html('/')}

<div class="hero">
  <div class="hero-inner">
    <div class="breadcrumb">
      <a href="/">Home</a><span class="sep">›</span>
      <a href="/countries/{cc.lower()}.html">{flag} {country}</a><span class="sep">›</span>
      <span>{name}</span>
    </div>
    <div class="hero-top">
      <div>
        <div class="hero-title">
          <div class="iata-badge">
            <div class="code">{iata}</div>
            <div class="label">IATA Code</div>
          </div>
          <div class="hero-name">
            <h1>{name}</h1>
            <div class="location">
              <span>{flag}</span>
              <span>{city}, {country}</span>
            </div>
            <div class="hero-badges">
              <span class="badge {badge_cls}">{ttype}</span>
            </div>
          </div>
        </div>
        <div class="hero-stats">
          <div class="hero-stat"><div class="value">{icao}</div><div class="label">ICAO Code</div></div>
          <div class="hero-stat"><div class="value">{elev.split(' ')[0] if elev != 'N/A' else 'N/A'}</div><div class="label">Elevation</div></div>
          <div class="hero-stat"><div class="value">{lat:.2f}°</div><div class="label">Latitude</div></div>
          <div class="hero-stat"><div class="value">{lon:.2f}°</div><div class="label">Longitude</div></div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="main">
  <div class="content">

    <div class="card">
      <div class="card-header"><span>ℹ️</span><h2>Airport Information</h2></div>
      <div class="info-grid">
        <div class="info-item"><div class="key">Full Name</div><div class="val">{name}</div></div>
        <div class="info-item"><div class="key">City</div><div class="val">{city}</div></div>
        <div class="info-item"><div class="key">Country</div><div class="val">{flag} {country}</div></div>
        <div class="info-item"><div class="key">Country Code</div><div class="val">{cc}</div></div>
        <div class="info-item"><div class="key">IATA Code</div><div class="val">{iata}</div></div>
        <div class="info-item"><div class="key">ICAO Code</div><div class="val">{icao}</div></div>
        <div class="info-item"><div class="key">Latitude</div><div class="val">{lat_str}</div></div>
        <div class="info-item"><div class="key">Longitude</div><div class="val">{lon_str}</div></div>
        <div class="info-item"><div class="key">Elevation</div><div class="val">{elev}</div></div>
        <div class="info-item"><div class="key">Type</div><div class="val">{ttype}</div></div>
        <div class="info-item"><div class="key">Wikipedia</div><div class="val">{wiki_link}</div></div>
        <div class="info-item"><div class="key">Region</div><div class="val">{escape_html(a["region"])}</div></div>
      </div>
    </div>


    <div class="card">
      <div class="card-header"><span>🛬</span><h2>Runways</h2></div>
      <div class="card-body">{runway_html}
      </div>
    </div>

    {freq_card_html}

    <div class="card">
      <div class="card-header"><span>🌱</span><h2>Carbon Footprint Calculator</h2></div>
      <div class="card-body">
        <p style="font-size:13px;color:#64748b;margin-bottom:16px;">Estimate CO₂ emissions for a flight departing from {iata}.</p>
        <div class="carbon-form">
          <div style="position:relative">
            <label>Destination Airport</label>
            <input type="text" id="destInput" placeholder="Search airport name or code…" autocomplete="off" style="text-transform:uppercase">
            <div id="carbonSuggest" style="display:none;position:absolute;left:0;right:0;top:100%;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.1);z-index:50;max-height:220px;overflow-y:auto"></div>
          </div>
          <div>
            <label>Cabin Class</label>
            <select id="classSelect">
              <option value="1">Economy</option>
              <option value="1.5">Business</option>
              <option value="2.5">First Class</option>
            </select>
          </div>
          <div style="display:flex;gap:16px">
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;font-weight:500;cursor:pointer"><input type="radio" name="trip" value="1" checked> One way</label>
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;font-weight:500;cursor:pointer"><input type="radio" name="trip" value="2"> Return</label>
          </div>
          <button class="carbon-btn" onclick="calcCarbon()">Calculate Emissions</button>
          <div class="carbon-result" id="carbonResult">
            <div class="co2" id="co2Val"></div>
            <div class="co2-label">kg CO₂ per passenger</div>
            <p style="font-size:12px;color:#64748b;margin-top:8px" id="carbonNote"></p>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><span>✈️</span><h2>Live Departures</h2></div>
      <div class="card-body" style="text-align:center;padding:28px 20px">
        <p style="color:#64748b;font-size:14px;margin-bottom:16px;">View real-time departures and arrivals for {iata}.</p>
        <a href="https://www.flightaware.com/live/airport/{icao}" target="_blank" rel="noopener"
           style="display:inline-block;background:#1a56db;color:#fff;padding:10px 24px;border-radius:8px;font-weight:600;font-size:14px;text-decoration:none;">
          View Live Departures on FlightAware ↗
        </a>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><span>📍</span><h2>Nearby Airports</h2></div>
      <div class="card-body">
        <ul class="nearby-list">{nearby_html}
        </ul>
      </div>
    </div>

  </div>

  <div class="sidebar">

    <div class="sidebar-card">
      <div class="card-header"><span>🏷️</span><h2>Airport Codes</h2></div>
      <div class="card-body">
        <div class="codes-display">
          <div class="code-box"><div class="code-val">{iata}</div><div class="code-type">IATA</div></div>
          <div class="code-box"><div class="code-val">{icao}</div><div class="code-type">ICAO</div></div>
        </div>
        <p style="font-size:12px;color:#94a3b8;margin-top:12px;line-height:1.5;">The IATA code <strong style="color:#1e293b">{iata}</strong> is used on airline tickets and baggage tags. The ICAO code <strong style="color:#1e293b">{icao}</strong> is used for air traffic control and flight planning.</p>
      </div>
    </div>

    <div class="sidebar-card">
      <div class="card-header"><span>🗺️</span><h2>Location</h2></div>
      <div class="card-body" style="padding:12px">
        <iframe
          src="https://www.openstreetmap.org/export/embed.html?bbox={lon-0.08:.6f}%2C{lat-0.05:.6f}%2C{lon+0.08:.6f}%2C{lat+0.05:.6f}&layer=mapnik&marker={lat:.6f}%2C{lon:.6f}"
          width="100%" height="220" style="border:0;border-radius:10px;display:block" allowfullscreen loading="lazy">
        </iframe>
        <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=13/{lat}/{lon}" target="_blank" rel="noopener"
           style="display:block;margin-top:10px;font-size:12px;color:#1a56db;font-weight:600;text-align:center;">
          Open in OpenStreetMap ↗
        </a>
      </div>
    </div>

    <div class="sidebar-card">
      <div class="card-header"><span>📊</span><h2>Quick Facts</h2></div>
      <div class="card-body" style="padding:8px 16px">
        <ul style="list-style:none">
          <li style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">
            <span>🌍</span><span style="color:#64748b">Located in <strong style="color:#1e293b">{city}, {country}</strong></span>
          </li>
          <li style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">
            <span>📏</span><span style="color:#64748b">Elevation: <strong style="color:#1e293b">{elev}</strong></span>
          </li>
          <li style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px">
            <span>🛫</span><span style="color:#64748b">Type: <strong style="color:#1e293b">{ttype}</strong></span>
          </li>
          <li style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;font-size:13px">
            <span>📡</span><span style="color:#64748b">Coordinates: <strong style="color:#1e293b">{lat:.4f}, {lon:.4f}</strong></span>
          </li>
        </ul>
      </div>
    </div>

  </div>
</div>

{footer_html()}

{SEARCH_JS}
{carbon_js(lat, lon, a['iata'])}

</body>
</html>'''

# ─── Homepage ─────────────────────────────────────────────────────────────────

def homepage():
    # Top airports to feature
    featured = ['LHR','JFK','DXB','CDG','SIN','AMS','FRA','SYD','LAX','NRT','HKG','ICN','BKK','MAD','FCO']
    featured_html = ''
    for code in featured:
        if code in by_iata:
            a = by_iata[code]
            flag = flag_emoji(a['country_code'])
            featured_html += f'''
    <a href="/{a['iata'].lower()}/index.html" style="display:flex;align-items:center;gap:12px;padding:14px 16px;background:#fff;border:1px solid var(--border);border-radius:10px;text-decoration:none;transition:box-shadow 0.2s;" onmouseover="this.style.boxShadow='0 4px 16px rgba(0,0,0,0.08)'" onmouseout="this.style.boxShadow=''">
      <span style="background:var(--blue-light);color:var(--blue);font-weight:800;font-size:15px;padding:8px 10px;border-radius:8px;min-width:52px;text-align:center;">{a['iata']}</span>
      <div>
        <div style="font-weight:600;font-size:14px;color:var(--text)">{escape_html(a['name'])}</div>
        <div style="font-size:12px;color:var(--muted)">{flag} {escape_html(a['city'])}, {escape_html(a['country_name'])}</div>
      </div>
    </a>'''

    lnk_style = 'display:inline-block;margin:2px;padding:4px 9px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;font-weight:700;font-size:13px;color:#1a56db;text-decoration:none;white-space:nowrap;'
    az_code_links = ''.join(f'<a href="/az/{c.lower()}.html" style="{lnk_style}">{c}</a>' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    az_name_links = ''.join(f'<a href="/az-name/{c.lower()}.html" style="{lnk_style}">{c}</a>' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    az_city_links = ''.join(f'<a href="/az-city/{c.lower()}.html" style="{lnk_style}">{c}</a>' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airport Code Lookup — IATA &amp; ICAO Codes for 8,800+ Airports</title>
  <meta name="description" content="Look up IATA and ICAO airport codes for 8,800+ airports worldwide. Find location, weather, maps and nearby airports.">
  <meta property="og:title" content="Airport Code Lookup — IATA &amp; ICAO Codes for 8,800+ Airports">
  <meta property="og:description" content="Look up IATA and ICAO airport codes for 8,800+ airports worldwide. Find location, weather, maps and nearby airports.">
  <meta property="og:url" content="https://airport-code.com/">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Airport Code Lookup — IATA &amp; ICAO Codes for 8,800+ Airports">
  <meta name="twitter:description" content="Look up IATA and ICAO airport codes for 8,800+ airports worldwide.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <link rel="canonical" href="https://airport-code.com/">
  <style>{SHARED_CSS}
    .hero-home {{ background: linear-gradient(135deg, var(--navy) 0%, #1a3a6b 100%); color:#fff; padding:80px 24px; text-align:center; position:relative; overflow:hidden; }}
    .hero-home::before {{ content:'✈'; position:absolute; right:-40px; top:-40px; font-size:300px; opacity:0.04; transform:rotate(25deg); }}
    .hero-home h1 {{ font-size:48px; font-weight:800; line-height:1.15; color:#fff; margin-bottom:16px; }}
    .hero-home h1 span {{ color: var(--sky); }}
    .hero-home p {{ font-size:18px; color:rgba(255,255,255,0.7); margin-bottom:36px; }}
    .search-big {{ display:flex; align-items:center; background:#fff; border-radius:12px; padding:8px 8px 8px 20px; gap:8px; max-width:580px; margin:0 auto; box-shadow:0 4px 20px rgba(0,0,0,0.2); position:relative; }}
    .search-big input {{ flex:1; border:none; outline:none; font-size:17px; font-family:'Outfit',sans-serif; color:var(--text); }}
    .search-big input::placeholder {{ color:#94a3b8; }}
    .search-big button {{ background:var(--blue); color:#fff; border:none; border-radius:8px; padding:10px 22px; font-size:15px; font-weight:600; cursor:pointer; font-family:'Outfit',sans-serif; white-space:nowrap; }}
    #home-results {{ position:absolute; top:calc(100% + 6px); left:0; right:0; background:#fff; border:1px solid var(--border); border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,0.12); z-index:200; overflow:hidden; display:none; }}
    #home-results a {{ display:flex;align-items:center;gap:10px;padding:10px 14px;text-decoration:none;color:var(--text);font-size:13px;border-bottom:1px solid var(--border);transition:background 0.15s; }}
    #home-results a:last-child {{ border-bottom:none; }}
    #home-results a:hover {{ background:var(--bg); }}
    #home-results .sr-code {{ background:var(--blue-light);color:var(--blue);font-weight:700;font-size:12px;padding:2px 7px;border-radius:5px;min-width:38px;text-align:center; }}
    #home-results .sr-name {{ font-weight:600; }}
    #home-results .sr-city {{ color:var(--muted);font-size:11px; }}
    .stats-bar {{ display:flex; justify-content:center; gap:48px; padding:32px 24px; background:var(--white); border-bottom:1px solid var(--border); flex-wrap:wrap; }}
    .stat-item .num {{ font-size:28px; font-weight:800; color:var(--navy); }}
    .stat-item .lbl {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:0.6px; }}
    .section {{ max-width:1100px; margin:0 auto; padding:40px 24px; }}
    .section h2 {{ font-size:22px; font-weight:800; color:var(--navy); margin-bottom:20px; }}
    .featured-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(300px,1fr)); gap:12px; }}
    .az-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(44px,1fr)); gap:8px; }}
    .az-link {{ display:flex; align-items:center; justify-content:center; background:#fff; border:1px solid var(--border); border-radius:8px; height:44px; font-size:18px; font-weight:700; color:var(--blue); text-decoration:none; transition:all 0.2s; }}
    .az-link:hover {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
  </style>
</head>
<body>

{nav_html('/')}

<div class="hero-home">
  <h1>Find Any <span>Airport Code</span></h1>
  <p>IATA &amp; ICAO codes for 8,800+ airports worldwide</p>
  <div class="search-big">
    <svg width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input type="text" id="homeSearch" placeholder="Airport name, city or IATA code…" autocomplete="off">
    <button onclick="doSearch()">Search</button>
    <div id="home-results"></div>
  </div>
</div>

<div class="stats-bar">
  <div class="stat-item"><div class="num">8,810</div><div class="lbl">Airports</div></div>
  <div class="stat-item"><div class="num">200+</div><div class="lbl">Countries</div></div>
  <div class="stat-item"><div class="num">Live</div><div class="lbl">Weather Data</div></div>
  <div class="stat-item"><div class="num">Free</div><div class="lbl">No Sign-up</div></div>
</div>

<div class="section">
  <h2>✈️ Popular Airports</h2>
  <div class="featured-grid">
    {featured_html}
  </div>
</div>

<div class="section" style="background:var(--white);border-top:1px solid var(--border);border-bottom:1px solid var(--border);max-width:100%;padding:40px 0">
  <div style="max-width:1100px;margin:0 auto;padding:0 24px">
    <h2>Browse by A–Z</h2>
    <div style="margin-top:8px">
      <div style="padding:16px 0;border-bottom:1px solid var(--border)">
        <div style="font-weight:700;font-size:15px;margin-bottom:10px">By Airport Code</div>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch">{az_code_links}</div>
      </div>
      <div style="padding:16px 0;border-bottom:1px solid var(--border)">
        <div style="font-weight:700;font-size:15px;margin-bottom:10px">By Airport Name</div>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch">{az_name_links}</div>
      </div>
      <div style="padding:16px 0">
        <div style="font-weight:700;font-size:15px;margin-bottom:10px">By City Name</div>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch">{az_city_links}</div>
      </div>
    </div>
  </div>
</div>

{footer_html()}

<script>
let homeDB = null;
async function loadHomeDB(){{
  if (homeDB) return;
  const r = await fetch('/airports.json');
  homeDB = await r.json();
}}
const homeInput = document.getElementById('homeSearch');
const homeResults = document.getElementById('home-results');
homeInput.addEventListener('focus', loadHomeDB);
homeInput.addEventListener('input', async function(){{
  const q = this.value.trim().toUpperCase();
  if (q.length < 2) {{ homeResults.style.display='none'; return; }}
  await loadHomeDB();
  const matches = homeDB.filter(a =>
    a.iata.startsWith(q) || a.name.toUpperCase().includes(q) || a.city.toUpperCase().includes(q)
  ).slice(0,8);
  if (!matches.length) {{ homeResults.style.display='none'; return; }}
  homeResults.innerHTML = matches.map(a =>
    `<a href="/${{a.iata.toLowerCase()}}/index.html">
      <span class="sr-code">${{a.iata}}</span>
      <div><div class="sr-name">${{a.name}}</div><div class="sr-city">${{a.city}}, ${{a.country}}</div></div>
    </a>`
  ).join('');
  homeResults.style.display = 'block';
}});
document.addEventListener('click', function(e){{
  if (!homeInput.contains(e.target)) homeResults.style.display='none';
}});
function doSearch(){{
  const q = homeInput.value.trim().toUpperCase();
  if (q.length === 3 && homeDB) {{
    const a = homeDB.find(x => x.iata === q);
    if (a) {{ window.location = '/' + q.toLowerCase() + '/index.html'; return; }}
  }}
  homeInput.dispatchEvent(new Event('input'));
}}
homeInput.addEventListener('keydown', function(e){{ if(e.key==='Enter') doSearch(); }});
</script>

</body>
</html>'''

# ─── A-Z index pages ──────────────────────────────────────────────────────────

def az_page(letter, airports_for_letter):
    letter_u = letter.upper()
    rows = ''
    for a in sorted(airports_for_letter, key=lambda x: x['iata']):
        flag = flag_emoji(a['country_code'])
        rows += f'''
      <tr>
        <td style="padding:12px 16px;font-weight:700;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--blue);text-decoration:none;">{a['iata']}</a></td>
        <td style="padding:12px 16px;font-size:12px;color:var(--muted);">{escape_html(a['icao'])}</td>
        <td style="padding:12px 16px;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--text);text-decoration:none;font-weight:600;">{escape_html(a['name'])}</a></td>
        <td style="padding:12px 16px;color:var(--muted);font-size:13px;">{escape_html(a['city'])}</td>
        <td style="padding:12px 16px;color:var(--muted);font-size:13px;">{flag} {escape_html(a['country_name'])}</td>
        <td style="padding:12px 16px;font-size:12px;color:var(--muted);">{type_label(a['type'])}</td>
      </tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airports Starting With {letter_u} | Airport Code</title>
  <meta name="description" content="All airports with IATA codes starting with the letter {letter_u}. Browse airport codes, names and locations.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    .az-nav {{ display:grid; grid-template-columns:repeat(13,1fr); gap:6px; padding:20px 0; }}
    .az-nav a {{ display:flex;align-items:center;justify-content:center;height:44px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px; }}
    .az-nav a.active {{ background:var(--blue);color:#fff; }}
    .az-nav a:not(.active) {{ background:#fff;color:var(--blue);border:1px solid var(--border); }}
    .az-nav a:not(.active):hover {{ background:var(--blue-light); }}
    @media(max-width:600px){{ .az-nav {{ grid-template-columns:repeat(9,1fr); gap:5px; }} }}
    table {{ width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden; }}
    thead th {{ padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid var(--border);background:#f8fafc; }}
    tbody tr {{ border-bottom:1px solid #f5f5f5; }}
    tbody tr:last-child {{ border-bottom:none; }}
    tbody tr:hover {{ background:#fafbfc; }}
  </style>
</head>
<body>

{nav_html('/')}

<div style="max-width:1100px;margin:0 auto;padding:32px 24px">
  <div style="margin-bottom:8px;font-size:12px;color:var(--muted)"><a href="/" style="color:var(--blue);text-decoration:none">Home</a> › <a href="/az" style="color:var(--blue);text-decoration:none">A–Z Index</a> › {letter_u}</div>
  <h1 style="font-size:28px;font-weight:800;color:var(--navy);margin-bottom:4px">Airports: {letter_u}</h1>
  <p style="color:var(--muted);margin-bottom:16px">{len(airports_for_letter)} airports with IATA codes starting with {letter_u}</p>

  <div class="az-nav">
    {''.join(f'<a href="/az/{c.lower()}.html" class="{"active" if c == letter_u else ""}">{c}</a>' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')}
  </div>

  <table>
    <thead>
      <tr>
        <th>IATA</th><th>ICAO</th><th>Airport Name</th><th>City</th><th>Country</th><th>Type</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
</div>

{footer_html()}
{SEARCH_JS}
</body>
</html>'''

def az_index():
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airport Codes A–Z Index | Airport Code</title>
  <meta name="description" content="Browse all 8,800+ IATA airport codes alphabetically. Find airports by the first letter of their code.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    .az-big-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:12px; margin-top:24px; }}
    .az-big-item {{ background:#fff; border:1px solid var(--border); border-radius:12px; padding:20px; text-align:center; text-decoration:none; transition:all 0.2s; }}
    .az-big-item:hover {{ box-shadow:0 4px 16px rgba(0,0,0,0.08); border-color:var(--blue); }}
    .az-big-item .letter {{ font-size:32px; font-weight:800; color:var(--navy); }}
    .az-big-item .count {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  </style>
</head>
<body>

{nav_html('/')}

<div style="max-width:1100px;margin:0 auto;padding:32px 24px">
  <div style="margin-bottom:8px;font-size:12px;color:var(--muted)"><a href="/" style="color:var(--blue);text-decoration:none">Home</a> › A–Z Index</div>
  <h1 style="font-size:32px;font-weight:800;color:var(--navy);margin-bottom:8px">Browse Airports A–Z</h1>
  <p style="color:var(--muted)">8,810 airports sorted by IATA code. Click a letter to browse.</p>
  <div class="az-big-grid" id="az-grid">Loading…</div>
</div>

{footer_html()}
{SEARCH_JS}
<script>
const counts = __AZ_COUNTS__;
const grid = document.getElementById('az-grid');
grid.innerHTML = Object.entries(counts).map(([l,c]) =>
  `<a href="/az/${{l.toLowerCase()}}.html" class="az-big-item">
    <div class="letter">${{l}}</div>
    <div class="count">${{c}} airports</div>
  </a>`
).join('');
</script>
</body>
</html>'''

# ─── Countries page ────────────────────────────────────────────────────────────

def countries_page(by_country):
    rows = ''
    for cc in sorted(by_country.keys(), key=lambda c: by_country[c][0]['country_name']):
        aps = by_country[cc]
        cn = escape_html(aps[0]['country_name'])
        flag = flag_emoji(cc)
        rows += f'''
    <a href="/countries/{cc.lower()}.html" style="display:flex;align-items:center;gap:12px;padding:14px 16px;background:#fff;border:1px solid var(--border);border-radius:10px;text-decoration:none;transition:box-shadow 0.2s;" onmouseover="this.style.boxShadow='0 4px 16px rgba(0,0,0,0.08)'" onmouseout="this.style.boxShadow=''">
      <span style="font-size:24px">{flag}</span>
      <div style="flex:1"><div style="font-weight:600;font-size:14px;color:var(--text)">{cn}</div><div style="font-size:12px;color:var(--muted)">{len(aps)} airports</div></div>
      <span style="font-size:12px;color:var(--muted);font-weight:600">{cc}</span>
    </a>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airports by Country | Airport Code</title>
  <meta name="description" content="Browse airport codes by country. Find all airports in any country worldwide.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    .country-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:10px; margin-top:24px; }}
  </style>
</head>
<body>
{nav_html('/')}
<div style="max-width:1100px;margin:0 auto;padding:32px 24px">
  <div style="margin-bottom:8px;font-size:12px;color:var(--muted)"><a href="/" style="color:var(--blue);text-decoration:none">Home</a> › By Country</div>
  <h1 style="font-size:32px;font-weight:800;color:var(--navy);margin-bottom:8px">Airports by Country</h1>
  <p style="color:var(--muted)">{len(by_country)} countries · 8,810 airports total</p>
  <div class="country-grid">{rows}</div>
</div>
{footer_html()}
{SEARCH_JS}
</body>
</html>'''

def country_page(cc, aps):
    cn = escape_html(aps[0]['country_name'])
    flag = flag_emoji(cc)
    rows = ''
    for a in sorted(aps, key=lambda x: (x['type'] != 'large_airport', x['type'] != 'medium_airport', x['iata'])):
        rows += f'''
      <tr>
        <td style="padding:12px 16px;font-weight:700;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--blue);text-decoration:none;">{a['iata']}</a></td>
        <td style="padding:12px 16px;font-size:12px;color:var(--muted);">{escape_html(a['icao'])}</td>
        <td style="padding:12px 16px;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--text);text-decoration:none;font-weight:600;">{escape_html(a['name'])}</a></td>
        <td style="padding:12px 16px;color:var(--muted);font-size:13px;">{escape_html(a['city'])}</td>
        <td style="padding:12px 16px;font-size:12px;color:var(--muted);">{type_label(a['type'])}</td>
      </tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airports in {cn} | Airport Code</title>
  <meta name="description" content="All airport codes for airports in {cn}. Browse IATA and ICAO codes for {len(aps)} airports.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    table {{ width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden; }}
    thead th {{ padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid var(--border);background:#f8fafc; }}
    tbody tr {{ border-bottom:1px solid #f5f5f5; }}
    tbody tr:last-child {{ border-bottom:none; }}
    tbody tr:hover {{ background:#fafbfc; }}
  </style>
</head>
<body>
{nav_html('/')}
<div style="max-width:1100px;margin:0 auto;padding:32px 24px">
  <div style="margin-bottom:8px;font-size:12px;color:var(--muted)"><a href="/" style="color:var(--blue);text-decoration:none">Home</a> › <a href="/countries" style="color:var(--blue);text-decoration:none">By Country</a> › {cn}</div>
  <h1 style="font-size:28px;font-weight:800;color:var(--navy);margin-bottom:4px">{flag} Airports in {cn}</h1>
  <p style="color:var(--muted);margin-bottom:24px">{len(aps)} airports with IATA codes</p>
  <table>
    <thead><tr><th>IATA</th><th>ICAO</th><th>Airport Name</th><th>City</th><th>Type</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
{footer_html()}
{SEARCH_JS}
</body>
</html>'''

# ─── Sitemap ──────────────────────────────────────────────────────────────────

def sitemap(airports):
    urls = [
        'https://airport-code.com/',
        'https://airport-code.com/az.html',
        'https://airport-code.com/countries.html',
    ]
    for c in 'abcdefghijklmnopqrstuvwxyz':
        urls.append(f'https://airport-code.com/az/{c}.html')
        urls.append(f'https://airport-code.com/az-name/{c}.html')
        urls.append(f'https://airport-code.com/az-city/{c}.html')
    for a in airports:
        urls.append(f"https://airport-code.com/{a['iata'].lower()}/")
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        parts.append(f'  <url><loc>{u}</loc></url>')
    parts.append('</urlset>')
    return '\n'.join(parts)

def az_name_city_page(letter, airports_for_letter, kind):
    """kind = 'name' or 'city'"""
    kind_label = 'Airport Name' if kind == 'name' else 'City Name'
    prefix = 'az-name' if kind == 'name' else 'az-city'
    rows = ''
    for a in sorted(airports_for_letter, key=lambda x: (x['name'] if kind == 'name' else x['city'])):
        flag = flag_emoji(a['country_code'])
        rows += f'''
      <tr>
        <td style="padding:12px 16px;font-weight:700;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--blue);text-decoration:none;">{escape_html(a['iata'])}</a></td>
        <td style="padding:12px 16px;"><a href="/{a['iata'].lower()}/index.html" style="color:var(--text);text-decoration:none;font-weight:600;">{escape_html(a['name'])}</a></td>
        <td style="padding:12px 16px;color:var(--muted);font-size:13px;">{escape_html(a['city'])}</td>
        <td style="padding:12px 16px;color:var(--muted);font-size:13px;">{flag} {escape_html(a['country_name'])}</td>
      </tr>'''

    letter_u = letter.upper()
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="site-root" content="/">
  <title>Airports with {kind_label} Starting With {letter_u} | Airport Code</title>
  <meta name="description" content="All airports with {kind_label.lower()} starting with {letter_u}. Browse {len(airports_for_letter)} airports.">

  <link rel="stylesheet" href="/fonts/outfit.css">
  <style>{SHARED_CSS}
    table {{ width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden; }}
    thead th {{ padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid var(--border);background:#f8fafc; }}
    tbody tr {{ border-bottom:1px solid #f5f5f5; }}
    tbody tr:last-child {{ border-bottom:none; }}
    tbody tr:hover {{ background:#fafbfc; }}
    .az-nav {{ display:grid; grid-template-columns:repeat(13,1fr); gap:6px; padding:20px 0; }}
    .az-nav a {{ display:flex;align-items:center;justify-content:center;height:44px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px; }}
    .az-nav a.active {{ background:var(--blue);color:#fff; }}
    .az-nav a:not(.active) {{ background:#fff;color:var(--blue);border:1px solid var(--border); }}
    .az-nav a:not(.active):hover {{ background:var(--blue-light); }}
    @media(max-width:600px){{ .az-nav {{ grid-template-columns:repeat(9,1fr); gap:5px; }} }}
  </style>
</head>
<body>
{nav_html('/')}
<div style="max-width:1100px;margin:0 auto;padding:32px 24px">
  <div style="margin-bottom:8px;font-size:12px;color:var(--muted)"><a href="/" style="color:var(--blue);text-decoration:none">Home</a> › {kind_label} › {letter_u}</div>
  <h1 style="font-size:28px;font-weight:800;color:var(--navy);margin-bottom:4px">Airports: {kind_label} Starting With {letter_u}</h1>
  <p style="color:var(--muted);margin-bottom:16px">{len(airports_for_letter)} airports</p>
  <div class="az-nav">
    {''.join(f'<a href="/{prefix}/{c.lower()}.html" class="{"active" if c == letter_u else ""}">{c}</a>' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')}
  </div>
  <table>
    <thead><tr><th>IATA</th><th>Airport Name</th><th>City</th><th>Country</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
{footer_html()}
{SEARCH_JS}
</body>
</html>'''

# ─── Generate everything ──────────────────────────────────────────────────────

print("\nGenerating airport pages...")
t1 = time.time()
for i, a in enumerate(airports):
    slug = a['iata'].lower()
    d = f"{OUT_DIR}/{slug}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/index.html", 'w', encoding='utf-8') as f:
        f.write(airport_page(a))
    if i % 500 == 0:
        print(f"  {i}/{len(airports)} ({time.time()-t1:.0f}s)")

print(f"  Done in {time.time()-t1:.0f}s")

# A-Z pages
print("Generating A-Z pages...")
os.makedirs(f"{OUT_DIR}/az", exist_ok=True)
az_counts = {}
for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    letter_airports = [a for a in airports if a['iata'].startswith(letter)]
    az_counts[letter] = len(letter_airports)
    with open(f"{OUT_DIR}/az/{letter.lower()}.html", 'w', encoding='utf-8') as f:
        f.write(az_page(letter, letter_airports))

# A-Z index — write as both az/index.html (clean URL) and az.html (fallback)
az_content = az_index().replace('__AZ_COUNTS__', json.dumps(az_counts))
with open(f"{OUT_DIR}/az.html", 'w', encoding='utf-8') as f:
    f.write(az_content)
with open(f"{OUT_DIR}/az/index.html", 'w', encoding='utf-8') as f:
    f.write(az_content)

# Countries
print("Generating country pages...")
os.makedirs(f"{OUT_DIR}/countries", exist_ok=True)
by_country = {}
for a in airports:
    cc = a['country_code']
    by_country.setdefault(cc, []).append(a)

countries_content = countries_page(by_country)
with open(f"{OUT_DIR}/countries.html", 'w', encoding='utf-8') as f:
    f.write(countries_content)
with open(f"{OUT_DIR}/countries/index.html", 'w', encoding='utf-8') as f:
    f.write(countries_content)

for cc, aps in by_country.items():
    with open(f"{OUT_DIR}/countries/{cc.lower()}.html", 'w', encoding='utf-8') as f:
        f.write(country_page(cc, aps))

# A-Z by name and city
print("Generating A-Z by name and city pages...")
os.makedirs(f"{OUT_DIR}/az-name", exist_ok=True)
os.makedirs(f"{OUT_DIR}/az-city", exist_ok=True)
for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    by_name = [a for a in airports if a['name'].upper().startswith(letter)]
    with open(f"{OUT_DIR}/az-name/{letter.lower()}.html", 'w', encoding='utf-8') as f:
        f.write(az_name_city_page(letter, by_name, 'name'))
    by_city = [a for a in airports if a['city'].upper().startswith(letter)]
    with open(f"{OUT_DIR}/az-city/{letter.lower()}.html", 'w', encoding='utf-8') as f:
        f.write(az_name_city_page(letter, by_city, 'city'))

# Homepage
print("Generating homepage...")
with open(f"{OUT_DIR}/index.html", 'w', encoding='utf-8') as f:
    f.write(homepage())

# Sitemap
print("Generating sitemap...")
with open(f"{OUT_DIR}/sitemap.xml", 'w', encoding='utf-8') as f:
    f.write(sitemap(airports))

# Static pages
ABOUT_CONTENT = '''
<h1>About Airport Code</h1>
<p style="color:var(--muted);margin-bottom:24px">Your free airport code lookup tool</p>
<p>Airport-code.com is a free, fast reference site for IATA and ICAO airport codes covering 8,810 airports across 200+ countries.</p>
<h2>What we provide</h2>
<ul>
  <li>IATA and ICAO codes for every airport</li>
  <li>Live weather conditions via Open-Meteo</li>
  <li>Runway details and radio frequencies</li>
  <li>Nearby airports with distances</li>
  <li>Interactive maps for every airport</li>
  <li>Carbon footprint calculator</li>
  <li>Browse by country or A–Z index</li>
</ul>
<h2>Data sources</h2>
<p>Airport data is sourced from <a href="https://ourairports.com">OurAirports</a>, an open-data project. Weather data is provided by <a href="https://open-meteo.com">Open-Meteo</a>.</p>
<h2>Contact</h2>
<p>For enquiries please visit our <a href="/contact.html">contact page</a>.</p>
'''

CONTACT_CONTENT = '''
<h1>Contact Us</h1>
<p style="color:var(--muted);margin-bottom:24px">Get in touch with the Airport Code team</p>
<p>For general enquiries, data corrections, or partnership opportunities, please email us at:</p>
<p><strong><a href="mailto:hello@airport-code.com">hello@airport-code.com</a></strong></p>
<h2>Data corrections</h2>
<p>If you spot an error in our airport data, please email us with the airport IATA code and the correction needed. We aim to respond within 2 business days.</p>
<h2>Link building &amp; partnerships</h2>
<p>If you run an aviation, travel, or logistics website and would like to discuss a link exchange or partnership, we'd love to hear from you.</p>
'''

TERMS_CONTENT = '''
<h1>Terms of Use</h1>
<p style="color:var(--muted);margin-bottom:24px">Last updated: April 2025</p>
<h2>Use of this site</h2>
<p>Airport-code.com provides airport code and travel reference information for personal and commercial use. You may use the information on this site freely, but you may not scrape or reproduce large portions of our data without permission.</p>
<h2>Accuracy</h2>
<p>We strive to keep all information accurate and up to date. However, airport data changes frequently. Always verify critical information — especially for flight planning — with official sources.</p>
<h2>Weather data</h2>
<p>Live weather is provided by Open-Meteo and is for informational purposes only. Do not rely on this data for aviation or safety-critical decisions.</p>
<h2>Links to third parties</h2>
<p>This site contains links to third-party websites. We are not responsible for the content or privacy practices of those sites.</p>
<h2>Changes</h2>
<p>We reserve the right to update these terms at any time. Continued use of the site constitutes acceptance of any changes.</p>
'''

PRIVACY_CONTENT = '''
<h1>Privacy Policy</h1>
<p style="color:var(--muted);margin-bottom:24px">Last updated: April 2025</p>
<h2>Data we collect</h2>
<p>Airport-code.com does not collect personal data. No registration or login is required to use this site.</p>
<h2>Cookies</h2>
<p>This site does not use tracking or advertising cookies. Your cookie consent preference is saved in your browser\'s localStorage only.</p>
<h2>Analytics</h2>
<p>We use Cloudflare\'s built-in analytics which collects anonymised traffic data (page views, country, browser type). No personally identifiable information is stored.</p>
<h2>Third-party services</h2>
<p>Weather data is fetched client-side from <a href="https://open-meteo.com">Open-Meteo</a>. Maps are provided by OpenStreetMap. Neither service receives personal data from you via this site.</p>
<h2>Contact</h2>
<p>For privacy-related enquiries, contact us at <a href="mailto:hello@airport-code.com">hello@airport-code.com</a>.</p>
'''

for slug, title, desc, content in [
    ('about',   'About',          'About airport-code.com — free IATA and ICAO airport code lookup for 8,810 airports worldwide.', ABOUT_CONTENT),
    ('contact', 'Contact',        'Contact the Airport Code team for data corrections, partnerships or general enquiries.', CONTACT_CONTENT),
    ('terms',   'Terms of Use',   'Terms of use for airport-code.com.', TERMS_CONTENT),
    ('privacy', 'Privacy Policy', 'Privacy policy for airport-code.com. We do not collect personal data.', PRIVACY_CONTENT),
]:
    os.makedirs(f"{OUT_DIR}/{slug}", exist_ok=True)
    with open(f"{OUT_DIR}/{slug}/index.html", 'w', encoding='utf-8') as f:
        f.write(static_page(title, desc, content, slug))
    # keep .html version too for any old links
    with open(f"{OUT_DIR}/{slug}.html", 'w', encoding='utf-8') as f:
        f.write(static_page(title, desc, content, slug))

# _redirects — no rules needed, all pages served from index.html in folders
with open(f"{OUT_DIR}/_redirects", 'w') as f:
    f.write("# Cloudflare Pages redirects\n")

total = time.time() - t0
print(f"\nDone! Generated {len(airports)} airport pages + indexes in {total:.0f}s")
print(f"Output: {OUT_DIR}")
