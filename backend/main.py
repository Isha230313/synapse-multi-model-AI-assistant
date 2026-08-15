"""
Synapse - Backend API
"""

from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
import os
import re
import json
import base64
from datetime import datetime, timezone
from dotenv import load_dotenv
import traceback
import httpx

# Local imports
from logger_config import logger
from models import PersonProfile
from services.pdf_service import PDFService
from services.ai_service import get_person_profile_full, llm_service
from services.email_service import EmailService
from services.kafka_service import kafka_service
from services.db_service import (
    connect_mongo, disconnect_mongo, is_mongo_available,
    mongo_save_entry, mongo_get_history, mongo_clear_history,
    mongo_save_profile,
    connect_redis, disconnect_redis,
    cache_get_profile, cache_set_profile,
)
from services.llm import LLMProviderType, ChatMessage as LLMChatMessage


# -------------------------------------
# Load environment variables
# -------------------------------------
# Load .env from backend directory (override=True to ensure fresh load)
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path, override=True)

# -------------------------------------
# Bearer Token Authentication
# -------------------------------------
# Get API bearer token from environment
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "")

# HTTPBearer security scheme - auto_error=False to handle missing tokens ourselves
security = HTTPBearer(auto_error=False)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    """
    Verify bearer token from Authorization header.
    Raises HTTPException if token is invalid or missing.
    """
    if not credentials:
        logger.warning("❌ No Authorization header provided")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated: Missing Authorization header. Please provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    if not API_BEARER_TOKEN:
        logger.error("❌ API_BEARER_TOKEN not set in environment. Authentication required but not configured.")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured. Please contact administrator.",
        )
    
    if not token:
        logger.warning("❌ Empty bearer token provided")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated: Empty bearer token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if token != API_BEARER_TOKEN:
        logger.warning(f"❌ Invalid bearer token attempted: {token[:10] if len(token) > 10 else token}...")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated: Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"✅ Valid bearer token authenticated")
    return token

# -------------------------------------
# Pydantic Models
# -------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_history: Optional[List[Dict[str, str]]] = Field(default=None, description="Previous conversation messages for context")

class ChatResponse(BaseModel):
    message: str
    source: str
    pdf_data: Optional[str] = None
    pdf_type: Optional[str] = None
    person_data: Optional[Dict[str, Any]] = None

class PersonPDFRequest(BaseModel):
    person_name: str = Field(..., description="Name of the person for PDF generation")

class EmailRequest(BaseModel):
    email: str = Field(..., description="Recipient email address")
    person_name: str = Field(..., description="Name of the person for PDF generation")
    subject: Optional[str] = Field(None, description="Email subject (optional)")
    message: Optional[str] = Field(None, description="Additional message in email body (optional)")

class EmailTextRequest(BaseModel):
    email: str = Field(..., description="Recipient email address")
    subject: Optional[str] = Field(None, description="Email subject (optional)")
    body: str = Field(..., description="Email body text to send")



# -------------------------------------
# Extract Person Name (PDF)
# -------------------------------------
def extract_pdf_person_name(message: str) -> Optional[str]:
    message = message.lower().strip()

    pattern = r"(?:pdf of|pdf on|generate pdf|create pdf|make pdf)\s+([a-zA-Z ]+)"
    match = re.search(pattern, message, re.IGNORECASE)

    if match:
        name = match.group(1).strip()
        if len(name) > 1:
            return name
    return None


# -------------------------------------
# Extract Person Name (Search)
# -------------------------------------
def extract_search_person_name(message: str) -> Optional[str]:
    """Extract person name from message. Returns None if it's not clearly a person search."""
    message = message.strip()
    message_lower = message.lower()
    
    # Skip if it's clearly a general question (not person-related)
    general_question_indicators = [
        "what is", "what are", "how to", "how do", "why", "when", "where",
        "explain", "define", "calculate", "solve", "write", "code", "program",
        "difference between", "compare", "which", "should i", "can you help",
        "help me", "how does", "how can", "what does", "what do"
    ]
    
    # If it starts with a general question indicator, it's likely not a person search
    if any(message_lower.startswith(indicator) for indicator in general_question_indicators):
        return None
    
    # Skip if it contains technical/programming keywords
    technical_keywords = [
        "python", "javascript", "code", "function", "variable", "api", "database",
        "algorithm", "programming", "syntax", "error", "bug", "debug", "compile"
    ]
    if any(keyword in message_lower for keyword in technical_keywords):
        return None
    
    # Person search patterns
    person_patterns = [
        r"who is\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"tell me about\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"search for\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"information about\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"details of\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"profile of\s+([a-zA-Z][a-zA-Z ]{1,30})",
        r"bio of\s+([a-zA-Z][a-zA-Z ]{1,30})",
    ]
    
    for pattern in person_patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            # Validate it looks like a name (2-4 words, starts with capital)
            words = name.split()
            if 1 <= len(words) <= 4 and name[0].isupper():
                return name
    
    # Simple name pattern: 2-4 capitalized words (like "Elon Musk", "Bill Gates")
    name_pattern = r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})$"
    m = re.match(name_pattern, message)
    if m and 1 <= len(message.split()) <= 4:
        return message.strip()
    
    return None


