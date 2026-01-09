"""
Query Building and Live Facts Retrieval for Zoho CRM.

Handles search_live_facts queries for Einwände, Calendly, Deals, etc.
"""

import logging
from typing import Any, Dict

from app.integrations.zoho.client import ZohoClient

logger = logging.getLogger(__name__)


async def query_einwaende(client: ZohoClient, zoho_id: str) -> str:
    """
    Queries Einwände (Objections) for an entity.
    
    Args:
        client: ZohoClient instance
        zoho_id: Zoho record ID (without "zoho_" prefix)
        
    Returns:
        Markdown formatted section or empty string
    """
    try:
        query = f"SELECT Name, Einwand_Kategorie, Einwandbeschreibung FROM Einw_nde WHERE Lead.id = '{zoho_id}' LIMIT 50"
        response = await client.post("/crm/v6/coql", json={"select_query": query})
        einwaende = response.get("data", [])
        
        if einwaende:
            section = ["### 🛡️ Einwände\n"]
            for obj in einwaende:
                name = obj.get("Name", "N/A")
                kategorie = obj.get("Einwand_Kategorie", "N/A")
                beschreibung = obj.get("Einwandbeschreibung", "")
                
                # Format output with category and description
                if beschreibung:
                    section.append(f"- **{name}** ({kategorie}): {beschreibung}")
                else:
                    section.append(f"- **{name}** ({kategorie})")
            return "\n".join(section)
            
    except Exception as e:
        logger.warning(f"⚠️ Einwände query failed: {e}")
    
    return "### 🛡️ Einwände\n*(Query failed)*"


async def query_calendly_events(client: ZohoClient, zoho_id: str) -> str:
    """
    Queries Calendly Events for an entity.
    
    Args:
        client: ZohoClient instance
        zoho_id: Zoho record ID (without "zoho_" prefix)
        
    Returns:
        Markdown formatted section or empty string
    """
    try:
        # Try Lead relation first
        query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE calendlyforzohocrm__Lead.id = '{zoho_id}' LIMIT 20"
        response = await client.post("/crm/v6/coql", json={"select_query": query})
        calendly = response.get("data", [])
        
        # Fallback: Try Contact relation
        if not calendly:
            query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE calendlyforzohocrm__Contact.id = '{zoho_id}' LIMIT 20"
            response = await client.post("/crm/v6/coql", json={"select_query": query})
            calendly = response.get("data", [])
        
        # Fallback: Try Account relation
        if not calendly:
            query = f"SELECT Name, calendlyforzohocrm__Start_Time, calendlyforzohocrm__Status FROM calendlyforzohocrm__Calendly_Events WHERE Verkn_pfter_Account.id = '{zoho_id}' LIMIT 20"
            response = await client.post("/crm/v6/coql", json={"select_query": query})
            calendly = response.get("data", [])
        
        if calendly:
            section = ["### 📅 Calendly Events\n"]
            for event in calendly:
                name = event.get("Name", "N/A")
                start_time = event.get("calendlyforzohocrm__Start_Time", "N/A")
                status = event.get("calendlyforzohocrm__Status", "N/A")
                section.append(f"- **{name}**: {start_time} (Status: {status})")
            return "\n".join(section)
            
    except Exception as e:
        logger.warning(f"⚠️ Calendly query failed: {e}")
    
    return "### 📅 Calendly Events\n*(Query failed)*"


async def query_deals(client: ZohoClient, zoho_id: str) -> str:
    """
    Queries Deals for an entity.
    
    Args:
        client: ZohoClient instance
        zoho_id: Zoho record ID (without "zoho_" prefix)
        
    Returns:
        Markdown formatted section or empty string
    """
    try:
        # Try Contact relation first (for converted leads)
        query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Contact_Name.id = '{zoho_id}' LIMIT 50"
        response = await client.post("/crm/v6/coql", json={"select_query": query})
        deals = response.get("data", [])
        
        # Fallback: Try Account relation
        if not deals:
            query = f"SELECT Deal_Name, Amount, Stage, Closing_Date FROM Deals WHERE Account_Name.id = '{zoho_id}' LIMIT 50"
            response = await client.post("/crm/v6/coql", json={"select_query": query})
            deals = response.get("data", [])
        
        if deals:
            section = ["### 💰 Deals\n"]
            total_amount = 0
            for deal in deals:
                name = deal.get("Deal_Name", "N/A")
                amount = deal.get("Amount", 0)
                stage = deal.get("Stage", "N/A")
                closing = deal.get("Closing_Date", "N/A")
                
                section.append(f"- **{name}**: €{amount:,.2f} | {stage} | Close: {closing}")
                
                if amount:
                    total_amount += float(amount)
            
            section.append(f"\n**Total Deal Value**: €{total_amount:,.2f}")
            return "\n".join(section)
            
    except Exception as e:
        logger.warning(f"⚠️ Deals query failed: {e}")
    
    return "### 💰 Deals\n*(Query failed)*"


async def search_live_facts(client: ZohoClient, entity_id: str, query_context: str) -> str:
    """
    Retrieves live facts about a Zoho entity.
    
    Queries multiple modules (Einwände, Calendly, Deals, Finance) and
    formats results as Markdown for LLM consumption.
    
    Args:
        client: ZohoClient instance
        entity_id: Zoho record ID (with "zoho_" prefix)
        query_context: Context about what information is needed
        
    Returns:
        Formatted Markdown string with entity facts
    """
    logger.info(f"🔍 Searching live facts for entity: {entity_id}")
    logger.debug(f"Query context: {query_context}")
    
    # Remove "zoho_" prefix
    if entity_id.startswith("zoho_"):
        zoho_id = entity_id[5:]
    else:
        zoho_id = entity_id
    
    # Collect results from all queries
    sections = []
    
    # Query Einwände
    einwaende_section = await query_einwaende(client, zoho_id)
    if einwaende_section:
        sections.append(einwaende_section)
    
    # Query Calendly Events
    calendly_section = await query_calendly_events(client, zoho_id)
    if calendly_section:
        sections.append(calendly_section)
    
    # Query Deals
    deals_section = await query_deals(client, zoho_id)
    if deals_section:
        sections.append(deals_section)
    
    # Skip Finance modules - COQL not supported for Subscriptions__s
    logger.debug("⚠️ Skipping Finance/Subscriptions - COQL not supported for finance modules")
    
    # === Build final response ===
    if not sections:
        return f"""
# Live Facts for Entity: {entity_id}

No data found across all modules (Einwände, Calendly Events, Deals).

Query Context: {query_context}
"""
    
    result = f"""
# Live Facts for Entity: {entity_id}

Query Context: _{query_context}_

{chr(10).join(sections)}

---
*Data source: Zoho CRM*
*Note: Some queries may have failed due to missing fields or permissions.*
"""
    
    logger.info(f"✅ Live facts compiled: {len(sections)} sections")
    
    return result

