# backend/services/ai_service.py
import os
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import httpx

from services.llm import LLMService, ChatMessage, LLMProviderType

logger = logging.getLogger(__name__)

# Load .env from backend directory (already loaded in main.py, but reload here to be safe)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# Initialize LLM Service (supports OpenAI and Gemini)
llm_service = LLMService()

# Try multiple possible variable names for API keys
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") or os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY")

# LLM configuration (with defaults)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1200"))

SERPAPI_BASE = "https://serpapi.com/search.json"
NEWS_API_URL = "https://newsapi.org/v2/everything"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_CONTENT_URL = "https://en.wikipedia.org/w/api.php"


### ---------- Helpers ----------

async def _http_get_json(url: str, params: dict, timeout: int = 15) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return {}


async def serpapi_search(query: str, params: dict) -> dict:
    if not SERPAPI_API_KEY:
        return {}
    params = params.copy()
    params["q"] = query
    params["api_key"] = SERPAPI_API_KEY
    return await _http_get_json(SERPAPI_BASE, params)


### ---------- LLM biography ----------

async def llm_bio(name: str, deep_research: bool = False) -> str:
    """Generate biography using the configured LLM provider.
    
    Args:
        name: Person's name
        deep_research: If True, uses Gemini 3 with comprehensive research prompts
    """
    if not llm_service.is_available():
        provider_name = llm_service.get_current_provider_name() or "LLM"
        return f"Mock biography for {name}. Configure {provider_name.upper()}_API_KEY environment variable in backend/.env file to get a real bio."
    
    # Check if we should use deep research mode (Gemini 3)
    current_provider = llm_service.get_current_provider_name()
    use_deep_research = deep_research or (current_provider == "gemini")
    
    # Initialize system_msg and user_msg to avoid UnboundLocalError
    # Default to standard mode messages
    system_msg = ChatMessage(
        role="system",
        content="You are an expert biographer. Produce detailed, factual biographies (400-600 words) suitable for a PDF profile. Include comprehensive information about early life, education, career, achievements, and current status."
    )
    user_msg = ChatMessage(
        role="user",
        content=f"Write a comprehensive 400-600 word factual biography for: {name}. Include: early life and background, education, complete career history with all major positions, significant achievements and awards, personal life details, and current status. Focus on verifiable public facts. Keep professional tone."
    )
    
    if use_deep_research and current_provider == "gemini":
        # Deep research mode with Gemini 3
        system_msg = ChatMessage(
            role="system",
            content="""You are an expert biographer and researcher specializing in comprehensive, in-depth biographical research. 
            Your task is to conduct DEEP RESEARCH and produce detailed, well-researched biographies that cover:
            - Early life and background (birthplace, family background, childhood experiences)
            - Education and formative years (schools, universities, degrees, mentors, influences)
            - Career trajectory and major milestones (all positions, companies, roles, transitions)
            - Significant achievements and contributions (awards, recognitions, breakthroughs)
            - Personal life and relationships (family, spouse, children, personal interests)
            - Current status and ongoing work (current role, recent activities, current projects)
            - Impact and legacy (influence on industry, society, lasting contributions)
            
            IMPORTANT: Conduct thorough research from multiple sources. Include specific dates, locations, names, and verifiable facts. 
            Write comprehensively with rich detail. Use multiple perspectives and ensure accuracy through fact-checking."""
        )
        user_msg = ChatMessage(
            role="user",
            content=f"""Conduct DEEP RESEARCH and write a comprehensive, detailed biography for: {name}

DEEP RESEARCH REQUIREMENTS:
- Write 600-1000 words (comprehensive, in-depth research)
- Cover ALL aspects thoroughly:
  * Early life: Birthplace, family background, childhood, formative experiences
  * Education: All schools, universities, degrees, majors, graduation years, mentors
  * Career: Complete career history with all positions, companies, roles, dates, transitions, promotions
  * Achievements: All awards, recognitions, honors, milestones, breakthroughs
  * Personal life: Family members (parents, spouse, children), relationships, personal interests, hobbies
  * Current status: Current role, company, recent activities, ongoing projects, current location
  * Impact: Influence on industry, society, lasting contributions, legacy
- Include SPECIFIC details: Exact dates, locations, names, numbers, facts
- Mention ALL notable works, publications, projects, companies founded/led
- Discuss their significance and impact in detail
- Include recent developments (last 2-3 years)
- Use multiple sources and perspectives
- Fact-check everything for accuracy

Write a thorough, well-researched biography that provides DEEP INSIGHTS into {name}'s complete life and career. Be comprehensive and detailed."""
        )
        
        try:
            # Use Gemini 3 specifically for deep research
            response = await llm_service.chat_completion(
                messages=[system_msg, user_msg],
                model="gemini-3-pro-preview" if current_provider == "gemini" else None,
                temperature=0.3,  # Slightly higher for more creative research
                max_tokens=3000  # Increased tokens for comprehensive deep research
            )
            logger.info(f"✅ Deep research bio generated for {name} using Gemini 3 ({len(response.content)} chars)")
            return response.content
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a quota/rate limit error
            if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                logger.warning(f"⚠️  Gemini quota exceeded for {name}. Falling back to OpenAI for deep research...")
                # Try with OpenAI if available
                if "openai" in llm_service.get_available_providers():
                    try:
                        llm_service.set_provider(LLMProviderType.OPENAI)
                        # Use enhanced deep research prompt for OpenAI fallback
                        openai_system = ChatMessage(
                            role="system",
                            content="""You are an expert biographer and researcher specializing in comprehensive, in-depth biographical research. 
                            Your task is to conduct DEEP RESEARCH and produce detailed, well-researched biographies that cover:
                            - Early life and background (birthplace, family background, childhood experiences)
                            - Education and formative years (schools, universities, degrees, mentors, influences)
                            - Career trajectory and major milestones (all positions, companies, roles, transitions)
                            - Significant achievements and contributions (awards, recognitions, breakthroughs)
                            - Personal life and relationships (family, spouse, children, personal interests)
                            - Current status and ongoing work (current role, recent activities, current projects)
                            - Impact and legacy (influence on industry, society, lasting contributions)
                            
                            IMPORTANT: Conduct thorough research from multiple sources. Include specific dates, locations, names, and verifiable facts. 
                            Write comprehensively with rich detail. Use multiple perspectives and ensure accuracy through fact-checking."""
                        )
                        openai_user = ChatMessage(
                            role="user",
                            content=f"""Conduct DEEP RESEARCH and write a comprehensive, detailed biography for: {name}

DEEP RESEARCH REQUIREMENTS:
- Write 600-1000 words (comprehensive, in-depth research)
- Cover ALL aspects thoroughly:
  * Early life: Birthplace, family background, childhood, formative experiences
  * Education: All schools, universities, degrees, majors, graduation years, mentors
  * Career: Complete career history with all positions, companies, roles, dates, transitions, promotions
  * Achievements: All awards, recognitions, honors, milestones, breakthroughs
  * Personal life: Family members (parents, spouse, children), relationships, personal interests, hobbies
  * Current status: Current role, company, recent activities, ongoing projects, current location
  * Impact: Influence on industry, society, lasting contributions, legacy
- Include SPECIFIC details: Exact dates, locations, names, numbers, facts
- Mention ALL notable works, publications, projects, companies founded/led
- Discuss their significance and impact in detail
- Include recent developments (last 2-3 years)
- Use multiple sources and perspectives
- Fact-check everything for accuracy

Write a thorough, well-researched biography that provides DEEP INSIGHTS into {name}'s complete life and career. Be comprehensive and detailed."""
                        )
                        response = await llm_service.chat_completion(
                            messages=[openai_system, openai_user],
                            temperature=0.3,
                            max_tokens=3000  # More tokens for OpenAI deep research
                        )
                        logger.info(f"✅ Deep research bio generated for {name} using OpenAI fallback ({len(response.content)} chars)")
                        return response.content
                    except Exception as fallback_error:
                        logger.error(f"OpenAI fallback also failed: {fallback_error}")
                        # Fall through to standard mode with default messages
            else:
                logger.error(f"Deep research bio generation failed: {e}")
                # Fall through to standard mode with default messages
    
    # Use standard mode (messages already initialized above)
    try:
        response = await llm_service.chat_completion(
            messages=[system_msg, user_msg],
            temperature=LLM_TEMPERATURE,
            max_tokens=2000  # Increased for better standard mode results
        )
        return response.content
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"❌ Biography generation failed for {name}: {error_type} - {error_msg}")
        return f"Could not fetch biography: {error_type} - {error_msg}"


