"""
CRM Tools für LangGraph Agents.
Ermöglicht Zugriff auf Live-Daten aus dem CRM-System.
"""

import logging

from langchain_core.tools import tool

from app.prompts import get_prompt
from app.services.crm_factory import get_crm_provider, is_crm_available

logger = logging.getLogger(__name__)

# Load tool descriptions from prompts folder
_GET_CRM_FACTS_DESCRIPTION = get_prompt("tool_get_crm_facts")
_CHECK_CRM_STATUS_DESCRIPTION = get_prompt("tool_check_crm_status")


@tool
async def get_crm_facts(entity_id: str, query_context: str = "") -> str:
    logger.info(f"🔧 CRM Tool: Getting facts for entity '{entity_id}'")
    logger.debug(f"Query context: {query_context}")
    
    # Check if CRM is configured
    if not is_crm_available():
        error_msg = "CRM ist nicht konfiguriert. Bitte ACTIVE_CRM_PROVIDER in der Konfiguration setzen."
        logger.warning(f"⚠️ {error_msg}")
        return error_msg
    
    try:
        # Get CRM provider
        provider = get_crm_provider()
        
        if not provider:
            return "CRM Provider konnte nicht geladen werden."
        
        # Fetch live facts
        logger.info(f"📞 Calling CRM: {provider.get_provider_name()}")
        
        facts = await provider.search_live_facts(
            entity_id=entity_id,
            query_context=query_context
        )
        
        logger.info(f"✅ CRM facts retrieved: {len(facts)} chars")
        
        return facts
        
    except Exception as e:
        error_msg = f"Fehler beim Abruf der CRM-Daten: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return error_msg


@tool
def check_crm_status() -> str:
    logger.info("🔧 CRM Tool: Checking CRM status")
    
    if not is_crm_available():
        return "❌ Kein CRM konfiguriert"
    
    try:
        provider = get_crm_provider()
        
        if not provider:
            return "❌ CRM Provider konnte nicht geladen werden"
        
        provider_name = provider.get_provider_name()
        
        # Check connection
        if provider.check_connection():
            result = f"✅ CRM verbunden: {provider_name}"
            logger.info(result)
            return result
        else:
            result = f"⚠️ CRM konfiguriert ({provider_name}) aber nicht erreichbar"
            logger.warning(result)
            return result
            
    except Exception as e:
        error_msg = f"❌ CRM Status-Check fehlgeschlagen: {str(e)}"
        logger.error(error_msg)
        return error_msg


# Set docstrings after function definitions
get_crm_facts.__doc__ = _GET_CRM_FACTS_DESCRIPTION
check_crm_status.__doc__ = _CHECK_CRM_STATUS_DESCRIPTION
