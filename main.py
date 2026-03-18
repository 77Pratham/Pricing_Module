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
    You are a film licensing consultant. Estimate a licensing price for this deal:

    - Title: {deal.title}
    - IMDB: {deal.imdb_link}
    - Region: {deal.region}
    - Duration: {deal.duration}
    - Rights Type: {deal.rights_type}
    - Language Rights: {deal.language_rights}
    - Platforms: {", ".join(deal.platforms)}

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
        messages=[{"role": "user", "content": prompt}]
    )

    import json
    result = response.choices[0].message.content
    return json.loads(result)


from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")

# Add this new route
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})