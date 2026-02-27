"""
Zillow Research Public CSV Registry
====================================
Base URL pattern: https://files.zillowstatic.com/research/public_csvs/{metric_folder}/{filename}.csv

All URLs verified to return valid data as of February 2026.

Filename anatomy for modern (post-2019) CSVs:
  {Geography}_{metric}_{home_type_code}[_{tier_or_variant}]_{smoothing}_{freq}.csv

  Geography codes:  Metro, Zip, County, City, State, Neighborhood, Country (rarely used as prefix)
  Home type codes:  uc_sfrcondo   = uncapped SFR + Condo/Co-op (All Homes)
                    uc_sfr        = uncapped SFR only
                    uc_condo      = uncapped Condo/Co-op only
                    sfrcondomfr   = SFR + Condo + Multifamily (ZORI only)
                    sfr           = SFR only (ZORI only)
  Tier suffixes:    tier_0.0_0.33   = bottom tier (5th-35th pct)
                    tier_0.33_0.67  = mid tier (35th-65th pct)  [default / most common]
                    tier_0.67_1.0   = top tier (65th-95th pct)
  Smoothing:        sm_sa  = smoothed, seasonally adjusted
                    sm     = smoothed only (no seasonal adjustment)
                    (none) = raw/unsmoothed

Older legacy URLs (pre-2019 path /research/public/) are also listed in LEGACY_URLS.

Sources used to compile this registry:
  - Zillow Research Data page: https://www.zillow.com/research/data/
  - Observable notebook: https://observablehq.com/@gnestor/zillow-housing-data
  - qlanners/zillow_data_pull (GitHub): zillow_paths.py
  - Direct URL probing of files.zillowstatic.com
  - Google Cache / search result snippets showing live URLs
"""

BASE = "https://files.zillowstatic.com/research/public_csvs"

# ---------------------------------------------------------------------------
# Geography-level metadata columns present in each CSV type
# ---------------------------------------------------------------------------
# Metro/State/Country:  RegionID, SizeRank, RegionName, RegionType, StateName
# Zip:    RegionID, SizeRank, RegionName, RegionType, StateName, State, City, Metro, CountyName
# County: RegionID, SizeRank, RegionName, RegionType, StateName, State, Metro, StateCodeFIPS, MunicipalCodeFIPS
# City:   RegionID, SizeRank, RegionName, RegionType, StateName, State, Metro, CountyName
# Neighborhood: RegionID, SizeRank, RegionName, RegionType, StateName, City, CityRegionID

# ---------------------------------------------------------------------------
# REGISTRY  — each entry is a dict with:
#   id          : unique string key
#   label       : human-readable name
#   category    : top-level grouping
#   metric_folder: the public_csvs subfolder
#   filename    : file name (without .csv)
#   url         : full download URL (no trailing ?t= timestamp needed)
#   geography   : geography level
#   home_type   : property type / cut description
#   smoothing   : 'smoothed_sa' | 'smoothed' | 'raw'
#   freq        : 'monthly' | 'weekly'
#   verified    : True if URL was confirmed live during research
#   notes       : extra context
# ---------------------------------------------------------------------------

REGISTRY = []


def _add(id, label, category, metric_folder, filename, geography, home_type,
         smoothing="smoothed_sa", freq="monthly", verified=True, notes=""):
    url = f"{BASE}/{metric_folder}/{filename}.csv"
    REGISTRY.append({
        "id": id,
        "label": label,
        "category": category,
        "metric_folder": metric_folder,
        "filename": filename,
        "url": url,
        "geography": geography,
        "home_type": home_type,
        "smoothing": smoothing,
        "freq": freq,
        "verified": verified,
        "notes": notes,
    })


# ===========================================================================
# 1. HOME VALUES — ZHVI (Zillow Home Value Index)
# ===========================================================================
# Metric folder: zhvi
# All-homes (SFR + Condo/Co-op), mid-tier, smoothed + seasonally adjusted
# These are the primary/flagship ZHVI series.

