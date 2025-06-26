from phi.agent import Agent
from phi.model.groq import Groq
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq agent (same as in main.py)
agent = Agent(
    model=Groq(id="llama-3.3-70b-versatile"),
    markdown=True
)

def test_ai_entity_extraction():
    # Test cases with complex requests
    test_cases = [
        "I need to set up something with John next Monday afternoon",
        "Can you please check if Dr. Smith has any available slots on Friday?",
        "I'd like to cancel my appointment with Sarah that was scheduled for tomorrow at 3pm",
        "Need to talk with Michael sometime next week, preferably in the morning"
    ]
    
    print("Testing AI-based entity extraction...")
    print("-" * 60)
    
    for test in test_cases:
        print(f"\nInput: '{test}'")
        
        # Create entity extraction prompt similar to what's in main.py
        entity_prompt = f"""
        Extract the following information from this text: "{test}"
        
        Extract ONLY the specific entities mentioned below. If an entity is not present, respond with NULL.
        
        Format your response as JSON with these keys:
        - person: The name of the person for the appointment (e.g. 'Dr. Smith', 'John', etc.)
        - date: The date for the appointment in YYYY-MM-DD format if possible
        - time: The time for the appointment in 24-hour format (HH:MM)
        """
        
        try:
            # Make the AI extraction attempt
            ai_response = agent.run(entity_prompt)
            print(f"AI Response:\n{ai_response.content}")
            
            # Try to parse the AI's response as JSON
            # Extract JSON block if present
            json_match = re.search(r'```json\n(.*?)\n```', ai_response.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = ai_response.content
            
            # Clean up the string for JSON parsing
            json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)
            
            try:
                ai_entities = json.loads(json_str)
                print(f"Parsed entities: {ai_entities}")
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                
        except Exception as e:
            print(f"Error: {e}")
            
        print("-" * 60)

if __name__ == "__main__":
    test_ai_entity_extraction() 