# -------------------------------------
# App + CORS
# -------------------------------------
app = FastAPI(title="Synapse", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Backend is running", "status": "ok"}

@app.get("/favicon.ico")
async def favicon():
    """Handle favicon requests to prevent 405 errors."""
    return Response(status_code=204)  # No Content

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Synapse"}


# CORS middleware - MUST be added before routes
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Services
pdf_service = PDFService()
email_service = EmailService()


# -------------------------------------
# Startup / Shutdown
# -------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Synapse…")
    logger.info(f"  LLM Provider: {llm_service.get_current_provider_name()}")
    logger.info(f"  Email Service: {'✅ Configured' if email_service.is_configured() else '❌ Not Configured'}")
    await connect_mongo()
    await connect_redis()
    await kafka_service.start()

@app.on_event("shutdown")
async def shutdown_event():
    await disconnect_mongo()
    await disconnect_redis()
    await kafka_service.stop()


# -------------------------------------
# Global Exception Handlers (with CORS headers)
# -------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper CORS headers."""
    logger.error(f"❌ HTTP Exception: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": type(exc).__name__
        },
        headers={
            "Access-Control-Allow-Origin": ", ".join(_cors_origins),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            **(exc.headers or {})
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with proper CORS headers."""
    logger.error(f"❌ Unhandled exception: {exc}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred. Please try again."},
        headers={
            "Access-Control-Allow-Origin": ", ".join(_cors_origins),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with proper CORS headers."""
    logger.error(f"❌ Validation error: {exc}")
    
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation error",
            "errors": exc.errors()
        },
        headers={
            "Access-Control-Allow-Origin": ", ".join(_cors_origins),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


# -------------------------------------
# Person PDF Handler
# -------------------------------------
async def handle_person_pdf_generation(message: str) -> ChatResponse:
    try:
        name = extract_pdf_person_name(message)
        if not name:
            return ChatResponse(
                message="Please specify a name: e.g., 'Generate PDF of Virat Kohli'",
                source="ai"
            )

        logger.info(f"📄 Generating PDF for: {name}")

        # Generate PDF with deep research (especially for Gemini)
        data = await get_person_profile_full(name, deep_research=True)
        if not data:
            return ChatResponse(
                message=f"Could not fetch details for {name}.",
                source="ai"
            )

        # Validate using PersonProfile model
        try:
            profile = PersonProfile(**data)
        except Exception as e:
            logger.error(f"❌ Invalid profile data: {e}")
            return ChatResponse(
                message=f"Error validating profile data: {str(e)}",
                source="ai"
            )

        # Generate PDF
        try:
            pdf_bytes = pdf_service.generate_person_profile_pdf(profile.dict())
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ PDF generation error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ChatResponse(
                message=f"Error generating PDF: {str(e)}",
                source="ai"
            )

        return ChatResponse(
            message=f"PDF generated successfully for {name}!",
            source="pdf",
            pdf_data=pdf_b64,
            pdf_type="person_profile"
        )
    except Exception as e:
        logger.error(f"❌ PDF handler error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            message=f"Error in PDF generation: {str(e)}",
            source="ai"
        )


# -------------------------------------
# Weather Handler
# -------------------------------------
async def handle_weather_query(message: str) -> ChatResponse:
    """Handle weather queries using OpenWeatherMap API."""
    try:
        
        # Get OpenWeatherMap API key
        weather_api_key = os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("WEATHER_API_KEY")
        if not weather_api_key:
            return ChatResponse(
                message="Weather service is not configured. Please add OPENWEATHERMAP_API_KEY to backend/.env file.\n\nYou can get a free API key from: https://openweathermap.org/api",
                source="ai"
            )
        
        # Extract location from message
        location = extract_location_from_message(message)
        if not location:
            return ChatResponse(
                message="Please specify a location. For example: 'What's the weather in New York?' or 'Weather in London'",
                source="ai"
            )
        
        logger.info(f"🌤️  Fetching weather for: {location}")
        
        # Fetch LIVE weather data from OpenWeatherMap (no caching)
        weather_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": weather_api_key,
            "units": "metric"  # Use metric units (Celsius)
        }
        
        # Add timestamp to prevent caching and ensure live data
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Make fresh request each time - no caching
                response = await client.get(
                    weather_url, 
                    params=params,
                    headers=headers,
                    follow_redirects=True
                )
                response.raise_for_status()
                weather_data = response.json()
                
                # Log that we got live data
                logger.info(f"✅ Live weather data fetched for {location} at {datetime.now().isoformat()}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ChatResponse(
                    message=f"Location '{location}' not found. Please check the spelling and try again.",
                    source="ai"
                )
            raise
        except Exception as e:
            logger.error(f"❌ Weather API error: {e}")
            return ChatResponse(
                message=f"Error fetching weather data: {str(e)}",
                source="ai"
            )
        
        # Extract all weather data
        city = weather_data.get("name", location)
        country = weather_data.get("sys", {}).get("country", "")
        temp = weather_data.get("main", {}).get("temp", 0)
        feels_like = weather_data.get("main", {}).get("feels_like", 0)
        temp_min = weather_data.get("main", {}).get("temp_min", 0)
        temp_max = weather_data.get("main", {}).get("temp_max", 0)
        humidity = weather_data.get("main", {}).get("humidity", 0)
        pressure = weather_data.get("main", {}).get("pressure", 0)
        description = weather_data.get("weather", [{}])[0].get("description", "").title()
        weather_icon = weather_data.get("weather", [{}])[0].get("icon", "")
        wind_speed = weather_data.get("wind", {}).get("speed", 0)
        wind_deg = weather_data.get("wind", {}).get("deg", 0)
        wind_gust = weather_data.get("wind", {}).get("gust", None)
        visibility = weather_data.get("visibility", 0) / 1000 if weather_data.get("visibility") else None  # Convert to km
        clouds = weather_data.get("clouds", {}).get("all", 0)
        
        # Sunrise/Sunset times
        sunrise_ts = weather_data.get("sys", {}).get("sunrise", None)
        sunset_ts = weather_data.get("sys", {}).get("sunset", None)
        timezone_offset = weather_data.get("timezone", 0)  # Offset in seconds from UTC
        
        # Current timestamp (when data was fetched - proves it's live)
        current_time = datetime.now(timezone.utc)
        
        # Wind direction
        wind_directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        wind_dir = wind_directions[int((wind_deg % 360) / 22.5)] if wind_deg else "N/A"
        
        # Format sunrise/sunset times
        sunrise_str = ""
        sunset_str = ""
        if sunrise_ts:
            sunrise_dt = datetime.fromtimestamp(sunrise_ts + timezone_offset, tz=timezone.utc)
            sunrise_str = sunrise_dt.strftime("%H:%M")
        if sunset_ts:
            sunset_dt = datetime.fromtimestamp(sunset_ts + timezone_offset, tz=timezone.utc)
            sunset_str = sunset_dt.strftime("%H:%M")
        
        # Format response with live data timestamp
        weather_message = f"""**🌤️ Live Weather in {city}{', ' + country if country else ''}**

**📍 Real-Time Conditions (Updated: {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC):**

**Temperature:**
• **Current:** {temp:.1f}°C
• **Feels Like:** {feels_like:.1f}°C
• **Range:** {temp_min:.1f}°C - {temp_max:.1f}°C

**Conditions:**
• **Weather:** {description}
• **Cloudiness:** {clouds}%
• **Humidity:** {humidity}%
• **Pressure:** {pressure} hPa"""

        if visibility:
            weather_message += f"\n• **Visibility:** {visibility:.1f} km"

        weather_message += f"\n\n**Wind:**\n• **Speed:** {wind_speed:.1f} m/s ({wind_dir})"
        
        if wind_gust:
            weather_message += f"\n• **Gusts:** {wind_gust:.1f} m/s"

        if sunrise_str and sunset_str:
            weather_message += f"\n\n**Sun:**\n• **Sunrise:** {sunrise_str} UTC\n• **Sunset:** {sunset_str} UTC"

        weather_message += f"\n\n_Data fetched live from OpenWeatherMap API_"
        
        return ChatResponse(
            message=weather_message,
            source="ai"
        )
    except Exception as e:
        logger.error(f"❌ Weather handler error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            message=f"Error fetching weather: {str(e)}",
            source="ai"
        )


def extract_location_from_message(message: str) -> Optional[str]:
    """Extract location from weather query message."""
    message_lower = message.lower().strip()
    
    # Temporal words that should stop location extraction
    temporal_words = r'\b(now|today|tomorrow|yesterday|currently|right now)\b'
    
    # Weather-related patterns - stop before temporal words or punctuation
    patterns = [
        # Patterns with "of" - specifically handle "weather of [location]"
        r"weather of\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"what is the weather of\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"what's the weather of\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        
        # Patterns with "in" - standard patterns
        r"weather in\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"weather at\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"weather for\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"what's the weather in\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"what is the weather in\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"how's the weather in\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"temperature in\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        r"temperature at\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
        
        # Fallback patterns
        r"weather\s+([a-zA-Z\s,]+?)(?:" + temporal_words + r"|[?$.,]|and|$)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            
            # Remove temporal words if they were captured
            location = re.sub(temporal_words, '', location, flags=re.IGNORECASE).strip()
            
            # Clean up location (remove common prepositions and words)
            # Remove "of" only if it's at the start (from "weather of paris" -> "paris")
            location = re.sub(r'^\s*of\s+', '', location, flags=re.IGNORECASE).strip()
            location = re.sub(r'\b(in|at|for|the|weather|temperature|what|is|how|s|of)\b', '', location, flags=re.IGNORECASE).strip()
            
            # Remove any remaining punctuation at the end
            location = re.sub(r'[.,?;:!]+$', '', location).strip()
            
            # Split and take only the location part (first few words, max 4)
            words = location.split()
            if len(words) > 4:
                # Likely captured too much, try to find the actual location
                # Common location patterns: single word cities, or "City, Country"
                if ',' in location:
                    location = location.split(',')[0].strip()
                else:
                    # Take first 2-3 words as location
                    location = ' '.join(words[:3]).strip()
            
            if location and len(location) > 1:
                return location
    
    # If message is just a location name (1-4 words, starts with capital)
    words = message.split()
    if 1 <= len(words) <= 4 and message[0].isupper():
        # Check if it's not a question word
        if not message_lower.startswith(('what', 'how', 'when', 'where', 'why', 'who', 'which')):
            # Remove temporal words
            cleaned = message.strip()
            cleaned = re.sub(temporal_words, '', cleaned, flags=re.IGNORECASE).strip()
            if cleaned:
                return cleaned
    
    return None


# -------------------------------------
# General Chat Handler
# -------------------------------------
async def handle_general_chat(message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> ChatResponse:
    """Handle general chatbot questions using LLM with conversation context."""
    try:
        if not llm_service.is_available():
            return ChatResponse(
                message="I'm currently unavailable. Please configure OPENAI_API_KEY or GEMINI_API_KEY in backend/.env",
                source="ai"
            )

        logger.info(f"💬 General chat question: {message[:100]}...")
        if conversation_history:
            logger.info(f"📜 Using conversation history: {len(conversation_history)} previous messages")

        # Build system message
        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
        system_content = f"""Today's date is {today}.

You are a helpful, knowledgeable, and friendly AI assistant.
                You can answer questions on a wide variety of topics including:
                - General knowledge and facts
                - Science and technology
                - History and geography
                - Current events
                - Programming and technical topics
                - Creative writing and brainstorming
                - Problem-solving and explanations

                Provide clear, accurate, and helpful responses. If you don't know something, say so honestly.
                Keep responses concise but informative. Use markdown formatting when appropriate.

                IMPORTANT:
                - Use the conversation history to understand context and provide relevant follow-up responses.
                - If the user asks a follow-up question, refer to previous messages in the conversation.
                - Always respond in natural, conversational language - NEVER return JSON, code blocks with JSON, or raw data structures.
                - Format your response as readable text that flows naturally."""
        
        # Create chat messages for LLM with conversation history
        chat_messages = [
            LLMChatMessage(
                role="system",
                content=system_content
            )
        ]
        
        # Add conversation history if provided (convert to LLMChatMessage format)
        if conversation_history:
            for msg in conversation_history:
                # Only include user and assistant messages, skip errors
                msg_type = msg.get('type', '').lower()
                msg_content = msg.get('content', '')
                
                if msg_type == 'user':
                    chat_messages.append(LLMChatMessage(role="user", content=msg_content))
                elif msg_type == 'assistant':
                    # Only include assistant text content, skip person data and PDF info
                    chat_messages.append(LLMChatMessage(role="assistant", content=msg_content))
        
        # Add current user message
        chat_messages.append(LLMChatMessage(role="user", content=message))
        
        # Get response from LLM
        response = await llm_service.chat_completion(
            messages=chat_messages,
            temperature=0.7,  # Slightly higher temperature for more natural conversation
            max_tokens=2000   # Allow longer responses for complex questions
        )
        
        # Clean up response content - remove any JSON code blocks or raw JSON
        response_content = response.content.strip()
        
        # Remove JSON code blocks if present
        if response_content.startswith("```json"):
            response_content = response_content[7:]
        elif response_content.startswith("```"):
            response_content = response_content[3:]
        
        if response_content.endswith("```"):
            response_content = response_content[:-3]
        
        response_content = response_content.strip()
        
        # If the entire response looks like JSON (starts with { or [), try to extract meaningful text
        if response_content.startswith("{") or response_content.startswith("["):
            # Try to extract text from JSON if it's a simple structure
            try:
                parsed = json.loads(response_content)
                # If it's a dict with a message or content field, use that
                if isinstance(parsed, dict):
                    if "message" in parsed:
                        response_content = str(parsed["message"])
                    elif "content" in parsed:
                        response_content = str(parsed["content"])
                    elif "text" in parsed:
                        response_content = str(parsed["text"])
                    else:
                        # Convert dict to readable text
                        response_content = " ".join([f"{k}: {v}" for k, v in parsed.items() if not isinstance(v, (dict, list))])
                elif isinstance(parsed, list):
                    response_content = " ".join([str(item) for item in parsed if not isinstance(item, (dict, list))])
            except:
                # If JSON parsing fails, just use the original content
                pass
        
        return ChatResponse(
            message=response_content,
            source="ai"
        )
    except Exception as e:
        logger.error(f"❌ General chat handler error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            message=f"Error processing your question: {str(e)}",
            source="ai"
        )


# -------------------------------------
# Person Search Handler
# -------------------------------------
async def handle_person_search(name: str) -> ChatResponse:
    try:
        logger.info(f"🔍 Searching for: {name}")

        # Check Redis cache first
        data = await cache_get_profile(name)
        if not data:
            data = await get_person_profile_full(name, deep_research=True)
            if data:
                await cache_set_profile(name, data)
                await mongo_save_profile(name, data)

        if not data:
            return ChatResponse(
                message=f"No details found for {name}.",
                source="ai"
            )

        try:
            profile = PersonProfile(**data)
        except Exception as e:
            logger.error(f"❌ Invalid profile data: {e}")
            logger.error(f"Data received: {data}")
            return ChatResponse(
                message=f"Error processing profile data: {str(e)}",
                source="ai"
            )

        text = f"**{profile.name}**\n\n{profile.bio}\n\n"

        if profile.news:
            text += "**Recent News:**\n"
            for n in profile.news[:3]:
                # Handle both dict and NewsItem Pydantic model
                if isinstance(n, dict):
                    title = n.get('title', '')
                else:
                    title = getattr(n, 'title', '')
                text += f"- {title}\n"

        # Convert profile to dict for frontend PersonCard component
        # Convert NewsItem objects to dicts for JSON serialization
        person_data_dict = profile.model_dump() if hasattr(profile, 'model_dump') else profile.dict()
        
        # Ensure news items are dicts, not NewsItem objects
        if person_data_dict.get('news'):
            person_data_dict['news'] = [
                item if isinstance(item, dict) else {
                    'title': getattr(item, 'title', ''),
                    'url': getattr(item, 'url', ''),
                    'description': getattr(item, 'description', '') if hasattr(item, 'description') else ''
                }
                for item in person_data_dict['news']
            ]

        return ChatResponse(
            message=text, 
            source="ai",
            person_data=person_data_dict
        )
    except Exception as e:
        logger.error(f"❌ Person search handler error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            message=f"Error searching for person: {str(e)}",
            source="ai"
        )


# -------------------------------------
# MAIN CHAT ENDPOINT
# -------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, token: str = Depends(verify_token)):
    try:
        message = request.message.strip()
        
        if not message:
            return ChatResponse(
                message="Please provide a message.",
                source="ai"
            )

        # Check PDF request
        if "pdf" in message.lower():
            try:
                return await handle_person_pdf_generation(message)
            except Exception as e:
                logger.error(f"❌ PDF generation error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return ChatResponse(
                    message=f"Error generating PDF: {str(e)}",
                    source="ai"
                )

        # Publish Kafka event (fire and forget)
        await kafka_service.publish_search_event(message)

        # Check weather query
        if any(keyword in message.lower() for keyword in ["weather", "temperature", "forecast", "climate"]):
            try:
                result = await handle_weather_query(message)
                await save_entry(message, "weather")
                return result
            except Exception as e:
                logger.error(f"❌ Weather query error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Fall through to general chat if weather fails

        # Check person search
        name = extract_search_person_name(message)
        if name:
            try:
                result = await handle_person_search(name)
                await save_entry(message, "person_search")
                return result
            except Exception as e:
                logger.error(f"❌ Person search error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return ChatResponse(
                    message=f"Error searching for person: {str(e)}",
                    source="ai"
                )

        # General chatbot - answer any question using LLM
        try:
            result = await handle_general_chat(message, request.conversation_history)
            await save_entry(message, "general")
            return result
        except Exception as e:
            logger.error(f"❌ General chat error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ChatResponse(
                message=f"Error processing your question: {str(e)}",
                source="ai"
            )
    
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ChatResponse(
            message=f"An error occurred: {str(e)}",
            source="ai"
        )


# -------------------------------------
# Person PDF Endpoint (JSON response with base64)
# -------------------------------------
@app.post("/person/pdf", response_model=ChatResponse)
async def person_pdf(request: PersonPDFRequest, token: str = Depends(verify_token)):
    """
    Generate a PDF report for a person.
    
    Requires:
    - person_name: Name of the person to generate PDF for
    """
    try:
        name = request.person_name.strip()
        if not name:
            raise HTTPException(
                status_code=400,
                detail="person_name is required"
            )
        
        logger.info(f"📄 Generating PDF for: {name}")

        # Generate PDF with deep research (especially for Gemini)
        data = await get_person_profile_full(name, deep_research=True)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch details for {name}"
            )

        # Validate using PersonProfile model
        try:
            profile = PersonProfile(**data)
        except Exception as e:
            logger.error(f"❌ Invalid profile data: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error validating profile data: {str(e)}"
            )

        # Generate PDF
        try:
            pdf_bytes = pdf_service.generate_person_profile_pdf(profile.dict())
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ PDF generation error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating PDF: {str(e)}"
            )

        return ChatResponse(
            message=f"PDF generated successfully for {name}!",
            source="pdf",
            pdf_data=pdf_b64,
            pdf_type="person_profile"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in PDF generation: {str(e)}"
        )


# -------------------------------------
# Direct PDF Download Endpoint (serves file directly)
# -------------------------------------
@app.get("/person/pdf/download/{person_name}")
async def download_person_pdf(person_name: str, token: str = Depends(verify_token)):
    """
    Direct download endpoint for PDF files.
    Serves the PDF file directly, which is more reliable than blob URLs.
    """
    try:
        from fastapi.responses import Response
        
        name = person_name.strip().replace('_', ' ').replace('-', ' ')
        if not name:
            raise HTTPException(
                status_code=400,
                detail="person_name is required"
            )
        
        logger.info(f"📥 Direct PDF download requested for: {name}")

        # Generate PDF with deep research
        data = await get_person_profile_full(name, deep_research=True)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch details for {name}"
            )

        # Validate using PersonProfile model
        try:
            profile = PersonProfile(**data)
        except Exception as e:
            logger.error(f"❌ Invalid profile data: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error validating profile data: {str(e)}"
            )

        # Generate PDF
        try:
            pdf_bytes = pdf_service.generate_person_profile_pdf(profile.dict())
        except Exception as e:
            logger.error(f"❌ PDF generation error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating PDF: {str(e)}"
            )

        # Return PDF file directly
        filename = f"{name.replace(' ', '_')}-profile.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF download endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in PDF download: {str(e)}"
        )