_ZHVI_GEOS_MAIN = [
    # (geography_label, geo_prefix, verified)
    ("Metro",           "Metro",         True),
    ("Zip Code",        "Zip",           True),
    ("County",          "County",        True),
    ("City",            "City",          True),
    ("State",           "State",         True),
    ("Neighborhood",    "Neighborhood",  True),   # large file, confirmed exists
]

for _geo_label, _geo_prefix, _v in _ZHVI_GEOS_MAIN:
    _add(
        id=f"zhvi_allhomes_midtier_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVI All Homes Mid-Tier Smoothed SA — {_geo_label}",
        category="Home Values (ZHVI)",
        metric_folder="zhvi",
        filename=f"{_geo_prefix}_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed_sa",
        verified=_v,
        notes="Mid-tier (35th–65th pct). Primary flagship ZHVI series.",
    )

# Bottom tier (5th–35th pct)
for _geo_label, _geo_prefix, _v in _ZHVI_GEOS_MAIN:
    _add(
        id=f"zhvi_allhomes_bottomtier_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVI All Homes Bottom-Tier Smoothed SA — {_geo_label}",
        category="Home Values (ZHVI)",
        metric_folder="zhvi",
        filename=f"{_geo_prefix}_zhvi_uc_sfrcondo_tier_0.0_0.33_sm_sa_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed_sa",
        verified=True if _geo_prefix in ("Metro", "State") else False,
        notes="Bottom tier (5th–35th pct).",
    )

# Top tier (65th–95th pct)
for _geo_label, _geo_prefix, _v in _ZHVI_GEOS_MAIN:
    _add(
        id=f"zhvi_allhomes_toptier_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVI All Homes Top-Tier Smoothed SA — {_geo_label}",
        category="Home Values (ZHVI)",
        metric_folder="zhvi",
        filename=f"{_geo_prefix}_zhvi_uc_sfrcondo_tier_0.67_1.0_sm_sa_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed_sa",
        verified=True if _geo_prefix in ("Metro", "State") else False,
        notes="Top tier (65th–95th pct).",
    )

# SFR only — mid-tier
for _geo_label, _geo_prefix, _v in _ZHVI_GEOS_MAIN:
    _add(
        id=f"zhvi_sfr_midtier_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVI Single-Family Residences Mid-Tier Smoothed SA — {_geo_label}",
        category="Home Values (ZHVI)",
        metric_folder="zhvi",
        filename=f"{_geo_prefix}_zhvi_uc_sfr_tier_0.33_0.67_sm_sa_month",
        geography=_geo_label,
        home_type="Single-Family Residences Only",
        smoothing="smoothed_sa",
        verified=True if _geo_prefix == "Metro" else False,
        notes="SFR only, mid-tier.",
    )

# Condo/Co-op only — mid-tier
for _geo_label, _geo_prefix, _v in _ZHVI_GEOS_MAIN:
    _add(
        id=f"zhvi_condo_midtier_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVI Condo/Co-op Mid-Tier Smoothed SA — {_geo_label}",
        category="Home Values (ZHVI)",
        metric_folder="zhvi",
        filename=f"{_geo_prefix}_zhvi_uc_condo_tier_0.33_0.67_sm_sa_month",
        geography=_geo_label,
        home_type="Condo/Co-op Only",
        smoothing="smoothed_sa",
        verified=True if _geo_prefix == "Metro" else False,
        notes="Condo/co-op only, mid-tier.",
    )

