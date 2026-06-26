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
    team_name = token_data["team"]
    initials = token_data["initials"]

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
    
    # Target date configuration (ensure UTC matching)
    df['start_date'] = pd.to_datetime(df['start_date'], utc=True)
    most_recent_date = max_date - timedelta(days=1)
    
    # Filter out historical activities
    df_filtered = df[df['start_date'] > most_recent_date].copy()
    if df_filtered.empty:
        print(f"ℹ️ No new activities for {athlete_name} since {most_recent_date.date()}.")
        return None

    # Safe mapping initialization
    df_filtered = df_filtered[['sport_type', 'distance', 'start_date']]
    df_filtered['start_date_dt'] = df_filtered['start_date'].dt.date
    df_filtered['type'] = 'Unknown' # Initialize column to prevent KeyError

    # Categorize Sport Types
    sport_mappings = {
        'ride': 'Cycle', 'training': 'Gym', 'workout': 'Gym', 'run': 'Run', 'swim': 'Swim',
        'tennis': 'Midweek sport', 'soccer': 'Midweek sport', 'squash': 'Midweek sport',
        'badminton': 'Midweek sport', 'rockclimbing': 'Midweek sport', 'golf': 'Midweek sport',
        'walk': 'Walk', 'hike': 'Walk'
    }

    for keyword, mapped_type in sport_mappings.items():
        df_filtered.loc[df_filtered['sport_type'].str.contains(keyword, case=False, na=False), 'type'] = mapped_type

    # Filter out Walks
    df_filtered = df_filtered[df_filtered['type'] != 'Walk']
    if df_filtered.empty:
        return None

    # Distance conversion (Meters to KM)
    df_filtered['distance'] = (df_filtered['distance'] / 1000).round(2)

    # Force flat rates for Gym and Midweek sports
    df_filtered['distance'] = df_filtered.apply(
        lambda row: 1.0 if row['type'] in ['Gym', 'Midweek sport'] else row['distance'], axis=1
    )

    # Points Assignment Logic
    points_map = {'Cycle': 1, 'Run': 4, 'Gym': 12, 'Midweek sport': 20, 'Swim': 16}
    df_filtered['points'] = df_filtered['type'].map(points_map).fillna(0)
    df_filtered['total_points'] = df_filtered['points'] * df_filtered['distance']
    df_filtered['day'] = df_filtered['start_date'].dt.day

    # Shortcode Activity Code mappings
    activity_code_map = {'Cycle': 'C', 'Gym': 'G', 'Run': 'R', 'Swim': 'S', 'Midweek sport': 'MS'}
    df_filtered['activity'] = df_filtered['type'].map(activity_code_map).fillna('O')

    # Drop timezone context safely for Excel compliance
    df_filtered['start_date'] = df_filtered['start_date'].dt.tz_localize(None)
    
    # Metadata injection
    df_filtered["Athlete"] = athlete_name
    df_filtered["Team"] = team_name
    df_filtered["Initials"] = initials

    df_filtered = df_filtered[['Initials', 'Athlete', 'Team', 'activity', 'distance', 'points', 'total_points', 'day', 'start_date_dt', 'start_date']]
    return df_filtered

if __name__ == '__main__':
    token_data = get_all_tokens()
    whole_team_results = []

    excel_filename = "activities.xlsx"

    if os.path.exists(excel_filename):
        existing_df = pd.read_excel(excel_filename)
        # Force conversion to datetime to find max entry safely
        existing_df['start_date'] = pd.to_datetime(existing_df['start_date'])
        max_date = existing_df['start_date'].max()
        if pd.isnull(max_date):
            max_date = datetime(2000, 1, 1)
        # Keep internal script dates timezone-aware (UTC)
        max_date = max_date.replace(tzinfo=timezone.utc)
    else:
        existing_df = pd.DataFrame()
        max_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
        
    for athlete in token_data:
        result = main(athlete, max_date)
        if result is not None and not result.empty:
            whole_team_results.append(result)

    if whole_team_results:
        all_athletes = pd.concat(whole_team_results, ignore_index=True)
        all_athletes = all_athletes.sort_values(by=['start_date_dt', 'Athlete'])
        
        # Combine fresh batch with cached file
        combined_df = pd.concat([existing_df, all_athletes], ignore_index=True)
        
        # Strip out explicit duplicate instances on match bounds
        combined_df = combined_df.drop_duplicates(subset=["Athlete", "start_date_dt", "activity"], keep="last")
        
        # Write updates down
        combined_df.to_excel(excel_filename, index=False)
        print(f"🎉 Code execution successful. File '{excel_filename}' updated with new activities.")
    else:
        print("ℹ️ No new workouts found for any athlete. Spreadsheet remains untouched.")