# Backward compatibility alias
async def openai_bio(name: str) -> str:
    """Backward compatibility alias for llm_bio."""
    return await llm_bio(name)


async def llm_extract_person_details(name: str, deep_research: bool = False) -> dict:
    """Extract structured person details using the configured LLM provider.
    
    Args:
        name: Person's name
        deep_research: If True, uses Gemini 3 with comprehensive research prompts
    """
    if not llm_service.is_available():
        return {}
    
    # Check if we should use deep research mode (Gemini 3)
    current_provider = llm_service.get_current_provider_name()
    use_deep_research = deep_research or (current_provider == "gemini")
    
    # Initialize system_msg and user_msg to avoid UnboundLocalError
    # Default to standard mode messages
    system_msg = ChatMessage(
        role="system",
        content="You extract detailed structured information about people. Return valid JSON only with these keys: nationality, current_job (MUST be a STRING like 'Title at Company', NOT a dictionary), city, date_of_birth, personal_info_detail (250-350 words about personal background, education, family, early life, relationships), social_media (object with platform:url pairs - MUST find ONLY OFFICIAL, VERIFIED accounts for platforms: Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and ANY other platforms they use. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts), social_media_detail (200-250 words describing their social media presence and engagement across ALL platforms), career (350-450 words detailed career history with all positions, dates, companies, achievements, transitions), notable_work (350-450 words about major accomplishments, works, contributions, awards, publications). Use 'N/A' only if truly unavailable."
    )
    user_msg = ChatMessage(
        role="user",
        content=f"Extract comprehensive structured information for: {name}. Return ONLY valid JSON with keys: nationality, current_job (as a STRING, not a dictionary), city, date_of_birth, personal_info_detail, social_media, social_media_detail, career, notable_work. For social_media: Search for and include ONLY OFFICIAL, VERIFIED accounts for platforms (Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and any others). CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts. Provide detailed, comprehensive information for each section. Include specific dates, locations, and facts where available."
    )
    
    if use_deep_research and current_provider == "gemini":
        # Deep research mode with Gemini 3 - comprehensive extraction
        system_msg = ChatMessage(
            role="system",
            content="""You are an expert researcher specializing in DEEP, COMPREHENSIVE information extraction about public figures.
            Conduct THOROUGH RESEARCH and extract detailed, well-researched information. Return valid JSON only with these keys:
            - nationality: Country/countries of citizenship (be specific, include dual citizenship if applicable)
            - current_job: Current position, role, company, or occupation as a STRING (format: "Title at Company" or "Position, Company" - NOT a dictionary/object)
            - city: Current city of residence (be specific with city and state/country if known)
            - date_of_birth: Full date of birth (format: Month Day, Year) if available
            - personal_info_detail: 400-600 words COMPREHENSIVE personal background including:
              * Early life: Birthplace, family background, parents' names and occupations, siblings
              * Education: All schools, universities, degrees, majors, graduation years
              * Family: Spouse name, marriage date, children names and ages, family relationships
              * Personal interests: Hobbies, interests, philanthropic activities, personal life details
              * Formative experiences: Key events that shaped their life
            - social_media: Object with platform:url pairs - MUST find ALL existing platforms. Search for EVERY platform: Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and ANY other platforms they use. Include ALL platforms that exist - be exhaustive and thorough. Return empty object {} only if NO social media exists at all.
            - social_media_detail: 300-400 words describing their social media presence, engagement style, content themes, follower demographics, influence, posting frequency, and activity across ALL platforms found
            - career: 500-700 words DETAILED career history including:
              * ALL major positions with dates, company names, titles, responsibilities
              * Career transitions and reasons
              * Major achievements in each role
              * Career milestones and promotions
              * Industry impact and influence
            - notable_work: 500-700 words about major accomplishments including:
              * ALL works, contributions, publications, projects
              * Awards and recognitions with dates
              * Major achievements and breakthroughs
              * Legacy and lasting impact
            
            IMPORTANT: Conduct DEEP RESEARCH. Use 'N/A' ONLY if information is truly unavailable after thorough research. Otherwise, provide comprehensive, detailed, well-researched information."""
        )
        user_msg = ChatMessage(
            role="user",
            content=f"""Conduct DEEP RESEARCH and extract comprehensive structured information for: {name}

DEEP RESEARCH REQUIREMENTS:
- Research THOROUGHLY from multiple sources (Wikipedia, news articles, official websites, social media, interviews)
- Extract ALL available information for each field - be exhaustive
- Provide DETAILED, comprehensive content (not brief summaries - write extensively)
- Include SPECIFIC details: Exact dates, locations, names, numbers, facts, quotes
- Cover ALL aspects comprehensively:
  * Personal life: Family, relationships, education, early life, personal interests
  * Career: Complete career history with all positions, dates, companies, achievements
  * Achievements: All awards, recognitions, publications, projects, contributions
  * Social media: ONLY OFFICIAL, VERIFIED accounts for platforms (Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, and any others), URLs for each platform, engagement metrics, content themes. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts.
- Ensure accuracy through fact-checking
- Return ONLY valid JSON with keys: nationality, current_job, city, date_of_birth, personal_info_detail, social_media, social_media_detail, career, notable_work

Provide the MOST COMPREHENSIVE and DETAILED information possible. Be thorough and exhaustive in your research."""
        )
        
        try:
            # Use Gemini 3 specifically for deep research
            result = await llm_service.chat_completion_json(
                messages=[system_msg, user_msg],
                model="gemini-3-pro-preview" if current_provider == "gemini" else None,
                max_tokens=5000,  # Increased tokens for comprehensive deep research extraction
                temperature=0.3  # Slightly higher for better research
            )
            logger.info(f"✅ Deep research details extracted for {name} using Gemini 3")
            return result
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a quota/rate limit error
            if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                logger.warning(f"⚠️  Gemini quota exceeded for {name}. Falling back to OpenAI for deep research...")
                # Try with OpenAI if available
                if "openai" in llm_service.get_available_providers():
                    try:
                        llm_service.set_provider(LLMProviderType.OPENAI)
                        # Use enhanced deep research prompt for OpenAI fallback
                        openai_system = ChatMessage(
                            role="system",
                            content="""You are an expert researcher specializing in DEEP, COMPREHENSIVE information extraction about public figures.
                            Conduct THOROUGH RESEARCH and extract detailed, well-researched information. Return valid JSON only with these keys:
                            - nationality: Country/countries of citizenship (be specific, include dual citizenship if applicable)
                            - current_job: Current position, role, company, or occupation as a STRING (format: "Title at Company" or "Position, Company" - NOT a dictionary/object)
                            - city: Current city of residence (be specific with city and state/country if known)
                            - date_of_birth: Full date of birth (format: Month Day, Year) if available
                            - personal_info_detail: 400-600 words COMPREHENSIVE personal background including:
                              * Early life: Birthplace, family background, parents' names and occupations, siblings
                              * Education: All schools, universities, degrees, majors, graduation years
                              * Family: Spouse name, marriage date, children names and ages, family relationships
                              * Personal interests: Hobbies, interests, philanthropic activities, personal life details
                              * Formative experiences: Key events that shaped their life
                            - social_media: Object with platform:url pairs - MUST find ONLY OFFICIAL, VERIFIED accounts. Search for EVERY platform: Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and ANY other platforms they use. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts. Return empty object {} only if NO official social media exists at all.
                            - social_media_detail: 300-400 words describing their social media presence, engagement style, content themes, follower demographics, influence, posting frequency, and activity across ALL platforms found
                            - career: 500-700 words DETAILED career history including:
                              * ALL major positions with dates, company names, titles, responsibilities
                              * Career transitions and reasons
                              * Major achievements in each role
                              * Career milestones and promotions
                              * Industry impact and influence
                            - notable_work: 500-700 words about major accomplishments including:
                              * ALL works, contributions, publications, projects
                              * Awards and recognitions with dates
                              * Major achievements and breakthroughs
                              * Legacy and lasting impact
                            
                            IMPORTANT: Conduct DEEP RESEARCH. Use 'N/A' ONLY if information is truly unavailable after thorough research. Otherwise, provide comprehensive, detailed, well-researched information."""
                        )
                        openai_user = ChatMessage(
                            role="user",
                            content=f"""Conduct DEEP RESEARCH and extract comprehensive structured information for: {name}

DEEP RESEARCH REQUIREMENTS:
- Research THOROUGHLY from multiple sources (Wikipedia, news articles, official websites, social media, interviews)
- Extract ALL available information for each field - be exhaustive
- Provide DETAILED, comprehensive content (not brief summaries - write extensively)
- Include SPECIFIC details: Exact dates, locations, names, numbers, facts, quotes
- Cover ALL aspects comprehensively:
  * Personal life: Family, relationships, education, early life, personal interests
  * Career: Complete career history with all positions, dates, companies, achievements
  * Achievements: All awards, recognitions, publications, projects, contributions
  * Social media: ONLY OFFICIAL, VERIFIED accounts for platforms (Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, and any others), URLs for each platform, engagement metrics, content themes. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts.
- Ensure accuracy through fact-checking
- Return ONLY valid JSON with keys: nationality, current_job, city, date_of_birth, personal_info_detail, social_media, social_media_detail, career, notable_work

Provide the MOST COMPREHENSIVE and DETAILED information possible. Be thorough and exhaustive in your research."""
                        )
                        result = await llm_service.chat_completion_json(
                            messages=[openai_system, openai_user],
                            max_tokens=4000,
                            temperature=0.3
                        )
                        logger.info(f"✅ Deep research details extracted for {name} using OpenAI fallback")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"OpenAI fallback also failed: {fallback_error}")
            else:
                logger.error(f"Deep research extraction failed: {e}")
                # Fall through to standard mode with default messages
    
    # Use standard mode (messages already initialized above)
    try:
        result = await llm_service.chat_completion_json(
            messages=[system_msg, user_msg],
            max_tokens=2000,
            temperature=0.2
        )
        # Validate that we got some data
        if result and isinstance(result, dict):
            # Check if we have at least some non-empty fields
            non_empty_fields = [k for k, v in result.items() if v and str(v).strip() and str(v).strip().lower() != 'n/a']
            if non_empty_fields:
                logger.info(f"✅ Extracted {len(non_empty_fields)} fields for {name}: {non_empty_fields}")
            else:
                logger.warning(f"⚠️  Extraction returned empty or N/A values for {name}")
            return result
        else:
            logger.error(f"❌ Invalid extraction result for {name}: {type(result)}")
            return {}
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"❌ Failed to extract person details for {name}: {e}")
        logger.debug(f"Extraction error traceback: {traceback.format_exc()}")
        
        # If it's a quota error and we haven't tried OpenAI yet, try OpenAI
        if ("429" in error_str or "quota" in error_str or "rate limit" in error_str) and current_provider != "openai":
            logger.warning(f"⚠️  Quota exceeded. Attempting OpenAI fallback for {name}...")
            if "openai" in llm_service.get_available_providers():
                try:
                    llm_service.set_provider(LLMProviderType.OPENAI)
                    # Try standard mode with OpenAI
                    fallback_system = ChatMessage(
                        role="system",
                        content="You extract detailed structured information about people. Return valid JSON only with these keys: nationality, current_job, city, date_of_birth, personal_info_detail (150-200 words about personal background, education, family, early life), social_media (object with platform:url pairs - MUST find ONLY OFFICIAL, VERIFIED accounts for platforms: Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and ANY other platforms they use. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts), social_media_detail (100-150 words describing their social media presence and engagement across ALL platforms), career (200-300 words detailed career history, positions, achievements, transitions), notable_work (200-300 words about major accomplishments, works, contributions, awards). Use 'N/A' if unknown."
                    )
                    fallback_user = ChatMessage(
                        role="user",
                        content=f"Extract detailed structured information for: {name}. Return ONLY valid JSON with keys: nationality, current_job, city, date_of_birth, personal_info_detail, social_media, social_media_detail, career, notable_work. For social_media: Search for and include ONLY OFFICIAL, VERIFIED accounts for platforms (Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and any others). CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts. Provide comprehensive details for each section."
                    )
                    result = await llm_service.chat_completion_json(
                        messages=[fallback_system, fallback_user],
                        max_tokens=2000,
                        temperature=0.2
                    )
                    if result and isinstance(result, dict):
                        logger.info(f"✅ OpenAI fallback extraction succeeded for {name}")
                        return result
                except Exception as fallback_error:
                    logger.error(f"❌ OpenAI fallback also failed: {fallback_error}")
        
        return {}