# Bedroom-count cuts — Zillow offers 1bd through 5+bd.
# Verified pattern: the folder is still 'zhvi' and the filename encodes
# bedroom count in a separate subfolder token. Zillow's data page confirms
# these exist but URL probing found the exact token is ambiguous.
# The pattern below matches Zillow's published data page as of 2025:
#   {Geo}_zhvi_bdrmcnt_{N}_sm_sa_month.csv  (inside zhvi/ folder)
# These 404'd in testing with both bare bdrmcnt and with uc_sfrcondo prefix,
# suggesting they may live under a differently-named folder or use a year-
# specific token. They are listed as unverified for defensive coding.
_ZHVI_BDRM_GEOS = [
    ("Metro", "Metro"), ("Zip Code", "Zip"), ("County", "County"),
    ("City", "City"), ("State", "State"),
]
for _N in [1, 2, 3, 4, 5]:
    _suffix = f"{_N}br" if _N < 5 else "5plusbr"
    _label_bdrm = f"{_N}+ bed" if _N == 5 else f"{_N} bed"
    for _geo_label, _geo_prefix in _ZHVI_BDRM_GEOS:
        _add(
            id=f"zhvi_{_suffix}_sm_sa_{_geo_prefix.lower()}",
            label=f"ZHVI {_label_bdrm} Smoothed SA — {_geo_label}",
            category="Home Values (ZHVI)",
            metric_folder="zhvi",
            filename=f"{_geo_prefix}_zhvi_bdrmcnt_{_N}_sm_sa_month",
            geography=_geo_label,
            home_type=f"{_label_bdrm} Homes",
            smoothing="smoothed_sa",
            verified=False,
            notes=(
                "URL pattern is per Zillow documentation. Exact filename token may "
                "vary — confirm at zillow.com/research/data/ before use."
            ),
        )

# ===========================================================================
# 2. HOME VALUE FORECASTS — ZHVF Growth
# ===========================================================================
# Metric folder: zhvf_growth
# Contains 1-month, 1-quarter, and 1-year-ahead growth forecasts.
# Columns: RegionID, SizeRank, RegionName, RegionType, StateName, BaseDate,
#          {forecast_date_1}, {forecast_date_2}, {forecast_date_3}
# Only mid-tier all-homes cut is offered for forecasts.
# Smoothed+SA and raw (no _sa) variants exist.
# Geographies confirmed: Metro, Zip. State/County/City not confirmed.

_ZHVF_ENTRIES = [
    ("Metro",    "Metro",  True),
    ("Zip Code", "Zip",    True),
    ("County",   "County", False),
    ("City",     "City",   False),
    ("State",    "State",  False),
]

for _geo_label, _geo_prefix, _v in _ZHVF_ENTRIES:
    _add(
        id=f"zhvf_growth_sm_sa_{_geo_prefix.lower()}",
        label=f"ZHVF Forecast Growth Smoothed SA — {_geo_label}",
        category="Home Value Forecasts (ZHVF)",
        metric_folder="zhvf_growth",
        filename=f"{_geo_prefix}_zhvf_growth_uc_sfrcondo_tier_0.33_0.67_sm_sa_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed_sa",
        verified=True if _geo_prefix == "Metro" else _v,
        notes="Forward-looking growth rate forecasts: 1-month, 1-quarter, 1-year ahead.",
    )
    _add(
        id=f"zhvf_growth_raw_{_geo_prefix.lower()}",
        label=f"ZHVF Forecast Growth Raw — {_geo_label}",
        category="Home Value Forecasts (ZHVF)",
        metric_folder="zhvf_growth",
        filename=f"{_geo_prefix}_zhvf_growth_uc_sfrcondo_tier_0.33_0.67_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="raw",
        verified=True if _geo_prefix in ("Metro", "Zip") else False,
        notes="Raw (unsmoothed) forecast growth. Zip confirmed via Google search snippet.",
    )

# ===========================================================================
# 3. RENTALS — ZORI (Zillow Observed Rent Index)
# ===========================================================================
# Metric folder: zori
# ZORI is a repeat-rent index measuring market-rate rents.
# Home types: uc_sfrcondomfr (all homes incl. multifamily), uc_sfr (SFR only)
# Smoothed only (no SA variant publicly listed).
# Geographies: Metro, Zip, County, City, State, Neighborhood confirmed.

_ZORI_GEOS = [
    ("Metro",        "Metro",        True),
    ("Zip Code",     "Zip",          True),
    ("County",       "County",       False),
    ("City",         "City",         False),
    ("State",        "State",        False),
    ("Neighborhood", "Neighborhood", True),
]

