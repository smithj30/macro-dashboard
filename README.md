# Macro Dashboard

A Streamlit-based macroeconomic dashboard for exploring, visualizing, and analyzing economic data.

## Features

- **FRED Integration** — search and pull any series from the St. Louis Fed database
- **File Upload** — import CSV or Excel files with automatic date detection
- **Web Scraping** — scrape HTML tables from any URL
- **Zillow Data** — ingest Zillow Home Value and Rent Index CSVs
- **Interactive Charts** — time series overlays, dual y-axes, correlation heatmaps, scatter plots
- **Regression & Analysis** — OLS regression, rolling correlation, YoY/MoM transforms, summary stats
- **Data Catalog** — manage multiple series simultaneously with merge support

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add your FRED API key:
   ```bash
   cp .env.example .env
   # Edit .env and set FRED_API_KEY=your_key_here
   ```
   Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Project Structure

```
macro-dashboard/
├── app.py                        # Main Streamlit entry point
├── requirements.txt
├── .env.example
├── README.md
└── modules/
    ├── data_ingestion/
    │   ├── fred_loader.py        # FRED API integration
    │   ├── file_loader.py        # CSV/Excel upload
    │   ├── web_scraper.py        # HTML table scraping
    │   └── zillow_loader.py      # Zillow CSV parsing
    ├── data_processing/
    │   └── transforms.py         # YoY, MoM, merge utilities
    ├── visualization/
    │   └── charts.py             # Plotly chart builders
    └── analysis/
        └── regression.py         # OLS, rolling correlation, stats
```

## Usage

Navigate using the sidebar:

- **Data Sources** — load data from FRED, files, web scraping, or Zillow CSVs
- **Chart Builder** — build time series, heatmap, or scatter charts from loaded series
- **Regression & Analysis** — run OLS regression, rolling correlation, and compute transforms
- **Data Table** — inspect and export any loaded dataset
