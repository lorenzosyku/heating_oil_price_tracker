import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ----------------------------
# CONFIGURATION
# ----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TABLE_NAME = "heating_oil_prices"

# ----------------------------
# SETUP SUPABASE CLIENT
# ----------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# FUNCTION TO GET LATEST DATE IN DB
# ----------------------------
def get_latest_date_in_db():
    """Get the most recent date in the database"""
    try:
        response = supabase.table(TABLE_NAME)\
            .select("date")\
            .order("date", desc=True)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            latest_date = pd.to_datetime(response.data[0]["date"])
            print(f"📅 Latest date in database: {latest_date.strftime('%Y-%m-%d')}")
            return latest_date
        else:
            print("📅 No existing data in database")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching latest date: {e}")
        return None

# ----------------------------
# FUNCTION TO LOAD & CLEAN CSV DATA
# ----------------------------
def fetch_nyserda_datagov():
    url = "https://data.ny.gov/api/views/rc94-5y2u/rows.csv?accessType=DOWNLOAD"
    print(f"📥 Fetching data from NYSERDA...")
    df = pd.read_csv(url)
    
    # Debug: Print column names to see what's available
    print("\n📋 Available columns:")
    print(df.columns.tolist())
    
    # Find the date column
    date_columns = [col for col in df.columns if 'date' in col.lower()]
    if not date_columns:
        potential_date_cols = [col for col in df.columns if any(word in col.lower()
                              for word in ['time', 'period', 'week', 'month', 'year'])]
        print(f"⚠️ No 'date' column found. Potential date columns: {potential_date_cols}")
        if potential_date_cols:
            date_col = potential_date_cols[0]
        else:
            raise ValueError("No date column could be identified")
    else:
        date_col = date_columns[0]
    
    print(f"✅ Using '{date_col}' as the date column")
    
    # Parse and clean date column
    df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df[df["date"].notnull()]
    
    # Drop the original date column to avoid confusion
    if date_col != "date":
        df = df.drop(columns=[date_col])
    
    # Get latest date from database to filter for new data only
    latest_date = get_latest_date_in_db()
    
    if latest_date:
        original_count = len(df)
        df = df[df["date"] > latest_date]
        print(f"🔍 Filtered to {len(df)} new rows (out of {original_count} total)")
        
        if len(df) == 0:
            print("✨ No new data available!")
            return None
    
    # Find all price columns (exclude the date column)
    price_columns = [col for col in df.columns if col != "date" and "average" in col.lower()]
    print(f"📊 Found price columns: {price_columns}")
    
    # Reshape from wide to long format
    df_long = df.melt(
        id_vars=["date"],
        value_vars=price_columns,
        var_name="region_name",
        value_name="price"
    )
    
    # Clean up region names - remove "($/gal)" and standardize
    df_long["region_name"] = df_long["region_name"].str.replace(r"\s*\(\$\/gal\)", "", regex=True)
    
    # Drop rows with null prices
    df_long = df_long[df_long["price"].notnull()]
    
    # Convert price to numeric with 2 decimal places
    df_long["price"] = pd.to_numeric(df_long["price"], errors="coerce").round(2)
    
    # Convert date to string format for JSON serialization
    df_long["date"] = df_long["date"].dt.strftime('%Y-%m-%d')
    
    print(f"\n📈 Prepared data summary:")
    print(f"   - Total rows: {len(df_long)}")
    print(f"   - Regions: {df_long['region_name'].nunique()}")
    print(f"   - Date range: {df_long['date'].min()} to {df_long['date'].max()}")
    print(f"   - Sample regions: {list(df_long['region_name'].unique()[:3])}")
    
    return df_long

# ----------------------------
# FUNCTION TO UPSERT INTO SUPABASE
# ----------------------------
def upsert_data_to_supabase(df):
    """Insert or update data in Supabase using upsert"""
    rows = df.to_dict(orient="records")
    BATCH_SIZE = 500
    
    total_processed = 0
    
    print(f"\n💾 Starting upsert of {len(rows)} rows in batches of {BATCH_SIZE}...")
    
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        batch_num = i//BATCH_SIZE + 1
        
        try:
            # Use upsert to insert new records or update existing ones
            response = supabase.table(TABLE_NAME).upsert(
                batch,
                on_conflict="date,region_name"
            ).execute()
            
            total_processed += len(batch)
            print(f"   ✅ Batch {batch_num}: Processed {len(batch)} rows ({total_processed}/{len(rows)})")
            
        except Exception as e:
            print(f"   ❌ Batch {batch_num}: Error - {e}")
            # Continue with next batch even if one fails
            continue
    
    print(f"\n✨ Upsert complete! Processed {total_processed} rows")
    return total_processed

# ----------------------------
# MAIN SCRIPT
# ----------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🛢️  NYSERDA Heating Oil Price Sync")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Fetch and process data
        df = fetch_nyserda_datagov()
        
        if df is not None and len(df) > 0:
            # Upsert data to Supabase
            upsert_data_to_supabase(df)
            print("\n" + "=" * 60)
            print("✅ Sync completed successfully!")
        else:
            print("\n" + "=" * 60)
            print("ℹ️  No new data to sync")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Script failed: {e}")
        print("Please check the CSV structure and your Supabase connection.")
        import traceback
        traceback.print_exc()
    
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)