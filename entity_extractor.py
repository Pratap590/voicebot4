import re
from typing import Dict, Any, Optional
from datetime import datetime

class EntityExtractor:
    """Extract key entities from natural language text for appointment scheduling"""
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract person, date, and time from text"""
        print(f"Extracting entities from: '{text}'")
        entities = {
            "person": None,
            "date": None,
            "time": None
        }
        
        text_lower = text.lower()
        
        # Common temporal words that should not be part of person names
        temporal_words = ["next", "last", "this", "tomorrow", "today", "yesterday", 
                         "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                         "january", "february", "march", "april", "may", "june", 
                         "july", "august", "september", "october", "november", "december",
                         "week", "month", "year", "am", "pm", "morning", "afternoon", "evening", "night"]
                         
        # Common prepositions, conjunctions, and verbs to exclude
        stop_words = ["with", "for", "at", "on", "in", "the", "and", "or", "but", "because", "as",
                     "hi", "hello", "hey", "can", "could", "would", "will", "shall", "must", "should",
                     "may", "might", "do", "does", "did", "has", "have", "had", "is", "am", "are", 
                     "was", "were", "be", "been", "being", "you", "your", "me", "my", "i", "we", "us",
                     "please", "thanks", "thank", "want", "need", "like", "help", "an", "a", "to", "from",
                     "by", "of", "it", "its", "they", "their", "them", "there", "here", "where", "when", "how"]
        
        # Words specific to appointment scheduling that should not be treated as names
        domain_specific_words = ["appointment", "schedule", "book", "make", "set", "get", "find", 
                                "check", "show", "list", "cancel", "reschedule", "time", "date", 
                                "meeting", "consultation", "session", "visit", "call", "talk",
                                "availability", "availibility", "available", "free", "busy", "slot", "opening"]
        
        # Special case: If the text is just a single word that's not in our stop words,
        # it might be a name (especially in response to "Who would you like to schedule with?")
        words = text.split()
        if len(words) == 1 and words[0].lower() not in stop_words and words[0].lower() not in temporal_words and words[0].lower() not in domain_specific_words:
            # This is likely just a name response
            entities["person"] = words[0].capitalize()
            print(f"Single word response detected as name: {entities['person']}")
            
            # Extract date and time if present
            date_result = self._extract_date(text)
            if date_result:
                entities["date"] = date_result
            
            time_result = self._extract_time(text)
            if time_result:
                entities["time"] = time_result
                
            print(f"Final extracted entities: {entities}")
            return entities
        
        # Check for "of Person" pattern (e.g., "availability of John")
        of_pattern = r"(?:of|for)\s+((?:dr|mr|mrs|ms|miss|prof)\.?\s+)?([A-Za-z][a-z]+)(?:\s+([A-Za-z][a-z]+))?"
        of_match = re.search(of_pattern, text_lower)
        if of_match:
            title = of_match.group(1) or ""
            first = of_match.group(2)
            last = of_match.group(3) or ""
            
            # Skip common words that could be mistaken for names
            if first not in stop_words and first not in temporal_words and first not in domain_specific_words:
                name_parts = []
                if title:
                    name_parts.append(title.strip().capitalize())
                name_parts.append(first.capitalize())
                if last and last not in stop_words and last not in temporal_words and last not in domain_specific_words:
                    name_parts.append(last.capitalize())
                
                entities["person"] = " ".join(name_parts)
                print(f"'Of pattern' detected person: {entities['person']}")
        
        # First try simple regex patterns for common phrases
        with_pattern = r"with\s+((?:dr|mr|mrs|ms|miss|prof)\.?\s+)?([A-Za-z][a-z]+)(?:\s+([A-Za-z][a-z]+))?"
        for_pattern = r"for\s+((?:dr|mr|mrs|ms|miss|prof)\.?\s+)?([A-Za-z][a-z]+)(?:\s+([A-Za-z][a-z]+))?"
        see_pattern = r"see\s+((?:dr|mr|mrs|ms|miss|prof)\.?\s+)?([A-Za-z][a-z]+)(?:\s+([A-Za-z][a-z]+))?"
        
        # Check "with Person" pattern
        if not entities["person"]:
            with_match = re.search(with_pattern, text_lower)
            if with_match:
                title = with_match.group(1) or ""
                first = with_match.group(2)
                last = with_match.group(3) or ""
                
                # Skip common words that could be mistaken for names
                if first not in stop_words and first not in temporal_words and first not in domain_specific_words:
                    name_parts = []
                    if title:
                        name_parts.append(title.strip().capitalize())
                    name_parts.append(first.capitalize())
                    if last and last not in stop_words and last not in temporal_words and last not in domain_specific_words:
                        name_parts.append(last.capitalize())
                    
                    entities["person"] = " ".join(name_parts)
        
        # If "with" pattern didn't work, try "for" pattern
        if not entities["person"]:
            for_match = re.search(for_pattern, text_lower)
            if for_match:
                title = for_match.group(1) or ""
                first = for_match.group(2)
                last = for_match.group(3) or ""
                
                if first not in stop_words and first not in temporal_words and first not in domain_specific_words:
                    name_parts = []
                    if title:
                        name_parts.append(title.strip().capitalize())
                    name_parts.append(first.capitalize())
                    if last and last not in stop_words and last not in temporal_words and last not in domain_specific_words:
                        name_parts.append(last.capitalize())
                    
                    entities["person"] = " ".join(name_parts)
        
        # If "for" pattern didn't work, try "see" pattern
        if not entities["person"]:
            see_match = re.search(see_pattern, text_lower)
            if see_match:
                title = see_match.group(1) or ""
                first = see_match.group(2)
                last = see_match.group(3) or ""
                
                if first not in stop_words and first not in temporal_words and first not in domain_specific_words:
                    name_parts = []
                    if title:
                        name_parts.append(title.strip().capitalize())
                    name_parts.append(first.capitalize())
                    if last and last not in stop_words and last not in temporal_words and last not in domain_specific_words:
                        name_parts.append(last.capitalize())
                    
                    entities["person"] = " ".join(name_parts)
        
        # If still no match, check for words that might be names (now accepting both upper and lowercase)
        if not entities["person"]:
            # Look for potential names in the text (not just capitalized words)
            for word in words:
                word_lower = word.lower()
                # Skip common words that could be mistaken for names
                if word_lower not in stop_words and word_lower not in temporal_words and word_lower not in domain_specific_words:
                    # Extra check to avoid misidentifying numbers as names
                    if not re.match(r'^\d+', word) and not word_lower.endswith('th') and not word_lower.endswith('rd') and not word_lower.endswith('st'):
                        entities["person"] = word.capitalize()
                        break
        
        # Extract date
        date_result = self._extract_date(text)
        if date_result:
            entities["date"] = date_result
        
        # Extract time
        time_result = self._extract_time(text)
        if time_result:
            entities["time"] = time_result
        
        print(f"Final extracted entities: {entities}")
        return entities
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text"""
        text_lower = text.lower()
        
        # Check for ordinal date expressions (e.g., "June 15", "15th of June")
        print(f"Checking for ordinal date in: '{text_lower}'")
        months = ["january", "february", "march", "april", "may", "june", 
                 "july", "august", "september", "october", "november", "december"]
        month_abbr = ["jan", "feb", "mar", "apr", "may", "jun", 
                     "jul", "aug", "sep", "oct", "nov", "dec"]
        
        # Pattern for "June 15, 2023" or "15 June 2023" or "June 15th, 2023"
        for month in months + month_abbr:
            # Month day, year
            pattern1 = f"{month}\\s+(\\d{{1,2}})(st|nd|rd|th)?(?:,|\\s)\\s*(\\d{{4}})"
            # Day month year
            pattern2 = f"(\\d{{1,2}})(st|nd|rd|th)?\\s+(?:of\\s+)?{month}(?:,|\\s)\\s*(\\d{{4}})"
            
            match1 = re.search(pattern1, text_lower)
            if match1:
                day = match1.group(1)
                year = match1.group(3)
                month_idx = months.index(month) + 1 if month in months else month_abbr.index(month) + 1
                if int(day) <= 31 and 1 <= month_idx <= 12:
                    print(f"Found ordinal date with explicit year: ({day}, {month}, {year})")
                    date_str = f"{year}-{month_idx:02d}-{int(day):02d}"
                    print(f"Found reference date: {date_str}")
                    return date_str
            
            match2 = re.search(pattern2, text_lower)
            if match2:
                day = match2.group(1)
                year = match2.group(3)
                month_idx = months.index(month) + 1 if month in months else month_abbr.index(month) + 1
                if int(day) <= 31 and 1 <= month_idx <= 12:
                    print(f"Found ordinal date with explicit year: ({day}, {month}, {year})")
                    date_str = f"{year}-{month_idx:02d}-{int(day):02d}"
                    print(f"Found reference date: {date_str}")
                    return date_str
            
            # Also check without explicit year (we can add current year)
            # Month day
            pattern3 = f"{month}\\s+(\\d{{1,2}})(st|nd|rd|th)?"
            # Day month
            pattern4 = f"(\\d{{1,2}})(st|nd|rd|th)?\\s+(?:of\\s+)?{month}"
            
            match3 = re.search(pattern3, text_lower)
            if match3:
                day = match3.group(1)
                curr_year = datetime.now().year
                month_idx = months.index(month) + 1 if month in months else month_abbr.index(month) + 1
                if int(day) <= 31 and 1 <= month_idx <= 12:
                    date_str = f"{curr_year}-{month_idx:02d}-{int(day):02d}"
                    print(f"Found reference date without year: {date_str}")
                    return date_str
            
            match4 = re.search(pattern4, text_lower)
            if match4:
                day = match4.group(1)
                curr_year = datetime.now().year
                month_idx = months.index(month) + 1 if month in months else month_abbr.index(month) + 1
                if int(day) <= 31 and 1 <= month_idx <= 12:
                    date_str = f"{curr_year}-{month_idx:02d}-{int(day):02d}"
                    print(f"Found reference date without year: {date_str}")
                    return date_str
        
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Extract time from text"""
        text_lower = text.lower()
        
        # Check for 12-hour format with AM/PM
        hour12_pattern = r"(\d{1,2})[:.h]?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)"
        match = re.search(hour12_pattern, text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            period = match.group(3)
            
            if 1 <= hour <= 12 and 0 <= minute <= 59:
                # Convert to 24-hour format
                if period.startswith('p') and hour < 12:
                    hour += 12
                elif period.startswith('a') and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}"
        
        # Check for hour only with am/pm (e.g., "10 am", "3 pm")
        simple_hour_pattern = r"(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)"
        match = re.search(simple_hour_pattern, text_lower)
        if match:
            print(f"Found simple time format: ({match.group(1)}, {match.group(2)})")
            hour = int(match.group(1))
            period = match.group(2)
            
            if 1 <= hour <= 12:
                # Convert to 24-hour format
                if period.startswith('p') and hour < 12:
                    hour += 12
                elif period.startswith('a') and hour == 12:
                    hour = 0
                
                time_str = f"{hour:02d}:00"
                print(f"Converted simple time to: {time_str}")
                return time_str
        
        return None

    def _extract_person(self, text):
        """Extract person name from text"""
        # For simple responses that might just be a name (answering "Who would you like to meet with?")
        if len(text.split()) <= 3:
            # Check if this is a follow-up response that's likely just a name
            potential_name = text.strip()
            # Clean up potential name from punctuation
            potential_name = re.sub(r'[^\w\s]', '', potential_name).strip()
            
            # Don't treat common single words and scheduling-related words as names
            common_words = [
                "yes", "no", "ok", "okay", "sure", "correct", "right", "wrong", "thanks", "thank", 
                "please", "maybe", "not", "want", "wanto", "need", "check", "cancel", "confirm",
                "wait", "hold", "stop", "start", "change", "help", "do", "don't", "dont", "doesn't",
                "doesnt", "available", "availability", "availibility", "cannot", "can't", "cant",
                "schedule", "appointment", "booking", "book", "make", "set", "create", "i'll", "ill",
                "meet", "meeting", "time", "date", "hour", "minute", "day", "month", "year",
                "ai", "what", "who", "when", "where", "why", "how", "which", "that", "this", "it"
            ]
            
            if potential_name.lower() in common_words:
                print(f"Ignored common word as person name: {potential_name}")
                return None
            
            # If it's a very short name (1-2 chars), likely not a name
            if len(potential_name) <= 2:
                return None
            
            # Simple check to make sure not a date or time
            if re.search(r'\d{1,2}:\d{2}', potential_name) or re.search(r'\d{1,2}(am|pm)', potential_name.lower()):
                return None
            
            # If it seems valid, return capitalized name
            if potential_name and len(potential_name) > 1:
                print(f"Single word response detected as name: {potential_name.capitalize()}")
                return potential_name.capitalize()
        
        # For more complex text with "with [Person]" pattern
        with_pattern = r'with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        with_match = re.search(with_pattern, text)
        if with_match:
            print(f"'With pattern' detected person: {with_match.group(1)}")
            return with_match.group(1)
        
        # For "of [Person]" pattern
        of_pattern = r'of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        of_match = re.search(of_pattern, text)
        if of_match:
            print(f"'Of pattern' detected person: {of_match.group(1)}")
            return of_match.group(1)
        
        # Try to extract using NER (could be implemented with spaCy or another NER system)
        # This is a placeholder for more advanced name extraction
        
        return None

def identify_intent(text):
    """Identify the intent from the user's message"""
    text = text.lower()
    
    # Define patterns for different intents
    schedule_patterns = [
        r"schedule an? appointment",
        r"book an? appointment",
        r"make an? appointment",
        r"set up an? appointment",
        r"create an? appointment",
        r"schedule a meeting",
        r"schedule .* with",
        r"book .* with",
        r"make .* with",
        r"schedule .* for",
        r"book .* for",
        r"make .* for"
    ]
    
    cancel_patterns = [
        r"cancel an? appointment",
        r"cancel .* meeting",
        r"cancel .* with",
        r"remove an? appointment",
        r"delete an? appointment",
        r"wanto cancel",
        r"want to cancel",
        r"need to cancel",
        r"don'?t want the appointment"
    ]
    
    check_availability_patterns = [
        r"check availability",
        r"check availibility",  # Common misspelling
        r"when .* available",
        r"what times are available",
        r"available times",
        r"is .* available",
        r"can .* meet",
        r"availability of",
        r"availibility of",
        r"when can .* meet",
        r"check when",
        r"not schedule .* check"
    ]
    
    list_appointments_patterns = [
        r"list appointments",
        r"show appointments",
        r"what appointments",
        r"my appointments",
        r"my schedule",
        r"view .* appointments"
    ]
    
    # Knowledge question patterns that should override other intents
    knowledge_patterns = [
        r"what is",
        r"what are", 
        r"who is",
        r"who are", 
        r"how does", 
        r"how do",
        r"explain", 
        r"tell me about", 
        r"when was",
        r"when is",
        r"where is",
        r"where are", 
        r"why is",
        r"why are", 
        r"define",
        r"definition",
        r"defination", 
        r"meaning of",
        r"what does",
        r"tell me more",
        r"can you explain"
    ]
    
    # Check for knowledge questions first, as these should override other intents
    for pattern in knowledge_patterns:
        if re.search(pattern, text):
            return "knowledge"
    
    # Check for check_availability before scheduling to prioritize it
    for pattern in check_availability_patterns:
        if re.search(pattern, text):
            return "check_availability"
    
    # Check for cancel before scheduling to prioritize it
    for pattern in cancel_patterns:
        if re.search(pattern, text):
            return "cancel_appointment"
    
    # Then check for other appointment-related intents
    for pattern in schedule_patterns:
        if re.search(pattern, text):
            return "schedule_appointment"
    
    for pattern in list_appointments_patterns:
        if re.search(pattern, text):
            return "list_appointments"
            
    # If nothing matched, return unknown
    return "unknown"

# For testing
if __name__ == "__main__":
    extractor = EntityExtractor()
    test_text = "I want to schedule an appointment with John on Monday at 3pm"
    entities = extractor.extract_entities(test_text)
    print(f"Extracted entities: {entities}")
    
    # Test relative dates
    test_cases = [
        "3 days from today",
        "tomorrow at 2pm",
        "next Monday",
        "after 7 days from today",
        "in 2 weeks"
    ]
    
    for test in test_cases:
        entities = extractor.extract_entities(test)
        print(f"Input: {test}")
        print(f"Entities: {entities}\n") 