from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import json
from typing import Optional, Dict, Any, List
import os
import base64
from datetime import datetime, timedelta
import dateutil.parser
from dateutil.relativedelta import relativedelta
import calendar
from phi.agent import Agent
from phi.model.groq import Groq
import asyncio
from dotenv import load_dotenv
from database import AppointmentDatabase
import re
import speech_recognition as sr
import io
import tempfile
from entity_extractor import EntityExtractor, identify_intent
import shutil

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="AI Voice Assistant")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize database
db = AppointmentDatabase()

# Initialize Groq agent
agent = Agent(
    model=Groq(id="llama-3.3-70b-versatile"),
    markdown=True  # Keep markdown enabled for web display
)

# Initialize entity extractor
entity_extractor = EntityExtractor()

# Global memory to store user information and conversation history
memory = {
    "users": {},  # Store user-specific info like common contacts
    "conversations": {},  # Store conversation history by session_id
    "entities": {},  # Store all entities mentioned by users
    "topics_discussed": {},  # Track topics already discussed by session
    "questions_asked": {}  # Track questions already asked to avoid repetition
}

# Define models
class Message(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    is_speech: bool = False  # Flag to indicate if this is for speech output

class TranscriptionRequest(BaseModel):
    audio_data: str  # Base64 encoded audio

class WebSocketMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    is_speech: bool = False  # Flag to indicate if this is for speech output

# Connected WebSocket clients
active_connections = []

def strip_markdown(text):
    """
    Remove markdown formatting characters from text for speech output
    """
    if not text:
        return text
    
    # Remove headers (# Header)
    text = re.sub(r'#+\s+', '', text)
    
    # Remove bold/italic formatting
    text = re.sub(r'\*\*|\*|__|\^|~~|`', '', text)
    
    # Remove bullet points
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    
    # Remove numbered lists
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    
    # Remove blockquotes
    text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)
    
    # Remove horizontal rules
    text = re.sub(r'\n\s*[\-\*_]{3,}\s*\n', '\n\n', text)
    
    # Remove links - convert [text](url) to just text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Fix double spaces
    text = re.sub(r'\s{2,}', ' ', text)
    
    # Fix multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def format_response_for_output(text, is_speech=False):
    """Format the response based on output type - keep markdown for display, strip for speech"""
    if is_speech:
        return strip_markdown(text)
    return text

def parse_relative_date(text):
    """
    Parse relative date expressions like 'tomorrow', 'next Monday', 'in 3 days',
    '4 days from June 11', etc.
    
    Returns a datetime object or None if no relative date is found
    """
    today = datetime.now()
    text = text.lower()
    
    # Handle simple relative dates
    if "tomorrow" in text:
        return today + timedelta(days=1)
    
    if "today" in text:
        return today
    
    if "yesterday" in text:
        return today - timedelta(days=1)
    
    # Handle "next/this [day of week]"
    days_of_week = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    for day, day_num in days_of_week.items():
        # Handle "next Monday" type expressions
        next_day_match = re.search(rf"next\s+{day}", text)
        if next_day_match:
            days_ahead = (day_num - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # If today is Monday and we want next Monday, go 7 days ahead
            return today + timedelta(days=days_ahead)
        
        # Handle "this Monday" type expressions
        this_day_match = re.search(rf"this\s+{day}", text)
        if this_day_match:
            days_ahead = (day_num - today.weekday()) % 7
            if days_ahead == 0:  # If it's already this day
                return today
            elif days_ahead < 0:  # If this day already passed this week
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        
        # Handle just "Monday" type expressions
        just_day_match = re.search(rf"\b{day}\b", text)
        if just_day_match and not next_day_match and not this_day_match:
            days_ahead = (day_num - today.weekday()) % 7
            if days_ahead == 0:  # Today
                return today
            elif days_ahead > 0:  # Later this week
                return today + timedelta(days=days_ahead)
            else:  # Next week
                return today + timedelta(days=days_ahead + 7)
    
    # Handle "in X days/weeks/months" expressions
    in_time_match = re.search(r"in\s+(\d+)\s+(day|days|week|weeks|month|months)", text)
    if in_time_match:
        number = int(in_time_match.group(1))
        unit = in_time_match.group(2)
        
        if unit in ["day", "days"]:
            return today + timedelta(days=number)
        elif unit in ["week", "weeks"]:
            return today + timedelta(days=number * 7)
        elif unit in ["month", "months"]:
            return today + relativedelta(months=number)
    
    # Handle "after X days/weeks/months" expressions
    after_time_match = re.search(r"after\s+(\d+)\s+(day|days|week|weeks|month|months)", text)
    if after_time_match:
        number = int(after_time_match.group(1))
        unit = after_time_match.group(2)
        
        if unit in ["day", "days"]:
            return today + timedelta(days=number)
        elif unit in ["week", "weeks"]:
            return today + timedelta(days=number * 7)
        elif unit in ["month", "months"]:
            return today + relativedelta(months=number)
    
    # Handle "X days/weeks/months from now" expressions
    from_now_match = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)\s+from\s+now", text)
    if from_now_match:
        number = int(from_now_match.group(1))
        unit = from_now_match.group(2)
        
        if unit in ["day", "days"]:
            return today + timedelta(days=number)
        elif unit in ["week", "weeks"]:
            return today + timedelta(days=number * 7)
        elif unit in ["month", "months"]:
            return today + relativedelta(months=number)
    
    # Handle "X days/weeks/months from [date]" expressions
    from_date_match = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)\s+from\s+(.+)", text)
    if from_date_match:
        number = int(from_date_match.group(1))
        unit = from_date_match.group(2)
        date_str = from_date_match.group(3).strip()
        
        try:
            # Try to parse the base date
            base_date = dateutil.parser.parse(date_str, fuzzy=True)
            
            if unit in ["day", "days"]:
                return base_date + timedelta(days=number)
            elif unit in ["week", "weeks"]:
                return base_date + timedelta(days=number * 7)
            elif unit in ["month", "months"]:
                return base_date + relativedelta(months=number)
        except:
            print(f"[DATE PARSING] Failed to parse base date: {date_str}")
            return None
    
    # Handle "end of month", "beginning of next month", etc.
    if "end of month" in text:
        last_day = calendar.monthrange(today.year, today.month)[1]
        return datetime(today.year, today.month, last_day)
    
    if "beginning of month" in text or "start of month" in text:
        return datetime(today.year, today.month, 1)
    
    if "end of next month" in text:
        next_month = today.month + 1
        year = today.year
        if next_month > 12:
            next_month = 1
            year += 1
        last_day = calendar.monthrange(year, next_month)[1]
        return datetime(year, next_month, last_day)
    
    if "beginning of next month" in text or "start of next month" in text:
        next_month = today.month + 1
        year = today.year
        if next_month > 12:
            next_month = 1
            year += 1
        return datetime(year, next_month, 1)
    
    return None

def format_date_for_display(date_obj):
    """Format a datetime object into a human-readable string"""
    if not date_obj:
        return None
    
    # Format as "Monday, January 1, 2023"
    return date_obj.strftime("%A, %B %d, %Y")

