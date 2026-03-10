import commentjson as json
import requests
import random
import html

CONFIG_PATH = "/home/pi/unified-orders/appsettings.json"

# -----------------------------
# Load config
# -----------------------------

with open(CONFIG_PATH) as f:
    cfg = json.load(f)

etsy = cfg["Etsy"]

API_KEY = etsy["ApiKey"]
API_SECRET = etsy["ApiSecret"]
REFRESH_TOKEN = etsy["RefreshToken"]
SHOP_ID = etsy["ShopId"]
SHOP_NAME = etsy["ShopName"]

OUTPUT_DIR = "/home/pi/etsy-data"

# -----------------------------
# Refresh Etsy token
# -----------------------------

def refresh_token():

    url = "https://api.etsy.com/v3/public/oauth/token"

    payload = {
        "grant_type": "refresh_token",
        "client_id": API_KEY,
        "client_secret": API_SECRET,
        "refresh_token": REFRESH_TOKEN
    }

    r = requests.post(url, data=payload).json()

    if "access_token" not in r:
        print("Token refresh failed:", r)
        exit()

    return r["access_token"]


ACCESS_TOKEN = refresh_token()

# -----------------------------
# Etsy request headers
# -----------------------------

headers = {
    "x-api-key": f"{API_KEY}:{API_SECRET}",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "User-Agent": "akosin-etsy-sync/1.0"
}

# -----------------------------
# Get shop stats
# -----------------------------

import requests
from bs4 import BeautifulSoup
import json



shop = requests.get(
    f"https://openapi.etsy.com/v3/application/shops/{SHOP_ID}",
    headers=headers
).json()

if "error" in shop:
    print("Shop API error:", shop)
    exit()


stats = {
    "rating": round(shop.get("review_average", 0), 1),
    "sales": shop.get("transaction_sold_count", 0)
}

with open(f"{OUTPUT_DIR}/etsy.json", "w") as f:
    json.dump(stats, f, indent=2)

# -----------------------------
# Get reviews
# -----------------------------

reviews_resp = requests.get(
    f"https://openapi.etsy.com/v3/application/shops/{SHOP_ID}/reviews?limit=50",
    headers=headers
).json()

review_list = []

listing_cache = {}

for r in reviews_resp["results"]:
    rating = r.get("rating", 0)
    text = r.get("review")

    if text:
        text = html.unescape(text).strip()

    if text and rating >= 4:
        listing_id = r.get("listing_id")

        # lookup listing title once and cache it
        if listing_id not in listing_cache:
            listing_resp = requests.get(
                f"https://openapi.etsy.com/v3/application/listings/{listing_id}",
                headers=headers
            ).json()

            raw_title = listing_resp.get("title", "this item")
            listing_cache[listing_id] = html.unescape(raw_title).strip()

        title = listing_cache[listing_id]

        # shorten very long titles
        if len(title) > 45:
            title = title[:42].rstrip() + "..."

        review_list.append({
            "name": "Etsy Customer",
            "product": title,
            "rating": rating,
            "text": text
        })

# Randomize reviews for carousel
review_list = random.sample(review_list, min(20, len(review_list)))

with open(f"{OUTPUT_DIR}/etsy-reviews.json", "w") as f:
    json.dump(review_list, f, indent=2, ensure_ascii=False)

# -----------------------------
# Get recent purchases
# -----------------------------

transactions_resp = requests.get(
    f"https://openapi.etsy.com/v3/application/shops/{SHOP_ID}/receipts?limit=20",
    headers=headers
).json()

recent_orders = []

for r in transactions_resp.get("results", []):

    full_name = r.get("name", "")
    name = full_name.split()[0] if full_name else "Someone"

    for t in r.get("transactions", []):

        title = t.get("title", "an item")

        recent_orders.append({
            "text": f"{name} just purchased {title}"
        })

# Randomize and limit ticker items
recent_orders = random.sample(recent_orders, min(10, len(recent_orders)))

with open(f"{OUTPUT_DIR}/recent-orders.json", "w") as f:
    json.dump({"orders": recent_orders}, f, indent=2)

import subprocess

subprocess.run(["git", "-C", OUTPUT_DIR, "add", "."])
subprocess.run(["git", "-C", OUTPUT_DIR, "commit", "-m", "update etsy stats"])
subprocess.run(["git", "-C", OUTPUT_DIR, "push"])


print("Etsy stats updated.")
