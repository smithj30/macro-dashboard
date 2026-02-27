# US Reindustrialization Dashboard - Complete Implementation Guide

## 🎯 PROJECT OBJECTIVE
Build a comprehensive dashboard tracking America's manufacturing renaissance through real-time economic indicators. Monitor industrial production, investment flows, employment trends, regional surveys, and reshoring activity.

## 🏗️ DASHBOARD LAYOUT

Create a responsive 6-panel grid layout:

```
┌─────────────────────────────────────────┐
│     📊 HEADER METRICS (4 Key KPIs)     │
│  Industrial Production | Employment     │
│  New Orders Growth    | Capacity Util   │
├─────────────────┬─────────────────────────┤
│ 📈 INDUSTRIAL   │ 🏗️ INVESTMENT &        │
│ PRODUCTION      │    CONSTRUCTION        │
│ Line chart      │ Stacked columns        │
│ (10-year view)  │ (Structures, Equipment) │
├─────────────────┼─────────────────────────┤
│ 📊 REGIONAL FED │ 🔮 FORWARD INDICATORS  │
│ SURVEYS         │ New Orders + Surveys    │
│ Multi-line      │ Combo: Line + Bar      │
│ (Philly, ISM)   │ (3-year trends)        │
├─────────────────┼─────────────────────────┤
│ 👥 EMPLOYMENT   │ 🔄 RESHORING TRACKER   │
│ TRENDS          │ Jobs + Recent News      │
│ Area chart      │ Bar chart + Table       │
│ (15-year view)  │ (Annual data)          │
└─────────────────┴─────────────────────────┘
```

## 📊 DATA SOURCES & API INTEGRATION

### FRED API (Primary Source)
```javascript
const FRED_CONFIG = {
  baseUrl: 'https://api.stlouisfed.org/fred/',
  apiKey: process.env.FRED_API_KEY, // User will provide
  endpoints: {
    industrial_production: 'INDPRO',
    capacity_utilization: 'TCU', 
    manufacturing_employment: 'MANEMP',
    new_orders_durable: 'DGORDER',
    new_orders_total: 'AMTMNO',
    construction_manufacturing: 'TLMFGCONS',
    construction_private_mfg: 'MPCV20IXS',
    philly_fed_current: 'GACDFSA066MSFRBPHI',
    philly_fed_future: 'NOFDFSA066MSFRBPHI'
  }
};
```

### BEA API (Investment Data)
```javascript
const BEA_CONFIG = {
  baseUrl: 'https://apps.bea.gov/api/data/',
  apiKey: process.env.BEA_API_KEY, // User will sign up (free)
  dataset: 'FixedAssets',
  tableID: '5.3.5U', // Real Private Fixed Investment
  lineCodes: ['3', '4'], // Structures, Equipment
  frequency: 'Q'
};
```

### Manual Data (Reshoring)
```javascript
const RESHORING_DATA = {
  // Source: https://reshorenow.org/recent-data/
  // Update annually with new reports
  annual_jobs: [
    { year: 2019, jobs: 159000 },
    { year: 2020, jobs: 109000 },
    { year: 2021, jobs: 265000 },
    { year: 2022, jobs: 350000 },
    { year: 2023, jobs: 287000 }
  ]
};
```

## 📈 CHART SPECIFICATIONS

### 1. Header Metrics Panel
Display 4 real-time KPIs with trend indicators:

```javascript
const headerMetrics = [
  {
    title: "Industrial Production",
    dataSource: "FRED:INDPRO",
    format: "index",
    showYoY: true,
    trendColor: "green" // or red based on change
  },
  {
    title: "Manufacturing Employment", 
    dataSource: "FRED:MANEMP",
    format: "millions",
    suffix: "M jobs",
    showYoY: true
  },
  {
    title: "New Orders Growth",
    dataSource: "CALCULATED", // YoY from DGORDER
    format: "percentage",
    suffix: "%",
    showTrend: true
  },
  {
    title: "Capacity Utilization",
    dataSource: "FRED:TCU",
    format: "percentage",
    suffix: "%",
    showYoY: true
  }
];
```

### 2. Industrial Production Chart
```javascript
const industrialProductionChart = {
  type: 'line',
  title: 'US Industrial Production Index',
  subtitle: 'Seasonally Adjusted, 2017=100',
  timeRange: '10_years',
  data: {
    source: 'FRED:INDPRO',
    frequency: 'monthly'
  },
  styling: {
    lineColor: '#1976D2',
    lineWidth: 2,
    showDataPoints: false
  },
  yAxis: {
    title: 'Index (2017=100)',
    startFromZero: false
  },
  annotations: [
    { date: '2020-03', text: 'COVID Impact' },
    { date: '2021-01', text: 'Recovery Begins' },
    { date: '2023-01', text: 'Reindustrialization Era' }
  ]
};
```

