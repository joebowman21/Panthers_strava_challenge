##test starter
import requests
from datetime import datetime
import pandas as pd

CLIENT_ID = '165742'
CLIENT_SECRET = '92d0c671ef9b1fd0652eb5ef8de8c12393f2d152'

def refresh_access_token(refresh_token):
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    ).json()
    return response['access_token'], response['refresh_token']

def fetch_today_activities(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    after = int(today.timestamp())

    response = requests.get(
        f'https://www.strava.com/api/v3/athlete/activities?after={after}',
        headers=headers
    )
    return response.json()

def main():
    rows = []
    updated_tokens = []

    with open('tokens.csv', 'r') as f:
        for line in f:
            athlete_id, refresh_token = line.strip().split(',')
            try:
                access_token, new_refresh = refresh_access_token(refresh_token)
                updated_tokens.append((athlete_id, new_refresh))
                activities = fetch_today_activities(access_token)

                for act in activities:
                    rows.append({
                        'Athlete ID': athlete_id,
                        'Name': act.get('name'),
                        'Type': act.get('type'),
                        'Distance (km)': round(act.get('distance', 0) / 1000, 2),
                        'Time (min)': round(act.get('elapsed_time', 0) / 60, 2),
                        'Date': act.get('start_date_local')
                    })
            except Exception as e:
                print(f"Error fetching data for user {athlete_id}: {e}")

    # Save updated tokens
    with open('tokens.csv', 'w') as f:
        for aid, token in updated_tokens:
            f.write(f"{aid},{token}\n")

    # Export to Excel
    df = pd.DataFrame(rows)
    df.to_excel('daily_activities.xlsx', index=False)
    print("✅ Daily activities exported to daily_activities.xlsx")

if __name__ == '__main__':
    main()
