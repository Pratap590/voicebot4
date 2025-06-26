# AI Assistant - Client Documentation

## Introduction
This document provides guidelines on how to effectively interact with our AI assistant. The system has two main modes:
1. **Appointment Mode** - For scheduling, checking availability, and managing appointments
2. **Knowledge Mode** - For answering general knowledge questions

The system preserves conversation context when switching between modes and intelligently detects when you might need to switch modes.

## Appointment Mode

### Effective Prompts

| Task | Recommended Prompts | Notes |
|------|-------------------|-------|
| Schedule Appointment | "Schedule an appointment with [person] on [date] at [time]" | Most effective with all details |
|  | "Book a meeting with [person] tomorrow at 2 PM" | Using relative dates |
|  | "I need to schedule with [person]" | System will ask for missing details |
| Check Availability | "Is [person] available on [date] at [time]?" | Complete query for best results |
|  | "Check [person]'s availability for next Monday afternoon" | Using relative dates/times |
|  | "When is [person] free this week?" | For broader availability check |
| Cancel Appointment | "Cancel my appointment with [person] on [date] at [time]" | Most effective with all details |
|  | "Cancel this appointment" | Works when you've just discussed an appointment |
|  | "I want to cancel John's appointment on Friday at 3 PM" | System will confirm details |
|  | "Cancel John's appointment on Friday" | System will ask for time |
| List Appointments | "Show my appointments with [person]" | Person-specific listing |
|  | "What appointments do I have on [date]?" | Date-specific listing |
|  | "List all my upcoming appointments" | For complete listing |

### Date and Time Formats

The system recognizes various date and time formats:

**Date Examples:**
- "June 12, 2025"
- "12th June 2025" 
- "Next Monday"
- "Tomorrow"
- "4 days from today"
- "Next week"
- "This Friday"

**Time Examples:**
- "10 AM" or "10am"
- "10:30 PM" or "10:30pm" 
- "3 o'clock"
- "In the morning" (defaults to 9:00 AM)
- "In the afternoon" (defaults to 2:00 PM)
- "In the evening" (defaults to 6:00 PM)
- "At noon" (12:00 PM)

### Getting the Best Responses

#### For Scheduling Appointments:
1. **Provide complete information**: Include person name, specific date, and specific time
2. **Be clear about recurring appointments**: Specify "every Monday" or "weekly" if needed
3. **Confirm details**: The system will ask for any missing information
4. **Check confirmation**: Always verify the appointment details in the system's confirmation message

#### For Checking Availability:
1. **Be specific about timeframe**: "Is John available tomorrow at 3 PM?" works better than "When is John free?"
2. **Include date and time range**: For best results, include both date and approximate time
3. **Person verification**: Make sure the person's name is clearly stated
4. **Consider alternatives**: If your requested time isn't available, the system will suggest alternatives

#### For Canceling Appointments:
1. **Provide exact details**: Include the person, date, and time of the appointment
2. **Verify cancellation**: Always check for the confirmation message
3. **Use context awareness**: After discussing an appointment, you can simply say "Cancel this appointment" 
4. **List before canceling**: If unsure of details, first list appointments, then cancel the specific one
5. **Be specific with time formats**: "3 PM", "3:00 PM", and "15:00" are all recognized
6. **Follow the prompts**: If you only provide partial information, the system will ask for the missing details
7. **Confirm success**: Look for the confirmation message stating "Your appointment with [person] on [date] at [time] has been canceled"

### Common Issues and Solutions

**Issue**: System doesn't recognize a person's name
- **Solution**: Try using a different capitalization or full name (e.g., "John Smith" instead of "john")

**Issue**: When canceling appointments, the system can't find the appointment
- **Solution**: First use "List appointments" to see exact dates and times, then use those exact details to cancel
- **Solution**: Make sure you're using the same date and time format that was used when scheduling

**Issue**: Cancellation not working properly
- **Solution**: Try being more specific with time formats (e.g., "3:00 PM" instead of "afternoon")
- **Solution**: Verify you're using the correct date format (try "June 20, 2025" instead of just "Friday")
- **Solution**: If the system asks for clarification, provide the exact missing information