### 3. Investment & Construction Chart
```javascript
const investmentChart = {
  type: 'stackedColumn',
  title: 'Manufacturing Investment & Construction',
  subtitle: 'Billions of Dollars, Annualized',
  timeRange: '5_years',
  series: [
    {
      name: 'Structures Investment',
      dataSource: 'BEA:Table_5.3.5_Line3',
      color: '#FF6B35'
    },
    {
      name: 'Equipment Investment',
      dataSource: 'BEA:Table_5.3.5_Line4', 
      color: '#004E89'
    },
    {
      name: 'Construction Spending',
      dataSource: 'FRED:TLMFGCONS',
      color: '#686963'
    }
  ],
  yAxis: {
    title: 'Billions USD',
    format: 'currency'
  }
};
```

### 4. Regional Fed Surveys Chart
```javascript
const regionalSurveysChart = {
  type: 'multiLine',
  title: 'Regional Fed Manufacturing Surveys',
  subtitle: 'Diffusion Indexes - Values >0 Indicate Expansion',
  timeRange: '3_years',
  series: [
    {
      name: 'Philadelphia Fed',
      dataSource: 'FRED:GACDFSA066MSFRBPHI',
      color: '#E91E63'
    },
    {
      name: 'Philadelphia Fed Future',
      dataSource: 'FRED:NOFDFSA066MSFRBPHI',
      color: '#9C27B0',
      lineDash: [5, 5] // dashed line for future
    }
  ],
  yAxis: {
    title: 'Diffusion Index',
    centerOnZero: true
  },
  referenceLines: [
    { value: 0, label: 'Neutral', color: '#999', width: 1 }
  ]
};
```

### 5. Forward Indicators Chart
```javascript
const forwardIndicatorsChart = {
  type: 'combo',
  title: 'Forward-Looking Manufacturing Indicators',
  timeRange: '3_years',
  leftAxis: {
    series: [{
      type: 'line',
      name: 'New Orders YoY Growth (%)',
      dataSource: 'CALCULATED_YOY:DGORDER',
      color: '#4CAF50'
    }],
    title: 'YoY Growth (%)'
  },
  rightAxis: {
    series: [{
      type: 'column',
      name: 'Philly Fed Future Orders',
      dataSource: 'FRED:NOFDFSA066MSFRBPHI',
      color: '#FF9800'
    }],
    title: 'Diffusion Index'
  }
};
```

### 6. Employment Trends Chart
```javascript
const employmentChart = {
  type: 'area',
  title: 'Manufacturing Employment',
  subtitle: 'Thousands of Jobs, Seasonally Adjusted',
  timeRange: '15_years',
  data: {
    source: 'FRED:MANEMP',
    frequency: 'monthly'
  },
  styling: {
    fillColor: '#3F51B5',
    fillOpacity: 0.3,
    lineColor: '#3F51B5'
  },
  yAxis: {
    title: 'Thousands of Jobs',
    format: 'thousands'
  },
  annotations: [
    { dateRange: ['2008-01', '2009-12'], text: 'Great Recession' },
    { dateRange: ['2020-03', '2020-12'], text: 'COVID Impact' },
    { date: '2021-01', text: 'Recovery Begins' }
  ]
};
```

### 7. Reshoring Tracker
```javascript
const reshoringTracker = {
  layout: 'split', // 60% chart, 40% table
  leftPanel: {
    type: 'column',
    title: 'Reshoring & FDI Jobs Announced',
    subtitle: 'Annual Data (Thousands)',
    data: RESHORING_DATA.annual_jobs,
    styling: {
      columnColor: '#2E7D32'
    },
    yAxis: {
      title: 'Jobs Announced (Thousands)',
      format: 'thousands'
    }
  },
  rightPanel: {
    type: 'table',
    title: 'Recent Major Announcements',
    columns: ['Company', 'Jobs', 'Location', 'Industry'],
    data: [
      ['Intel', '3,000', 'Ohio', 'Semiconductors'],
      ['Ford', '2,500', 'Tennessee', 'EV Batteries'], 
      ['GM', '4,000', 'Michigan', 'EV Manufacturing'],
      ['TSMC', '2,000', 'Arizona', 'Semiconductors']
    ],
    maxRows: 8
  }
};
```

## ⚙️ IMPLEMENTATION REQUIREMENTS

### API Integration Functions
```javascript
// Implement these core functions:

async function fetchFREDSeries(seriesId, startDate, endDate) {
  const url = `${FRED_CONFIG.baseUrl}series/observations`;
  const params = {
    series_id: seriesId,
    api_key: FRED_CONFIG.apiKey,
    file_type: 'json',
    observation_start: startDate,
    observation_end: endDate
  };
  // Handle API response, rate limiting, errors
  // Return formatted data array
}

async function fetchBEAData(dataset, tableID, lineCodes, year) {
  const url = `${BEA_CONFIG.baseUrl}`;
  const params = {
    UserID: BEA_CONFIG.apiKey,
    method: 'GetData',
    datasetname: dataset,
    TableID: tableID,
    LineCode: lineCodes.join(','),
    Year: year
  };
  // Handle BEA API response format
  // Return formatted quarterly data
}

function calculateYoYChange(dataArray) {
  // Calculate year-over-year percentage changes
  // Handle missing data gracefully
}

function formatMetricValue(value, format, suffix = '') {
  // Format numbers appropriately (millions, percentages, currency)
}
```

