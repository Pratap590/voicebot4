# AI Voice Assistant

A complete AI-powered voice and text assistant for scheduling appointments and answering knowledge questions.

## Features

- **Dual-Mode System**:
  - **Appointment Mode**: Schedule, cancel, check availability, and list appointments
  - **Knowledge Mode**: Answer general knowledge questions
- **Natural Language Processing**: Understand natural sentences and extract key entities
- **Voice Interface**: Speak commands and questions directly to the assistant
- **Database Integration**: Store and retrieve appointments from MySQL database
- **Context Awareness**: Remembers conversation context for multi-turn interactions

## Requirements

- Python 3.8+
- MySQL Database
- Groq API Key

## Setup

1. **Clone the repository**

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configure MySQL Database**:
   - Create a new MySQL database called `appointments_db`
   - The application will automatically create the necessary tables

4. **Configure Environment Variables**:
   Create a `.env` file in the project root with the following:
   ```
   # Database Configuration
   DB_HOST=localhost
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=appointments_db
   DB_PORT=3306

   # Groq API Key
   GROQ_API_KEY=your_groq_api_key
   ```

5. **Run the application**:
   ```
   python main.py
   ```
   
   The application will start on http://localhost:8000

## Usage

### Appointment Mode

- **Schedule appointments** with phrases like:
  - "Schedule an appointment with John on next Monday at 3 PM"
  - "Book a meeting with Sarah tomorrow at 2 PM"

- **Check availability** with phrases like:
  - "Is John available on Friday at 3 PM?"
  - "Check Sarah's availability for next Monday afternoon"

- **Cancel appointments** with phrases like:
  - "Cancel my appointment with John on Friday at 3 PM"
  - "I need to cancel the meeting with Sarah tomorrow"

- **List appointments** with phrases like:
  - "Show my appointments with John"
  - "What appointments do I have on Friday?"

### Knowledge Mode

- Ask general knowledge questions like:
  - "What is quantum computing?"
  - "Who is Marie Curie?"
  - "Explain how vaccines work"

### Voice Interface

- Click the microphone button to speak your commands and questions
- The system will transcribe your speech and process your request
- The assistant will respond both in text and via speech synthesis

### Mode Switching

- Use the mode selector at the top of the interface
- Alternatively, say "Switch to appointment mode" or "Switch to knowledge mode"

## File Structure

- **main.py**: FastAPI application and main logic
- **database.py**: MySQL database connection and appointment management
- **static/**: CSS and JavaScript files
- **templates/**: HTML templates
- **requirements.txt**: Python dependencies

## Tech Stack

- **Backend**: FastAPI, Python
- **Database**: MySQL
- **LLM**: Groq's llama-3.3-70b-versatile
- **Frontend**: HTML, CSS, JavaScript
- **Speech Recognition**: SpeechRecognition, Web Speech API
- **Speech Synthesis**: Web Speech API 