def enhance_entity_extraction(text):
    """Enhance the basic entity extraction with relative date/time understanding"""
    # First get the basic entities
    entities = entity_extractor.extract_entities(text)
    
    # Check if we already have a date, if not try to extract a relative date
    if "date" not in entities or not entities["date"]:
        relative_date = parse_relative_date(text)
        if relative_date:
            entities["date"] = format_date_for_display(relative_date)
            print(f"[RELATIVE DATE] Parsed relative date: {entities['date']}")
        else:
            # Try to extract date for common date formats that might not be caught
            # Look for patterns like "23rd July" or "July 23" without year
            date_patterns = [
                # "23rd July", "23 July", etc.
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)",
                # "July 23", "July 23rd", etc.
                r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?",
                # Short month names: "23 Jan", "Jan 23"
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?"
            ]
            
            text_lower = text.lower()
            
            # Map month names to numbers
            month_to_num = {
                "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, 
                "sep": 9, "oct": 10, "nov": 11, "dec": 12
            }
            
            curr_year = datetime.now().year
            
            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Handle both formats: "23 July" and "July 23"
                    if match.group(1) in month_to_num:
                        # Format: "July 23"
                        month = match.group(1)
                        day = match.group(2)
                        month_num = month_to_num[month]
                    else:
                        # Format: "23 July"
                        day = match.group(1)
                        month = match.group(2)
                        month_num = month_to_num[month]
                        
                    # Validate day is in range 1-31
                    day_num = int(re.sub(r'[^\d]', '', day))
                    if 1 <= day_num <= 31:
                        entities["date"] = f"{curr_year}-{month_num:02d}-{day_num:02d}"
                        print(f"[DATE EXTRACTION] Extracted date: {entities['date']}")
                        break
                        
            # Also look for just year numbers (e.g., "2025")
            if not entities["date"]:
                year_match = re.search(r'\b(20\d{2})\b', text)
                if year_match:
                    # If we found a year but no month/day, assume it's January 1st
                    # This is just a fallback for when only a year is mentioned
                    year = year_match.group(1)
                    entities["date"] = f"{year}-01-01"
                    print(f"[DATE EXTRACTION] Extracted year as date: {entities['date']}")
            
    return entities