### Dashboard Layout & Styling
```css
/* Responsive grid layout */
.dashboard-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto 1fr 1fr 1fr;
  gap: 20px;
  padding: 20px;
  height: 100vh;
}

.header-metrics {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
}

.metric-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  text-align: center;
}

.metric-value {
  font-size: 2em;
  font-weight: bold;
  color: #1976D2;
}

.metric-change {
  font-size: 0.9em;
  margin-top: 5px;
}

.metric-change.positive { color: #4CAF50; }
.metric-change.negative { color: #F44336; }

.chart-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .dashboard-container {
    grid-template-columns: 1fr;
    grid-template-rows: auto repeat(6, 400px);
  }
  
  .header-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

### Data Refresh Logic
```javascript
class DashboardDataManager {
  constructor() {
    this.lastRefresh = {};
    this.refreshIntervals = {
      fred: 30 * 60 * 1000, // 30 minutes
      bea: 60 * 60 * 1000,  // 1 hour
      manual: 24 * 60 * 60 * 1000 // 24 hours
    };
  }

  async refreshAllData() {
    try {
      // Refresh FRED data
      const fredData = await this.refreshFREDData();
      
      // Refresh BEA data
      const beaData = await this.refreshBEAData();
      
      // Update charts
      this.updateAllCharts(fredData, beaData);
      
      // Update timestamp
      this.updateLastRefreshDisplay();
      
    } catch (error) {
      console.error('Data refresh failed:', error);
      this.showErrorNotification(error.message);
    }
  }

  async refreshFREDData() {
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 15 * 365 * 24 * 60 * 60 * 1000)
      .toISOString().split('T')[0]; // 15 years ago
    
    const promises = Object.entries(FRED_CONFIG.endpoints).map(
      ([key, seriesId]) => fetchFREDSeries(seriesId, startDate, endDate)
        .then(data => ({ [key]: data }))
    );
    
    const results = await Promise.all(promises);
    return Object.assign({}, ...results);
  }
}
```

### Error Handling & User Experience
```javascript
// Implement graceful error handling
function handleAPIError(error, source) {
  console.error(`${source} API Error:`, error);
  
  // Show user-friendly error message
  const errorDiv = document.createElement('div');
  errorDiv.className = 'error-notification';
  errorDiv.innerHTML = `
    <strong>Data Update Failed</strong><br>
    ${source} API temporarily unavailable. 
    Showing cached data from ${getLastRefreshTime(source)}.
    <button onclick="retryRefresh('${source}')">Retry</button>
  `;
  document.body.appendChild(errorDiv);
}

// Add loading states
function showLoadingState(chartId) {
  const chartContainer = document.getElementById(chartId);
  chartContainer.innerHTML = '<div class="loading-spinner">Loading...</div>';
}

// Add data freshness indicators
function updateDataTimestamps() {
  document.querySelectorAll('.chart-panel').forEach(panel => {
    const timestamp = panel.querySelector('.data-timestamp');
    if (timestamp) {
      timestamp.textContent = `Last updated: ${new Date().toLocaleString()}`;
    }
  });
}
```

## 🚀 IMPLEMENTATION CHECKLIST

### Phase 1: Core Setup
- [ ] Set up API key configuration (FRED required, BEA recommended)
- [ ] Create responsive grid layout
- [ ] Implement basic FRED data fetching
- [ ] Build header metrics panel

### Phase 2: Charts Implementation  
- [ ] Industrial Production line chart
- [ ] Manufacturing Employment area chart
- [ ] Investment & Construction stacked chart (needs BEA API)
- [ ] Regional Fed Surveys multi-line chart

### Phase 3: Advanced Features
- [ ] Forward Indicators combo chart
- [ ] Reshoring Tracker with table
- [ ] Data refresh automation
- [ ] Error handling and loading states

### Phase 4: Polish & UX
- [ ] Mobile responsiveness
- [ ] Export functionality (PNG/PDF)
- [ ] Tooltips and data explanations
- [ ] Performance optimization

## 🔑 API SETUP INSTRUCTIONS

### FRED API (Already Have)
- Use existing API key in environment variable: `FRED_API_KEY`

### BEA API (Required for Investment Charts)
1. Go to: https://apps.bea.gov/api/signup/
2. Fill in name/email (2 minutes)
3. Get API key via email
4. Add to environment: `BEA_API_KEY`

### Optional: BLS API
- Only needed if FRED employment data insufficient
- Register at: https://www.bls.gov/developers/

## 📊 SUCCESS METRICS

Dashboard should provide:
✅ Real-time manufacturing health overview  
✅ Historical context (15-year employment, 10-year production)
✅ Investment trends (structures vs equipment)  
✅ Forward-looking indicators (surveys, new orders)
✅ Reshoring progress tracking
✅ Mobile-friendly responsive design

---

**This prompt provides everything needed to build a professional US Reindustrialization Dashboard. Start with the core FRED-based charts, then add BEA investment data for the complete picture.**