import os
import pandas as pd
import requests

# PLACES: Local Data for Better Health, County Data (2025 release, long/tidy format)
API_URL = "https://data.cdc.gov/resource/swc5-untb.json"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "places_county_raw.csv")


def fetch_from_api(limit=250000):
    """Pull the full PLACES county dataset from the Socrata API, no cleaning applied."""
    params = {"$limit": limit}
    response = requests.get(API_URL, params=params)
    response.raise_for_status()
    df = pd.DataFrame(response.json())
    return df


def get_raw_places_data(refresh=False):
    """Load from cache if it exists, otherwise fetch fresh from the API and cache it."""
    if not refresh and os.path.exists(CACHE_PATH):
        return pd.read_csv(CACHE_PATH)

    df = fetch_from_api()
    df.to_csv(CACHE_PATH, index=False)
    return df


if __name__ == "__main__":
    data = get_raw_places_data(refresh=True)
    print(f"Pulled {len(data)} rows.")
    print(data.head())