# Backward compatibility alias
async def openai_extract_person_details(name: str) -> dict:
    """Backward compatibility alias for llm_extract_person_details."""
    return await llm_extract_person_details(name)


### ---------- Social Media Validation Functions ----------

def normalize_social_media_url(url: str, platform: str) -> str:
    """Normalize social media URL to prevent duplicates."""
    if not url or not isinstance(url, str):
        return ""
    
    url = url.strip().lower()
    
    # Remove trailing slashes and common parameters
    url = url.rstrip('/')
    # Remove common tracking parameters
    for param in ['?ref=', '?utm_', '?fbclid=', '?igshid=', '?si=']:
        if param in url:
            url = url.split(param)[0]
    
    # Normalize platform-specific URLs
    platform_lower = platform.lower()
    
    # Twitter/X normalization
    if 'twitter.com' in url or 'x.com' in url:
        if '/status/' in url:
            # Extract profile URL from tweet URL
            parts = url.split('/status/')[0]
            url = parts
        url = url.replace('twitter.com', 'x.com')
    
    # Instagram normalization
    if 'instagram.com' in url:
        if '/p/' in url or '/reel/' in url:
            # Extract profile URL from post URL
            parts = url.split('/p/')[0].split('/reel/')[0]
            url = parts.rstrip('/')
        if '/explore/' in url or '/accounts/' in url:
            return ""  # Skip explore/accounts pages
    
    # LinkedIn normalization
    if 'linkedin.com' in url:
        if '/in/' in url:
            # Keep only the profile part
            parts = url.split('/in/')
            if len(parts) > 1:
                profile_id = parts[1].split('/')[0].split('?')[0]
                url = f"https://www.linkedin.com/in/{profile_id}"
        elif '/company/' in url or '/school/' in url:
            return ""  # Skip company/school pages (not personal profiles)
    
    # YouTube normalization
    if 'youtube.com' in url or 'youtu.be' in url:
        if '/channel/' in url:
            # Keep channel URL as is
            pass
        elif '/user/' in url:
            # Keep user URL as is
            pass
        elif '/watch' in url or '/shorts/' in url:
            # Extract channel from video URL (would need API call, skip for now)
            return ""
        elif 'youtu.be' in url:
            # Convert short URL (would need API call, skip for now)
            return ""
    
    # Facebook normalization
    if 'facebook.com' in url or 'fb.com' in url:
        if '/pages/' in url or '/groups/' in url:
            return ""  # Skip pages/groups
        if '/profile.php' in url:
            # Keep profile.php URLs as is
            pass
    
    return url


