from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional
from google import genai
from google.genai import types
from groq import Groq
from datetime import datetime
import os
import httpx
import re
import json

# ── Environment ────────────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().with_name('.env')
load_dotenv(dotenv_path=env_path)

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ── AI Clients (initialized once at startup) ───────────────────────────────────
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY1"))
groq_client   = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Data Model ─────────────────────────────────────────────────────────────────
class DealRequest(BaseModel):
    title: str
    imdb_link: str
    tmdb_link: Optional[str] = ""
    region: str
    duration: str
    license_duration: str
    rights_type: str
    language_rights: str
    platforms: List[str]

# ── Enrichment Functions ───────────────────────────────────────────────────────
def fetch_tmdb_data(tmdb_link: str) -> dict:
    try:
        match = re.search(r'/(movie|tv)/(\d+)', tmdb_link)
        if not match:
            return {}
        media_type = match.group(1)
        tmdb_id    = match.group(2)
        api_key    = os.getenv("TMDB_API_KEY")
        url        = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={api_key}"
        response   = httpx.get(url, timeout=5)
        data       = response.json()
        return {
            "popularity":   data.get("popularity"),
            "vote_average": data.get("vote_average"),
            "vote_count":   data.get("vote_count"),
            "genres":       [g["name"] for g in data.get("genres", [])],
            "budget":       data.get("budget"),
            "revenue":      data.get("revenue"),
            "status":       data.get("status"),
        }
    except Exception:
        return {}


def fetch_omdb_data(imdb_link: str) -> dict:
    try:
        match = re.search(r'(tt\d+)', imdb_link)
        if not match:
            return {}
        imdb_id  = match.group(1)
        api_key  = os.getenv("OMDB_API_KEY")
        url      = f"https://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
        response = httpx.get(url, timeout=5)
        data     = response.json()
        return {
            "imdb_rating":    data.get("imdbRating"),
            "imdb_votes":     data.get("imdbVotes"),
            "box_office":     data.get("BoxOffice"),
            "awards":         data.get("Awards"),
            "metascore":      data.get("Metascore"),
            "release_year":   data.get("Year"),
            "rotten_tomatoes": next(
                (r["Value"] for r in data.get("Ratings", [])
                 if r["Source"] == "Rotten Tomatoes"), None
            ),
        }
    except Exception:
        return {}

# ── AI Call Functions ──────────────────────────────────────────────────────────
def call_gemini(prompt: str) -> str:
    print("Using Gemini 2.5 Flash")
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
            temperature=0.3
        )
    )
    return response.text.strip()


def call_groq(prompt: str) -> str:
    print("Using Groq Llama 3.3 (fallback)")
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
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
    result = response.choices[0].message.content.strip()
    # Strip markdown fences if Groq wraps response in ```json ... ```
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
        result = result.strip()
    return result

