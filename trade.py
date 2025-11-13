import time
import secrets
import re
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
import httpx

# --- CONFIGURATION ---

GEMINI_API_KEY = "AIzaSyAczygDf7ao8GJv4MYOnco1hBMLf-dKtzg"
RATE_LIMIT_PER_MINUTE = 5
RATE_LIMIT_INTERVAL = 60
GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"
API_VERSION = "v1beta"
API_BASE_URL = "https://generativelanguage.googleapis.com"

SESSION_KEYS: Dict[str, Dict[str, Any]] = {}
TEST_API_KEY = secrets.token_hex(16)
SESSION_KEYS[TEST_API_KEY] = {"user_id": "test_user", "created_at": time.time()}
RATE_LIMITER: Dict[str, List[float]] = {}

# --- MODELS ---
class AnalysisReport(BaseModel):
    sector: str
    markdown_report: str
    grounding_sources: List[Dict[str, str]] = []

class AuthStatus(BaseModel):
    api_key: str

class AnalyzeRequest(BaseModel):
    sector: str

# --- EXCEPTIONS ---
class RateLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_PER_MINUTE} requests per {RATE_LIMIT_INTERVAL}s."
        )

class InvalidAPIKey(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key. Use the /auth endpoint to get a key."
        )

# --- DEPENDENCIES ---
def get_current_user_id(api_key: str = Header(..., alias="X-API-Key")) -> str:
    session_data = SESSION_KEYS.get(api_key)
    if not session_data or 'user_id' not in session_data:
        raise InvalidAPIKey()
    return session_data['user_id']

def rate_limit_dependency(user_id: str = Depends(get_current_user_id)):
    current_time = time.time()
    RATE_LIMITER[user_id] = [
        t for t in RATE_LIMITER.get(user_id, []) if t > current_time - RATE_LIMIT_INTERVAL
    ]
    if len(RATE_LIMITER[user_id]) >= RATE_LIMIT_PER_MINUTE:
        raise RateLimitExceeded()
    RATE_LIMITER[user_id].append(current_time)

# --- AI Service ---
class AIService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing.")
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=API_BASE_URL)
        self.endpoint = f"/{API_VERSION}/models/{GEMINI_MODEL}:generateContent"

    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(5), reraise=True)
    async def _make_api_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.endpoint}?key={self.api_key}"
        response = await self.client.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json()

    async def generate_analysis(self, sector: str) -> Dict[str, Any]:
        system_prompt = (
            "You are a top Indian financial analyst. Analyze the current market trends, "
            "growth drivers, and policies for the specified Indian sector. "
            "Output a detailed Markdown report structured as:\n"
            "1. Executive Summary\n2. Market Dynamics\n3. Trade Opportunities\n"
            "4. Regulatory Environment\n5. Risks and Challenges."
        )
        user_query = f"Provide a market analysis for the {sector} sector in India."
        payload = {
            "contents": [{"parts": [{"text": user_query}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"temperature": 0.3},
        }
        try:
            result = await self._make_api_call(payload)
            candidate = result.get('candidates', [{}])[0]
            generated_text = (
                candidate.get('content', {}).get('parts', [{}])[0].get('text', f"No data generated for {sector}.")
            )
            sources = []
            grounding_metadata = candidate.get('groundingMetadata')
            if grounding_metadata and grounding_metadata.get('groundingAttributions'):
                for attr in grounding_metadata['groundingAttributions']:
                    web = attr.get('web', {})
                    if web.get('uri') and web.get('title'):
                        sources.append({'uri': web['uri'], 'title': web['title']})
            return {"markdown_report": generated_text, "grounding_sources": sources}
        except RetryError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="AI service failed after retries.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"External API error: {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Unexpected error: {str(e)}")

try:
    ai_service = AIService(GEMINI_API_KEY)
except ValueError:
    ai_service = None

app = FastAPI(title="Trade Opportunities API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Trade Opportunities API. Visit /docs."}

@app.post("/auth", response_model=AuthStatus)
async def get_api_key():
    new_key = secrets.token_hex(32)
    SESSION_KEYS[new_key] = {"user_id": new_key, "created_at": time.time()}
    return AuthStatus(api_key=new_key)

@app.post("/analyze", response_model=AnalysisReport, dependencies=[Depends(rate_limit_dependency)])
async def analyze_sector(request: AnalyzeRequest):
    sector = request.sector
    if ai_service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="AI Service not initialized.")
    if not (2 <= len(sector) <= 50 and re.match(r"^[A-Za-z0-9&\s]+$", sector)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sector name. Use 2–50 characters (letters, numbers, spaces, & allowed)."
        )
    analysis = await ai_service.generate_analysis(sector.strip())
    return AnalysisReport(sector=sector, **analysis)

if __name__ == "__main__":
    import uvicorn
    print(f"Test API Key (X-API-Key): {TEST_API_KEY}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
