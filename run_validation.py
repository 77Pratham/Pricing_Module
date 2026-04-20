import pandas as pd
import requests
import time

URL = "http://127.0.0.1:8000/estimate"

movies = [
    # Blockbusters — vary platform and rights
    {"title": "Oppenheimer",         "imdb": "https://www.imdb.com/title/tt15398776/", "tmdb": "https://www.themoviedb.org/movie/872585",  "region": "India",         "duration": "180 min",       "license": "1 year",             "rights": "Exclusive",     "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "Oppenheimer",         "imdb": "https://www.imdb.com/title/tt15398776/", "tmdb": "https://www.themoviedb.org/movie/872585",  "region": "India",         "duration": "180 min",       "license": "Perpetual / Permanent","rights": "Exclusive",   "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "Avatar",              "imdb": "https://www.imdb.com/title/tt0499549/",  "tmdb": "https://www.themoviedb.org/movie/19995",   "region": "Europe",        "duration": "162 min",       "license": "3 years",            "rights": "Exclusive",     "language": "Original + Dubbed",             "platforms": ["Pay TV"]},
    {"title": "The Avengers",        "imdb": "https://www.imdb.com/title/tt0848228/",  "tmdb": "https://www.themoviedb.org/movie/24428",   "region": "US & Canada",   "duration": "143 min",       "license": "2 years",            "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["FAST channels"]},
    {"title": "Furious 7",           "imdb": "https://www.imdb.com/title/tt2820852/",  "tmdb": "https://www.themoviedb.org/movie/168259",  "region": "LATAM",         "duration": "137 min",       "license": "1 year",             "rights": "Non-Exclusive", "language": "Original + Dubbed",             "platforms": ["Free-to-Air TV"]},

    # Mid-range — vary region and duration
    {"title": "Whiplash",            "imdb": "https://www.imdb.com/title/tt2582802/",  "tmdb": "https://www.themoviedb.org/movie/244786",  "region": "India",         "duration": "107 min",       "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["OTT / Streaming"]},
    {"title": "GoodFellas",          "imdb": "https://www.imdb.com/title/tt0099685/",  "tmdb": "https://www.themoviedb.org/movie/769",     "region": "Europe",        "duration": "146 min",       "license": "2 years",            "rights": "Exclusive",     "language": "Original + Dubbed + Subtitled", "platforms": ["Pay TV"]},
    {"title": "The Godfather",       "imdb": "https://www.imdb.com/title/tt0068646/",  "tmdb": "https://www.themoviedb.org/movie/238",     "region": "India",         "duration": "175 min",       "license": "5 years",            "rights": "Exclusive",     "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "Schindler's List",    "imdb": "https://www.imdb.com/title/tt0108052/",  "tmdb": "https://www.themoviedb.org/movie/424",     "region": "Europe",        "duration": "195 min",       "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["Free-to-Air TV"]},
    {"title": "Fight Club",          "imdb": "https://www.imdb.com/title/tt0137523/",  "tmdb": "https://www.themoviedb.org/movie/550",     "region": "Southeast Asia","duration": "139 min",       "license": "6 months",           "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["YouTube"]},

    # Low budget / small market
    {"title": "Donnie Darko",        "imdb": "https://www.imdb.com/title/tt0246578/",  "tmdb": "https://www.themoviedb.org/movie/141",     "region": "India",         "duration": "113 min",       "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["FAST channels"]},
    {"title": "Cube",                "imdb": "https://www.imdb.com/title/tt0123755/",  "tmdb": "https://www.themoviedb.org/movie/431",     "region": "Trinidad",      "duration": "90 min",        "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["OTT / Streaming"]},
    {"title": "Maqbool",             "imdb": "https://www.imdb.com/title/tt0347304/",  "tmdb": "",                                         "region": "Trinidad",      "duration": "130 min",       "license": "Perpetual / Permanent","rights": "Exclusive",   "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "I Origins",           "imdb": "https://www.imdb.com/title/tt2884206/",  "tmdb": "https://www.themoviedb.org/movie/225728",  "region": "Caribbean",     "duration": "106 min",       "license": "6 months",           "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["YouTube"]},
    {"title": "12 Angry Men",        "imdb": "https://www.imdb.com/title/tt0050083/",  "tmdb": "https://www.themoviedb.org/movie/389",     "region": "Sub-Saharan Africa","duration": "96 min",    "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["Free-to-Air TV"]},

    # Series
    {"title": "Squid Game Season 1", "imdb": "https://www.imdb.com/title/tt10919420/", "tmdb": "https://www.themoviedb.org/tv/93405",      "region": "India",         "duration": "9 episodes",    "license": "2 years",            "rights": "Exclusive",     "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "Stranger Things S1",  "imdb": "https://www.imdb.com/title/tt4574334/",  "tmdb": "https://www.themoviedb.org/tv/66732",      "region": "LATAM",         "duration": "8 episodes",    "license": "1 year",             "rights": "Non-Exclusive", "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},

    # Same title, different regions — regional pricing test
    {"title": "Parasite",            "imdb": "https://www.imdb.com/title/tt6751668/",  "tmdb": "https://www.themoviedb.org/movie/496243",  "region": "India",         "duration": "132 min",       "license": "1 year",             "rights": "Exclusive",     "language": "Original + Dubbed",             "platforms": ["OTT / Streaming"]},
    {"title": "Parasite",            "imdb": "https://www.imdb.com/title/tt6751668/",  "tmdb": "https://www.themoviedb.org/movie/496243",  "region": "Europe",        "duration": "132 min",       "license": "1 year",             "rights": "Exclusive",     "language": "Original + Dubbed + Subtitled", "platforms": ["OTT / Streaming"]},
    {"title": "Parasite",            "imdb": "https://www.imdb.com/title/tt6751668/",  "tmdb": "https://www.themoviedb.org/movie/496243",  "region": "Caribbean",     "duration": "132 min",       "license": "1 year",             "rights": "Non-Exclusive", "language": "Original only",                 "platforms": ["FAST channels"]},
]

results = []

for i, movie in enumerate(movies):
    payload = {
        "title": movie["title"],
        "imdb_link": movie["imdb"],
        "tmdb_link": movie["tmdb"],
        "region": movie["region"],
        "duration": movie["duration"],
        "license_duration": movie["license"],
        "rights_type": movie["rights"],
        "language_rights": movie["language"],
        "platforms": movie["platforms"]
    }

    try:
        print(f"[{i+1}/20] {movie['title']} — {movie['region']} — {movie['rights']} — {movie['license']}...")
        response = requests.post(URL, json=payload, timeout=120)
        data = response.json()

        results.append({
            "title": movie["title"],
            "region": movie["region"],
            "rights": movie["rights"],
            "license": movie["license"],
            "platform": movie["platforms"][0],
            "language": movie["language"],
            "flat_fee": data["pricing_estimate"]["flat_fee_range"],
            "mg": data["pricing_estimate"]["minimum_guarantee"],
            "rev_share": data["pricing_estimate"]["revenue_share_range"],
            "confidence": data["confidence_level"],
            "reasoning": data["reasoning"]
        })
        print(f"  → {data['pricing_estimate']['flat_fee_range']} | {data['confidence_level']}")

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "title": movie["title"], "region": movie["region"],
            "rights": movie["rights"], "license": movie["license"],
            "platform": movie["platforms"][0], "language": movie["language"],
            "flat_fee": "ERROR", "mg": "ERROR",
            "rev_share": "ERROR", "confidence": "ERROR", "reasoning": str(e)
        })

    time.sleep(2)

df = pd.DataFrame(results)
print("\n--- FULL RESULTS ---")
print(df[["title", "region", "rights", "license", "flat_fee", "confidence"]].to_string())
df.to_csv("validation_20_cases.csv", index=False)
print("\nSaved to validation_20_cases.csv")