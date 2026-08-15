# --- Assume a new file: models.py ---
from pydantic import BaseModel, Field
from typing import List, Union, Dict, Any

class NewsItem(BaseModel):
    title: str = Field("", description="Title of the news article.")
    url: str = Field("", description="URL of the news article.")

class PersonProfile(BaseModel):
    name: str = Field(..., description="The person's full name.")
    bio: str = Field("", description="A brief biography of the person.")
    nationality: str = Field("N/A", description="Nationality of the person.")
    current_job: str = Field("N/A", description="Current job/occupation.")
    city: str = Field("N/A", description="City of residence.")
    date_of_birth: str = Field("N/A", description="Date of birth.")
    education: str = Field("N/A", description="Educational background from Wikipedia.")
    family: str = Field("N/A", description="Family information from Wikipedia.")
    net_worth: str = Field("N/A", description="Net worth or estimated wealth from Wikipedia.")
    known_for: str = Field("N/A", description="What the person is known for from Wikipedia.")
    personal_info_detail: str = Field("", description="Detailed personal information.")
    social_media: Dict[str, Any] = Field(default_factory=dict, description="Social media profiles.")
    social_media_detail: str = Field("", description="Social media presence details.")
    career: str = Field("N/A", description="Career information.")
    notable_work: str = Field("N/A", description="Notable work/achievements.")
    news: List[Union[NewsItem, Dict[str, Any]]] = Field(default_factory=list, description="A list of recent news articles.")
    images: List[str] = Field(default_factory=list, description="A list of image URLs or base64 data.")
    instagram_posts: List[Dict[str, Any]] = Field(default_factory=list, description="A list of Instagram posts.")
    instagram_profile_picture: str = Field("", description="Instagram profile picture URL.")
    sources: List[str] = Field(default_factory=list, description="List of source URLs for citations and references.")
    field_citations: Dict[str, str] = Field(default_factory=dict, description="Map of field names to their source URLs for accurate citations.")
    created_at: str = Field("", description="Timestamp when profile was created.")
    
    class Config:
        arbitrary_types_allowed = True

# --- End models.py assumption ---