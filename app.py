from flask import Flask, request, redirect
import requests
import pandas as pd
import os

# Replace these with your Strava app values
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

app = Flask(__name__)

@app.route('/')
def index():
    return redirect(
        f"https://www.strava.com/oauth/authorize?client_id=165742"
        f"&response_type=code&redirect_uri={REDIRECT_URI}"
        f"&scope=read,activity:read_all&approval_prompt=auto"
    )

@app.route('/callback')
def callback():
    code = request.args.get('code')

    # Step 1: Exchange code for access token
    token_response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': '165743',
            'client_secret': 'd0015e5854fc1797ac8997d7bfb455f571ec3376',
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI 
        }
    ).json()
    print(token_response)
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    athlete_id = token_response['athlete']['id']

    # Save refresh token (e.g., to a file or DB)
    with open('tokens.csv', 'a') as f:
        f.write(f"{athlete_id},{refresh_token}\n")

    return f"✅ User {athlete_id} connected successfully!"

    # Step 2: Fetch activities
    activities_response = requests.get(
        'https://www.strava.com/api/v3/athlete/activities',
        headers={'Authorization': f'Bearer {access_token}'}
    ).json()

    # Step 3: Extract and format activity data
    activities = []
    for act in activities_response:
        activities.append({
            'Name': act.get('name'),
            'Type': act.get('type'),
            'Distance (km)': round(act.get('distance', 0) / 1000, 2),
            'Time (min)': round(act.get('elapsed_time', 0) / 60, 2),
            'Date': act.get('start_date_local')
        })

    df = pd.DataFrame(activities)
    df.to_excel('strava_activities.xlsx', index=False)

    return '✅ Activities fetched and exported to Excel (strava_activities.xlsx). You can close this tab.'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Render provides the correct port
    app.run(host='0.0.0.0', port=port)