**Issue**: When checking availability, getting incorrect responses
- **Solution**: Be very specific with date and time format, using "June 12, 2025 at 3:00 PM" style formatting

**Issue**: Scheduling conflicts not being detected
- **Solution**: Always verify the confirmation message shows the correct date and time

## Knowledge Mode

### Effective Prompts

| Task | Recommended Prompts | Examples |
|------|-------------------|---------|
| General Knowledge | "What is [topic]?" | "What is quantum computing?" |
|  | "Who is [person]?" | "Who is Marie Curie?" |
|  | "Define [term]" | "Define artificial intelligence" |
|  | "Explain [concept]" | "Explain how vaccines work" |
|  | "Tell me about [subject]" | "Tell me about climate change" |
|  | "What's the difference between [A] and [B]?" | "What's the difference between ML and AI?" |

### Getting the Best Knowledge Responses

1. **Ask specific questions**: "What are the main causes of climate change?" works better than "Tell me about the environment"
2. **Use clear terminology**: Avoid ambiguous terms or abbreviations unless commonly known
3. **One question at a time**: For complex topics, start with a general question, then ask follow-ups
4. **Request clarification**: If the answer is too technical, ask "Can you explain that in simpler terms?"
5. **Ask for examples**: "Can you give examples of machine learning applications?" helps with understanding

### Common Knowledge Mode Issues

**Issue**: Responses are too brief or incomplete
- **Solution**: Ask follow-up questions like "Can you elaborate on that?" or "Tell me more about [specific aspect]"

**Issue**: Response contains outdated information
- **Solution**: Ask "Do you have more recent information about this topic?"

**Issue**: Technical terms are not explained
- **Solution**: Ask "Can you define the technical terms you used?"

## Switching Between Modes

The system intelligently handles mode switching:

- **Automatic Detection**: The system will detect if you're asking a knowledge question in appointment mode (or vice versa) and offer to switch modes.
- **Explicit Mode Switching**: Use any of these phrases to manually switch modes:
  - "Switch to appointment mode" or "Use appointment scheduler"
  - "Switch to knowledge mode" or "Use knowledge assistant"
- **Context Preservation**: Your conversation context is preserved when switching modes.
- **Mode Confirmation**: The system will confirm which mode you're using after switching.

### Examples

- If in Knowledge Mode: "I want to schedule an appointment with John" → System will offer to switch to Appointment Mode
- If in Appointment Mode: "What is quantum computing?" → System will offer to switch to Knowledge Mode

## Voice Interaction Tips

If using voice input:
1. **Speak clearly**: Enunciate person names and dates carefully
2. **Verify transcription**: Check that the system correctly transcribed your speech
3. **Use standard time formats**: "Three PM" works better than "three in the afternoon"
4. **Pause between requests**: Allow the system to process each request fully

## UI Controls

- The UI displays your current mode at the top of the screen
- You can manually switch modes using the mode selector buttons
- Use the "Clear Chat" button to reset the conversation while maintaining your selected mode
- Audio responses can be toggled on/off with the sound button

## Advanced Tips

1. **Conversation summaries**: Ask "Summarize our conversation" to get a recap
2. **Context awareness**: The system remembers previous mentions of people and dates within the same conversation
3. **Correcting mistakes**: If the system misunderstands, say "No, I meant..." and clarify
4. **Handling interruptions**: If your conversation is interrupted, you can say "Let's continue with [topic]"
5. **Appointment modifications**: To change an appointment, first cancel it, then create a new one
6. **Contextual cancellation**: After discussing specific appointments, you can say "cancel this appointment" or "cancel it" without repeating all the details

## Troubleshooting

If the assistant doesn't understand your request:
1. Rephrase your question more clearly and with complete information
2. Check which mode you're currently in (displayed in the UI)
3. If needed, explicitly switch modes using the phrases above
4. Provide more specific information (person, date, time) for appointments
5. For appointment cancellation issues, first list appointments to see exact details
6. If cancellation fails, try specifying the exact date format (e.g., "2025-06-20" instead of "June 20")
7. If problems persist, try clearing the chat with "clear chat" and starting fresh
8. For persistent technical issues, refresh the browser or restart the application

---