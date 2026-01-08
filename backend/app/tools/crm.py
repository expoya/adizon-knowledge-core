"""
CRM Tools für LangGraph Agents.
Ermöglicht Zugriff auf Live-Daten aus dem CRM-System.
"""

import logging

from langchain_core.tools import tool

from app.services.crm_factory import get_crm_provider, is_crm_available

logger = logging.getLogger(__name__)


@tool
def get_crm_facts(entity_id: str, query_context: str = "") -> str:
    """
    Holt Live-Fakten über eine Entity aus dem CRM-System.
    
    Ruft aktuelle Informationen zu einer Person oder Firma ab:
    - Einwände (Objections)
    - Calendly Events (Meetings)
    - Deals (Geschäfte)
    - Finance (Subscriptions, Rechnungen)
    
    Args:
        entity_id: Die CRM Entity ID (z.B. "zoho_3652397000000649013")
        query_context: Kontext über welche Informationen gebraucht werden
        
    Returns:
        Formatierter String mit aktuellen CRM-Daten oder Fehlermeldung
        
    Example:
        >>> get_crm_facts("zoho_123456", "deals and revenue")
        '''
        # Live Facts for Entity: zoho_123456
        
        ### 💰 Deals
        - **Solar Installation**: €50,000.00 | Proposal | Close: 2026-02-01
        ...
        '''
    """
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
        
        facts = provider.search_live_facts(
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
    """
    Prüft ob ein CRM-System konfiguriert und erreichbar ist.
    
    Returns:
        Status-String mit Provider-Name oder Fehlermeldung
        
    Example:
        >>> check_crm_status()
        "✅ CRM verbunden: Zoho CRM"
    """
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