# -------------------------------------
# Email PDF Endpoint
# -------------------------------------
@app.post("/email-pdf")
async def email_pdf(request: EmailRequest, token: str = Depends(verify_token)):
    """
    Generate a PDF report for a person and email it as an attachment.
    
    Requires:
    - Email service configuration (MAILGUN_API_KEY or EMAIL_API, MAILGUN_DOMAIN, EMAIL_FROM)
    - Valid recipient email address
    - Person name for PDF generation
    """
    try:
        if not email_service.is_configured():
            raise HTTPException(
                status_code=500,
                detail="Email service not configured. Please set MAILGUN_API_KEY (or EMAIL_API), MAILGUN_DOMAIN, and EMAIL_FROM in .env"
            )
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email):
            raise HTTPException(
                status_code=400,
                detail="Invalid email address format"
            )
        
        logger.info(f"📧 Generating PDF for {request.person_name} and sending to {request.email}")
        
        # Generate PDF with deep research (especially for Gemini)
        data = await get_person_profile_full(request.person_name, deep_research=True)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch details for {request.person_name}"
            )
        
        # Validate profile data
        try:
            profile = PersonProfile(**data)
        except Exception as e:
            logger.error(f"❌ Invalid profile data: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error validating profile data: {str(e)}"
            )
        
        # Generate PDF bytes
        try:
            pdf_bytes = pdf_service.generate_person_profile_pdf(profile.dict())
        except Exception as e:
            logger.error(f"❌ PDF generation error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating PDF: {str(e)}"
            )
        
        # Prepare email content with spam-friendly subject
        # Avoid spam trigger words and use clear, professional subject
        default_subject = f"Profile Report - {request.person_name}"
        subject = request.subject or default_subject
        
        # Remove common spam trigger words from subject
        spam_words = ['free', 'urgent', '!!!', 'click here', 'limited time']
        subject_lower = subject.lower()
        for word in spam_words:
            if word in subject_lower:
                logger.warning(f"⚠️  Subject contains potential spam word: {word}")
        pdf_filename = f"{request.person_name.replace(' ', '_')}_Profile_Report.pdf"
        
        body = f"""Hello,

Please find attached the profile report for {request.person_name}.

"""
        if request.message:
            body += f"{request.message}\n\n"
        
        body += f"""This report was generated using AI technology and includes comprehensive information about {request.person_name}.

Best regards,
Synapse
"""
        
        # Send email
        result = await email_service.send_pdf_email(
            to_email=request.email,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            person_name=request.person_name
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": result.get("message"),
                "email": request.email,
                "person_name": request.person_name
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to send email")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Email PDF endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )


# -------------------------------------
# Email Configuration Status
# -------------------------------------
@app.get("/email/status")
async def email_status(token: str = Depends(verify_token)):
    """Check email service configuration status."""
    return email_service.get_configuration_status()


# -------------------------------------
# Email Text Endpoint
# -------------------------------------
@app.post("/email-text")
async def email_text(request: EmailTextRequest, token: str = Depends(verify_token)):
    """Send a plain text/chat message via email."""
    try:
        if not email_service.is_configured():
            raise HTTPException(status_code=500, detail="Email service not configured.")

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email):
            raise HTTPException(status_code=400, detail="Invalid email address format")

        subject = request.subject or "Message from Synapse"
        result = await email_service.send_text_email(
            to_email=request.email,
            subject=subject,
            body=request.body,
        )

        if result.get("success"):
            return {"success": True, "message": result.get("message"), "email": request.email}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to send email"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Email text endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# -------------------------------------
