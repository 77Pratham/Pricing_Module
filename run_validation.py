import pandas as pd
import requests
import time

# Fixed deal parameters — only title changes
FIXED_PARAMS = {
    "region": "India",
    "duration": "120 min",
    "license_duration": "1 year",
    "rights_type": "Non-Exclusive",
    "language_rights": "Original only",
    "platforms": ["OTT / Streaming"],
    "imdb_link": "",   # left blank — we don't have IMDB ids in this dataset
    "tmdb_link": ""    # same
}

# Your 20 movies — deduplicated and cleaned
movies = [
    {"title": "Avatar",                              "revenue": 2_787_965_087, "vote_average": 7.2, "category": "Blockbuster"},
    {"title": "Titanic",                             "revenue": 1_845_034_188, "vote_average": 7.5, "category": "Blockbuster"},
    {"title": "The Avengers",                        "revenue": 1_519_557_910, "vote_average": 7.4, "category": "Blockbuster"},
    {"title": "Jurassic World",                      "revenue": 1_513_528_810, "vote_average": 6.5, "category": "Blockbuster"},
    {"title": "Furious 7",                           "revenue": 1_506_249_360, "vote_average": 7.3, "category": "Blockbuster"},
    {"title": "The Shawshank Redemption",            "revenue": 28_341_469,    "vote_average": 8.5, "category": "Mid-range"},
    {"title": "The Godfather: Part II",              "revenue": 47_542_841,    "vote_average": 8.3, "category": "Mid-range"},
    {"title": "Whiplash",                            "revenue": 13_092_000,    "vote_average": 8.3, "category": "Mid-range"},
    {"title": "GoodFellas",                          "revenue": 46_836_394,    "vote_average": 8.2, "category": "Mid-range"},
    {"title": "Psycho",                              "revenue": 32_000_000,    "vote_average": 8.2, "category": "Mid-range"},
    {"title": "Donnie Darko",                        "revenue": 1_270_522,     "vote_average": 7.7, "category": "Low budget"},
    {"title": "12 Angry Men",                        "revenue": 1_000_000,     "vote_average": 8.2, "category": "Low budget"},
    {"title": "Lock Stock and Two Smoking Barrels",  "revenue": 3_897_569,     "vote_average": 7.5, "category": "Low budget"},
    {"title": "Cube",                                "revenue": 501_818,       "vote_average": 6.9, "category": "Low budget"},
    {"title": "I Origins",                           "revenue": 336_472,       "vote_average": 7.5, "category": "Low budget"},
    {"title": "The Godfather",                       "revenue": 245_066_411,   "vote_average": 8.4, "category": "Classic"},
    {"title": "Fight Club",                          "revenue": 100_853_753,   "vote_average": 8.3, "category": "Classic"},
    {"title": "Schindler's List",                    "revenue": 321_365_567,   "vote_average": 8.3, "category": "Classic"},
]

URL = "http://127.0.0.1:8000/estimate"  # local server

results = []

for movie in movies:
    payload = {**FIXED_PARAMS, "title": movie["title"]}

    try:
        print(f"Estimating: {movie['title']}...")
        response = requests.post(URL, json=payload, timeout=30)
        data = response.json()

        flat_fee = data["pricing_estimate"]["flat_fee_range"]
        mg = data["pricing_estimate"]["minimum_guarantee"]
        rev_share = data["pricing_estimate"]["revenue_share_range"]
        confidence = data["confidence_level"]

        results.append({
            "category": movie["category"],
            "title": movie["title"],
            "kaggle_revenue": f"${movie['revenue']:,.0f}",
            "vote_average": movie["vote_average"],
            "flat_fee_range": flat_fee,
            "min_guarantee": mg,
            "revenue_share": rev_share,
            "confidence": confidence,
        })

        print(f"  → {flat_fee} | {confidence}")

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "category": movie["category"],
            "title": movie["title"],
            "kaggle_revenue": f"${movie['revenue']:,.0f}",
            "vote_average": movie["vote_average"],
            "flat_fee_range": "ERROR",
            "min_guarantee": "ERROR",
            "revenue_share": "ERROR",
            "confidence": "ERROR",
        })

    time.sleep(1)  # avoid hammering the API

# Save results
df = pd.DataFrame(results)
df.to_csv("validation_results.csv", index=False)
print("\n--- VALIDATION RESULTS ---")
print(df[["category", "title", "kaggle_revenue", "flat_fee_range", "confidence"]].to_string())
print("\nSaved to validation_results.csv")

# --- RANKING ANALYSIS ---

def parse_lower_bound(fee_str):
    """Extract lower bound number from fee string like 'USD 1.5M - USD 3M'"""
    try:
        # grab the first number
        import re
        fee_str = fee_str.replace(",", "").replace("USD", "").strip()
        first = fee_str.split("-")[0].strip()
        if "M" in first:
            return float(first.replace("M", "")) * 1_000_000
        elif "k" in first:
            return float(first.replace("k", "")) * 1_000
        else:
            return float(first)
    except:
        return 0

df["fee_lower"] = df["flat_fee_range"].apply(parse_lower_bound)

# Sort by kaggle revenue (ground truth) and by our estimate
df["kaggle_revenue_num"] = df["kaggle_revenue"].str.replace("[$,]", "", regex=True).astype(float)

df_sorted_kaggle   = df.sort_values("kaggle_revenue_num", ascending=False).reset_index(drop=True)
df_sorted_estimate = df.sort_values("fee_lower", ascending=False).reset_index(drop=True)

print("\n--- RANK COMPARISON ---")
print(f"{'Rank':<5} {'By Kaggle Revenue':<40} {'By Our Estimate':<40}")
print("-" * 85)
for i in range(len(df)):
    kaggle_title    = df_sorted_kaggle.loc[i, "title"][:38]
    estimate_title  = df_sorted_estimate.loc[i, "title"][:38]
    match = "✅" if kaggle_title == estimate_title else "  "
    print(f"{i+1:<5} {kaggle_title:<40} {estimate_title:<40} {match}")

# Count how many are in the right category tier
print("\n--- CATEGORY TIER CHECK ---")
category_order = ["Blockbuster", "Classic", "Mid-range", "Low budget"]
for cat in category_order:
    avg_fee = df[df["category"] == cat]["fee_lower"].mean()
    print(f"{cat:<15} → avg lower bound: USD {avg_fee:,.0f}")

print("\n--- VERDICT ---")
block_avg = df[df["category"] == "Blockbuster"]["fee_lower"].mean()
mid_avg   = df[df["category"] == "Mid-range"]["fee_lower"].mean()
low_avg   = df[df["category"] == "Low budget"]["fee_lower"].mean()

if block_avg > mid_avg > low_avg:
    print("✅ PASS — Module correctly ranks Blockbuster > Mid-range > Low budget")
elif block_avg > low_avg:
    print("⚠️  PARTIAL — Blockbusters correctly above Low budget but Mid-range ordering off")
else:
    print("❌ FAIL — Module is not correctly ranking by commercial value")