# Function to parse entities from natural language with AI fallback
def extract_entities(text):
    """Extract person, date, time from natural language text using EntityExtractor and AI fallback"""
    print(f"[ENTITY EXTRACTION] Processing text: '{text}'")
    
    # Use the enhanced entity extraction with relative date parsing
    result = enhance_entity_extraction(text)
    
    # Don't treat common single-word responses as person names
    if result["person"] is not None:
        # Check for common responses that should not be treated as names
        common_responses = ["yes", "no", "okay", "sure", "correct", "right", "thanks", "thank", "please"]
        # Check for time patterns that should not be treated as names
        time_patterns = [r'^\d{1,2}:\d{2}$', r'^\d{1,2}(am|pm|a\.m\.|p\.m\.)$', r'^\d{1,2}\s*(am|pm|a\.m\.|p\.m\.)$']
        # Add more common words that shouldn't be treated as person names
        common_words = ["feeling", "anytime", "anything", "something", "nothing", "anyone", "someone", 
                       "nobody", "everybody", "everyone", "whenever", "whatever", "however", "anywhere", 
                       "going", "looking", "thinking", "trying", "hoping", "planning", "wanting", "needing",
                       "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                       "first", "second", "third", "fourth", "fifth", "last", "next", "this", "that",
                       "these", "those", "there", "here", "today", "tomorrow", "yesterday",
                       "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        # Check for singular capitalized word at beginning of sentence (likely not a person)
        if len(text.split()) > 2 and text.strip().startswith(result["person"]) and len(result["person"].split()) == 1:
            print(f"[ENTITY EXTRACTION] Ignoring capitalized first word as person name: {result['person']}")
            result["person"] = None
        
        # Check if the person is a common response
        elif result["person"].lower() in common_responses:
            print(f"[ENTITY EXTRACTION] Ignoring common response as person name: {result['person']}")
            result["person"] = None
        
        # Check if the person is a common word that shouldn't be treated as a name
        elif result["person"].lower() in common_words:
            print(f"[ENTITY EXTRACTION] Ignoring common word as person name: {result['person']}")
            result["person"] = None
        
        # Check if the person matches a time pattern
        elif any(re.match(pattern, result["person"].lower()) for pattern in time_patterns):
            print(f"[ENTITY EXTRACTION] Ignoring time pattern as person name: {result['person']}")
            result["person"] = None
        
        # Check if person is a scheduling keyword
        elif result["person"].lower() in ["another", "new", "schedule", "appointment", "what", "ai"]:
            print(f"[ENTITY EXTRACTION] Ignoring scheduling keyword as person name: {result['person']}")
            result["person"] = None
    
    # Track if basic extraction failed to get important entities
    extraction_failed = (result["person"] is None or result["date"] is None or result["time"] is None)
    
    if extraction_failed:
        print(f"[ENTITY EXTRACTION] Basic extraction incomplete: {result}")
        missing_entities = []
        if result["person"] is None:
            missing_entities.append("person")
        if result["date"] is None:
            missing_entities.append("date")
        if result["time"] is None:
            missing_entities.append("time")
        
        print(f"[ENTITY EXTRACTION] Missing entities: {missing_entities}")
    
    print(f"[ENTITY EXTRACTION] Final entities from extractor: {result}")
    return result

def extract_topics_from_text(text):
    """Extract general topics and concepts from text"""
    # Simple keyword-based topic extraction
    topics = []
    
    # Define some topic keywords to match
    topic_keywords = {
        "appointment": ["appointment", "schedule", "book", "reservation", "meeting", "availability"],
        "time_management": ["time", "schedule", "calendar", "availability", "busy", "free"],
        "contact": ["contact", "person", "people", "name", "meet with", "call"],
        "health": ["doctor", "health", "medical", "appointment", "checkup", "examination"],
        "business": ["business", "meeting", "client", "customer", "project", "work"],
        "personal": ["family", "friend", "personal", "vacation", "holiday", "break"]
    }
    
    text_lower = text.lower()
    for topic, keywords in topic_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            topics.append(topic)
    
    return topics

def update_memory_with_conversation(session_id, user_text, ai_response, context):
    """Store conversation details and extract useful information for memory"""
    if not session_id:
        return
    
    # Initialize memory structures if needed
    if session_id not in memory["conversations"]:
        memory["conversations"][session_id] = []
    if session_id not in memory["entities"]:
        memory["entities"][session_id] = {}
    if session_id not in memory["topics_discussed"]:
        memory["topics_discussed"][session_id] = set()
    if session_id not in memory["questions_asked"]:
        memory["questions_asked"][session_id] = set()
    
    # Store the conversation with timestamp
    timestamp = datetime.now().isoformat()
    
    # Copy the context to avoid reference issues
    context_copy = {}
    if context:
        for key, value in context.items():
            context_copy[key] = value
    
    memory["conversations"][session_id].append({
        "user": user_text,
        "ai": ai_response,
        "timestamp": timestamp,
        "context": context_copy
    })
    
    print(f"[MEMORY] Stored conversation at {timestamp} with context: {context_copy}")
    
    # Extract entities from user text
    entities = extract_entities(user_text)
    for key, value in entities.items():
        if value:
            if key not in memory["entities"][session_id]:
                memory["entities"][session_id][key] = []
            if value not in memory["entities"][session_id][key]:
                memory["entities"][session_id][key].append(value)
                print(f"[MEMORY] Added entity {key}: {value}")
    
    # Extract and store topics
    topics = extract_topics_from_text(user_text)
    for topic in topics:
        memory["topics_discussed"][session_id].add(topic)
        print(f"[MEMORY] Added topic: {topic}")
    
    # Store potential questions asked
    if "?" in user_text:
        memory["questions_asked"][session_id].add(user_text.strip())
        print(f"[MEMORY] Stored question: {user_text}")

def has_similar_question_been_asked(session_id, question):
    """Check if a similar question has been asked before"""
    if not session_id or session_id not in memory["questions_asked"]:
        return False
    
    question = question.lower().strip()
    
    for asked_question in memory["questions_asked"][session_id]:
        # Simple similarity check - can be improved
        if question in asked_question.lower() or asked_question.lower() in question:
            return True
    
    return False

def get_memory_for_context(session_id, conversation_context=None):
    """Retrieve relevant memory information for the current context"""
    if conversation_context is None:
        conversation_context = {}
    
    if not session_id:
        return conversation_context
    
    # Get user-specific stored info
    if session_id in memory["users"]:
        for key, value in memory["users"][session_id].items():
            if key not in conversation_context:
                conversation_context[key] = value
                print(f"[MEMORY] Retrieved {key} = {value} from user memory")
    
    # Get entity information
    if session_id in memory["entities"]:
        for key, values in memory["entities"][session_id].items():
            if key not in conversation_context and values:
                # Use most recent entity value
                conversation_context[key] = values[-1]
                print(f"[MEMORY] Retrieved entity {key} = {values[-1]}")
    
    return conversation_context

def generate_conversation_summary(session_id):
    """Generate a summary of the conversation history"""
    if session_id not in memory["conversations"]:
        return "No conversation history found."
    
    conversation = memory["conversations"][session_id]
    
    if not conversation:
        return "No conversation history found."
    
    # Use Groq to generate a concise summary
    conversation_text = "\n".join([f"User: {msg['user']}\nAI: {msg['ai']}" for msg in conversation])
    
    prompt = f"""
    Summarize the following conversation between a user and an AI assistant in a single paragraph.
    Focus on the main topics discussed, decisions made, and information gathered.
    Keep the summary concise but informative.
    Do not use any markdown formatting (no # or * characters) in your response.
    
    Conversation:
    {conversation_text}
    
    Summary:
    """
    
    try:
        summary = agent.run(prompt).content
        # Always strip markdown for summaries to be safe
        return strip_markdown(summary)
    except Exception as e:
        print(f"Error generating summary: {e}")
        # Fallback to a basic summary
        return f"This conversation included {len(conversation)} exchanges about appointments and scheduling."

def check_if_summary_requested(text):
    """Check if the user is requesting a conversation summary"""
    summary_patterns = [
        r"(conversation|chat) summary",
        r"summarize (our|this) (conversation|chat|discussion)",
        r"give me a summary",
        r"what have we (talked|discussed) (about)?",
        r"recap (our|this) (conversation|chat)",
        r"sum( |)up (our|this|the) (conversation|chat|discussion)"
    ]
    
    text_lower = text.lower()
    for pattern in summary_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False

async def extract_entities_with_ai(text, missing_entities):
    """Use the LLM to extract entities from text when regular extraction fails"""
    print(f"[AI EXTRACTION] Attempting to extract {missing_entities} from text: '{text}'")
    
    entities_to_extract = ", ".join(missing_entities)
    
    prompt = f"""
    Extract the following entities from this text: {entities_to_extract}
    Text: "{text}"
    
    Format your response as valid JSON with these keys: {json.dumps(missing_entities)}
    If an entity is not present in the text, set its value to null or "unknown" (not a string "NULL").
    
    Important guidelines:
    - For "person": Extract the name of the person to meet with, doctor name, or other contact.
      - If the text mentions "doctor" or "physician", use "Doctor" as the person
      - If no specific person is mentioned, return null for person
      - Do not extract common words like "one", "that", "available", "anytime", etc. as person names
    
    - For "date": Extract appointment or meeting date
      - Dates should be in "Month Day, Year" format (e.g., "June 30, 2025")
      - If text contains only a date (like "July 25"), don't extract it as a time
      - For relative dates like "tomorrow" or "next Monday", do your best to translate them
    
    - For "time": Extract appointment or meeting time
      - Times should be in standard 12-hour format with AM/PM (e.g., "3:30 PM")
      - If text contains only a time (like "5pm"), don't extract it as a date
      - If text mentions "anytime", "whenever available", or similar, extract as "first available"
    
    Example response format:
    ```json
    {
      "person": "John Smith",
      "date": "June 15, 2023",
      "time": "3:30 PM"
    }
    ```
    
    Only return the JSON, nothing else.
    """
    
    try:
        response = agent.run(prompt)
        content = response.content.strip()
        
        # Extract JSON from the response
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content
        
        # Clean up common issues with JSON parsing
        # Replace any single quotes with double quotes for JSON compatibility
        json_str = json_str.replace("'", '"')
        
        # Fix common null issues
        json_str = json_str.replace('"NULL"', 'null')
        json_str = json_str.replace('"null"', 'null')
        json_str = json_str.replace('NULL', 'null')
        
        print(f"[AI EXTRACTION] Response: {json_str}")
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # Fall back to regex extraction if JSON parsing fails
            print("[AI EXTRACTION] JSON parsing failed, falling back to regex extraction")
            result = {}
            
            for entity in missing_entities:
                # Extract pattern like "person": "John Smith" or "date": null
                pattern = f'"{entity}"\\s*:\\s*(?:"([^"]*?)"|null)'
                match = re.search(pattern, json_str)
                if match and match.group(1):
                    result[entity] = match.group(1)
                else:
                    result[entity] = None
        
        # Convert any "NULL" strings to None
        for key in result:
            if isinstance(result[key], str):
                if result[key].lower() in ["null", "unknown", ""]:
                    result[key] = None
            
            # Validate that date doesn't look like a time
            if key == "date" and result[key] is not None:
                if re.search(r'^\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?$', str(result[key]).lower()):
                    print(f"[AI EXTRACTION] Rejected date value that looks like a time: {result[key]}")
                    result[key] = None
            
            # Validate that time doesn't look like a date
            if key == "time" and result[key] is not None:
                if re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', 
                            str(result[key]).lower()) or re.search(r'\d{4}-\d{2}-\d{2}', str(result[key])):
                    print(f"[AI EXTRACTION] Rejected time value that looks like a date: {result[key]}")
                    result[key] = None
                
                # Convert flexible time expressions to a standard format
                if result[key] and any(phrase in result[key].lower() for phrase in 
                                      ["anytime", "any time", "whenever", "available", "asap", "as soon as", "earliest"]):
                    result[key] = "first available"
                    print(f"[AI EXTRACTION] Converted flexible time expression to: {result[key]}")
        
        # Ensure all missing entities are in the result
        for entity in missing_entities:
            if entity not in result:
                result[entity] = None
                
        print(f"[AI EXTRACTION] Final extracted entities: {result}")
        return result
    except Exception as e:
        print(f"[AI EXTRACTION] Error: {e}")
        return {entity: None for entity in missing_entities}