# LLM Provider Management Endpoints
# -------------------------------------


class ProviderSwitchRequest(BaseModel):
    provider: str = Field(..., description="Provider name: 'openai' or 'gemini'")


@app.get("/llm/provider/status")
async def llm_provider_status(token: str = Depends(verify_token)):
    """Get current LLM provider status."""
    try:
        current_provider = llm_service.get_current_provider_name()
        available_providers = llm_service.get_available_providers()
        is_available = llm_service.is_available()
        
        return {
            "current_provider": current_provider,
            "available_providers": available_providers,
            "is_available": is_available,
            "status": "configured" if is_available else "not_configured"
        }
    except Exception as e:
        logger.error(f"❌ LLM provider status error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting provider status: {str(e)}"
        )


@app.get("/llm/provider/available")
async def llm_provider_available(token: str = Depends(verify_token)):
    """Get list of available LLM providers."""
    try:
        available = llm_service.get_available_providers()
        return {
            "available_providers": available,
            "count": len(available)
        }
    except Exception as e:
        logger.error(f"❌ LLM provider available error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting available providers: {str(e)}"
        )


@app.post("/llm/provider/switch")
async def llm_provider_switch(request: ProviderSwitchRequest, token: str = Depends(verify_token)):
    """Switch LLM provider dynamically."""
    try:
        provider_str = request.provider.lower().strip()
        
        # Validate provider name
        if provider_str not in ["openai", "gemini"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider: {provider_str}. Must be 'openai' or 'gemini'"
            )
        
        # Check if provider is available
        available = llm_service.get_available_providers()
        if provider_str not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider_str}' is not available. Available providers: {available}"
            )
        
        # Switch provider
        provider_type = LLMProviderType(provider_str)
        success = llm_service.set_provider(provider_type)

        if success:
            current = llm_service.get_current_provider_name()
            logger.info(f"✅ Switched LLM provider to: {current}")
            return {
                "success": True,
                "message": f"Successfully switched to {current}",
                "current_provider": current,
                "available_providers": available
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to switch to provider: {provider_str}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM provider switch error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error switching provider: {str(e)}"
        )