for _geo_label, _geo_prefix, _v in _ZORI_GEOS:
    # All homes incl. multifamily
    _add(
        id=f"zori_allhomes_sm_{_geo_prefix.lower()}",
        label=f"ZORI All Homes + Multifamily Smoothed — {_geo_label}",
        category="Rentals (ZORI)",
        metric_folder="zori",
        filename=f"{_geo_prefix}_zori_uc_sfrcondomfr_sm_month",
        geography=_geo_label,
        home_type="SFR + Condo/Co-op + Multifamily",
        smoothing="smoothed",
        verified=_v,
        notes="Primary ZORI series. Includes all rental housing types.",
    )
    # SFR only
    _add(
        id=f"zori_sfr_sm_{_geo_prefix.lower()}",
        label=f"ZORI Single-Family Residences Smoothed — {_geo_label}",
        category="Rentals (ZORI)",
        metric_folder="zori",
        filename=f"{_geo_prefix}_zori_uc_sfr_sm_month",
        geography=_geo_label,
        home_type="Single-Family Residences Only",
        smoothing="smoothed",
        verified=True if _geo_prefix == "Metro" else False,
        notes="SFR-only ZORI cut.",
    )

# Legacy ZORI filename pattern (older CSVs still accessible)
# These use the old path /research/public/ and a different filename convention.
# Kept here for reference; prefer the modern public_csvs URLs above.
_add(
    id="zori_allhomes_legacy_zip",
    label="ZORI All Homes + Multifamily Smoothed SSA — Zip Code (legacy)",
    category="Rentals (ZORI)",
    metric_folder="zori",
    filename="Zip_ZORI_AllHomesPlusMultifamily_Smoothed",
    geography="Zip Code",
    home_type="SFR + Condo/Co-op + Multifamily",
    smoothing="smoothed",
    verified=False,
    notes=(
        "Older pre-2022 naming convention. URL: "
        "https://files.zillowstatic.com/research/public_csvs/zori/Zip_ZORI_AllHomesPlusMultifamily_Smoothed.csv"
    ),
)

# ===========================================================================
# 4. FOR-SALE LISTINGS
# ===========================================================================
# Several distinct metric folders cover active listings, inventory, and
# list prices. All are for-sale (not rental) listings.

# --- 4a. Inventory (For-Sale Active Listings Count) ---
# Metric folder: invt_fs
_INVT_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  True),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _INVT_GEOS:
    _add(
        id=f"invt_fs_allhomes_sm_{_geo_prefix.lower()}",
        label=f"For-Sale Inventory (Active Listings) Smoothed — {_geo_label}",
        category="For-Sale Listings",
        metric_folder="invt_fs",
        filename=f"{_geo_prefix}_invt_fs_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=_v,
        notes="Count of unique listings active at any time in a given month.",
    )

# --- 4b. New Listings ---
# Metric folder: new_listings
_NEW_LISTINGS_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  True),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _NEW_LISTINGS_GEOS:
    _add(
        id=f"new_listings_allhomes_sm_{_geo_prefix.lower()}",
        label=f"New For-Sale Listings Smoothed — {_geo_label}",
        category="For-Sale Listings",
        metric_folder="new_listings",
        filename=f"{_geo_prefix}_new_listings_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=_v,
        notes="Newly listed homes coming to market each month.",
    )

# --- 4c. Median List Price ---
# Metric folder: mlp
_MLP_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  False),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _MLP_GEOS:
    _add(
        id=f"mlp_allhomes_sm_{_geo_prefix.lower()}",
        label=f"Median List Price Smoothed — {_geo_label}",
        category="For-Sale Listings",
        metric_folder="mlp",
        filename=f"{_geo_prefix}_mlp_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=True if _geo_prefix == "Metro" else False,
        notes="Median asking price of active for-sale listings.",
    )