async def process_appointment_intent(message_text, context, session_id=None):
    """Process appointment-related intents and determine next steps"""
    intent = context.get("intent", "schedule_appointment")
    phase = context.get("phase", "init")
    response = ""
    
    print(f"[PROCESS_INTENT] Processing with phase: {phase}, intent: {intent}, context: {context}")
    
    # Check for special time expressions when in asking_time phase
    if phase == "asking_time" and "time" not in context:
        # Look for special time expressions
        anytime_patterns = [
            r"any\s*time",
            r"when\w*\s+available",
            r"earliest\s+available",
            r"first\s+available",
            r"whenever",
            r"any\s+open\w*\s+slot",
            r"any\s+opening",
            r"as\s+soon\s+as\s+possible",
            r"asap",
            r"fit\s+me\s+in",
            r"earliest\s+appointment"
        ]
        
        for pattern in anytime_patterns:
            if re.search(pattern, message_text.lower()):
                print(f"[PROCESS_INTENT] Detected flexible time expression: '{message_text}'")
                context["time"] = "first available"
                print(f"[PROCESS_INTENT] Set time to 'first available'")
                break
    
    # Check for "cancel this appointment" or "cancel current appointment" patterns
    cancel_current_patterns = [
        "cancel this appointment", 
        "cancel the current appointment",
        "cancel that appointment",
        "cancel it",
        "don't want this appointment",
        "remove this appointment"
    ]
    
    if any(pattern in message_text.lower() for pattern in cancel_current_patterns) and context.get("person") and context.get("date"):
        # User wants to cancel the appointment we're currently discussing
        print("[PROCESS_INTENT] Detected request to cancel current appointment")
        context["intent"] = "cancel_appointment"
        intent = "cancel_appointment"
        context["phase"] = "confirming_cancel"
        return f"I'll cancel your appointment with {context['person']} on {context['date']} at {context.get('time', 'the scheduled time')}. Is that correct?", context
    
    # Handle check availability intent specially
    if intent == "check_availability":
        print("[PROCESS_INTENT] Processing check_availability intent")
        
        if "person" not in context or not context["person"]:
            context["phase"] = "asking_person_check"
            return "Whose availability would you like to check?", context
            
        elif "date" not in context or not context["date"]:
            context["phase"] = "asking_date_check"
            return f"For which date would you like to check {context['person']}'s availability?", context
            
        else:
            # We have enough info to check availability
            context["phase"] = "showing_availability"
            # Here you would query the database for actual availability
            # For now, show mock data
            available_times = ["9:00 AM", "10:30 AM", "2:00 PM", "3:30 PM", "4:45 PM"]
            times_str = ", ".join(available_times)
            response = f"{context['person']} is available on {context['date']} at the following times: {times_str}"
            return response, context
    
    # Handle cancel appointment intent specially
    if intent == "cancel_appointment":
        print("[PROCESS_INTENT] Processing cancel_appointment intent")
        
        if "person" not in context or not context["person"]:
            context["phase"] = "asking_person_cancel"
            return "Whose appointment would you like to cancel?", context
            
        elif "date" not in context or not context["date"]:
            context["phase"] = "asking_date_cancel"
            return f"On what date is the appointment with {context['person']} that you want to cancel?", context
            
        elif "time" not in context or not context["time"]:
            context["phase"] = "asking_time_cancel"
            return f"At what time is the appointment with {context['person']} on {context['date']} that you want to cancel?", context
            
        else:
            # If we're already confirming and the user has confirmed
            if phase == "confirming_cancel" and any(word in message_text.lower() for word in ["yes", "correct", "right", "ok", "okay", "sure", "yeah", "yep", "do that", "please"]):
                # Here you would actually remove the appointment from the database
                try:
                    # Get correct person name (not "That") for the appointment
                    person = context.get("person")
                    if person and person.lower() == "that":  # Fix for "do that" scenario
                        # Find the last valid person name in context
                        for key, value in context.items():
                            if key == "previous_person" and value:
                                person = value
                                break
                    
                    date_str = context.get("date")
                    time_str = context.get("time")
                    
                    print(f"[CANCEL] Canceling appointment for {person} on {date_str} at {time_str}")
                    # Here you would call your database function to cancel
                    # db.cancel_appointment(person, date_str, time_str)
                    
                    # Mark as completed
                    context["phase"] = "completed"
                    context["appointment_completed_at"] = datetime.now().isoformat()
                    context["ready_for_new_topic"] = True
                    
                    # Make sure the correct person name is restored
                    context["person"] = person
                    
                    return f"I've cancelled your appointment with {person} on {date_str} at {time_str}. Is there anything else I can help you with?", context
                    
                except Exception as e:
                    print(f"[ERROR] Error cancelling appointment: {e}")
                    return "I'm sorry, there was an error cancelling your appointment. Please try again.", context
            else:
                # We have all required info for cancellation but need confirmation
                context["phase"] = "confirming_cancel"
                # Store the current person name as a backup in case "do that" changes it
                if context.get("person") and context["person"].lower() != "that":
                    context["previous_person"] = context["person"]
                return f"I'll cancel your appointment with {context['person']} on {context['date']} at {context['time']}. Is that correct?", context
    
    # Initialize phase if not set
    if not phase or phase == "init":
        if intent == "schedule_appointment":
            if "person" not in context or not context["person"]:
                context["phase"] = "asking_person"
                response = "Who would you like to schedule an appointment with?"
            elif "date" not in context or not context["date"]:
                context["phase"] = "asking_date"
                response = f"What day would you like to schedule with {context['person']}?"
            elif "time" not in context or not context["time"]:
                context["phase"] = "asking_time"
                response = f"What time would you like for your appointment with {context['person']} on {context['date']}?"
            else:
                # We have all required info
                context["phase"] = "confirming"
                response = f"I'll schedule your appointment with {context['person']} on {context['date']} at {context['time']}. Is that correct?"
        
        elif intent == "list_appointments":
            # Handle list appointments intent
            context["phase"] = "listing_appointments"
            # Here you would query the database for actual appointments
            # For now, show mock data
            response = "You have the following appointments scheduled:\n- Dr. Smith on Monday at 2:00 PM\n- Dentist on Friday at 10:30 AM"
    
    # Handle ongoing conversation based on current phase
    else:
        # Handle check_availability phases
        if phase == "asking_person_check":
            if "person" in context and context["person"]:
                # We have the person, now ask for date
                context["phase"] = "asking_date_check"
                response = f"For which date would you like to check {context['person']}'s availability?"
            else:
                response = "I need to know whose availability you want to check. Please provide a name."
                
        elif phase == "asking_date_check":
            if "date" in context and context["date"]:
                # We have all the info needed to check availability
                context["phase"] = "showing_availability"
                # Here you would query the database for actual availability
                # For now, show mock data
                available_times = ["9:00 AM", "10:30 AM", "2:00 PM", "3:30 PM", "4:45 PM"]
                times_str = ", ".join(available_times)
                response = f"{context['person']} is available on {context['date']} at the following times: {times_str}"
            else:
                response = f"I need a date to check availability for {context['person']}. What day are you interested in?"
                
        elif phase == "showing_availability" and "time" in message_text.lower():
            # User wants to schedule at one of the available times
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?', message_text.lower())
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                period = time_match.group(3) or ""
                
                # Convert to 24-hour format if needed
                if period.startswith('p') and hour < 12:
                    hour += 12
                elif period.startswith('a') and hour == 12:
                    hour = 0
                
                context["time"] = f"{hour:02d}:{minute:02d}"
                # Change intent to schedule and phase to confirming
                context["intent"] = "schedule_appointment"
                context["phase"] = "confirming"
                response = f"I'll schedule your appointment with {context['person']} on {context['date']} at {context['time']}. Is that correct?"
            else:
                response = "I didn't understand the time you want. Please specify a time like '3:30 PM'."
                
        # Handle cancel_appointment phases
        elif phase == "asking_person_cancel":
            if "person" in context and context["person"]:
                # We have the person, now ask for date
                context["phase"] = "asking_date_cancel"
                response = f"On what date is the appointment with {context['person']} that you want to cancel?"
            else:
                response = "I need to know whose appointment you want to cancel. Please provide a name."
                
        elif phase == "asking_date_cancel":
            if "date" in context and context["date"]:
                # We have the date, now ask for time
                context["phase"] = "asking_time_cancel"
                response = f"At what time is the appointment with {context['person']} on {context['date']} that you want to cancel?"
            else:
                response = f"I need to know the date of the appointment with {context['person']} that you want to cancel."
                
        elif phase == "asking_time_cancel":
            if "time" in context and context["time"]:
                # We have all the info, confirm cancellation
                context["phase"] = "confirming_cancel"
                # Store the current person name as a backup
                context["previous_person"] = context["person"]
                response = f"I'll cancel your appointment with {context['person']} on {context['date']} at {context['time']}. Is that correct?"
            else:
                response = f"At what time is the appointment with {context['person']} on {context['date']} that you want to cancel?"
                
        elif phase == "confirming_cancel":
            # Check if user confirmed cancellation
            if any(word in message_text.lower() for word in ["yes", "correct", "right", "ok", "okay", "sure", "do that", "please", "yeah", "yep"]):
                # Here you would remove the appointment from the database
                try:
                    # Get correct person name (not "That") for the appointment
                    person = context.get("person")
                    if person and person.lower() == "that":  # Fix for "do that" scenario
                        # Use the previous person name if available
                        if context.get("previous_person"):
                            person = context["previous_person"]
                    
                    date_str = context.get("date")
                    time_str = context.get("time")
                    
                    print(f"[CANCEL] Canceling appointment for {person} on {date_str} at {time_str}")
                    # Here you would call your database function to cancel
                    # db.cancel_appointment(person, date_str, time_str)
                    
                    # Mark as completed
                    context["phase"] = "completed"
                    context["appointment_completed_at"] = datetime.now().isoformat()
                    context["ready_for_new_topic"] = True
                    
                    # Make sure the correct person name is restored
                    context["person"] = person
                    
                    response = f"I've cancelled your appointment with {person} on {date_str} at {time_str}. Is there anything else I can help you with?"
                except Exception as e:
                    print(f"Error cancelling appointment: {e}")
                    response = "I'm sorry, there was an error cancelling your appointment. Please try again."
            else:
                # User didn't confirm, ask what they want to change
                context["phase"] = "asking_change_cancel"
                response = "What would you like to change about the cancellation?"
        
        # Handle schedule_appointment phases
        elif phase == "asking_person":
            if "person" in context and context["person"]:
                # We have the person, now ask for date
                context["phase"] = "asking_date"
                response = f"What day would you like to schedule with {context['person']}?"
            else:
                response = "I need to know who you want to schedule with. Please provide a name."
        
        elif phase == "asking_date":
            if "date" in context and context["date"]:
                # We have the date, now ask for time
                context["phase"] = "asking_time"
                response = f"What time would you like for your appointment with {context['person']} on {context['date']}?"
            else:
                response = f"I need a date for your appointment with {context['person']}. When would you like to schedule it?"
        
        elif phase == "asking_time":
            if "time" in context and context["time"]:
                # We have all the info, confirm
                context["phase"] = "confirming"
                response = f"I'll schedule your appointment with {context['person']} on {context['date']} at {context['time']}. Is that correct?"
            else:
                response = f"What time would you like for your appointment with {context['person']} on {context['date']}?"
        
        elif phase == "confirming":
            # Check if user confirmed the appointment
            if "yes" in message_text.lower() or "correct" in message_text.lower() or "right" in message_text.lower():
                # Here you would save the appointment to the database
                try:
                    # Format date and time for database
                    person = context.get("person")
                    date_str = context.get("date")
                    time_str = context.get("time")
                    
                    # Save to database if we have all required fields
                    if person and date_str and time_str:
                        # Here you would call your database function
                        # Example: db.add_appointment(person, date_str, time_str)
                        context["phase"] = "completed"
                        response = f"Great! Your appointment with {person} has been scheduled for {date_str} at {time_str}."
                    else:
                        context["phase"] = "init"  # Reset if missing info
                        response = "I'm missing some information. Let's start over. Who would you like to schedule with?"
                except Exception as e:
                    print(f"Error saving appointment: {e}")
                    response = "I'm sorry, there was an error scheduling your appointment. Please try again."
            else:
                # User didn't confirm, ask what they want to change
                context["phase"] = "asking_change"
                response = "What would you like to change about the appointment?"
        
        elif phase in ["asking_change", "asking_change_cancel"]:
            # Handle changes to the appointment details
            if "person" in message_text.lower() or "who" in message_text.lower() or "name" in message_text.lower():
                if intent == "cancel_appointment":
                    context["phase"] = "asking_person_cancel"
                else:
                    context["phase"] = "asking_person"
                context.pop("person", None)
                response = "Who would you like to schedule with instead?" if intent == "schedule_appointment" else "Whose appointment would you like to cancel?"
            elif "date" in message_text.lower() or "day" in message_text.lower() or "when" in message_text.lower():
                if intent == "cancel_appointment":
                    context["phase"] = "asking_date_cancel"
                else:
                    context["phase"] = "asking_date"
                context.pop("date", None)
                response = "What day would you prefer instead?"
            elif "time" in message_text.lower() or "hour" in message_text.lower():
                if intent == "cancel_appointment":
                    context["phase"] = "asking_time_cancel"
                else:
                    context["phase"] = "asking_time"
                context.pop("time", None)
                response = "What time would you prefer instead?"
            else:
                # Reset if we can't determine what to change
                context["phase"] = "init"
                response = "Let's start over. What would you like to do?"
    
    # If we still don't have a response, give a generic one
    if not response:
        response = "I'm not sure what you want to do with your appointment. Can you please be more specific?"
    
    # If we've completed the appointment process, prepare for a new conversation
    if phase == "completed" or context.get("phase") == "completed":
        print(f"[PROCESS_INTENT] Appointment process completed. Setting a timeout to reset context.")
        # Add a note that we've completed this appointment flow
        # In a real implementation, you might want to schedule a timer to reset the context
        # after a brief delay to allow for follow-up questions about the same appointment
        context["appointment_completed_at"] = datetime.now().isoformat()
        context["ready_for_new_topic"] = True
    
    print(f"[PROCESS_INTENT] Updated phase to: {context.get('phase', 'unknown')}, response: {response[:30]}...")
    return response, context

