# 🛢️ Heating Oil Price Tracker - Data Ingestion

Automated data pipeline to sync NYSERDA heating oil prices to Supabase.

## 🚀 Setup

1. **Install dependencies:**
```bash
   pip install -r requirements.txt
```

2. **Configure environment variables:**
   Create a `.env` file:
```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your-service-role-key
```

3. **Create Supabase table:**
```sql
   CREATE TABLE heating_oil_prices (
       id BIGSERIAL PRIMARY KEY,
       date DATE NOT NULL,
       region_name TEXT NOT NULL,
       price NUMERIC(10, 2),
       created_at TIMESTAMPTZ DEFAULT NOW(),
       UNIQUE(date, region_name)
   );
   
   CREATE INDEX idx_heating_oil_date ON heating_oil_prices(date DESC);
   CREATE INDEX idx_heating_oil_region ON heating_oil_prices(region_name);
```

## 🏃 Running Locally
```bash
python nyserda_xls_ingest.py
```

## ⏰ Automated Sync

GitHub Actions runs the sync every Monday at 9 AM UTC.

**Manual trigger:** Go to Actions tab → Sync NYSERDA Heating Oil Data → Run workflow

## 📊 Data Source

- **Source:** NYSERDA (New York State Energy Research and Development Authority)
- **URL:** https://data.ny.gov/Energy-Environment/Heating-Oil-Retail-Prices-Weekly-Average-by-Region/rc94-5y2u
- **Update Frequency:** Weekly

## 🗄️ Database Schema

| Column       | Type         | Description                    |
|--------------|--------------|--------------------------------|
| id           | BIGSERIAL    | Primary key                    |
| date         | DATE         | Price date                     |
| region_name  | TEXT         | NY region name                 |
| price        | NUMERIC(10,2)| Price per gallon (USD)         |
| created_at   | TIMESTAMPTZ  | Record creation timestamp      |

## 🔒 Security

- Environment variables stored in GitHub Secrets
- `.env` file excluded from version control
- Uses Supabase service role key for authentication
```

---

## 🎯 Visual Structure
```
┌─────────────────────────────────────────────────────┐
│  GitHub Repository                                  │
│  ├── .github/workflows/sync-data.yml  (automation) │
│  ├── nyserda_xls_ingest.py           (main script) │
│  ├── requirements.txt                 (packages)   │
│  ├── .gitignore                       (git config) │
│  └── README.md                        (docs)       │
└─────────────────────────────────────────────────────┘
                      │
                      │ (scheduled/manual trigger)
                      ▼
┌─────────────────────────────────────────────────────┐
│  GitHub Actions Runner                              │
│  1. Install Python                                  │
│  2. Install dependencies                            │
│  3. Run nyserda_xls_ingest.py                       │
│     (uses secrets from GitHub)                      │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  NYSERDA Data Source                                │
│  https://data.ny.gov/.../rows.csv                   │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  Supabase Database                                  │
│  Table: heating_oil_prices                          │
└─────────────────────────────────────────────────────┘