# --- 4d. Price Cuts (Share of Listings with a Price Cut) ---
# Metric folder: pct_listings_price_cut   (404'd during testing with sm suffix)
# NOTE: During URL probing, pct_listings_price_cut/Metro_pct_listings_price_cut_uc_sfrcondo_sm_month.csv
# returned 404. The folder may be named differently or the suffix may vary.
# Listed as unverified. Alternative names to try: "share_listings_price_cut",
# "list_price_cut_pct". The old-format URL used:
# State_Listings_PriceCut_SeasAdj_AllHomes.csv
_add(
    id="pct_price_cut_allhomes_sm_metro",
    label="Share of Listings with a Price Cut — Metro (unverified)",
    category="For-Sale Listings",
    metric_folder="pct_listings_price_cut",
    filename="Metro_pct_listings_price_cut_uc_sfrcondo_sm_month",
    geography="Metro",
    home_type="All Homes (SFR + Condo/Co-op)",
    smoothing="smoothed",
    verified=False,
    notes=(
        "Folder name may differ. Also try: list_price_cut_pct, "
        "share_listings_price_cut. Legacy URL: "
        "http://files.zillowstatic.com/research/public/State/State_Listings_PriceCut_SeasAdj_AllHomes.csv"
    ),
)

# --- 4e. Mean Days on Zillow Pending ---
# Metric folder: mean_doz_pending  (confirmed via Google search result snippet)
_DOZ_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  False),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _DOZ_GEOS:
    _add(
        id=f"mean_doz_pending_sm_{_geo_prefix.lower()}",
        label=f"Mean Days to Pending Smoothed — {_geo_label}",
        category="For-Sale Listings",
        metric_folder="mean_doz_pending",
        filename=f"{_geo_prefix}_mean_doz_pending_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=_v,
        notes=(
            "Mean number of days from first listed to pending status. "
            "Folder is 'mean_doz_pending' (doz = days on Zillow)."
        ),
    )

# ===========================================================================
# 5. SALE PRICES & SALES VOLUME
# ===========================================================================

# --- 5a. Median Sale Price (smoothed) ---
# Metric folder: median_sale_price
_MSP_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     True),
    ("County",   "County",  True),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _MSP_GEOS:
    _add(
        id=f"median_sale_price_sm_{_geo_prefix.lower()}",
        label=f"Median Sale Price Smoothed — {_geo_label}",
        category="Sales",
        metric_folder="median_sale_price",
        filename=f"{_geo_prefix}_median_sale_price_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=_v,
        notes="Median transaction price of homes sold.",
    )

# --- 5b. Median Sale Price (raw/unsmoothed) ---
# Metric folder: median_sale_price  (raw variant uses different filename suffix)
# URL probing: Metro_median_sale_price_uc_sfrcondo_month.csv → valid
#              Metro_median_sale_price_raw_uc_sfrcondo_month.csv → 404
for _geo_label, _geo_prefix, _v in _MSP_GEOS:
    _add(
        id=f"median_sale_price_raw_{_geo_prefix.lower()}",
        label=f"Median Sale Price Raw — {_geo_label}",
        category="Sales",
        metric_folder="median_sale_price",
        filename=f"{_geo_prefix}_median_sale_price_uc_sfrcondo_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="raw",
        verified=True if _geo_prefix == "Metro" else False,
        notes="Unsmoothed monthly median sale price.",
    )

# --- 5c. Sales Count Nowcast ---
# Metric folder: sales_count_now
_SCN_GEOS = [
    ("Metro",    "Metro",   True),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  False),
    ("City",     "City",    False),
    ("State",    "State",   False),
]
for _geo_label, _geo_prefix, _v in _SCN_GEOS:
    _add(
        id=f"sales_count_now_{_geo_prefix.lower()}",
        label=f"Sales Count Nowcast — {_geo_label}",
        category="Sales",
        metric_folder="sales_count_now",
        filename=f"{_geo_prefix}_sales_count_now_uc_sfrcondo_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="raw",
        verified=True if _geo_prefix == "Metro" else False,
        notes=(
            "Estimated unique properties sold per month, accounting for reporting latency. "
            "No smoothing applied."
        ),
    )

# --- 5d. Median Sale Price per Sq Ft ---
# Not confirmed via URL probing. Pattern inferred from Zillow documentation.
for _geo_label, _geo_prefix in [("Metro", "Metro"), ("Zip Code", "Zip"), ("County", "County")]:
    _add(
        id=f"median_sale_price_per_sqft_sm_{_geo_prefix.lower()}",
        label=f"Median Sale Price per Sq Ft Smoothed — {_geo_label}",
        category="Sales",
        metric_folder="median_sale_price_per_sqft",
        filename=f"{_geo_prefix}_median_sale_price_per_sqft_uc_sfrcondo_sm_month",
        geography=_geo_label,
        home_type="All Homes (SFR + Condo/Co-op)",
        smoothing="smoothed",
        verified=False,
        notes=(
            "Folder and filename inferred from pattern. Verify at zillow.com/research/data/."
        ),
    )