async def handle_appointment_query(message_text, context=None, session_id=None, is_speech=False):
    """Handle appointment scheduling, cancellation, or availability checking"""
    if context is None:
        context = {}
    
    # Store original valid values that we don't want to override
    original_person = context.get("person")
    original_phase = context.get("phase")
    
    # Initialize context if needed
    if "intent" not in context:
        intent = identify_intent(message_text)
        if intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"]:
            context["intent"] = intent
            print(f"[INTENT] Detected intent: {intent}, Previous intent: None")
            print(f"[INTENT] Setting new intent in context: {intent}")
        else:
            # Default to schedule if intent is unclear
            context["intent"] = "schedule_appointment"
            print(f"[INTENT] Detected intent: {intent}, defaulting to schedule_appointment")
    else:
        # We already have an intent in the context
        intent = identify_intent(message_text)
        print(f"[INTENT] Detected intent: {intent}, Previous intent: {context['intent']}")
        
        # If the new message has a clear intent that's different, update it
        if intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"]:
            if intent != context["intent"]:
                print(f"[INTENT] Changing intent from {context['intent']} to {intent}")
                context["intent"] = intent
                # Reset phase for the new intent
                context.pop("phase", None)
            else:
                print(f"[INTENT] Setting new intent in context: {intent}")
        else:
            # Keep the previous intent if the new message doesn't have a clear one
            print(f"[INTENT] Maintaining previous intent: {context['intent']}")
    
    # Extract entities from the message
    print(f"[ENTITY EXTRACTION] Processing text: '{message_text}'")
    entities = extract_entities(message_text)
    
    # Check if we have all the required entities
    missing_entities = []
    
    # For scheduling, we need person, date, and time
    if context["intent"] == "schedule_appointment":
        if not entities.get("person") and not context.get("person"):
            missing_entities.append("person")
        if not entities.get("date") and not context.get("date"):
            missing_entities.append("date")
        if not entities.get("time") and not context.get("time"):
            missing_entities.append("time")
    
    # For cancellation, we need person and either date or time
    elif context["intent"] == "cancel_appointment":
        if not entities.get("person") and not context.get("person"):
            missing_entities.append("person")
        if (not entities.get("date") and not context.get("date")) and (not entities.get("time") and not context.get("time")):
            missing_entities.append("date")
            missing_entities.append("time")
    
    # For availability checking, we need person and optionally date
    elif context["intent"] == "check_availability":
        if not entities.get("person") and not context.get("person"):
            missing_entities.append("person")
    
    print(f"[ENTITY EXTRACTION] Basic extraction incomplete: {entities}")
    print(f"[ENTITY EXTRACTION] Missing entities: {missing_entities}")
    
    # If we have missing entities and we're in a specific phase, try to extract them from the context
    if missing_entities and "phase" in context:
        current_phase = context.get("phase")
        
        # If we're asking for a person and this message is likely just a name response
        if current_phase in ["asking_person", "asking_person_cancel", "asking_person_check"] and len(message_text.split()) <= 3:
            # Try to interpret the entire message as a name
            potential_name = message_text.strip()
            if potential_name and len(potential_name) > 1:
                # Check if it's not in our domain-specific words
                domain_specific_words = ["appointment", "schedule", "book", "make", "set", "get", "find", 
                                        "check", "show", "list", "cancel", "reschedule", "time", "date", 
                                        "meeting", "consultation", "session", "visit", "call", "talk",
                                        "availability", "availibility", "available", "free", "busy", "slot", "opening"]
                
                if potential_name.lower() not in domain_specific_words:
                    entities["person"] = potential_name.capitalize()
                    print(f"[ENTITY EXTRACTION] Interpreted message as name: {entities['person']}")
                    missing_entities = [e for e in missing_entities if e != "person"]
    
    # Update context with any entities we found through standard extraction
    print(f"[ENTITY EXTRACTION] Final entities from extractor: {entities}")
    for key, value in entities.items():
        if value:
            # Special case: don't override person with domain-specific words
            if key == "person" and value.lower() in ["availability", "availibility", "appointment"]:
                print(f"[ENTITY EXTRACTION] Ignoring domain word as person: {value}")
                continue
                
            # Don't override 'person' if we're already past the person-asking phase 
            # and the new person entity looks suspicious
            if (key == "person" and 
                original_person is not None and 
                original_phase not in ["init", "asking_person", "asking_person_cancel", "asking_person_check"]):
                print(f"[ENTITY EXTRACTION] Not overriding existing person '{original_person}' with '{value}' in phase '{original_phase}'")
                continue
                
            context[key] = value
            print(f"[CONTEXT] Updated {key} = {value}")
            if session_id:
                memory["entities"].setdefault(session_id, {}).setdefault(key, [])
                if value not in memory["entities"][session_id][key]:
                    memory["entities"][session_id][key].append(value)
                    print(f"[MEMORY] Stored {key} = {value} in memory")
    
    # Always try AI extraction if there are any missing entities
    # This ensures we get as much information as possible from each message
    if missing_entities:
        try:
            print(f"[AI EXTRACTION] Using AI to extract missing entities: {missing_entities}")
            ai_entities = await extract_entities_with_ai(message_text, missing_entities)
            
            # Update with AI-extracted entities
            for key in missing_entities:
                if key in ai_entities and ai_entities[key]:
                    # Special case: don't accept date or time as person name
                    if key == "person" and (
                        re.search(r'\d{4}-\d{2}-\d{2}', str(ai_entities[key])) or  # Date pattern
                        re.search(r'\d{1,2}:\d{2}', str(ai_entities[key]))  # Time pattern
                    ):
                        print(f"[AI EXTRACTION] Rejected {key} = {ai_entities[key]} (looks like date/time)")
                        continue
                    
                    # Don't override 'person' if we're already past the person-asking phase
                    if (key == "person" and 
                        original_person is not None and 
                        original_phase not in ["init", "asking_person", "asking_person_cancel", "asking_person_check"]):
                        print(f"[AI EXTRACTION] Not overriding existing person '{original_person}' with '{ai_entities[key]}' in phase '{original_phase}'")
                        continue
                        
                    context[key] = ai_entities[key]
                    print(f"[AI EXTRACTION] Added {key} = {ai_entities[key]}")
                    
                    # Also update memory
                    if session_id:
                        memory["entities"].setdefault(session_id, {}).setdefault(key, [])
                        if ai_entities[key] not in memory["entities"][session_id][key]:
                            memory["entities"][session_id][key].append(ai_entities[key])
                            print(f"[MEMORY] Added entity {key}: {ai_entities[key]}")
        except Exception as e:
            print(f"[AI EXTRACTION] Error: {e}")
            
    # Add topics to memory
    if session_id:
        topics = extract_topics_from_text(message_text)
        for topic in topics:
            memory["topics_discussed"].setdefault(session_id, set()).add(topic)
            print(f"[MEMORY] Added topic: {topic}")
    
    # Process the appointment request based on intent and available entities
    response, updated_context = await process_appointment_intent(message_text, context, session_id)
    
    # Update the context with any changes from processing
    context.update(updated_context)
    
    # Store the conversation in memory
    if session_id:
        update_memory_with_conversation(session_id, message_text, response, context)
    
    return {"response": response, "context": context, "session_id": session_id}

