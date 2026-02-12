import argostranslate.package
import argostranslate.translate
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Initialize Argos Translate
def initialize_argos():
    """Initialize Argos Translate and download language packages if needed"""
    try:
        # Update package index
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        
        # Get installed packages
        installed_packages = argostranslate.package.get_installed_packages()
        installed_codes = set()
        for pkg in installed_packages:
            installed_codes.add(f"{pkg.from_code}-{pkg.to_code}")
        
        logger.info(f"Installed language packages: {installed_codes}")
        
        # Define common language pairs to install
        common_pairs = [
            ("en", "es"), ("es", "en"),  # English <-> Spanish
            ("en", "fr"), ("fr", "en"),  # English <-> French
            ("en", "de"), ("de", "en"),  # English <-> German
            ("en", "it"), ("it", "en"),  # English <-> Italian
            ("en", "pt"), ("pt", "en"),  # English <-> Portuguese
            ("en", "ru"), ("ru", "en"),  # English <-> Russian
            ("en", "zh"), ("zh", "en"),  # English <-> Chinese
            ("en", "ja"), ("ja", "en"),  # English <-> Japanese
            ("en", "ar"), ("ar", "en"),  # English <-> Arabic
            ("en", "hi"), ("hi", "en"),  # English <-> Hindi
             ("en", "ml"),
        ]
        
        # Install missing packages
        for from_code, to_code in common_pairs:
            pair_code = f"{from_code}-{to_code}"
            if pair_code not in installed_codes:
                # Find and install the package
                package_to_install = next(
                    (pkg for pkg in available_packages 
                     if pkg.from_code == from_code and pkg.to_code == to_code),
                    None
                )
                if package_to_install:
                    logger.info(f"Installing language package: {from_code} -> {to_code}")
                    argostranslate.package.install_from_path(package_to_install.download())
                    
        logger.info("Argos Translate initialization complete")
        
    except Exception as e:
        logger.error(f"Error initializing Argos Translate: {str(e)}")

# Call initialization when module is loaded
try:
    initialize_argos()
except Exception as e:
    logger.warning(f"Failed to initialize Argos Translate: {str(e)}")

def translate_text(text: str, target_lang: str, source_lang: str = "en") -> str:
    """
    Translate a single text string using Argos Translate
    
    Args:
        text: Text to translate
        target_lang: Target language code (e.g., 'es', 'fr', 'de')
        source_lang: Source language code (default: 'en')
    
    Returns:
        Translated text
    """
    if not text or not text.strip():
        return text
    
    # If source and target are the same, return original
    if source_lang == target_lang:
        return text
    
    try:
        # Get installed languages
        installed_languages = argostranslate.translate.get_installed_languages()
        
        # Find source language
        from_lang = next(
            (lang for lang in installed_languages if lang.code == source_lang),
            None
        )
        
        if not from_lang:
            logger.warning(f"Source language '{source_lang}' not found. Returning original text.")
            return text
        
        # Find target language
        to_lang = next(
            (lang for lang in installed_languages if lang.code == target_lang),
            None
        )
        
        if not to_lang:
            logger.warning(f"Target language '{target_lang}' not found. Returning original text.")
            return text
        
        # Get translation
        translation = from_lang.get_translation(to_lang)
        
        if not translation:
            logger.warning(f"No translation available from '{source_lang}' to '{target_lang}'")
            return text
        
        # Translate the text
        translated_text = translation.translate(text)
        return translated_text
        
    except Exception as e:
        logger.error(f"Translation failed for text: {str(e)}")
        return text

def translate_list(items: List[str], target_lang: str, source_lang: str = "en") -> List[str]:
    """
    Translate a list of strings
    
    Args:
        items: List of strings to translate
        target_lang: Target language code
        source_lang: Source language code
    
    Returns:
        List of translated strings
    """
    translated_items = []
    
    for item in items:
        if isinstance(item, str):
            translated_items.append(translate_text(item, target_lang, source_lang))
        else:
            translated_items.append(item)
    
    return translated_items

