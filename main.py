# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI(title="Trade Opportunities Analysis (India)")

# ✅ Allow CORS so Streamlit can call FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for testing, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Authentication endpoint (mock)
@app.post("/auth")
def authenticate():
    # Simulate generating a fake API key
    api_key = "fake_api_key_12345"
    return {"api_key": api_key, "message": "✅ New API Key Generated!"}


# 📊 Model for input validation
class SectorRequest(BaseModel):
    sector: str = Field(..., min_length=2, max_length=50, regex=r'^[A-Za-z0-9\s&-]+$')


# 🧠 Example data (mock sector trends)
sector_trends = {
    "pharmaceuticals": ["Strong R&D growth", "High export potential", "Ayurvedic product expansion"],
    "it": ["AI-driven services booming", "Cloud migration surge", "Automation market growing"],
    "agriculture": ["AgriTech adoption rising", "Organic farming demand", "Export markets expanding"],
    "automobile": ["EV production incentives", "Hybrid demand increase", "Component exports rising"],
}


# 🧩 Analysis endpoint
@app.post("/analyze")
def analyze_sector(request: SectorRequest):
    sector_name = request.sector.strip().lower()
    if sector_name not in sector_trends:
        raise HTTPException(
            status_code=400,
            detail="Invalid sector name. Try Pharmaceuticals, IT, Agriculture, or Automobile.",
        )

    trends = sector_trends[sector_name]
    score = random.randint(60, 95)

    return {
        "sector": request.sector.title(),
        "opportunities": trends,
        "growth_score": score,
        "status": "✅ Analysis completed successfully",
    }