async def handle_knowledge_query(text, session_id=None, is_speech=False):
    """Process general knowledge requests"""
    # Check if user is requesting a conversation summary
    if check_if_summary_requested(text):
        summary = generate_conversation_summary(session_id) if session_id else "No conversation history found."
        return {
            "response": format_response_for_output(summary, is_speech),
            "context": {},
            "session_id": session_id
        }
        
    # Define categories for better prompt construction
    categories = {
        "ai": ["what is ai", "artificial intelligence", "machine learning", "neural network", "deep learning"],
        "science": ["physics", "chemistry", "biology", "astronomy", "science"],
        "history": ["history", "historical", "ancient", "world war", "century"],
        "technology": ["computer", "software", "hardware", "internet", "programming", "code", "technology"],
        "general": ["what is", "how does", "explain", "define", "tell me about"]
    }
    
    # Determine the category of the question
    text_lower = text.lower()
    category = "general"
    for cat, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            category = cat
            break
    
    # Craft a better prompt based on the category
    if category == "ai":
        prompt = f"""
        User query: '{text}'
        Provide a helpful, accurate, and educational response about AI concepts.
        Include relevant technical details where appropriate but explain them clearly.
        Don't introduce yourself or mention that you're an AI. Just answer the question directly.
        Do not use any markdown formatting (no # or * characters) in your response.
        """
    elif category == "science":
        prompt = f"""
        User query: '{text}'
        Provide a clear, accurate scientific explanation that is factually correct and educational.
        Use analogies where helpful to explain complex concepts.
        Don't introduce yourself or mention that you're an AI. Just answer the question directly.
        Do not use any markdown formatting (no # or * characters) in your response.
        """
    elif category == "history":
        prompt = f"""
        User query: '{text}'
        Provide a historically accurate response with relevant dates and context.
        Be objective and educational in your explanation of historical events or figures.
        Don't introduce yourself or mention that you're an AI. Just answer the question directly.
        Do not use any markdown formatting (no # or * characters) in your response.
        """
    elif category == "technology":
        prompt = f"""
        User query: '{text}'
        Provide a helpful technical explanation that is accurate and educational.
        Include practical examples or relevant technical details where appropriate.
        Don't introduce yourself or mention that you're an AI. Just answer the question directly.
        Do not use any markdown formatting (no # or * characters) in your response.
        """
    else:
        prompt = f"""
        User query: '{text}'
        Provide a helpful, accurate, and concise response. Focus on directly answering the question
        with factual information. Be educational and informative.
        Don't introduce yourself or mention that you're an AI. Just answer the question directly.
        Do not use any markdown formatting (no # or * characters) in your response.
        """
    
    # Get response from Groq
    try:
        response = agent.run(prompt).content
        print(f"Knowledge response for category '{category}': {response[:100]}...")
        
        # Format response for output (strip markdown if for speech)
        result = format_response_for_output(response, is_speech)
        
        # Store conversation in memory
        update_memory_with_conversation(session_id, text, result, {})
        
        return {
            "response": result,
            "context": {},
            "session_id": session_id
        }
    except Exception as e:
        print(f"Error in knowledge query: {e}")
        return {
            "response": format_response_for_output("I'm sorry, I couldn't retrieve that information right now. Please try asking in a different way.", is_speech),
            "context": {},
            "session_id": session_id
        }

