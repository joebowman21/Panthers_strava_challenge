import pandas as pd
import requests
import os
import json
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# Your Strava app credentials
# CLIENT_ID = os.getenv("CLIENT_ID")
# CLIENT_SECRET = os.getenv("SECRET_ID")
CLIENT_ID = '165742'
CLIENT_SECRET = '92d0c671ef9b1fd0652eb5ef8de8c12393f2d152'
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
    print(CLIENT_ID)
    print(CLIENT_SECRET)
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        proxies={"https": None}
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
    )
    except:
        print("trying a second time")
        response = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers=headers,
        params={"per_page": per_page},
    )
    if response.status_code != 200:
        print(f"❌ Failed to fetch activities: {response.text}")
        return []
    # response_2 = requests.get(
    #     "https://www.strava.com/api/v3/athlete",
    #     headers=headers,
    #     params={"per_page": per_page},
    # )
    # print(response_2.json())
    return response.json()

def main(token_data,max_date):
    # Load JSON (single athlete)

    athlete_name = token_data["athlete_name"]
    refresh_token = token_data["refresh_token"]
    team_name = token_data["Team"]
    initials = token_data["initials"]

    print(f"\n🔄 Refreshing token for {athlete_name} ...")
    new_tokens = refresh_access_token(refresh_token)
    if not new_tokens:
        print("❌ Token refresh failed.")
        return

    access_token = new_tokens["access_token"]
    print(f"✅ Access token refreshed for {athlete_name}")
    activities = get_activities(access_token)
    df = pd.DataFrame(activities)
    df['start_date'] = pd.to_datetime(df['start_date'])

    # Get the most recent date (date only, no time)
    most_recent_date = max_date - timedelta(days=1)
    # Filter activities to only those on the most recent date
    df_filtered = df[df['start_date'] > most_recent_date].copy()

    # Select and clean columns
    df_filtered = df_filtered[['sport_type', 'distance', 'start_date']]
    df_filtered['start_date_dt'] = df_filtered['start_date'].dt.date
    df_filtered.loc[df_filtered['sport_type'].str.contains('ride', case=False, na=False), 'type'] = 'Cycle'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Training', case=False, na=False), 'type'] = 'Gym'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Workout', case=False, na=False), 'type'] = 'Gym'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Run', case=False, na=False), 'type'] = 'Run'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Swim', case=False, na=False), 'type'] = 'Swim'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Tennis', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Soccer', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Squash', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Badminton', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('RockClimbing', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Golf', case=False, na=False), 'type'] = 'Midweek sport'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Walk', case=False, na=False), 'type'] = 'Walk'
    df_filtered.loc[df_filtered['sport_type'].str.contains('Hike', case=False, na=False), 'type'] = 'Walk'
    df_filtered = df_filtered[df_filtered['type']!= 'Walk']
    df_filtered['distance'] = (df_filtered['distance'] / 1000).round(2)
    print(df_filtered['type'])
    print(df_filtered['sport_type'])
    df_filtered['distance'] = df_filtered.apply(
    lambda row: 1 if 'gym' in row['type'].lower() else 1 if 'midweek sport' in row['type'].lower() else row['distance'],
    axis=1
)
    df_filtered['points'] = df_filtered['type'].apply(
    lambda x: 1 if 'cycle' in x.lower() else 4 if 'run' in x.lower() else 12 if 'gym' in x.lower() else 20 if 'midweek sport' in x.lower() else 16 if 'swim' in x.lower() else 0
)
    df_filtered['total_points'] = df_filtered.apply(
        lambda row: row['points'] * row['distance'], axis=1
    )
    df_filtered['day'] = df_filtered['start_date'].dt.day
    df_filtered.loc[df_filtered['type'].str.contains('Cycle', case=False, na=False), 'activity'] = 'C'
    df_filtered.loc[df_filtered['type'].str.contains('Gym', case=False, na=False), 'activity'] = 'G'
    df_filtered.loc[df_filtered['type'].str.contains('Workout', case=False, na=False), 'activity'] = 'G'
    df_filtered.loc[df_filtered['type'].str.contains('Run', case=False, na=False), 'activity'] = 'R'
    df_filtered.loc[df_filtered['type'].str.contains('Swim', case=False, na=False), 'activity'] = 'S'
    df_filtered.loc[df_filtered['type'].str.contains('Midweek sport', case=False, na=False), 'activity'] = 'MS'
    
    df_filtered['start_date'] = pd.to_datetime(df_filtered['start_date']).dt.tz_localize(None)
    df_filtered["Athlete"] = athlete_name
    df_filtered["Team"] = team_name
    df_filtered["Initials"] = initials
    df_filtered = df_filtered[['Initials','Athlete','Team', 'activity', 'distance','points','total_points','day', 'start_date_dt','start_date']]
    print(df_filtered)
    return df_filtered

    # print(f"\n📋 Activities for {athlete_name} ({len(activities)} found):")
    # data=[]
    # for a in activities:
    #     data.append(f"- {a['type']} | {a['distance']} meters | {a['start_date']}")
    # print(data)

if __name__ == '__main__':
    token_data = get_all_tokens ()
    logging.info(token_data)

    whole_team_results = []

    if os.path.exists('activities.xlsx'):
        df = pd.read_excel('activities.xlsx')
        df['start_date'] = pd.to_datetime(df['start_date'], utc = True)
        max_date = df['start_date'].max()
      
    else:
        df = pd.DataFrame()
        max_date =  datetime(2000, 1, 1, tzinfo=timezone.utc)
        
    for athlete in token_data:
        result = main(athlete,max_date)
        print(result)
        whole_team_results.append(result)

    all_athletes = pd.concat(whole_team_results, ignore_index=True)
    all_athletes = all_athletes.sort_values(by=['start_date_dt','Athlete'])
    # print(all_athletes)
    excel_filename = f"activities.xlsx"
    # print(whole_team_results)
    # print(df)
    # --- Read existing data if it exists ---
    if os.path.exists(excel_filename):
        existing_df = pd.read_excel(excel_filename)
    else:
        existing_df = pd.DataFrame()

    # --- Combine new + old ---
    combined_df = pd.concat([existing_df, all_athletes], ignore_index=True)

    # --- Drop duplicates (if needed) ---
    # For example, if an athlete already has an entry for the same date & activity
    combined_df = combined_df.drop_duplicates(subset=["Athlete", "start_date_dt", "activity"], keep="last")

    # --- Save back to file ---
    combined_df.to_excel(excel_filename, index=False)