# -------------------------------------
# LLM Server Endpoints
# -------------------------------------

class LLMChatRequest(BaseModel):
    """Request model for LLM chat completion."""
    messages: List[Dict[str, str]] = Field(..., description="List of chat messages with 'role' and 'content'")
    model: Optional[str] = Field(None, description="Model name (uses provider default if not specified)")
    temperature: Optional[float] = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    provider: Optional[str] = Field(None, description="Override provider: 'openai' or 'gemini' (uses current if not specified)")
    stream: Optional[bool] = Field(False, description="Stream response (not yet implemented)")


class LLMChatResponse(BaseModel):
    """Response model for LLM chat completion."""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class LLMCompletionRequest(BaseModel):
    """Request model for LLM completion (OpenAI-compatible)."""
    prompt: str = Field(..., description="Text prompt")
    model: Optional[str] = Field(None, description="Model name")
    temperature: Optional[float] = Field(0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    provider: Optional[str] = Field(None, description="Override provider: 'openai' or 'gemini'")


class LLMCompletionResponse(BaseModel):
    """Response model for LLM completion."""
    text: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None


@app.post("/llm/chat", response_model=LLMChatResponse)
async def llm_chat(request: LLMChatRequest, token: str = Depends(verify_token)):
    """
    Generate chat completion using the configured LLM provider.
    
    This endpoint provides direct access to the LLM service with provider selection.
    """
    try:
        # Validate LLM service availability
        if not llm_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service not available. Please configure OPENAI_API_KEY or GEMINI_API_KEY"
            )
        
        # Handle provider override if specified
        original_provider = None
        if request.provider:
            provider_str = request.provider.lower().strip()
            if provider_str not in ["openai", "gemini"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid provider: {provider_str}. Must be 'openai' or 'gemini'"
                )
            
            available = llm_service.get_available_providers()
            if provider_str not in available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Provider '{provider_str}' is not available. Available: {available}"
                )
            
            # Temporarily switch provider for this request
            original_provider = llm_service.get_current_provider_name()
            provider_type = LLMProviderType(provider_str)
            llm_service.set_provider(provider_type)
        
        # Validate messages
        if not request.messages or len(request.messages) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one message is required"
            )
        
        # Convert messages to ChatMessage objects
        try:
            chat_messages = []
            for msg in request.messages:
                if not isinstance(msg, dict):
                    raise ValueError("Messages must be dictionaries")
                if "role" not in msg or "content" not in msg:
                    raise ValueError("Each message must have 'role' and 'content' fields")
                chat_messages.append(LLMChatMessage(
                    role=msg["role"],
                    content=str(msg["content"])
                ))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid message format: {str(e)}"
            )
        
        # Generate completion
        try:
            response = await llm_service.chat_completion(
                messages=chat_messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            current_provider = llm_service.get_current_provider_name()
            
            # Restore original provider if we switched
            if original_provider and original_provider != current_provider:
                try:
                    llm_service.set_provider(LLMProviderType(original_provider))
                except:
                    pass  # Don't fail if restore fails
            
            return LLMChatResponse(
                content=response.content,
                model=response.model,
                provider=current_provider or "unknown",
                usage=response.usage,
                finish_reason=response.finish_reason
            )
            
        except Exception as e:
            logger.error(f"❌ LLM chat completion error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"LLM completion failed: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM chat endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )


@app.post("/llm/completions", response_model=LLMCompletionResponse)
async def llm_completions(request: LLMCompletionRequest, token: str = Depends(verify_token)):
    """
    Generate text completion using the configured LLM provider.
    
    OpenAI-compatible endpoint for simple prompt completions.
    """
    try:
        # Validate LLM service availability
        if not llm_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service not available. Please configure OPENAI_API_KEY or GEMINI_API_KEY"
            )
        
        # Handle provider override if specified
        original_provider = None
        if request.provider:
            provider_str = request.provider.lower().strip()
            if provider_str not in ["openai", "gemini"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid provider: {provider_str}. Must be 'openai' or 'gemini'"
                )
            
            available = llm_service.get_available_providers()
            if provider_str not in available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Provider '{provider_str}' is not available. Available: {available}"
                )
            
            original_provider = llm_service.get_current_provider_name()
            provider_type = LLMProviderType(provider_str)
            llm_service.set_provider(provider_type)
        
        # Convert prompt to chat messages
        chat_messages = [LLMChatMessage(role="user", content=request.prompt)]
        
        # Generate completion
        try:
            response = await llm_service.chat_completion(
                messages=chat_messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            current_provider = llm_service.get_current_provider_name()
            
            # Restore original provider if we switched
            if original_provider and original_provider != current_provider:
                try:
                    llm_service.set_provider(LLMProviderType(original_provider))
                except:
                    pass
            
            return LLMCompletionResponse(
                text=response.content,
                model=response.model,
                provider=current_provider or "unknown",
                usage=response.usage
            )
            
        except Exception as e:
            logger.error(f"❌ LLM completion error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"LLM completion failed: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LLM completions endpoint error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )


# -------------------------------------
# Search History
# -------------------------------------

_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'data', 'history.json')

def _load_history() -> list:
    os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
    if not os.path.exists(_HISTORY_FILE):
        return []
    try:
        with open(_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save_history(data: list):
    os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
    with open(_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def save_entry(message: str, response_type: str):
    if is_mongo_available():
        await mongo_save_entry(message, response_type)
    else:
        # Fallback to local file
        history = _load_history()
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        session = next((s for s in history if s['date'] == today), None)
        if session is None:
            session = {'date': today, 'entries': []}
            history.insert(0, session)
        session['entries'].append({
            'message': message,
            'type': response_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        _save_history(history)

@app.get("/history")
async def get_search_history(token: str = Depends(verify_token)):
    if is_mongo_available():
        return {"history": await mongo_get_history()}
    return {"history": _load_history()}

@app.delete("/history")
async def delete_search_history(token: str = Depends(verify_token)):
    if is_mongo_available():
        await mongo_clear_history()
    else:
        _save_history([])
    return {"success": True, "message": "History cleared."}


# -------------------------------------
# Run App
# -------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