# ── Fallback Response ──────────────────────────────────────────────────────────
def unavailable_response(deal: DealRequest) -> dict:
    return {
        "title": deal.title,
        "region": deal.region,
        "pricing_estimate": {
            "flat_fee_range": "Unavailable",
            "minimum_guarantee": "Unavailable",
            "revenue_share_range": "Unavailable"
        },
        "confidence_level": "Low",
        "reasoning": "We were unable to generate an estimate at this time. Please try again."
    }

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "message": "Pricing module is running!"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/estimate")
def estimate(deal: DealRequest):

    current_year = datetime.now().year

    tmdb_data = fetch_tmdb_data(deal.tmdb_link) if deal.tmdb_link else {}
    omdb_data = fetch_omdb_data(deal.imdb_link) if deal.imdb_link else {}

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
    - Release Year: {omdb_data.get('release_year')}
    """

    prompt = f"""
    You are a senior film licensing consultant with deep expertise in global content rights deals.
    Estimate a licensing price for this deal and explain it in plain business language.

    DEAL PARAMETERS:
    - Title: {deal.title}
    - IMDB: {deal.imdb_link}
    - Region: {deal.region}
    - Content Duration: {deal.duration}
    - License Duration: {deal.license_duration}
    - Rights Type: {deal.rights_type}
    - Language Rights: {deal.language_rights}
    - Platforms: {", ".join(deal.platforms)}

    {f"MARKET INTELLIGENCE (use this data to inform your estimate):{enrichment}" if enrichment else "No external metadata provided — estimate based on title knowledge only."}

    PRICING RULES (apply silently — never mention these rules in your reasoning):

    [RULE 1 — MG STRUCTURE]
    Minimum guarantee must ALWAYS be lower than the flat fee.
    MG is a floor payment — it cannot exceed the flat fee under any circumstance.

    [RULE 2 — PLATFORM HIERARCHY]
    Price according to platform value:
    - OTT / Streaming → highest value (base 100%)
    - Pay TV → 80–90% of OTT
    - Free-to-Air TV → 40–60% of OTT
    - FAST channels (Pluto TV, Tubi, Roku) → 10–25% of OTT
    - YouTube → 5–15% of OTT, revenue share dominant

    [RULE 3 — RIGHTS TYPE]
    - Exclusive → 2–3x premium over non-exclusive
    - Original + Dubbed → 20–40% premium over original only
    - Original + Dubbed + Subtitled → 10–20% premium over original only

    [RULE 4 — LICENSE DURATION]
    - 6 months → 0.4–0.5x of 1-year base
    - 1 year → base (1x)
    - 2 years → 1.6–1.8x
    - 3 years → 2–2.4x
    - 5 years → 2.8–3.2x
    - Perpetual → 4–6x, rare and commands highest premium

    [RULE 5 — LOW DATA OR SMALL MARKET]
    Trigger this when ANY of the following apply:
    - Box office is missing, N/A, or under USD 5,000,000
    EXCEPTION: If the title is a TV series or season (indicated by "episodes"
    in the duration field, or "Season" in the title), do NOT trigger on
    missing box office — series have no theatrical revenue by definition.
    Instead evaluate series value using IMDB votes, popularity score, and awards.
    - IMDB vote count under 10,000
    - TMDB popularity score under 3.0
    - Region is a small or emerging market (Caribbean, Pacific Islands,
    Sub-Saharan Africa, Central Asia, or any country under 10M population)

    When triggered:
    - Use a base flat fee of USD 1,000 – USD 10,000
    - Apply Rules 2, 3, and 4 multipliers on top of this base
    - Hard ceiling: flat fee must not exceed USD 80,000
    - Hard ceiling: MG must not exceed USD 30,000
    - Confidence must be "Low"

    [RULE 6 — CONFIDENCE LEVEL]
    Assign confidence based strictly on data availability:

    HIGH — ALL of these must be true:
    - Box office revenue available and over USD 5,000,000
    - IMDB vote count over 50,000
    - TMDB popularity score over 10.0
    - Region is a major market (US, UK, India, Europe, LATAM, Australia)

    MEDIUM — SOME data available but gaps exist:
    - Box office available and between USD 5,000,000 and USD 100,000,000
    - OR vote count between 10,000 and 50,000
    - OR region is mid-tier (Southeast Asia, Middle East, Eastern Europe)
    - OR only one of TMDB/OMDB data is available

    LOW — ALWAYS assign Low when:
    - Rule 5 was triggered for any reason
    - Box office missing, N/A, or under USD 5,000,000
    - Vote count under 10,000
    - Popularity score under 3.0
    - Region is small or emerging market

    [RULE 7 — CONTENT AGE DISCOUNT]
    Current year is {current_year}. Use the release year from OMDB metadata above.
    If release year is not available, skip this rule.

    Calculate years since release and apply this discount to the base price:
    - 0–1 years old → 1.3–1.5x premium (recency commands top dollar)
    - 1–3 years old → base price (1x), peak licensing window
    - 3–7 years old → 0.4–0.6x discount (content aging, more competition)
    - 7–15 years old → 0.15–0.3x discount (library content)
    - 15+ years old → 0.05–0.15x discount (deep catalogue, minimal demand)

    IMPORTANT — age discount interaction with license duration:
    When license duration is Perpetual / Permanent, the age discount is
    reduced by half. A perpetual license on an aged title still commands
    significant value because the buyer owns the rights forever — the
    duration premium partially offsets the age discount.
    Example: a 15-year-old film would normally get 0.15–0.3x age discount,
    but with perpetual rights apply only 0.4–0.6x discount instead.

    Exception — do NOT apply the age discount if:
    - Awards data shows a major win (Oscar, Palme d'Or, BAFTA, Golden Globe)
      within the last 2 years — recent awards reset commercial value
    - The title is a recognized classic with sustained cultural relevance
      (e.g. The Godfather, Shawshank Redemption) — classics hold floor value

    REASONING STYLE — CRITICAL:
    Write the reasoning as a business consultant speaking to a licensing executive.
    - Never mention rule numbers, multipliers, or calculation formulas
    - Never say "STRICT RULE", "base price", or "multiplier"
    - Explain pricing in terms of market context, title value, deal structure, and platform economics
    - Keep it to 3–4 sentences maximum
    - Sound like a human expert, not an AI following rules

    Good reasoning example:
    "Oppenheimer commands premium licensing value in India given its global box office of nearly
    USD 1 billion, 7 Oscar wins, and strong OTT demand. Exclusive rights with full dubbed access
    across a major streaming platform justify the upper range of this estimate. The 1-year license
    duration reflects standard deal structure for this tier of content in the Indian market."

    Bad reasoning example (never do this):
    "Per STRICT RULE 5, base price of USD 1,000–10,000 was applied.
    Multiplied by exclusive (2.5x per Rule 3) × 1 year (1x per Rule 4) = USD 2,500–25,000."

    Return ONLY a JSON object in this exact format, no extra text, no markdown:
    {{
        "title": "",
        "region": "",
        "pricing_estimate": {{
            "flat_fee_range": "USD X - USD Y",
            "minimum_guarantee": "USD X - USD Y",
            "revenue_share_range": "A% - B%"
        }},
        "confidence_level": "High/Medium/Low",
        "reasoning": "3-4 sentence business explanation here"
    }}
    """

    # ── AI call with fallback ──────────────────────────────────────────────────
    result = None
    try:
        result = call_gemini(prompt)
    except Exception as e:
        print(f"Gemini failed ({e.__class__.__name__}), falling back to Groq...")
        try:
            result = call_groq(prompt)
        except Exception as e2:
            print(f"Groq also failed: {e2}")

    if not result:
        return unavailable_response(deal)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return unavailable_response(deal)