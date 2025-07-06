from flask import Flask, request, redirect
import requests
import pandas as pd
import os
import logging
import smtplib
from email.message import EmailMessage

logging.basicConfig(level=logging.INFO)

EMAIL_ADDRESS = 'joebowman21@outlook.com'
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = 'joelbelcher@hotmail.co.uk'
SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 58


# Replace these with your Strava app values

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
            'client_id': '165742',
            'client_secret': '92d0c671ef9b1fd0652eb5ef8de8c12393f2d152',
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://panthers-strava-challenge.onrender.com/callback' 
        }
    ).json()
    print(token_response)
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    athlete_id = token_response['athlete']['id']
    logging.info(access_token)
    logging.info(refresh_token)
    logging.info(athlete_id)
    
    # Save refresh token (e.g., to a file or DB)
    with open('tokens.csv', 'a') as f:
        f.write(f"{athlete_id},{refresh_token}\n")
        
    try:
        send_email_with_attachment(
            subject=f"New Strava token saved for athlete {athlete_id}",
            body=f"Tokens.csv updated with athlete {athlete_id}'s refresh token.",
            to=EMAIL_TO,
            attachment_path='tokens.csv'
        )
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

    return f"✅ User {athlete_id} connected successfully!"

def send_email_with_attachment(subject, body, to, attachment_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to
    msg.set_content(body)

    # Read the file and attach
    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)

    msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

    # Send email via SMTP server
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
