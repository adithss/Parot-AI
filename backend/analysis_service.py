import os
import logging
import json
from google import genai

logger = logging.getLogger("analysis_service")

def analyze_transcript(transcript: str) -> dict:
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("GOOGLE_API_KEY not set")

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an intelligent meeting assistant. Analyze the following transcript and provide a structured JSON response.

IMPORTANT: Return ONLY valid JSON without any markdown formatting, code blocks, or preamble.

Analyze the following transcript and return a JSON object with this exact structure:
{{
  "summary": "A concise 2-3 sentence summary of the meeting",
  "sentiment": {{
    "overall": "Positive, Negative, or Neutral",
    "highlights": ["key quote 1", "key quote 2"]
  }},
  "emotionAnalysis": [
    {{"emotion": "Excitement", "reasoning": "why this emotion was detected"}},
    {{"emotion": "Concern", "reasoning": "why this emotion was detected"}}
  ],
  "keyDecisions": ["decision 1", "decision 2"],
  "actionItems": ["action item 1", "action item 2"],
  "diarizedTranscript": [
    {{"speaker": "Speaker_00", "text": "what they said"}},
    {{"speaker": "Speaker_01", "text": "what they said"}}
  ]
}}

If no action items or decisions are found, use empty arrays [].

Transcript:
{transcript}

Return ONLY the JSON object, no other text.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        # Get the response text
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        # Parse JSON
        try:
            analysis_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text was: {response_text}")
            # Return a default structure if parsing fails
            analysis_data = {
                "summary": "Failed to parse analysis. Raw response: " + response_text[:200],
                "sentiment": {"overall": "Neutral", "highlights": []},
                "emotionAnalysis": [],
                "keyDecisions": [],
                "actionItems": [],
                "diarizedTranscript": []
            }
        
        # Validate required fields
        required_fields = ["summary", "sentiment", "emotionAnalysis", "keyDecisions", "actionItems", "diarizedTranscript"]
        for field in required_fields:
            if field not in analysis_data:
                if field == "sentiment":
                    analysis_data[field] = {"overall": "Neutral", "highlights": []}
                elif field == "summary":
                    analysis_data[field] = "No summary available"
                else:
                    analysis_data[field] = []
        
        return analysis_data

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise Exception(f"Failed to analyze transcript: {e}")