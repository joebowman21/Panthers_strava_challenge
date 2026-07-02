import os
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
from supabase import create_client, Client

# Strava app credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_all_tokens():
    """Fetch all athlete tokens stored in Supabase."""
    try:
        response = supabase.table("strava_tokens").select("*").execute()
        data = response.data
        if not data:
            print("⚠️ No tokens found in Supabase.")
        return data
    except Exception as e:
        print(f"❌ Error fetching tokens: {e}")
        return []

def get_max_activity_date(athlete_name):
    """Fetch the latest activity start_date from Supabase for a specific athlete."""
    try:
        response = supabase.table("activities") \
            .select("start_date") \
            .eq("athlete", athlete_name) \
            .order("start_date", desc=True) \
            .limit(1) \
            .execute()
        
        data = response.data
        if data and data[0].get("start_date"):
            max_date = pd.to_datetime(data[0]["start_date"]).to_pydatetime()
            return max_date.replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"ℹ️ Could not fetch max date for {athlete_name}: {e}")
    
    # Strictly defaults to Midnight on Day 1 of the challenge
    return datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

def refresh_access_token(refresh_token):
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )
    if response.status_code != 200:
        print(f"❌ Failed to refresh token: {response.text}")
        return None
    return response.json()

def get_activities(access_token, per_page=100):
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"per_page": per_page},
            timeout=15
        )
    except Exception:
        print("⚠️ Timeout or connection issue, trying a second time...")
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"per_page": per_page},
            timeout=20
        )
        
    if response.status_code != 200:
        print(f"❌ Failed to fetch activities: {response.text}")
        return []
    return response.json()

