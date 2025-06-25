from flask import Flask, request, redirect
import requests
import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO)

# Replace these with your Strava app values
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

app = Flask(__name__)

@app.route('/')
def index():
    logging.info("Redirecting to Strava authorization URL")
    return redirect(
        "https://www.strava.com/oauth/authorize"
        "?client_id=165742"
        "&response_type=code"
        "&redirect_uri=https://panthers-strava-challenge.onrender.com/callback"
        "&scope=read,activity:read_all"
        "&approval_prompt=auto"
    )
    
@app.route('/callback')
def callback():
    code = request.args.get('code')
    logging.info(code)
    if not code:
        logging.error("No authorization code found in request")
        return "❌ No authorization code found.", 400
    # Step 1: Exchange code for access token
    logging.info("exchanging code for access token")
    logging.info(code)
    logging.info(REDIRECT_URI)
    token_response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': '165742',
            'client_secret': 'd0015e5854fc1797ac8997d7bfb455f571ec3376',
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://panthers-strava-challenge.onrender.com/callback' 
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
