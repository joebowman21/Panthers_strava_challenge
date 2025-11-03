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
import supabase

class StravaAPI:
    def __init__(self):
        self.app = Flask(__name__)
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.redirect_url = os.getenv("REDIRECT_URL")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.client_id or not self.client_secret:
            raise ValueError("❌ Missing STRAVA client_id or STRAVA client_secret environment variables!")
        
        self.supabase = create_client(self.supabase_url, self.supabase_service_role_key)

        self.register_routes()

    def register_routes(self):
        self.app.add_url_rule('/', view_func=self.index)
        self.app.add_url_rule('/callback', view_func=self.callback)
        
    def store_token(self,athlete_id, athlete_name, team, initials, refresh_token):
        """Save or update a user's refresh token in Supabase."""
        self.supabase.table("strava_tokens").upsert({
            "athlete_id": athlete_id,
            "athlete_name": athlete_name,
            "team": team,
            "initials": initials,
            "refresh_token": refresh_token,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }, on_conflict="athlete_id").execute()
            
    def index(self):
        logging.info("Redirecting to Strava authorization URL")
        url = (
            "https://www.strava.com/oauth/authorize"
            f"?client_id={client_id}"
            "&response_type=code"
            f"&redirect_uri={redirect_url}"
            "&scope=read,activity:read_all"
            "&approval_prompt=auto"
        )
        return redirect(url)
            
    def callback(self):
        """Handle OAuth callback and store tokens."""
        logging.info("beginnging call back")
        code = request.args.get('code')
        logging.info(code)
        if not code:
            logging.error("No authorization code found in request")
            return "❌ No authorization code found.", 400
        # Step 1: Exchange code for access token
        logging.info("exchanging code for access token")
        try:
            token_response = requests.post(
                'https://www.strava.com/oauth/token',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': redirect_url 
                }
            ).json()
            token_response.raise_for_status()
            data = token_response.json()
        except Exception as e:
            logging.exception("Error fetching token from Strava")
            return jsonify({"error": str(e)}), 500
                         
        # Save refresh token (e.g., to a file or DB)
        athlete = token_response['athlete']
        self.store_token(
            athlete_id=athlete['id'],
            athlete_name=f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            team="Panthers",     # optional — could make dynamic later
            initials="JB",       # optional — could make dynamic later
            refresh_token=refresh_token
        )
        
        return f"✅ User {athlete_id} connected successfully!"

if __name__ == "__main__":
    api = StravaAPI()
    api.app.run(debug=True)
