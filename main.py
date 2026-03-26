from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path
from typing import List
import os

env_path = Path(__file__).resolve().with_name('.env')
load_dotenv(dotenv_path=env_path)

app = FastAPI()


class DealRequest(BaseModel):
    title: str
    imdb_link: str
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

@app.post("/estimate")
def estimate(deal: DealRequest):
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

# Add this new route
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})