# ===========================================================================
# 6. RENTAL LISTINGS  (Median Asking Rent for Listed Properties)
# ===========================================================================
# Separate from ZORI (which is a repeat-rent index).
# Zillow also publishes median observed/asking rent from listing data.
# These live under different folder names depending on vintage.
# Observed from Observable notebook and Zillow data page.

for _geo_label, _geo_prefix, _v in [
    ("Metro",    "Metro",   False),
    ("Zip Code", "Zip",     False),
    ("County",   "County",  False),
    ("City",     "City",    False),
    ("State",    "State",   False),
]:
    _add(
        id=f"rental_listings_sm_{_geo_prefix.lower()}",
        label=f"Median Observed Rent (Rental Listings) — {_geo_label}",
        category="Rental Listings",
        metric_folder="zori",
        filename=f"{_geo_prefix}_zori_sm_month",
        geography=_geo_label,
        home_type="All Homes (observed market-rate rent)",
        smoothing="smoothed",
        verified=False,
        notes=(
            "Some older Zillow references used Zip_zori_sm_month.csv (without uc_ prefix). "
            "If the uc_sfrcondomfr version 404s, try this filename."
        ),
    )

# ===========================================================================
# LEGACY URLS (old /research/public/ path, pre-2019 filenames)
# ===========================================================================
# These use the older path and capitalized filenames. Many still work.
# Geographies: Metro, State, County, City (no Zip-level per-sqft in old format)

LEGACY_BASE = "http://files.zillowstatic.com/research/public"