def get_previous_intent(session_id, max_history=5):
    """Get the most recent intent from conversation history"""
    if not session_id or session_id not in memory["conversations"]:
        return None
    
    conversations = memory["conversations"][session_id]
    
    # Look through recent conversation for appointment-related intents
    for i in range(len(conversations) - 1, max(-1, len(conversations) - max_history), -1):
        if i >= 0 and "context" in conversations[i] and "intent" in conversations[i]["context"]:
            return conversations[i]["context"]["intent"]
    
    return None

async def process_message(message_text, conversation_context=None, session_id=None, is_speech=False):
    """Process an incoming message and return the appropriate response"""
    if conversation_context is None:
        conversation_context = {}
    
    # Save original context values to check for unwanted overrides later
    original_person = conversation_context.get("person")
    
    print(f"[PROCESS] Received message: '{message_text}' with context: {conversation_context}")
    
    if not message_text:
        return {"response": "I didn't receive any message. How can I help you?"}

    # Check if this is a request for conversation summary
    if check_if_summary_requested(message_text):
        summary = generate_conversation_summary(session_id)
        return {"response": summary, "context": conversation_context, "session_id": session_id}
    
    # Special case handling for seeing a doctor
    if ("see a doctor" in message_text.lower() or 
        "see the doctor" in message_text.lower() or 
        "need a doctor" in message_text.lower() or 
        "need to see a doctor" in message_text.lower()):
        print("[PROCESS] Detected request to see a doctor")
        # Set intent to schedule appointment
        conversation_context["intent"] = "schedule_appointment"
        # Set person to "Doctor"
        conversation_context["person"] = "Doctor"
        print("[PROCESS] Auto-set person to 'Doctor'")
    
    # Check for users explicitly trying to change the intent
    text_lower = message_text.lower()
    
    # Intent correction/switching patterns
    if "check availability" in text_lower or "check availibility" in text_lower or "availability" in text_lower:
        print("[PROCESS] User explicitly mentioned checking availability, switching intent")
        conversation_context["intent"] = "check_availability"
        conversation_context["phase"] = "init"
        # Keep the person if already in context
        person = conversation_context.get("person")
        date = conversation_context.get("date")
        # Reset other context
        conversation_context = {"intent": "check_availability", "phase": "init"}
        if person:
            conversation_context["person"] = person
        if date:
            conversation_context["date"] = date
        
    elif "cancel" in text_lower and "appointment" in text_lower:
        print("[PROCESS] User explicitly mentioned canceling appointment, switching intent")
        conversation_context["intent"] = "cancel_appointment"
        conversation_context["phase"] = "init"
        # Keep the person if already in context
        person = conversation_context.get("person")
        date = conversation_context.get("date")
        # Reset other context
        conversation_context = {"intent": "cancel_appointment", "phase": "init"}
        if person:
            conversation_context["person"] = person
        if date:
            conversation_context["date"] = date
    
    # Check for knowledge questions using entity_extractor's identify_intent
    detected_intent = identify_intent(message_text)
    print(f"[INTENT] Detected intent: {detected_intent}")
    
    if detected_intent == "knowledge":
        print("[PROCESS] Detected knowledge intent, bypassing appointment flow")
        return await handle_knowledge_query(message_text, session_id, is_speech)
    
    # Define knowledge question indicators more comprehensively - backup check
    knowledge_question_indicators = [
        "what is", "what are", "who is", "who are", "how does", "how do", "explain", "tell me about",
        "when was", "when is", "where is", "where are", "why is", "why are", "define", "definition", 
        "defination", "meaning of", "can you explain", "what does", "tell me more"
    ]
    
    # Check for general knowledge questions that should bypass appointment flow
    is_knowledge_question = False
    for indicator in knowledge_question_indicators:
        if indicator in message_text.lower():
            is_knowledge_question = True
            break
    
    if is_knowledge_question:
        print("[PROCESS] Detected knowledge question indicator, bypassing appointment flow")
        return await handle_knowledge_query(message_text, session_id, is_speech)
        
    # Check for keywords that indicate a new appointment flow should be started
    new_appointment_keywords = [
        "new appointment", "another appointment", "different appointment", 
        "schedule another", "book another", "make another"
    ]
    
    if any(keyword in message_text.lower() for keyword in new_appointment_keywords):
        print("[PROCESS] Detected request for new appointment, resetting context")
        # Reset the context completely for a new appointment
        conversation_context = {"intent": "schedule_appointment"}
        
        # Extract person if mentioned in the message
        temp_entities = extract_entities(message_text)
        if temp_entities.get("person"):
            conversation_context["person"] = temp_entities.get("person")
            print(f"[PROCESS] Added person to new appointment: {temp_entities.get('person')}")
        
        return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
    
    # Check if we're in the middle of a scheduling flow
    current_phase = conversation_context.get("phase")
    current_intent = conversation_context.get("intent")
    
    print(f"[PROCESS] Current phase: {current_phase}, Current intent: {current_intent}")
    
    # Reset context if we're in completed phase
    if current_phase == "completed":
        print(f"[PROCESS] Resetting context after completed phase")
        conversation_context = {}
        current_phase = None
        current_intent = None
    
    # If no current intent but we have session history, check for previous intent
    if not current_intent and session_id:
        previous_intent = get_previous_intent(session_id)
        if previous_intent:
            print(f"[PROCESS] Found previous intent in memory: {previous_intent}")
            conversation_context["intent"] = previous_intent
            current_intent = previous_intent
    
    # If we have a detected intent that's different from current/previous, use the detected one
    if detected_intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"] and detected_intent != current_intent:
        print(f"[PROCESS] Using explicitly detected intent '{detected_intent}' over current intent '{current_intent}'")
        conversation_context = {"intent": detected_intent, "phase": "init"}
        # Extract entities from the message
        temp_entities = extract_entities(message_text)
        for key, value in temp_entities.items():
            if value:
                conversation_context[key] = value
        return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
    
    # If we're already in an appointment flow, continue with that
    if current_phase and current_phase != "init" and current_intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"]:
        print(f"[PROCESS] Continuing existing appointment flow: {current_intent}, phase: {current_phase}")
        # Check if the message contains a date or time and we're waiting for those
        if current_phase in ["asking_date", "asking_date_cancel", "asking_date_check"] and "date" not in conversation_context:
            # Try to extract date from this message specifically
            date_result = parse_relative_date(message_text)
            if date_result:
                conversation_context["date"] = format_date_for_display(date_result)
                print(f"[PROCESS] Extracted date from follow-up message: {conversation_context['date']}")
            else:
                # Try enhanced entity extraction for dates
                enhanced_entities = enhance_entity_extraction(message_text)
                if enhanced_entities.get("date"):
                    conversation_context["date"] = enhanced_entities["date"]
                    print(f"[PROCESS] Extracted date from enhanced extraction: {conversation_context['date']}")
        
        if current_phase in ["asking_time", "asking_time_cancel", "asking_time_after_availability"] and "time" not in conversation_context:
            # Try to extract time from this message specifically
            time_result = entity_extractor._extract_time(message_text)
            if time_result:
                conversation_context["time"] = time_result
                print(f"[PROCESS] Extracted time from follow-up message: {conversation_context['time']}")
                
        # Continue with the appointment flow
        return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
    
    # Also check if the message contains date/time entities which might indicate it's a follow-up
    # to an appointment-related conversation
    temp_entities = extract_entities(message_text)
    if (temp_entities.get("date") or temp_entities.get("time")) and session_id:
        # If we have date/time entities and a previous appointment-related conversation,
        # treat this as a continuation of that conversation
        previous_intent = get_previous_intent(session_id)
        if previous_intent in ["schedule_appointment", "cancel_appointment", "check_availability"]:
            print(f"[PROCESS] Found date/time in message with previous appointment intent: {previous_intent}")
            # Update context with the intent from memory and any extracted entities
            conversation_context["intent"] = previous_intent
            
            # Add extracted entities to the context
            for key, value in temp_entities.items():
                if value:
                    conversation_context[key] = value
                    print(f"[PROCESS] Added entity from follow-up: {key}={value}")
            
            # Handle as appointment query
            return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
    
    # If standard intent detection returned "unknown" for a complex query, use AI to detect intent
    if detected_intent == "unknown" and len(message_text.split()) > 3:
        try:
            # Use the LLM to determine if this is more likely an appointment-related query
            # or a general knowledge question
            intent_prompt = f"""
            Analyze this message and determine the most appropriate category:
            Message: "{message_text}"
            
            Choose ONE of these categories:
            1. schedule_appointment - if the message is about creating a new appointment
            2. cancel_appointment - if the message is about canceling an existing appointment
            3. check_availability - if the message is about checking when someone is available
            4. list_appointments - if the message is about viewing existing appointments
            5. general_knowledge - if the message is asking a general question not related to appointments
            
            Just return the category name, nothing else.
            """
            
            ai_response = agent.run(intent_prompt)
            ai_intent = ai_response.content.strip().lower()
            print(f"[AI INTENT DETECTION] Result: {ai_intent}")
            
            if ai_intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"]:
                print(f"[AI INTENT DETECTION] Classified as specific appointment intent: {ai_intent}")
                conversation_context["intent"] = ai_intent
                conversation_context["phase"] = "init"
                return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
            elif "appointment" in ai_intent:
                print("[AI INTENT DETECTION] Classified as general appointment query")
                return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
            else:
                print("[AI INTENT DETECTION] Classified as knowledge query")
                return await handle_knowledge_query(message_text, session_id, is_speech)
                
        except Exception as e:
            print(f"[AI INTENT DETECTION] Error: {e}")
            # Fall back to the original detection below
    
    if detected_intent in ["schedule_appointment", "cancel_appointment", "check_availability", "list_appointments"]:
        # This is an appointment-related query
        # If it's a new intent, reset the context except for the intent
        if current_intent != detected_intent:
            conversation_context = {"intent": detected_intent}
            print(f"[PROCESS] New appointment intent detected: {detected_intent}, resetting context")
        
        return await handle_appointment_query(message_text, conversation_context, session_id, is_speech)
    else:
        # This is a knowledge query or unknown intent
        return await handle_knowledge_query(message_text, session_id, is_speech)