def main(token_data, max_date):
    athlete_name = token_data["athlete_name"]
    refresh_token = token_data["refresh_token"]
    team_name = token_data.get("team", "Unassigned")
    initials = token_data.get("initials", "XX")

    print(f"\n🔄 Refreshing token for {athlete_name} ...")
    new_tokens = refresh_access_token(refresh_token)
    if not new_tokens:
        print(f"❌ Token refresh failed for {athlete_name}.")
        return None

    access_token = new_tokens["access_token"]
    print(f"✅ Access token refreshed for {athlete_name}")
    
    activities = get_activities(access_token)
    if not activities:
        print(f"ℹ️ No activities returned from Strava for {athlete_name}.")
        return None

    df = pd.DataFrame(activities)
    
    df['start_date'] = pd.to_datetime(df['start_date'], utc=True)
    
    # 🔒 Absolute floor setup: Ensures zero activities prior to July 1st can pass
    july_start = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

    if max_date <= july_start:
        most_recent_date = july_start
    else:
        most_recent_date = max_date - timedelta(days=1)
        if most_recent_date < july_start:
            most_recent_date = july_start
    
    # Filter the workouts dynamically against the guardrails
    df_filtered = df[df['start_date'] >= july_start].copy()
    df_filtered = df_filtered[df_filtered['start_date'] >= most_recent_date].copy()
    
    if df_filtered.empty:
        print(f"ℹ️ No new activities for {athlete_name} since {most_recent_date.date()}.")
        return None

    df_filtered = df_filtered[['id', 'sport_type', 'distance', 'moving_time', 'start_date', 'name']]
    df_filtered['start_date_dt'] = df_filtered['start_date'].dt.date
    df_filtered['type'] = 'Unknown'
    
    df_filtered['distance_km'] = (df_filtered['distance'] / 1000).round(2)
    df_filtered['minutes'] = (df_filtered['moving_time'] / 60).round(2)

    df_filtered['pace_min_km'] = df_filtered.apply(
        lambda r: r['minutes'] / r['distance_km'] if r['distance_km'] > 0 else 0, axis=1
    )

    # Expanded mappings to handle Garmin specific Run profiles seamlessly
    sport_mappings = {
        'ride': 'Cycle', 
        'run': 'Run', 
        'trailrun': 'Run',
        'virtualrun': 'Run',
        'swim': 'Swim',
        'tennis': 'Midweek sport', 
        'soccer': 'Midweek sport', 
        'squash': 'Midweek sport',
        'badminton': 'Midweek sport', 
        'rockclimbing': 'Midweek sport', 
        'golf': 'Midweek sport'
    }

    for keyword, mapped_type in sport_mappings.items():
        df_filtered.loc[df_filtered['sport_type'].str.contains(keyword, case=False, na=False), 'type'] = mapped_type

    df_filtered.loc[df_filtered['sport_type'].str.contains('workout|training|weightlifting', case=False, na=False), 'type'] = 'Gym'

    # 📢 VISIBILITY LOG HEADER: Output everything discovered for this specific execution slice
    print(f"📊 Raw activity dump for {athlete_name}:")

    valid_rows = []
    for idx, row in df_filtered.iterrows():
        points_per_km = 0
        flat_points = 0
        activity_code = 'O'
        is_valid = False

        if row['type'] == 'Run':
            if row['distance_km'] >= 2.0 and row['pace_min_km'] <= 7.0:
                points_per_km = 4
                activity_code = 'R'
                is_valid = True

        elif row['type'] == 'Cycle':
            is_lime = 'lime' in str(row['name']).lower()
            if row['distance_km'] >= 2.0 and not is_lime:
                points_per_km = 1.5
                activity_code = 'C'
                is_valid = True

        elif row['type'] == 'Swim':
            points_per_km = 20
            activity_code = 'S'
            is_valid = True

        elif row['type'] == 'Gym':
            if row['minutes'] >= 40.0:
                flat_points = 12
                activity_code = 'G'
                is_valid = True

        elif row['type'] == 'Midweek sport':
            flat_points = 20
            activity_code = 'MS'
            is_valid = True

        # Log entry outcome straight to the standard output console for review
        status_msg = "✅ PASSED & SCORED" if is_valid else "❌ FILTERED OUT (0 pts)"
        print(f"   - Activity: '{row['name']}' | Strava Type: {row['sport_type']} | Mapped As: {row['type']} | Duration: {row['minutes']} mins | Distance: {row['distance_km']} km -> {status_msg}")

        if is_valid:
            calculated_points = (row['distance_km'] * points_per_km) + flat_points
            
            valid_rows.append({
                'strava_activity_id': str(row['id']),
                'initials': initials,
                'athlete': athlete_name,
                'team': team_name,
                'activity': activity_code,
                'distance': row['distance_km'],
                'points': points_per_km if points_per_km > 0 else flat_points,
                'total_points': round(calculated_points, 2),
                'day': row['start_date'].day,
                'start_date_dt': str(row['start_date_dt']),
                'start_date': row['start_date'].strftime('%Y-%m-%dT%H:%M:%SZ')
            })

    if not valid_rows:
        return None

    return pd.DataFrame(valid_rows)

if __name__ == '__main__':
    token_data = get_all_tokens()
    whole_team_results = []
        
    for athlete in token_data:
        athlete_name = athlete["athlete_name"]
        
        max_date = get_max_activity_date(athlete_name)
        print(f"📅 Checking for new activities for {athlete_name} uploaded since: {max_date}")
        
        result = main(athlete, max_date)
        if result is not None and not result.empty:
            whole_team_results.append(result)

    if whole_team_results:
        all_athletes = pd.concat(whole_team_results, ignore_index=True)
        all_athletes = all_athletes.sort_values(by=['start_date', 'athlete'])
        
        all_athletes.columns = all_athletes.columns.str.lower()
        all_athletes['start_date_dt'] = all_athletes['start_date_dt'].astype(str)
        
        records = all_athletes.to_dict(orient='records')
        
        try:
            # 🛡️ DEDUPLICATION LOGIC: Safely upserts row-by-row on individual activity IDs
            supabase.table("activities").upsert(
                records, 
                on_conflict="strava_activity_id"
            ).execute()
            print(f"🎉 Database sync complete. Successfully upserted {len(records)} entries into Supabase!")
        except Exception as e:
            print(f"❌ Failed pushing entries directly to Supabase: {e}")
    else:
        print("ℹ️ No new workouts found for any athlete. Database tables remain current.")
