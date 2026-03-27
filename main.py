from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional
import os

env_path = Path(__file__).resolve().with_name('.env')
load_dotenv(dotenv_path=env_path)

app = FastAPI()


class DealRequest(BaseModel):
    title: str
    imdb_link: str
    tmdb_link: Optional[str] = ""
    region: str
    duration: str
    rights_type: str
    language_rights: str
    platforms: List[str]

@app.get("/health")
def health():
    return {"message": "Pricing module is running!"}


from groq import Groq

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        f"GROQ_API_KEY is missing; checked {env_path} and environment variables. "
        "Set GROQ_API_KEY in .env or system env before starting uvicorn."
    )

client = Groq(api_key=api_key)


import httpx
import re

def fetch_tmdb_data(tmdb_link: str) -> dict:
    try:
        # Extract movie/tv id from link
        # e.g. https://www.themoviedb.org/movie/299534
        match = re.search(r'/(movie|tv)/(\d+)', tmdb_link)
        if not match:
            return {}
        
        media_type = match.group(1)  # movie or tv
        tmdb_id = match.group(2)
        api_key = os.getenv("TMDB_API_KEY")
        
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={api_key}"
        response = httpx.get(url, timeout=5)
        data = response.json()
        
        return {
            "popularity": data.get("popularity"),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "genres": [g["name"] for g in data.get("genres", [])],
            "budget": data.get("budget"),
            "revenue": data.get("revenue"),
            "status": data.get("status"),
        }
    except Exception:
        return {}


def fetch_omdb_data(omdb_link: str) -> dict:
    try:
        # Extract IMDB id from link
        # e.g. https://www.omdbapi.com/?i=tt4154796
        # OR user might paste imdb link — extract tt id
        match = re.search(r'(tt\d+)', omdb_link)
        if not match:
            return {}
        
        imdb_id = match.group(1)
        api_key = os.getenv("OMDB_API_KEY")
        
        url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
        response = httpx.get(url, timeout=5)
        data = response.json()
        
        return {
            "imdb_rating": data.get("imdbRating"),
            "imdb_votes": data.get("imdbVotes"),
            "box_office": data.get("BoxOffice"),
            "awards": data.get("Awards"),
            "metascore": data.get("Metascore"),
            "rotten_tomatoes": next(
                (r["Value"] for r in data.get("Ratings", []) 
                 if r["Source"] == "Rotten Tomatoes"), None
            ),
        }
    except Exception:
        return {}

@app.post("/estimate")
def estimate(deal: DealRequest):

    # Fetch enrichment data
    tmdb_data = fetch_tmdb_data(deal.tmdb_link) if deal.tmdb_link else {}
    omdb_data = fetch_omdb_data(deal.imdb_link) if deal.imdb_link else {}

    # Build enrichment section for prompt
    enrichment = ""
    if tmdb_data:
        enrichment += f"""
    TMDB Metadata:
    - Popularity score: {tmdb_data.get('popularity')}
    - Vote average: {tmdb_data.get('vote_average')} / 10
    - Vote count: {tmdb_data.get('vote_count')}
    - Genres: {', '.join(tmdb_data.get('genres', []))}
    - Production budget: {tmdb_data.get('budget')}
    - Box office revenue: {tmdb_data.get('revenue')}
    """
    if omdb_data:
        enrichment += f"""
    OMDB Metadata:
    - IMDB Rating: {omdb_data.get('imdb_rating')}
    - IMDB Votes: {omdb_data.get('imdb_votes')}
    - Box Office Gross: {omdb_data.get('box_office')}
    - Awards: {omdb_data.get('awards')}
    - Metascore: {omdb_data.get('metascore')}
    - Rotten Tomatoes: {omdb_data.get('rotten_tomatoes')}
    """

    prompt = f"""
    You are a senior film licensing consultant with deep expertise in content rights deals globally.
    Estimate a licensing price for this deal:

    - Title: {deal.title}
    - IMDB: {deal.imdb_link}
    - Region: {deal.region}
    - Duration: {deal.duration}
    - Rights Type: {deal.rights_type}
    - Language Rights: {deal.language_rights}
    - Platforms: {", ".join(deal.platforms)}

    {f"Real metadata fetched from TMDB and OMDB to inform your estimate:{enrichment}" if enrichment else "No external metadata provided — estimate based on title knowledge only."}
    

    STRICT RULE 1 — MG must always be less than flat fee:
    The minimum_guarantee is a guaranteed floor payment.
    It must ALWAYS be lower than the flat_fee_range.
    Example: if flat fee is USD 500k–2M, MG must be e.g. USD 200k–800k.
    MG higher than flat fee is structurally impossible. Never do this.

    STRICT RULE 2 — Platform value hierarchy (apply discounts):
    - OTT / Streaming → base price (100%)
    - Pay TV → 80–90% of OTT value
    - Free-to-Air TV → 40–60% of OTT value
    - FAST channels (Pluto TV, Tubi, Roku) → 10–25% of OTT value
    - YouTube → 5–15% of OTT value, revenue share dominant

    STRICT RULE 3 — Rights type multiplier:
    - Exclusive rights → 2–3x higher than non-exclusive
    - Original + Dubbed → 20–40% premium over original only

    Return ONLY a JSON object in this exact format, no extra text:
    {{
        "title": "",
        "region": "",
        "pricing_estimate": {{
            "flat_fee_range": "USD X - USD Y",
            "minimum_guarantee": "USD X - USD Y",
            "revenue_share_range": "A% - B%"
        }},
        "confidence_level": "High/Medium/Low",
        "reasoning": "explanation here"
    }}
    """


    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a film licensing consultant. Always respond with valid JSON only. Never add explanations or markdown formatting outside the JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    import json

    result = response.choices[0].message.content

    # Strip markdown fences if model wraps response in ```json ... ```
    result = result.strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
        result = result.strip()

    return json.loads(result)


from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})