# Define routes
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(message: Message):
    # Process the message
    result = await process_message(
        message.text,
        conversation_context=message.context,
        session_id=message.session_id,
        is_speech=message.is_speech
    )
    return result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(websocket)}"
    active_connections.append(websocket)
    
    # Initialize conversation context for this session
    conversation_context = {}
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                text = message_data.get("message", "")
                client_context = message_data.get("context", {})
                is_speech = message_data.get("is_speech", False)
                
                # Merge client-provided context with our stored context
                if client_context:
                    conversation_context.update(client_context)
                
                # Generate a unique session ID if not provided
                client_session_id = message_data.get("session_id")
                if client_session_id:
                    session_id = client_session_id
                
                # Process message based on intent detection
                result = await process_message(
                    text,
                    conversation_context=conversation_context,
                    session_id=session_id,
                    is_speech=is_speech
                )
                
                # Update our stored context with any changes from processing
                if "context" in result:
                    conversation_context = result["context"]
                    print(f"[WEBSOCKET] Updated context: {conversation_context}")
                
                await websocket.send_text(json.dumps(result))
                
            except json.JSONDecodeError:
                # Handle plain text messages (fallback)
                result = await process_message(data, conversation_context=conversation_context, session_id=session_id)
                
                # Update context for next message
                if "context" in result:
                    conversation_context = result["context"]
                
                await websocket.send_text(json.dumps(result))
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Handle speech-to-text conversion using SpeechRecognition"""
    print("\n[TRANSCRIPTION] Received audio file for transcription")
    
    temp_file_path = None
    
    try:
        # Read the audio file
        contents = await file.read()
        print(f"[TRANSCRIPTION] Audio size: {len(contents)} bytes")
        
        # Create a recognizer
        recognizer = sr.Recognizer()
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name
        
        print(f"[TRANSCRIPTION] Saved audio to temp file: {temp_file_path}")
        
        try:
            # For audio data coming from the web browser, we need to use the recognize_google method
            # with a direct HTTP request to Google's Speech-to-Text API
            audio_url = f"file://{temp_file_path}"
            
            print(f"[TRANSCRIPTION] Attempting to recognize speech from {audio_url}")
            
            # Send data to Google's servers for recognition
            with open(temp_file_path, "rb") as audio_file:
                # Get the audio data as bytes
                audio_bytes = audio_file.read()
                
            # Create an Audio object from bytes
            audio = sr.AudioData(audio_bytes, sample_rate=44100, sample_width=2)
            
            # Recognize the speech
            text = recognizer.recognize_google(audio)
            print(f"[TRANSCRIPTION] Recognition successful: '{text}'")
            return {"transcription": text}
        except sr.UnknownValueError:
            print("[TRANSCRIPTION] Google Speech Recognition could not understand audio")
            return {"error": "Could not understand audio. Please speak clearly."}
        except sr.RequestError as e:
            print(f"[TRANSCRIPTION] Could not request results from Google Speech Recognition service; {e}")
            return {"error": "Speech service unavailable. Please try again later."}
        except Exception as e:
            print(f"[TRANSCRIPTION] Error recognizing speech: {e}")
            
            # If all approaches fail, let's tell the user there was an issue
            return {"error": "Could not process audio. Please try typing your message instead."}
            
    except Exception as e:
        print(f"[TRANSCRIPTION] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"error": "Could not process audio file."}
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"[TRANSCRIPTION] Removed temporary file: {temp_file_path}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True) 