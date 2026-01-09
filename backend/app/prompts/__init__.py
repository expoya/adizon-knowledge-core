"""
Prompt Management für Adizon Knowledge Core.

Dieses Modul lädt alle System-Prompts aus separaten Text-Dateien,
um sicheres und einfaches Prompt-Engineering zu ermöglichen.
"""

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Base directory für Prompts
PROMPTS_DIR = Path(__file__).parent


class PromptLoader:
    """Lädt und cached Prompts aus Text-Dateien."""
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def load(cls, prompt_name: str) -> str:
        """
        Lädt einen Prompt aus einer Text-Datei.
        
        Args:
            prompt_name: Name des Prompts ohne .txt Extension
                        (z.B. "intent_classification")
        
        Returns:
            Der Prompt-Text als String
            
        Raises:
            FileNotFoundError: Wenn der Prompt nicht existiert
        """
        # Check cache
        if prompt_name in cls._cache:
            return cls._cache[prompt_name]
        
        # Lade von Datei
        prompt_file = PROMPTS_DIR / f"{prompt_name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}\n"
                f"Available prompts: {cls.list_available()}"
            )
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            
            # Cache it
            cls._cache[prompt_name] = prompt_text
            
            logger.debug(f"Loaded prompt '{prompt_name}' ({len(prompt_text)} chars)")
            return prompt_text
            
        except Exception as e:
            logger.error(f"Failed to load prompt '{prompt_name}': {e}")
            raise
    
    @classmethod
    def list_available(cls) -> list[str]:
        """
        Listet alle verfügbaren Prompts auf.
        
        Returns:
            Liste von Prompt-Namen (ohne .txt Extension)
        """
        prompt_files = PROMPTS_DIR.glob("*.txt")
        return sorted([p.stem for p in prompt_files])
    
    @classmethod
    def reload(cls, prompt_name: str = None) -> None:
        """
        Lädt Prompts neu (z.B. nach Änderungen).
        
        Args:
            prompt_name: Spezifischer Prompt oder None für alle
        """
        if prompt_name:
            cls._cache.pop(prompt_name, None)
            logger.info(f"Reloaded prompt: {prompt_name}")
        else:
            cls._cache.clear()
            logger.info("Reloaded all prompts")


def get_prompt(name: str) -> str:
    """
    Convenience-Funktion zum Laden eines Prompts.
    
    Args:
        name: Name des Prompts (ohne .txt)
        
    Returns:
        Der Prompt-Text
    """
    return PromptLoader.load(name)


# Pre-load commonly used prompts at module import
try:
    PromptLoader.load("intent_classification")
    PromptLoader.load("sql_generation")
    PromptLoader.load("answer_generation")
    logger.info(f"✅ Prompts loaded: {PromptLoader.list_available()}")
except Exception as e:
    logger.warning(f"⚠️ Failed to pre-load prompts: {e}")

