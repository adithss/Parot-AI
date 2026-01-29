import os
import logging
from google import genai

logger = logging.getLogger("chat_service")

def query_meeting_context(
    transcript: str,
    summary: str,
    sentiment: dict,
    emotion_analysis: list,
    action_items: list,
    key_decisions: list,
    question: str
) -> str:
    """
    Answer questions about a meeting using context from the transcript and analysis.
    Returns a direct conversational answer, not structured data.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("GOOGLE_API_KEY not set")

        client = genai.Client(api_key=api_key)

        # Build context from all meeting information
        context_parts = []
        
        # Add summary
        if summary:
            context_parts.append(f"MEETING SUMMARY:\n{summary}")
        
        # Add sentiment
        if sentiment and sentiment.get('overall'):
            context_parts.append(f"\nOVERALL SENTIMENT: {sentiment['overall']}")
            if sentiment.get('highlights'):
                highlights = "\n".join(f"- {h}" for h in sentiment['highlights'])
                context_parts.append(f"Key Highlights:\n{highlights}")
        
        # Add decisions
        if key_decisions:
            decisions = "\n".join(f"- {d}" for d in key_decisions)
            context_parts.append(f"\nKEY DECISIONS:\n{decisions}")
        
        # Add action items
        if action_items:
            items = "\n".join(f"- {item}" for item in action_items)
            context_parts.append(f"\nACTION ITEMS:\n{items}")
        
        # Add emotion analysis
        if emotion_analysis:
            emotions = "\n".join(
                f"- {e.get('emotion', 'Unknown')}: {e.get('reasoning', '')}" 
                for e in emotion_analysis
            )
            context_parts.append(f"\nEMOTION ANALYSIS:\n{emotions}")
        
        # Add full transcript
        if transcript:
            context_parts.append(f"\nFULL TRANSCRIPT:\n{transcript}")
        
        context = "\n\n".join(context_parts)
        
        # Create prompt for conversational response
        prompt = f"""You are a helpful AI assistant that answers questions about a meeting. 

Here is all the information from the meeting:

{context}

Based on the meeting information above, please answer the following question in a natural, conversational way. Be specific and reference relevant parts of the meeting when answering. If the information needed to answer the question is not available in the meeting data, say so politely.

Question: {question}

Provide a clear, concise, and helpful answer:"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        # Get the response text
        answer = response.text.strip()
        
        logger.info(f"Generated answer for question: {question[:50]}...")
        
        return answer

    except Exception as e:
        logger.error(f"Chat service error: {e}")
        raise Exception(f"Failed to generate answer: {e}")