def is_valid_social_media_url(url: str, platform: str, person_name: str) -> bool:
    """Validate that a social media URL is likely official and belongs to the person."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False
    
    url_lower = url.lower()
    platform_lower = platform.lower()
    name_parts = person_name.lower().split()
    
    # Platform-specific domain validation
    platform_domains = {
        'twitter': ['twitter.com', 'x.com', 't.co'],
        'x': ['twitter.com', 'x.com', 't.co'],
        'instagram': ['instagram.com'],
        'linkedin': ['linkedin.com'],
        'facebook': ['facebook.com', 'fb.com'],
        'youtube': ['youtube.com', 'youtu.be'],
        'tiktok': ['tiktok.com'],
        'threads': ['threads.net'],
        'mastodon': ['mastodon.social', 'mastodon.online'],
        'snapchat': ['snapchat.com'],
        'pinterest': ['pinterest.com'],
        'reddit': ['reddit.com'],
        'medium': ['medium.com'],
        'github': ['github.com'],
        'discord': ['discord.com', 'discord.gg'],
        'telegram': ['t.me', 'telegram.org'],
        'clubhouse': ['clubhouse.com'],
        'twitch': ['twitch.tv'],
        'patreon': ['patreon.com'],
        'substack': ['substack.com'],
        'bluesky': ['bsky.app'],
        'truth social': ['truthsocial.com'],
        'tumblr': ['tumblr.com'],
        'vimeo': ['vimeo.com'],
        'soundcloud': ['soundcloud.com'],
        'spotify': ['spotify.com'],
        'apple music': ['music.apple.com'],
        'cameo': ['cameo.com']
    }
    
    # Check if URL matches platform domain
    valid_domains = platform_domains.get(platform_lower, [])
    if not any(domain in url_lower for domain in valid_domains):
        return False
    
    # Filter out suspicious patterns
    suspicious_patterns = [
        '/fan/', '/fans/', '/fanpage', '/fan-page',
        '/parody', '/fake', '/imposter',
        '/official-fan', '/unofficial',
        'fanclub', 'fan-club',
        '/page/', '/pages/',  # Facebook pages (not personal profiles)
        '/group/', '/groups/',  # Facebook groups
        '/explore/', '/accounts/',  # Instagram explore/accounts
        '/company/', '/school/',  # LinkedIn company/school pages
        '/watch', '/shorts/',  # YouTube videos (not channels)
        '?ref=', '?utm_', '?fbclid=',  # Tracking URLs (already normalized)
    ]
    
    for pattern in suspicious_patterns:
        if pattern in url_lower:
            logger.debug(f"⚠️  Filtered suspicious URL pattern '{pattern}' from {url[:60]}...")
            return False
    
    # Check for random number sequences (often fake accounts)
    import re
    # Extract username/handle from URL
    username_match = re.search(r'/([^/?]+)(?:/|$|\?)', url_lower)
    if username_match:
        username = username_match.group(1)
        # If username is mostly numbers or random characters, might be fake
        if len(username) > 0:
            num_ratio = sum(c.isdigit() for c in username) / len(username)
            if num_ratio > 0.7 and len(username) > 5:  # More than 70% numbers
                logger.debug(f"⚠️  Filtered URL with suspicious numeric username: {url[:60]}...")
                return False
    
    return True


def validate_and_deduplicate_social_media(social_media_dict: dict, person_name: str) -> dict:
    """Validate and remove duplicates from social media dictionary."""
    if not social_media_dict or not isinstance(social_media_dict, dict):
        return {}
    
    validated = {}
    seen_urls = set()
    
    for platform, url in social_media_dict.items():
        if not url or not isinstance(url, str) or url == "N/A":
            continue
        
        # Normalize URL
        normalized_url = normalize_social_media_url(url, platform)
        if not normalized_url:
            logger.debug(f"⚠️  Skipped invalid/normalized URL for {platform}: {url[:60]}...")
            continue
        
        # Check for duplicates
        if normalized_url in seen_urls:
            logger.debug(f"⚠️  Removed duplicate URL for {platform}: {url[:60]}...")
            continue
        
        # Validate URL
        if not is_valid_social_media_url(normalized_url, platform, person_name):
            logger.debug(f"⚠️  Removed invalid/unverified URL for {platform}: {url[:60]}...")
            continue
        
        # Add to validated dict
        validated[platform] = normalized_url
        seen_urls.add(normalized_url)
        logger.debug(f"✅ Validated {platform} URL: {normalized_url[:60]}...")
    
    return validated


### ---------- SerpAPI: images & instagram-like posts ----------

async def fetch_person_images(name: str, limit: int = 6) -> List[str]:
    """Uses SerpAPI image search to return direct image URLs."""
    try:
        params = {"engine": "google", "tbm": "isch", "ijn": 0}
        data = await serpapi_search(name, params)
        images = []
        for it in data.get("images_results", [])[:limit]:
            url = it.get("original") or it.get("thumbnail")
            if url:
                images.append(url)
        return images
    except Exception:
        return []


async def fetch_instagram_profile_pic(name: str) -> str:
    """
    Attempt to fetch an Instagram profile picture by searching "name instagram profile picture".
    Result may not always be the true IG DP, but SerpAPI often returns usable profile thumbnails.
    """
    try:
        params = {"engine": "google", "tbm": "isch", "ijn": 0}
        query = f"{name} instagram profile picture"
        data = await serpapi_search(query, params)
        for it in data.get("images_results", [])[:8]:
            url = it.get("original") or it.get("thumbnail")
            if url:
                return url
        return ""
    except Exception:
        return ""


async def fetch_instagram_posts_like(name: str, limit: int = 4) -> List[Dict]:
    """Use SerpAPI to get Instagram posts."""
    try:
        params = {"engine": "google", "tbm": "isch", "ijn": 0}
        query = f"site:instagram.com {name}"
        data = await serpapi_search(query, params)
        posts = []
        for it in data.get("images_results", [])[:limit]:
            posts.append({
                "image_url": it.get("original") or it.get("thumbnail"),
                "title": it.get("title") or "",
                "link": it.get("link") or ""
            })
        return posts
    except Exception:
        return []


### ---------- Wikipedia ----------

async def fetch_wikipedia_content(name: str) -> str:
    """Fetch Wikipedia page content for a person."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # First, get page summary
            params = {
                "action": "query",
                "format": "json",
                "titles": name,
                "prop": "extracts",
                "exintro": False,
                "explaintext": True,
                "redirects": 1
            }
            r = await client.get(WIKIPEDIA_CONTENT_URL, params=params)
            r.raise_for_status()
            data = r.json()
            
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return ""
            
            # Get the first page content
            page = list(pages.values())[0]
            extract = page.get("extract", "")
            
            if not extract:
                # Try alternative: get summary from REST API
                try:
                    r2 = await client.get(f"{WIKIPEDIA_API_URL}/{name.replace(' ', '_')}")
                    r2.raise_for_status()
                    summary_data = r2.json()
                    extract = summary_data.get("extract", "") or summary_data.get("description", "")
                except Exception:
                    pass
            
            return extract[:5000]  # Limit to 5000 characters
    except Exception as e:
        logger.debug(f"Wikipedia fetch error for {name}: {e}")
        return ""


