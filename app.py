from flask import Flask, request, redirect, send_file
import requests
import pandas as pd
import os
import logging
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("SECRET_ID")
REDIRECT_URL = os.getenv("REDIRECT_URL")


if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("❌ Missing STRAVA CLIENT_ID or STRAVA CLIENT_SECRET environment variables!")

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
    with open('tokens.csv', 'a') as f:
        f.write(f"{athlete_id},{refresh_token}\n")

    return f"✅ User {athlete_id} connected successfully!"
    
@app.route('/download-tokens')
def download_tokens():
    try:
        return send_file('tokens.csv', mimetype='text/csv', as_attachment=True, download_name='tokens.csv')
    except Exception as e:
        logging.error(f"Error sending tokens.csv file: {e}")
        return "Failed to download file", 500