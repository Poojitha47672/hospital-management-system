import json
import requests as http_requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from .models import GoogleToken

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'

def get_flow():
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/oauth2callback/'
    )
    return flow

def exchange_code_for_tokens(code, code_verifier):
    with open(CREDENTIALS_FILE) as f:
        cred_data = json.load(f)['web']

    response = http_requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': cred_data['client_id'],
        'client_secret': cred_data['client_secret'],
        'redirect_uri': 'http://localhost:8000/oauth2callback/',
        'grant_type': 'authorization_code',
        'code_verifier': code_verifier,
    })
    return response.json(), cred_data

def get_credentials(user):
    try:
        token = GoogleToken.objects.get(user=user)
        creds = Credentials(
            token=token.token,
            refresh_token=token.refresh_token,
            token_uri=token.token_uri,
            client_id=token.client_id,
            client_secret=token.client_secret,
            scopes=json.loads(token.scopes)
        )
        return creds
    except GoogleToken.DoesNotExist:
        return None

def save_credentials_from_token(user, token_data, cred_data):
    access_token = token_data.get('access_token')
    if not access_token:
        print("Token exchange failed:", token_data)
        return
    GoogleToken.objects.update_or_create(
        user=user,
        defaults={
            'token': access_token,
            'refresh_token': token_data.get('refresh_token'),
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': cred_data['client_id'],
            'client_secret': cred_data['client_secret'],
            'scopes': json.dumps(SCOPES)
        }
    )

def save_credentials(user, creds):
    GoogleToken.objects.update_or_create(
        user=user,
        defaults={
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': json.dumps(list(creds.scopes))
        }
    )

def create_calendar_event(creds, title, start_datetime, end_datetime, description=''):
    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': title,
        'description': description,
        'start': {'dateTime': start_datetime},
        'end': {'dateTime': end_datetime}
    }
    service.events().insert(calendarId='primary', body=event).execute()