import os
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

# ----------------------------
# CONFIGURATION
# ----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
EIA_API_KEY = os.getenv("EIA_API_KEY")
TABLE_NAME = "nymex_prices"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ----------------------------
# SETUP SUPABASE CLIENT
# ----------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# FUNCTION TO GET LATEST DATE IN DB
# ----------------------------
def get_latest_price_from_db():
    """Get the most recent NYMEX price in the database"""
    try:
        response = supabase.table(TABLE_NAME)\
            .select("date, price")\
            .order("date", desc=True)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            latest = response.data[0]
            print(f"📅 Latest price in database: ${latest['price']} on {latest['date']}")
            return latest
        else:
            print("📅 No existing data in database")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching latest price: {e}")
        return None

# ----------------------------
# FUNCTION TO FETCH NYMEX PRICE FROM EIA (WITH RETRY)
# ----------------------------
def fetch_nymex_price_eia():
    """Fetch NYMEX Heating Oil price from EIA API with retry logic"""
    
    if not EIA_API_KEY:
        print("❌ Missing EIA_API_KEY in environment variables")
        print()
        print("📝 Get a free API key:")
        print("   1. Go to: https://www.eia.gov/opendata/")
        print("   2. Click 'Register' in the top right")
        print("   3. Fill out the form (takes 2 minutes)")
        print("   4. Check your email for the API key")
        print("   5. Add EIA_API_KEY=your_key to your .env file")
        print()
        raise ValueError("EIA_API_KEY not found")
    
    print("📡 Fetching NYMEX Heating Oil price from EIA...")
    
    # EIA Series ID for NY Harbor Heating Oil Spot Price FOB ($/gal)
    series_id = "PET.EER_EPLLPA_PF4_Y35NY_DPG.D"
    
    url = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 1
    }
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("response", {}).get("data"):
                raise ValueError("No data returned from EIA")
            
            latest = data["response"]["data"][0]
            price = float(latest["value"])
            date = latest["period"]
            
            print(f"✅ Successfully fetched from EIA (attempt {attempt})")
            print(f"   Price: ${price:.2f}")
            print(f"   Date: {date}")
            
            return {
                "price": round(price, 2),
                "date": date
            }
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 401:
                    print("❌ API key is invalid. Cannot retry.")
                    raise
                elif e.response.status_code == 403:
                    print("❌ API key doesn't have permission. Cannot retry.")
                    raise
            
            if attempt < MAX_RETRIES:
                print(f"⏳ Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ All {MAX_RETRIES} attempts failed")
                raise
                
        except (KeyError, ValueError) as e:
            print(f"❌ Error parsing EIA response: {e}")
            if 'data' in locals():
                print(f"Response data: {data}")
            raise

# ----------------------------
# FUNCTION TO CALCULATE CHANGE
# ----------------------------
def calculate_change(current_price, previous_price):
    """Calculate price change and percentage"""
    if previous_price is None or previous_price == 0:
        return 0, 0
    
    change = current_price - previous_price
    change_percent = (change / previous_price) * 100
    
    return round(change, 2), round(change_percent, 2)

# ----------------------------
# FUNCTION TO UPSERT INTO SUPABASE
# ----------------------------
def upsert_price_to_supabase(price_data):
    """Insert or update NYMEX price in Supabase"""
    
    try:
        print(f"\n💾 Upserting price to Supabase...")
        
        response = supabase.table(TABLE_NAME).upsert(
            price_data,
            on_conflict="date"
        ).execute()
        
        print(f"✅ Successfully saved to database!")
        return response
        
    except Exception as e:
        print(f"❌ Error upserting to Supabase: {e}")
        raise

# ----------------------------
# MAIN SCRIPT
# ----------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🛢️  NYMEX Heating Oil Price Update (EIA Source)")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    try:
        # Get previous price from database
        latest_db = get_latest_price_from_db()
        previous_price = float(latest_db["price"]) if latest_db else None
        
        print()
        
        # Fetch current price from EIA
        current_data = fetch_nymex_price_eia()
        
        current_price = current_data["price"]
        current_date = current_data["date"]
        
        # Calculate change
        change, change_percent = calculate_change(current_price, previous_price)
        
        print()
        print("=" * 60)
        print("💰 Price Information:")
        print(f"   Date: {current_date}")
        print(f"   Current Price: ${current_price:.2f}")
        if previous_price:
            print(f"   Previous Price: ${previous_price:.2f}")
            print(f"   Change: {'+'if change >= 0 else ''}${change:.2f} ({'+'if change_percent >= 0 else ''}{change_percent:.1f}%)")
        print("=" * 60)
        print()
        
        # Prepare data for upsert
        price_data = {
            "date": current_date,
            "price": current_price,
            "change": change,
            "change_percent": change_percent,
            "updated_at": datetime.now().isoformat()
        }
        
        # Upsert to database
        upsert_price_to_supabase(price_data)
        
        print()
        print("=" * 60)
        print("✅ Update completed successfully!")
        print()
        print("📊 Data Source: U.S. Energy Information Administration (EIA)")
        print("📈 Series: NY Harbor Heating Oil Spot Price FOB")
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Script failed: {e}")
        print()
        print("Troubleshooting:")
        print("  • Check that EIA_API_KEY is in your .env file")
        print("  • Verify your Supabase credentials")
        print("  • Make sure the nymex_prices table exists")
        print()
        import traceback
        traceback.print_exc()
        exit(1)
    
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)