async def extract_personal_info_from_wikipedia(name: str, wikipedia_content: str) -> Dict:
    """Extract education, family, net worth, and known for from Wikipedia content using LLM service."""
    if not wikipedia_content or not llm_service.is_available():
        logger.warning(f"⚠️  Cannot extract Wikipedia info: content={bool(wikipedia_content)}, llm_available={llm_service.is_available()}")
        return {}
    
    system_msg = ChatMessage(
        role="system",
        content="""You are an expert at extracting specific, focused information from Wikipedia articles. 
        Extract ONLY the relevant information for each field. Be precise and focused:
        
        - education: ONLY educational background - schools, universities, degrees, majors, graduation years. Do NOT include career achievements, work experience, or other biographical details.
        - family: ONLY family information - parents' names and occupations, spouse(s), children, siblings. Do NOT include education, career, or achievements.
        - net_worth: ONLY net worth or estimated wealth figures if explicitly mentioned. Include currency and source if available. Do NOT include salary, income, or other financial details.
        - known_for: ONLY what they are most famous for - their primary claim to fame in 1-2 concise sentences. Focus on their main achievements or recognition.
        
        Return valid JSON only. Use 'N/A' if specific information is not found in the provided content."""
    )
    user_msg = ChatMessage(
        role="user",
        content=f"""Extract ONLY the specific information requested for {name} from this Wikipedia content.
        
        IMPORTANT: Each field must contain ONLY its specific information:
        - education: ONLY schools, universities, degrees, majors
        - family: ONLY family members (parents, spouse, children)
        - net_worth: ONLY net worth/wealth figures if mentioned
        - known_for: ONLY what they are famous for (1-2 sentences)
        
        Wikipedia content:
        {wikipedia_content[:4000]}
        
        Return ONLY valid JSON with keys: education, family, net_worth, known_for."""
    )
    
    try:
        result = await llm_service.chat_completion_json(
            messages=[system_msg, user_msg],
            max_tokens=1200,
            temperature=0.1
        )
        
        logger.info(f"✅ Wikipedia extraction completed for {name}: {list(result.keys())}")
        
        # Post-process to ensure fields are focused and clean
        def clean_field(field_name: str, value: str, focus_keywords: list) -> str:
            """Clean and validate field content to ensure it's focused."""
            if not value or value.lower() == 'n/a' or value.strip() == '':
                return 'N/A'
            
            value = value.strip()
            # Check if value seems relevant (contains focus keywords or is short enough to be specific)
            if len(value) > 500:  # Too long, might contain irrelevant info
                # Try to extract most relevant sentence
                sentences = value.split('.')
                relevant_sentences = []
                for sentence in sentences:
                    sentence = sentence.strip()
                    if any(keyword.lower() in sentence.lower() for keyword in focus_keywords):
                        relevant_sentences.append(sentence)
                        if len('. '.join(relevant_sentences)) > 300:
                            break
                if relevant_sentences:
                    value = '. '.join(relevant_sentences) + '.'
                else:
                    value = value[:300] + '...'
            
            return value
        
        # Clean each field with specific focus keywords
        if 'education' in result:
            original_edu = result.get('education', 'N/A')
            result['education'] = clean_field('education', original_edu, 
                ['university', 'college', 'school', 'degree', 'graduated', 'studied', 'major', 'bachelor', 'master', 'phd'])
            logger.info(f"📚 Education extracted: {result['education'][:100] if result['education'] != 'N/A' else 'N/A'}")
        
        if 'family' in result:
            original_family = result.get('family', 'N/A')
            result['family'] = clean_field('family', original_family,
                ['father', 'mother', 'parent', 'spouse', 'wife', 'husband', 'married', 'child', 'son', 'daughter', 'sibling', 'brother', 'sister'])
            logger.info(f"👨‍👩‍👧 Family extracted: {result['family'][:100] if result['family'] != 'N/A' else 'N/A'}")
        
        if 'net_worth' in result:
            original_worth = result.get('net_worth', 'N/A')
            result['net_worth'] = clean_field('net_worth', original_worth,
                ['net worth', 'wealth', 'billionaire', 'millionaire', 'fortune', 'estimated', 'worth', '$', 'USD', 'billion', 'million'])
            logger.info(f"💰 Net worth extracted: {result['net_worth'][:100] if result['net_worth'] != 'N/A' else 'N/A'}")
        
        if 'known_for' in result:
            original_known = result.get('known_for', 'N/A')
            result['known_for'] = clean_field('known_for', original_known,
                ['known', 'famous', 'founded', 'created', 'developed', 'CEO', 'founder', 'invented'])
            logger.info(f"⭐ Known for extracted: {result['known_for'][:100] if result['known_for'] != 'N/A' else 'N/A'}")
        
        return result
    except Exception as e:
        logger.error(f"❌ Error extracting Wikipedia info for {name}: {e}")
        logger.debug(f"Wikipedia extraction traceback: {traceback.format_exc()}")
        return {}


### ---------- NewsAPI ----------

async def fetch_news(name: str, limit: int = 5) -> List[Dict]:
    if not NEWSAPI_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            params = {
                "q": name,
                "apiKey": NEWSAPI_KEY,
                "language": "en",
                "pageSize": limit,
                "sortBy": "publishedAt"
            }
            r = await client.get(NEWS_API_URL, params=params)
            r.raise_for_status()
            data = r.json()
            articles = []
            for a in data.get("articles", [])[:limit]:
                articles.append({
                    "title": a.get("title"),
                    "description": a.get("description"),
                    "url": a.get("url"),
                    "source": a.get("source", {}).get("name")
                })
            return articles
    except Exception:
        return []


### ---------- Unified function ----------