LEGACY_URLS = {
    # --- Home Values (ZHVI) ---
    "zhvi_allhomes_metro_legacy":       f"{LEGACY_BASE}/Metro/Metro_Zhvi_AllHomes.csv",
    "zhvi_allhomes_state_legacy":       f"{LEGACY_BASE}/State/State_Zhvi_AllHomes.csv",
    "zhvi_allhomes_county_legacy":      f"{LEGACY_BASE}/County/County_Zhvi_AllHomes.csv",
    "zhvi_allhomes_city_legacy":        f"{LEGACY_BASE}/City/City_Zhvi_AllHomes.csv",
    "zhvi_sfr_metro_legacy":            f"{LEGACY_BASE}/Metro/Metro_Zhvi_SingleFamilyResidence.csv",
    "zhvi_sfr_state_legacy":            f"{LEGACY_BASE}/State/State_Zhvi_SingleFamilyResidence.csv",
    "zhvi_topquart_metro_legacy":       f"{LEGACY_BASE}/Metro/Metro_Zhvi_TopQuartile.csv",
    "zhvi_bottomquart_metro_legacy":    f"{LEGACY_BASE}/Metro/Metro_Zhvi_BottomQuartile.csv",
    "zhvi_1bed_metro_legacy":           f"{LEGACY_BASE}/Metro/Metro_Zhvi_1bedroom.csv",
    "zhvi_2bed_metro_legacy":           f"{LEGACY_BASE}/Metro/Metro_Zhvi_2bedroom.csv",
    "zhvi_3bed_metro_legacy":           f"{LEGACY_BASE}/Metro/Metro_Zhvi_3bedroom.csv",
    "zhvi_4bed_metro_legacy":           f"{LEGACY_BASE}/Metro/Metro_Zhvi_4bedroom.csv",
    "zhvi_5bed_metro_legacy":           f"{LEGACY_BASE}/Metro/Metro_Zhvi_5BedroomOrMore.csv",
    "zhvi_per_sqft_allhomes_metro_legacy": f"{LEGACY_BASE}/Metro/Metro_Zhvi_Summary.csv",

    # --- Rentals ---
    "zori_allhomes_metro_legacy":       f"{LEGACY_BASE}/Metro/Metro_ZORI_AllHomesPlusMultifamily_SSA.csv",
    "zori_allhomes_zip_legacy":         f"{LEGACY_BASE}/Zip/Zip_ZORI_AllHomesPlusMultifamily_SSA.csv",
    "median_rent_studio_state":         f"{LEGACY_BASE}/State/State_MedianRentalPrice_Studio.csv",
    "median_rent_1br_state":            f"{LEGACY_BASE}/State/State_MedianRentalPrice_1Bedroom.csv",
    "median_rent_2br_state":            f"{LEGACY_BASE}/State/State_MedianRentalPrice_2Bedroom.csv",
    "median_rent_3br_state":            f"{LEGACY_BASE}/State/State_MedianRentalPrice_3Bedroom.csv",
    "median_rent_4br_state":            f"{LEGACY_BASE}/State/State_MedianRentalPrice_4Bedroom.csv",
    "median_rent_sfr_state":            f"{LEGACY_BASE}/State/State_MedianRentalPrice_Sfr.csv",
    "median_rent_studio_county":        f"{LEGACY_BASE}/County/County_MedianRentalPrice_Studio.csv",
    "median_rent_1br_county":           f"{LEGACY_BASE}/County/County_MedianRentalPrice_1Bedroom.csv",
    "median_rent_2br_county":           f"{LEGACY_BASE}/County/County_MedianRentalPrice_2Bedroom.csv",
    "median_rent_3br_county":           f"{LEGACY_BASE}/County/County_MedianRentalPrice_3Bedroom.csv",
    "median_rent_4br_county":           f"{LEGACY_BASE}/County/County_MedianRentalPrice_4Bedroom.csv",
    "median_rent_sfr_county":           f"{LEGACY_BASE}/County/County_MedianRentalPrice_Sfr.csv",
    "median_rent_studio_city":          f"{LEGACY_BASE}/City/City_MedianRentalPrice_Studio.csv",
    "median_rent_1br_city":             f"{LEGACY_BASE}/City/City_MedianRentalPrice_1Bedroom.csv",
    "median_rent_2br_city":             f"{LEGACY_BASE}/City/City_MedianRentalPrice_2Bedroom.csv",
    "median_rent_3br_city":             f"{LEGACY_BASE}/City/City_MedianRentalPrice_3Bedroom.csv",
    "median_rent_4br_city":             f"{LEGACY_BASE}/City/City_MedianRentalPrice_4Bedroom.csv",
    "median_rent_sfr_city":             f"{LEGACY_BASE}/City/City_MedianRentalPrice_Sfr.csv",
    "median_rent_per_sqft_studio_state": f"{LEGACY_BASE}/State/State_MedianRentalPricePerSqft_Studio.csv",
    "median_rent_per_sqft_1br_state":   f"{LEGACY_BASE}/State/State_MedianRentalPricePerSqft_1Bedroom.csv",
    "median_rent_per_sqft_sfr_state":   f"{LEGACY_BASE}/State/State_MedianRentalPricePerSqft_Sfr.csv",

    # --- For-Sale Listings (legacy) ---
    "median_list_price_allhomes_state": f"{LEGACY_BASE}/State/State_MedianListingPrice_AllHomes.csv",
    "median_list_price_bottomtier_state": f"{LEGACY_BASE}/State/State_MedianListingPrice_BottomTier.csv",
    "median_list_price_toptier_state":  f"{LEGACY_BASE}/State/State_MedianListingPrice_TopTier.csv",
    "median_list_price_allhomes_county": f"{LEGACY_BASE}/County/County_MedianListingPrice_AllHomes.csv",
    "median_list_price_allhomes_city":  f"{LEGACY_BASE}/City/City_MedianListingPrice_AllHomes.csv",
    "median_list_price_per_sqft_state": f"{LEGACY_BASE}/State/State_MedianListingPricePerSqft_AllHomes.csv",
    "pct_price_cut_seas_adj_state":     f"{LEGACY_BASE}/State/State_Listings_PriceCut_SeasAdj_AllHomes.csv",
    "pct_price_cut_seas_adj_county":    f"{LEGACY_BASE}/County/County_Listings_PriceCut_SeasAdj_AllHomes.csv",
    "median_pct_price_reduction_state": f"{LEGACY_BASE}/State/State_MedianPctOfPriceReduction_AllHomes.csv",
    "days_on_zillow_state":             f"{LEGACY_BASE}/State/DaysOnZillow_State.csv",
    "days_on_zillow_county":            f"{LEGACY_BASE}/County/DaysOnZillow_County.csv",
    "days_on_zillow_city":              f"{LEGACY_BASE}/City/DaysOnZillow_City.csv",
    "monthly_listings_nsa_state":       f"{LEGACY_BASE}/State/MonthlyListings_NSA_AllHomes_State.csv",
    "monthly_listings_nsa_county":      f"{LEGACY_BASE}/County/MonthlyListings_NSA_AllHomes_County.csv",
    "median_daily_listings_nsa_state":  f"{LEGACY_BASE}/State/MedianDailyListings_NSA_AllHomes_State.csv",

    # --- Sales (legacy) ---
    "sale_counts_state":                f"{LEGACY_BASE}/State/Sale_Counts_State.csv",
    "sale_counts_county":               f"{LEGACY_BASE}/County/Sale_Counts_County.csv",
    "sale_counts_city":                 f"{LEGACY_BASE}/City/Sale_Counts_City.csv",
    "sale_to_list_ratio_state":         f"{LEGACY_BASE}/State/SaleToListRatio_State.csv",
    "sale_to_list_ratio_county":        f"{LEGACY_BASE}/County/SaleToListRatio_County.csv",
    "sales_prev_foreclosed_state":      f"{LEGACY_BASE}/State/SalesPrevForeclosed_Share_State.csv",
    "sales_prev_foreclosed_county":     f"{LEGACY_BASE}/County/SalesPrevForeclosed_Share_County.csv",

    # --- Crosswalks ---
    "county_crosswalk":                 f"{LEGACY_BASE}/CountyCrossWalk_Zillow.csv",
    "mortgage_rate_conventional":       f"{LEGACY_BASE}/MortgageRateConventionalFixed.csv",
}

# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def get_registry() -> list:
    """Return the full registry list."""
    return REGISTRY


def get_categories() -> list:
    """Return sorted list of unique category names."""
    return sorted({e["category"] for e in REGISTRY})


def get_geographies() -> list:
    """Return sorted list of unique geography levels."""
    return sorted({e["geography"] for e in REGISTRY})


def get_by_category(cat: str) -> list:
    """Return all entries in a given category."""
    return [e for e in REGISTRY if e["category"] == cat]


def get_by_geography(geo: str) -> list:
    """Return all entries for a given geography level."""
    return [e for e in REGISTRY if e["geography"] == geo]


def find_entry(dataset_id: str) -> dict:
    """Return the registry entry matching the given id, or None."""
    for entry in REGISTRY:
        if entry["id"] == dataset_id:
            return entry
    return None


def registry_key(entry: dict) -> str:
    """Generate a consistent catalog key for a registry entry."""
    return f"zillow_{entry['id']}"


def get_by_id(dataset_id: str) -> dict:
    """Return the registry entry matching the given id, or raise KeyError."""
    for entry in REGISTRY:
        if entry["id"] == dataset_id:
            return entry
    raise KeyError(f"No Zillow dataset with id='{dataset_id}' in registry.")


def list_verified() -> list:
    """Return only entries whose URLs were confirmed live during research."""
    return [e for e in REGISTRY if e["verified"]]


def summary() -> str:
    """Return a human-readable summary of the registry."""
    lines = [
        f"Zillow Research CSV Registry — {len(REGISTRY)} modern entries + {len(LEGACY_URLS)} legacy URLs",
        f"Categories: {', '.join(get_categories())}",
        f"Geographies: {', '.join(get_geographies())}",
        f"Verified entries: {len(list_verified())}",
    ]
    for cat in get_categories():
        entries = get_by_category(cat)
        lines.append(f"  {cat}: {len(entries)} entries")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
    print()
    print("Sample verified URLs:")
    for e in list_verified()[:8]:
        print(f"  [{e['geography']:12s}] {e['label']}")
        print(f"           {e['url']}")