def translate_meeting_content(
    content: Dict[str, Any],
    target_lang: str,
    source_lang: str = "en"
) -> Dict[str, Any]:
    """
    Translate meeting analysis content
    
    Args:
        content: Meeting analysis content dictionary
        target_lang: Target language code
        source_lang: Source language code (default: 'en')
    
    Returns:
        Translated content dictionary
    """
    translated_content = {}
    
    try:
        # Translate summary
        if "summary" in content and content["summary"]:
            logger.info("Translating summary...")
            translated_content["summary"] = translate_text(
                content["summary"],
                target_lang,
                source_lang
            )
        
        # Translate action items
        if "actionItems" in content and content["actionItems"]:
            logger.info("Translating action items...")
            translated_content["actionItems"] = translate_list(
                content["actionItems"],
                target_lang,
                source_lang
            )
        
        # Translate key decisions
        if "keyDecisions" in content and content["keyDecisions"]:
            logger.info("Translating key decisions...")
            translated_content["keyDecisions"] = translate_list(
                content["keyDecisions"],
                target_lang,
                source_lang
            )
        
        # Translate diarized transcript
        if "diarizedTranscript" in content and content["diarizedTranscript"]:
            logger.info("Translating transcript...")
            translated_transcript = []
            
            for segment in content["diarizedTranscript"]:
                if isinstance(segment, dict) and "text" in segment:
                    translated_segment = {
                        "speaker": segment["speaker"],  # Don't translate speaker names
                        "text": translate_text(
                            segment["text"],
                            target_lang,
                            source_lang
                        )
                    }
                    translated_transcript.append(translated_segment)
                else:
                    translated_transcript.append(segment)
            
            translated_content["diarizedTranscript"] = translated_transcript
        
        # Translate sentiment (only highlights, keep overall sentiment)
        if "sentiment" in content and content["sentiment"]:
            logger.info("Translating sentiment...")
            translated_sentiment = {
                "overall": content["sentiment"].get("overall", "Neutral")  # Don't translate
            }
            
            if "highlights" in content["sentiment"]:
                translated_sentiment["highlights"] = translate_list(
                    content["sentiment"]["highlights"],
                    target_lang,
                    source_lang
                )
            
            translated_content["sentiment"] = translated_sentiment
        
        # Translate emotion analysis
        if "emotionAnalysis" in content and content["emotionAnalysis"]:
            logger.info("Translating emotion analysis...")
            translated_emotions = []
            
            for emotion in content["emotionAnalysis"]:
                if isinstance(emotion, dict):
                    translated_emotion = {
                        "emotion": emotion.get("emotion", ""),  # Keep emotion labels
                    }
                    
                    if "reasoning" in emotion:
                        translated_emotion["reasoning"] = translate_text(
                            emotion["reasoning"],
                            target_lang,
                            source_lang
                        )
                    
                    translated_emotions.append(translated_emotion)
                else:
                    translated_emotions.append(emotion)
            
            translated_content["emotionAnalysis"] = translated_emotions
        
        logger.info("Translation completed successfully")
        return translated_content
        
    except Exception as e:
        logger.error(f"Error during translation: {str(e)}")
        # Return original content if translation fails
        return content

def get_available_languages() -> List[Dict[str, str]]:
    """
    Get list of available/installed languages from Argos Translate
    
    Returns:
        List of language dictionaries with 'code' and 'name'
    """
    try:
        installed_languages = argostranslate.translate.get_installed_languages()
        
        # Get unique language codes
        language_codes = set()
        for lang in installed_languages:
            language_codes.add(lang.code)
        
        # Map codes to names
        language_names = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
            "ar": "Arabic",
            "hi": "Hindi",
            "ko": "Korean",
            "nl": "Dutch",
            "pl": "Polish",
            "tr": "Turkish",
            "ml": "Malayalam"
        }
        
        languages = []
        for code in sorted(language_codes):
            languages.append({
                "code": code,
                "name": language_names.get(code, code.upper())
            })
        
        return languages
        
    except Exception as e:
        logger.error(f"Failed to get languages: {str(e)}")
        # Return common languages as fallback
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
        ]

def install_language_package(from_code: str, to_code: str) -> bool:
    """
    Install a specific language package
    
    Args:
        from_code: Source language code
        to_code: Target language code
    
    Returns:
        True if successful, False otherwise
    """
    try:
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        
        package_to_install = next(
            (pkg for pkg in available_packages 
             if pkg.from_code == from_code and pkg.to_code == to_code),
            None
        )
        
        if package_to_install:
            logger.info(f"Installing language package: {from_code} -> {to_code}")
            argostranslate.package.install_from_path(package_to_install.download())
            return True
        else:
            logger.warning(f"Package not found: {from_code} -> {to_code}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to install package: {str(e)}")
        return False