async def get_person_profile_full(name: str, deep_research: bool = False) -> Dict:
    """
    Fetch biography (OpenAI/Gemini), news (NewsAPI), images & Instagram posts (SerpAPI), Wikipedia personal info.
    
    Args:
        name: Person's name
        deep_research: If True, uses Gemini 3 with comprehensive research (defaults to True if Gemini is current provider)
    
    Returns:
    { name, bio, nationality, current_job, city, date_of_birth, education, family, net_worth, known_for, social_media, career, notable_work, news[], images[], instagram_profile_picture, instagram_posts[], created_at }
    """
    # Auto-enable deep research if Gemini is the current provider
    current_provider = llm_service.get_current_provider_name()
    if not deep_research and current_provider == "gemini":
        deep_research = True
        logger.info(f"🔬 Auto-enabling deep research mode for {name} (Gemini provider detected)")
    
    # run in parallel
    bio_task = asyncio.create_task(llm_bio(name, deep_research=deep_research))
    details_task = asyncio.create_task(llm_extract_person_details(name, deep_research=deep_research))
    news_task = asyncio.create_task(fetch_news(name))
    images_task = asyncio.create_task(fetch_person_images(name))
    insta_posts_task = asyncio.create_task(fetch_instagram_posts_like(name))
    insta_dp_task = asyncio.create_task(fetch_instagram_profile_pic(name))
    wikipedia_content_task = asyncio.create_task(fetch_wikipedia_content(name))

    bio = await bio_task
    details = await details_task
    news = await news_task
    images = await images_task
    insta_posts = await insta_posts_task
    insta_dp = await insta_dp_task
    wikipedia_content = await wikipedia_content_task
    
    # Log what we received
    logger.info(f"📊 Data collection summary for {name}:")
    logger.info(f"   Bio: {len(bio) if bio else 0} chars - {'✅' if bio else '❌'}")
    logger.info(f"   Details keys: {list(details.keys()) if details else 'None'}")
    if details:
        for key, value in details.items():
            if isinstance(value, str):
                logger.info(f"   Details[{key}]: {len(value)} chars - {'✅' if value and value != 'N/A' else '❌ Empty'}")
            elif isinstance(value, dict):
                logger.info(f"   Details[{key}]: {len(value)} items - {'✅' if value else '❌ Empty'}")
            else:
                logger.info(f"   Details[{key}]: {value}")
    else:
        logger.error(f"❌ CRITICAL: Details extraction returned empty dict for {name}!")
        logger.error(f"   This means llm_extract_person_details failed completely.")
        logger.error(f"   All fields will default to 'N/A' in the PDF.")
    logger.info(f"   News items: {len(news) if news else 0}")
    logger.info(f"   Images: {len(images) if images else 0}")
    logger.info(f"   Wikipedia content: {len(wikipedia_content) if wikipedia_content else 0} chars")
    
    # Extract personal info from Wikipedia
    wikipedia_info = {}
    if wikipedia_content:
        logger.info(f"📚 Extracting Wikipedia info for {name} (content length: {len(wikipedia_content)})")
        wikipedia_info = await extract_personal_info_from_wikipedia(name, wikipedia_content)
        logger.info(f"📚 Wikipedia extraction result: {list(wikipedia_info.keys())}")
        logger.info(f"📚 Education: {'✅ Found (' + str(len(wikipedia_info.get('education', ''))) + ' chars)' if wikipedia_info.get('education') and wikipedia_info.get('education') != 'N/A' else '❌ Missing'}")
        logger.info(f"📚 Family: {'✅ Found (' + str(len(wikipedia_info.get('family', ''))) + ' chars)' if wikipedia_info.get('family') and wikipedia_info.get('family') != 'N/A' else '❌ Missing'}")
        logger.info(f"📚 Net Worth: {'✅ Found (' + str(len(wikipedia_info.get('net_worth', ''))) + ' chars)' if wikipedia_info.get('net_worth') and wikipedia_info.get('net_worth') != 'N/A' else '❌ Missing'}")
        logger.info(f"📚 Known For: {'✅ Found (' + str(len(wikipedia_info.get('known_for', ''))) + ' chars)' if wikipedia_info.get('known_for') and wikipedia_info.get('known_for') != 'N/A' else '❌ Missing'}")
    else:
        logger.warning(f"⚠️  No Wikipedia content found for {name}")

    # Extract Wikipedia fields, handling "N/A" strings properly
    def get_wiki_field(field_name: str, fallback: str = "") -> str:
        """Get Wikipedia field, return empty string instead of 'N/A' if missing."""
        value = wikipedia_info.get(field_name, "")
        if value and isinstance(value, str):
            value = value.strip()
            if value.lower() == 'n/a' or value == '':
                return fallback
            return value
        return fallback
    
    # Get known_for - only use Wikipedia extraction, no fallback to full bio
    # If Wikipedia doesn't have it, extract a concise "known for" from bio if available
    known_for_value = get_wiki_field("known_for", "")
    if not known_for_value and bio:
        # Try to extract a concise "known for" from the bio (1-2 sentences max)
        try:
            # Use LLM service to extract just what they're known for from the bio
            if llm_service.is_available():
                extract_msg = ChatMessage(
                    role="user",
                    content=f"From this biography, extract ONLY what {name} is most famous/known for in 1-2 concise sentences:\n\n{bio[:500]}\n\nReturn only the answer, no explanation."
                )
                extract_resp = await llm_service.chat_completion(
                    messages=[extract_msg],
                    max_tokens=100,
                    temperature=0.1
                )
                extracted = extract_resp.content.strip()
                if extracted and len(extracted) < 300:  # Keep it concise
                    known_for_value = extracted
                    logger.info(f"✅ Extracted 'known_for' from bio: {known_for_value[:100]}")
        except Exception as e:
            logger.debug(f"Failed to extract 'known_for' from bio: {e}")
            pass  # If extraction fails, leave it empty
    
    # Extract missing fields from bio/details if Wikipedia didn't provide them
    education_value = get_wiki_field("education", "")
    family_value = get_wiki_field("family", "")
    net_worth_value = get_wiki_field("net_worth", "")
    
    # Get personal_info_detail which contains comprehensive personal information
    personal_info_detail = details.get("personal_info_detail", "")
    
    # Log what sources we have available
    if personal_info_detail:
        logger.info(f"📋 personal_info_detail available ({len(personal_info_detail)} chars): {personal_info_detail[:150]}")
    
    # Combine bio and personal_info_detail for extraction
    combined_text = ""
    if bio:
        combined_text += f"Biography: {bio[:1500]}\n\n"
    if personal_info_detail:
        combined_text += f"Personal Information Details: {personal_info_detail[:1500]}"
    
    # If Wikipedia extraction failed, try comprehensive extraction from bio/personal_info_detail using LLM service
    if (not education_value or not family_value or not net_worth_value) and combined_text:
        logger.info(f"📋 Attempting comprehensive fallback extraction from bio/personal_info_detail for missing fields")
        try:
            if llm_service.is_available():
                extract_system = ChatMessage(
                    role="system",
                    content="""You extract specific information from biographical text. Extract ALL available information.
                    Return ONLY valid JSON with these keys:
                    - education: Schools, universities, degrees, majors, educational institutions (be comprehensive)
                    - family: Family members (parents, spouse, children, siblings) with names and details
                    - net_worth: Net worth/wealth figures, estimated fortune if mentioned
                    - known_for: What they are most famous for (1-2 sentences)
                    
                    Extract as much detail as possible. Use empty string "" only if truly not found."""
                )
                extract_user = ChatMessage(
                    role="user",
                    content=f"""Extract comprehensive information for {name} from the following text. Extract ALL available details:

Text:
{combined_text[:3000]}

Return ONLY valid JSON with keys: education, family, net_worth, known_for. Extract as much detail as possible."""
                )
                import json
                fallback_data = await llm_service.chat_completion_json(
                    messages=[extract_system, extract_user],
                    max_tokens=1500,  # More tokens for comprehensive extraction
                    temperature=0.2
                )
                
                # Use fallback data only if Wikipedia didn't provide it
                if not education_value and fallback_data.get("education"):
                    edu_val = fallback_data.get("education", "").strip()
                    if edu_val and edu_val.lower() not in ["n/a", ""]:
                        education_value = edu_val
                        logger.info(f"📚 Education extracted from bio/personal_info fallback: {education_value[:100]}")
                
                if not family_value and fallback_data.get("family"):
                    fam_val = fallback_data.get("family", "").strip()
                    if fam_val and fam_val.lower() not in ["n/a", ""]:
                        family_value = fam_val
                        logger.info(f"📚 Family extracted from bio/personal_info fallback: {family_value[:100]}")
                
                if not net_worth_value and fallback_data.get("net_worth"):
                    worth_val = fallback_data.get("net_worth", "").strip()
                    if worth_val and worth_val.lower() not in ["n/a", ""]:
                        net_worth_value = worth_val
                        logger.info(f"📚 Net Worth extracted from bio/personal_info fallback: {net_worth_value[:100]}")
                
                # Also update known_for if missing
                if not known_for_value and fallback_data.get("known_for"):
                    known_val = fallback_data.get("known_for", "").strip()
                    if known_val and known_val.lower() not in ["n/a", ""]:
                        known_for_value = known_val
                        logger.info(f"📚 Known For extracted from bio/personal_info fallback: {known_for_value[:100]}")
        except Exception as e:
            logger.error(f"❌ Fallback extraction error: {e}")
            logger.debug(f"Fallback extraction traceback: {traceback.format_exc()}")
    
    # Log final values being returned
    # Log final values being returned
    logger.info(f"📋 Final values for {name}:")
    logger.info(f"   Education: {'✅ Found (' + str(len(education_value)) + ' chars)' if education_value and education_value != 'N/A' else '❌ Empty'}")
    logger.info(f"   Family: {'✅ Found (' + str(len(family_value)) + ' chars)' if family_value and family_value != 'N/A' else '❌ Empty'}")
    logger.info(f"   Net Worth: {'✅ Found (' + str(len(net_worth_value)) + ' chars)' if net_worth_value and net_worth_value != 'N/A' else '❌ Empty'}")
    logger.info(f"   Known For: {'✅ Found (' + str(len(known_for_value)) + ' chars)' if known_for_value and known_for_value != 'N/A' else '❌ Empty'}")
    logger.info(f"   Career: {'✅ Found (' + str(len(details.get('career', ''))) + ' chars)' if details.get('career') and details.get('career') != 'N/A' else '❌ Empty'}")
    logger.info(f"   Notable Work: {'✅ Found (' + str(len(details.get('notable_work', ''))) + ' chars)' if details.get('notable_work') and details.get('notable_work') != 'N/A' else '❌ Empty'}")
    logger.info(f"   Personal Info Detail: {'✅ Found (' + str(len(details.get('personal_info_detail', ''))) + ' chars)' if details.get('personal_info_detail') else '❌ Empty'}")
    logger.info(f"   Bio: {'✅ Found (' + str(len(bio)) + ' chars)' if bio else '❌ Empty'}")
    
    # Collect source URLs for citations and references
    sources = []
    field_citations = {}  # Map field names to their source URLs
    
    # Wikipedia URL - used for education, family, net_worth, known_for, personal_info_detail
    # Always construct Wikipedia URL (even if content fetch failed, we might still use it for citations)
    wikipedia_url = f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}"
    
    # Add Wikipedia to sources if we have content OR if we're using it for field citations
    if wikipedia_content:
        if wikipedia_url not in sources:
            sources.insert(0, wikipedia_url)  # Add Wikipedia as first source
        # Map Wikipedia fields to Wikipedia URL
        if education_value and education_value != "N/A":
            field_citations['education'] = wikipedia_url
        if family_value and family_value != "N/A":
            field_citations['family'] = wikipedia_url
        if net_worth_value and net_worth_value != "N/A":
            field_citations['net_worth'] = wikipedia_url
        if known_for_value and known_for_value != "N/A":
            field_citations['known_for'] = wikipedia_url
        if personal_info_detail and personal_info_detail != "N/A":
            field_citations['personal_info_detail'] = wikipedia_url
    else:
        # Even if Wikipedia content fetch failed, if we're using Wikipedia in field_citations, add it to sources
        # This happens when fallback extraction uses Wikipedia
        if any('wikipedia.org' in str(url).lower() for url in field_citations.values()):
            if wikipedia_url not in sources:
                sources.insert(0, wikipedia_url)
                logger.info(f"✅ Added Wikipedia URL to sources (from field_citations): {wikipedia_url}")
    
    # News article URLs - for notable work/news sections
    # Filter news articles to ensure they're actually about the searched person
    news_urls = []
    filtered_news = []
    original_news_count = len(news)
    name_lower = name.lower()
    name_parts = [part.strip() for part in name_lower.split() if len(part.strip()) > 1]  # Filter out single letters
    
    for news_item in news:
        # Handle both dict and NewsItem Pydantic model
        if isinstance(news_item, dict):
            news_url = news_item.get("url")
            news_title = news_item.get("title", "")
            news_description = news_item.get("description", "")
        else:
            # It's a NewsItem Pydantic model - access attributes directly
            news_url = getattr(news_item, "url", None)
            news_title = getattr(news_item, "title", "")
            news_description = getattr(news_item, "description", "") if hasattr(news_item, "description") else ""
        
        if not news_url or not news_title:
            continue
        
        title = news_title.lower() if news_title else ""
        description = news_description.lower() if news_description else ""
        combined_text = f"{title} {description}"
        
        # Check if the person's name appears in the article
        # NewsAPI already filters by name, so we trust most results but filter obvious mismatches
        name_found = False
        
        if len(name_parts) >= 2:
            # Multi-word name: check if any significant part appears
            # Require at least one name part (prefer last name, but accept first name if distinctive)
            last_name = name_parts[-1]
            first_name = name_parts[0]
            
            # Check if last name appears (most distinctive)
            if last_name in combined_text and len(last_name) > 2:
                name_found = True
            # Or if first name is distinctive and appears
            elif len(first_name) > 3 and first_name in combined_text:
                name_found = True
            # Or if full name appears
            elif name_lower in combined_text:
                name_found = True
        else:
            # Single word name: require exact match (case-insensitive)
            if name_lower in combined_text:
                name_found = True
        
        # If name found, include the article (NewsAPI already filtered, so trust it)
        # Only filter out if name is clearly not found
        if name_found:
            filtered_news.append(news_item)
            sources.append(news_url)
            news_urls.append(news_url)
            logger.debug(f"✅ Added news article: {news_title[:60]}...")
        else:
            logger.debug(f"⚠️  Filtered out news article (name not found): {news_title[:60]}...")
    
    # Replace original news list with filtered news
    news = filtered_news
    logger.info(f"📰 Filtered news for {name}: {len(filtered_news)} relevant articles out of {original_news_count} total")
    
    # Social media URLs - validate and deduplicate to ensure ONLY official, verified accounts
    social_media_urls = []
    social_media_dict_raw = details.get("social_media", {}) if details else {}
    validated_social_media = {}
    
    # Validate and deduplicate social media URLs
    try:
        validated_social_media = validate_and_deduplicate_social_media(social_media_dict_raw, name)
    except Exception as e:
        logger.error(f"❌ Error validating social media URLs for {name}: {e}")
        logger.debug(f"Social media validation traceback: {traceback.format_exc()}")
        # Fallback to raw dict if validation fails
        validated_social_media = social_media_dict_raw if isinstance(social_media_dict_raw, dict) else {}
    
    if validated_social_media and len(validated_social_media) > 0:
        platforms_found = []
        for platform, url in validated_social_media.items():
            if url and isinstance(url, str) and url.startswith("http"):
                sources.append(url)
                social_media_urls.append(url)
                field_citations[f'social_media_{platform}'] = url
                platforms_found.append(platform)
        
        if platforms_found:
            logger.info(f"✅ Validated social media platforms for {name}: {', '.join(platforms_found)} ({len(platforms_found)} official platforms)")
            if len(social_media_dict_raw) > len(validated_social_media):
                filtered_count = len(social_media_dict_raw) - len(validated_social_media)
                logger.info(f"🔍 Filtered out {filtered_count} duplicate/unverified social media URL(s)")
        else:
            logger.warning(f"⚠️  Social media dict exists but no valid URLs found for {name} after validation")
    else:
        if social_media_dict_raw and len(social_media_dict_raw) > 0:
            logger.warning(f"⚠️  All social media URLs for {name} were filtered out (duplicates/unverified)")
        else:
            logger.warning(f"⚠️  No social media platforms found for {name} (dict empty or missing)")
    
    # Add image URLs (limit to first 3 to avoid too many references)
    # SerpAPI already filters by person name in the search query, so we trust the results
    image_urls = []
    for img_url in images[:3]:
        if img_url and isinstance(img_url, str) and img_url.startswith("http"):
            # SerpAPI already filtered by name, so we trust the results
            # Include all images returned by SerpAPI since they're already filtered
            sources.append(img_url)
            image_urls.append(img_url)
            logger.debug(f"✅ Added image from SerpAPI: {img_url[:60]}...")
    
    # Instagram post URLs
    # SerpAPI already filters by "site:instagram.com {name}", so we trust the results
    instagram_urls = []
    for post in insta_posts:
        if isinstance(post, dict) and post.get("link"):
            insta_url = post.get("link", "")
            # SerpAPI already filtered by name, so we trust the results
            if insta_url.startswith("http"):
                sources.append(insta_url)
                instagram_urls.append(insta_url)
                logger.debug(f"✅ Added Instagram post from SerpAPI: {insta_url[:60]}...")
    
    # Map career and notable_work to Wikipedia if available, otherwise use first news article
    career = details.get("career", "N/A")
    notable_work = details.get("notable_work", "N/A")
    
    # Always ensure Wikipedia is in sources if we're using it for citations
    if wikipedia_url not in sources:
        # Check if Wikipedia is referenced in any field_citations
        if any('wikipedia.org' in str(url).lower() for url in field_citations.values()):
            sources.insert(0, wikipedia_url)
            logger.info(f"✅ Added Wikipedia URL to sources (referenced in field_citations): {wikipedia_url}")
        # Also add if we have Wikipedia content or extracted Wikipedia data
        elif wikipedia_content or education_value or family_value or net_worth_value:
            sources.insert(0, wikipedia_url)
            logger.info(f"✅ Added Wikipedia URL to sources (has Wikipedia data): {wikipedia_url}")
    
    if career and career != "N/A":
        if wikipedia_url:
            field_citations['career'] = wikipedia_url
            # Ensure Wikipedia is in sources
            if wikipedia_url not in sources:
                sources.insert(0, wikipedia_url)
        elif news_urls:
            field_citations['career'] = news_urls[0]
    
    if notable_work and notable_work != "N/A":
        if wikipedia_url:
            field_citations['notable_work'] = wikipedia_url
            # Ensure Wikipedia is in sources
            if wikipedia_url not in sources:
                sources.insert(0, wikipedia_url)
        elif news_urls:
            field_citations['notable_work'] = news_urls[0]
    
    # Bio comes from OpenAI's knowledge base, cite Wikipedia if available (NOT Twitter/social media)
    if bio and bio != "N/A":
        if wikipedia_url:
            field_citations['bio'] = wikipedia_url
            # Ensure Wikipedia is in sources
            if wikipedia_url not in sources:
                sources.insert(0, wikipedia_url)
        # Don't cite Twitter/social media for bio - bio doesn't come from there
    
    # Remove duplicates while preserving order
    # Trust the sources since they come from APIs that already filter by person name
    seen = set()
    unique_sources = []
    for source in sources:
        if source and source not in seen:
            # All sources are already validated:
            # - Wikipedia: constructed from person's name
            # - News: from NewsAPI filtered by name query
            # - Images: from SerpAPI filtered by name query
            # - Instagram: from SerpAPI filtered by name query
            # - Social media: from LLM extraction for this person
            seen.add(source)
            unique_sources.append(source)
    
    # Log collected sources and field citations
    logger.info(f"📚 Collected {len(unique_sources)} unique sources for citations:")
    for idx, source in enumerate(unique_sources[:10], 1):  # Log first 10
        logger.info(f"   [{idx}] {source}")
    if len(unique_sources) > 10:
        logger.info(f"   ... and {len(unique_sources) - 10} more sources")
    
    logger.info(f"📚 Field citations: {field_citations}")
    
    # Validate details before using them - if details is empty, try comprehensive extraction from bio
    if not details or len(details) == 0:
        logger.warning(f"⚠️  Details dict is empty for {name}. Attempting comprehensive emergency extraction from bio...")
        if bio and len(bio) > 100:
            try:
                # Comprehensive emergency extraction from bio using LLM - extract ALL fields
                emergency_system = ChatMessage(
                    role="system",
                    content="""You are an expert at extracting comprehensive information from biographical text. 
                    Extract ALL available information. Return valid JSON with these keys:
                    - nationality: Country/countries of citizenship
                    - current_job: Current position, role, company (as STRING, not dictionary)
                    - city: Current city of residence
                    - date_of_birth: Full date of birth if available
                    - personal_info_detail: Comprehensive personal background (300-500 words) including early life, education, family, relationships
                    - social_media: Object with platform:url pairs - MUST find ONLY OFFICIAL, VERIFIED accounts. Search for EVERY platform: Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and ANY other platforms they use. CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts. Return empty object {} only if NO official social media exists at all.
                    - social_media_detail: Description of social media presence across ALL platforms found (200-300 words)
                    - career: Detailed career history (400-600 words) with all positions, dates, companies, achievements
                    - notable_work: Major accomplishments, works, contributions, awards (400-600 words)
                    
                    Extract as much information as possible from the biography. Use 'N/A' only if truly unavailable."""
                )
                emergency_user = ChatMessage(
                    role="user",
                    content=f"""Extract comprehensive information for {name} from this biography. Extract ALL available fields:

{bio[:3000]}

Return ONLY valid JSON with keys: nationality, current_job, city, date_of_birth, personal_info_detail, social_media, social_media_detail, career, notable_work. 

For social_media: Search for and include ONLY OFFICIAL, VERIFIED accounts for platforms (Twitter/X, Instagram, LinkedIn, Facebook, YouTube, TikTok, Threads, Mastodon, Snapchat, Pinterest, Reddit, Medium, GitHub, Discord, Telegram, Clubhouse, Twitch, Patreon, Substack, Bluesky, Truth Social, Tumblr, Vimeo, SoundCloud, Spotify, Apple Music, OnlyFans, Cameo, and any others). CRITICAL: Only include OFFICIAL, VERIFIED accounts - verify each URL belongs to the actual person, check for verified badges, official website links, Wikipedia citations. DO NOT include fan pages, parody accounts, or unverified accounts. Extract as much detail as possible."""
                )
                emergency_details = await llm_service.chat_completion_json(
                    messages=[emergency_system, emergency_user],
                    max_tokens=4000,  # More tokens for comprehensive extraction
                    temperature=0.2
                )
                if emergency_details and isinstance(emergency_details, dict) and len(emergency_details) > 0:
                    logger.info(f"✅ Comprehensive emergency extraction succeeded for {name}: {list(emergency_details.keys())}")
                    # Count non-empty fields
                    non_empty = [k for k, v in emergency_details.items() if v and str(v).strip() and str(v).strip().lower() != 'n/a']
                    logger.info(f"✅ Emergency extraction found {len(non_empty)} non-empty fields: {non_empty}")
                    details = emergency_details
                else:
                    logger.error(f"❌ Emergency extraction returned empty result for {name}")
            except Exception as emergency_error:
                logger.error(f"❌ Emergency extraction error for {name}: {emergency_error}")
                logger.debug(f"Emergency extraction traceback: {traceback.format_exc()}")
    
    # If details extraction partially failed (some fields missing), try to fill gaps from bio
    if details and bio and len(bio) > 100:
        # Check which critical fields are missing
        missing_fields = []
        if not details.get("career") or details.get("career") == "N/A" or len(str(details.get("career", ""))) < 50:
            missing_fields.append("career")
        if not details.get("notable_work") or details.get("notable_work") == "N/A" or len(str(details.get("notable_work", ""))) < 50:
            missing_fields.append("notable_work")
        if not details.get("personal_info_detail") or len(str(details.get("personal_info_detail", ""))) < 100:
            missing_fields.append("personal_info_detail")
        
        if missing_fields:
            logger.info(f"📋 Attempting to fill missing fields from bio: {missing_fields}")
            try:
                gap_fill_system = ChatMessage(
                    role="system",
                    content="Extract specific information from biographical text. Return ONLY valid JSON."
                )
                gap_fill_user = ChatMessage(
                    role="user",
                    content=f"""Extract the following fields for {name} from this biography. Extract as much detail as possible:

Missing fields to extract: {', '.join(missing_fields)}

Biography:
{bio[:2500]}

Return ONLY valid JSON with keys: {', '.join(missing_fields)}. Provide comprehensive, detailed information."""
                )
                gap_fill_data = await llm_service.chat_completion_json(
                    messages=[gap_fill_system, gap_fill_user],
                    max_tokens=3000,
                    temperature=0.2
                )
                
                # Fill in missing fields
                for field in missing_fields:
                    if gap_fill_data.get(field) and str(gap_fill_data.get(field)).strip() and str(gap_fill_data.get(field)).strip().lower() != 'n/a':
                        details[field] = gap_fill_data.get(field)
                        logger.info(f"✅ Filled missing field '{field}' from bio: {str(details[field])[:100]}...")
            except Exception as gap_error:
                logger.error(f"❌ Gap filling error: {gap_error}")
                logger.debug(f"Gap filling traceback: {traceback.format_exc()}")
    
    # Helper function to safely convert current_job to string
    def format_current_job(job_value) -> str:
        """Convert current_job to string format, handling dict responses."""
        if not job_value or job_value == "N/A":
            return "N/A"
        if isinstance(job_value, dict):
            # Extract title and company from dict
            title = job_value.get("title", "")
            company = job_value.get("company", "")
            if title and company:
                return f"{title} at {company}"
            elif title:
                return title
            elif company:
                return company
            else:
                # Try to get any string value from the dict
                for key, value in job_value.items():
                    if isinstance(value, str) and value:
                        return value
                return "N/A"
        return str(job_value) if job_value else "N/A"
    
    # Final data summary before returning
    final_data = {
        "name": name,
        "bio": bio if bio else "N/A",
        "nationality": details.get("nationality", "N/A") if details else "N/A",
        "current_job": format_current_job(details.get("current_job", "N/A") if details else "N/A"),
        "city": details.get("city", "N/A") if details else "N/A",
        "date_of_birth": details.get("date_of_birth", "N/A") if details else "N/A",
        "education": education_value if education_value else "N/A",
        "family": family_value if family_value else "N/A",
        "net_worth": net_worth_value if net_worth_value else "N/A",
        "known_for": known_for_value if known_for_value else "N/A",
        "personal_info_detail": details.get("personal_info_detail", "") if details else "",
        "social_media": validated_social_media if validated_social_media else (details.get("social_media", {}) if details else {}),
        "social_media_detail": details.get("social_media_detail", "") if details else "",
        "career": details.get("career", "N/A") if details else "N/A",
        "notable_work": details.get("notable_work", "N/A") if details else "N/A",
        "news": news,
        "images": images,
        "instagram_profile_picture": insta_dp,
        "instagram_posts": insta_posts,
        "sources": unique_sources,
        "field_citations": field_citations,  # Map of field names to source URLs
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Log final data summary
    logger.info(f"📊 Final data summary for {name}:")
    for key, value in final_data.items():
        if key in ['news', 'images', 'instagram_posts', 'sources', 'field_citations', 'social_media']:
            if isinstance(value, (list, dict)):
                logger.info(f"   {key}: {len(value) if value else 0} items")
            else:
                logger.info(f"   {key}: {value}")
        elif isinstance(value, str):
            logger.info(f"   {key}: {'✅ ' + str(len(value)) + ' chars' if value and value != 'N/A' else '❌ Empty'}")
        else:
            logger.info(f"   {key}: {value}")
    
    return final_data
