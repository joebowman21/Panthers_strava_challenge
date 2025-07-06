def get_activities(access_token, per_page=30):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers=headers,
        params={'per_page': per_page}
    )
    return response.json()
