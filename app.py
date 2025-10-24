from flask import Flask, request, redirect, send_file
import requests
import pandas as pd
import os
import logging
import smtplib
from email.message import EmailMessage
from supabase import create_client, Client
from cryptography.fernet import Fernet
import os, time

app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URL = os.getenv("REDIRECT_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("❌ Missing STRAVA CLIENT_ID or STRAVA CLIENT_SECRET environment variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def store_token(athlete_id, athlete_name, team, initials, refresh_token):
    """Save or update a user's refresh token in Supabase."""
    supabase.table("strava_tokens").upsert({
        "athlete_id": athlete_id,
        "athlete_name": athlete_name,
        "team": team,
        "initials": initials,
        "refresh_token": refresh_token,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }, on_conflict="athlete_id").execute()

@app.route('/')
def index():
    logging.info("Redirecting to Strava authorization URL")
    return redirect(
        "https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URL}"
        "&scope=read,activity:read_all"
        "&approval_prompt=auto"
    )
    
@app.route('/callback')
def callback():
    logging.info("beginnging call back")
    code = request.args.get('code')
    logging.info(code)
    if not code:
        logging.error("No authorization code found in request")
        return "❌ No authorization code found.", 400
    # Step 1: Exchange code for access token
    logging.info("exchanging code for access token")
    token_response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URL 
        }
    ).json()
    logging.info(token_response)
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    athlete_id = token_response['athlete']['id']
    logging.info(access_token)
    logging.info(refresh_token)
    logging.info(athlete_id)
    
    # Save refresh token (e.g., to a file or DB)
    athlete = token_response['athlete']
    store_token(
    athlete_id=athlete['id'],
    athlete_name=f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
    team="Panthers",     # optional — could make dynamic later
    initials="JB",       # optional — could make dynamic later
    refresh_token=refresh_token
)

    return f"✅ User {athlete_id} connected successfully!"
