"""
Query Building and Live Facts Retrieval for Zoho CRM.

Handles search_live_facts queries for Einwände, Calendly, Deals, etc.
"""

import logging
import re
from typing import Any, Dict, Union

from app.integrations.zoho.client import ZohoClient

logger = logging.getLogger(__name__)


def parse_currency_to_float(value: Union[str, float, int, None]) -> float:
    """
    Parse currency values to float.

    Handles:
    - German format: "EUR 2.988,00" → 2988.00
    - English format: "EUR 2,988.00" → 2988.00
    - Already numeric: 2988.00 → 2988.00
    - None or empty: → 0.0

    Args:
        value: Currency value in various formats

    Returns:
        Float value
    """
    if value is None:
        return 0.0

    # Already a number
    if isinstance(value, (int, float)):
        return float(value)

    # Convert to string and clean
    text = str(value).strip()

    if not text:
        return 0.0

    # Remove currency symbols and whitespace
    text = re.sub(r'[€$£¥]|EUR|USD|GBP', '', text, flags=re.IGNORECASE).strip()

    # Detect format: German uses comma as decimal, period as thousands
    # If we have both comma and period, determine which is decimal
    has_comma = ',' in text
    has_period = '.' in text

    if has_comma and has_period:
        # Both present - check which comes last (that's the decimal)
        comma_pos = text.rfind(',')
        period_pos = text.rfind('.')

        if comma_pos > period_pos:
            # German format: 2.988,00
            text = text.replace('.', '').replace(',', '.')
        else:
            # English format: 2,988.00
            text = text.replace(',', '')
    elif has_comma:
        # Only comma - likely German decimal separator
        text = text.replace(',', '.')
    # If only period, it's already correct

    # Remove any remaining non-numeric characters except decimal point and minus
    text = re.sub(r'[^\d.\-]', '', text)

    try:
        return float(text) if text else 0.0
    except ValueError:
        logger.warning(f"Could not parse currency value: {value}")
        return 0.0


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


async def query_notes(client: ZohoClient, zoho_id: str) -> str:
    """
    Queries Notes for an entity (Contact, Account, Lead, Deal).
    
    Args:
        client: ZohoClient instance
        zoho_id: Zoho record ID (without "zoho_" prefix)
        
    Returns:
        Markdown formatted section or empty string
    """
    try:
        # Notes use Parent_Id which can point to any module
        # FIXED: Parent_Id.id → Parent_Id (correct COQL syntax)
        query = f"SELECT Note_Title, Note_Content, Created_Time FROM Notes WHERE Parent_Id = '{zoho_id}' ORDER BY Created_Time DESC LIMIT 20"
        response = await client.post("/crm/v6/coql", json={"select_query": query})
        notes = response.get("data", [])
        
        if notes:
            section = ["### 📝 Notizen\n"]
            for note in notes:
                title = note.get("Note_Title", "Ohne Titel")
                content = note.get("Note_Content", "")
                created = note.get("Created_Time", "N/A")
                
                # Truncate long content
                if content and len(content) > 200:
                    content = content[:200] + "..."
                
                section.append(f"- **{title}** ({created})")
                if content:
                    section.append(f"  {content}")
            
            return "\n".join(section)
            
    except Exception as e:
        logger.warning(f"⚠️ Notes query failed: {e}")
    
    return ""  # Return empty string if no notes (not an error)


async def query_books_invoices(
    crm_account_id: str,
    books_client = None,
    analytics_client = None
) -> str:
    """
    Queries Zoho Books Invoices for a CRM Account.
    
    Prefers Analytics SQL (faster, more reliable), falls back to Books API.
    
    Args:
        crm_account_id: CRM Account ID (without "zoho_" prefix)
        books_client: ZohoBooksClient instance (fallback)
        analytics_client: ZohoAnalyticsClient instance (preferred)
        
    Returns:
        Markdown formatted section or empty string
    """
    logger.debug(f"📊 Fetching Books Invoices for CRM Account: {crm_account_id}")
    
    # STRATEGY 1: Use Analytics SQL (FAST, RELIABLE)
    if analytics_client:
        try:
            logger.debug("  🔍 Using Zoho Analytics SQL for invoice query...")
            invoices_data = await analytics_client.get_invoices_for_account(crm_account_id)
            
            if invoices_data:
                # Format Analytics data (column names might differ)
                # Note: Analytics returns currency as formatted strings like "EUR 2.988,00"
                customer_invoices = []
                for row in invoices_data:
                    total_val = parse_currency_to_float(row.get("total"))
                    status = row.get("status", "").lower()
                    balance_val = 0.0 if status == "paid" else total_val

                    customer_invoices.append({
                        "invoice_number": row.get("invoice_number"),
                        "status": row.get("status"),
                        "total": total_val,
                        "balance": balance_val,
                        "date": row.get("invoice_date"),
                        "due_date": row.get("invoice_date"),  # Analytics might not have due_date
                        "payment_date": row.get("payment_date"),
                    })
            else:
                customer_invoices = []
        
        except Exception as e:
            logger.warning(f"⚠️ Analytics invoice query failed: {e} - falling back to Books API")
            # Fall through to Books API fallback
            analytics_client = None
    
    # STRATEGY 2: Fallback to Books API (SLOW, requires full fetch + filter)
    if not analytics_client:
        if not books_client:
            logger.debug("⚠️ Neither Analytics nor Books client available - skipping invoice query")
            return ""
        
        try:
            logger.debug("  🔍 Using Books API for invoice query (fallback)...")
            
            # Build customer mapping to find correct Books customer_id
            customer_mapping = await books_client.build_customer_to_account_mapping()
            
            # Reverse mapping: CRM Account ID → Books Customer ID
            reverse_mapping = {v: k for k, v in customer_mapping.items()}
            books_customer_id = reverse_mapping.get(crm_account_id)
            
            if not books_customer_id:
                logger.debug(f"⚠️ No Books Customer found for CRM Account {crm_account_id}")
                return ""
            
            # Fetch invoices for this customer
            invoices = await books_client.fetch_all_invoices(max_pages=5)
            
            # Filter by customer_id
            customer_invoices = [
                inv for inv in invoices 
                if str(inv.get("customer_id")) == books_customer_id
            ]
        
        except Exception as e:
            logger.warning(f"⚠️ Books API invoice query failed: {e}")
            return ""
    
    # FORMAT RESULTS (common for both Analytics and Books API)
    if customer_invoices:
        section = ["### 🧾 Rechnungen (Zoho Books)\n"]
        total_amount = 0
        total_balance = 0
        
        for invoice in customer_invoices[:20]:  # Limit to 20
            invoice_number = invoice.get("invoice_number", "N/A")
            status = invoice.get("status", "N/A")
            total = float(invoice.get("total", 0))
            balance = float(invoice.get("balance", 0))
            date = invoice.get("date", "N/A")
            due_date = invoice.get("due_date", "N/A")
            currency = invoice.get("currency_code", "EUR")
            
            # Status emoji
            status_emoji = {
                "paid": "✅",
                "sent": "📤",
                "draft": "📝",
                "overdue": "⚠️",
                "void": "❌"
            }.get(status.lower(), "📄")
            
            section.append(
                f"- {status_emoji} **{invoice_number}**: {currency} {total:,.2f} "
                f"(Balance: {balance:,.2f}) | {status} | "
                f"Date: {date} | Due: {due_date}"
            )
            
            total_amount += total
            total_balance += balance
        
        section.append(f"\n**Total**: {currency} {total_amount:,.2f}")
        section.append(f"**Outstanding Balance**: {currency} {total_balance:,.2f}")
        section.append(f"**Total Invoices**: {len(customer_invoices)}")
        
        logger.info(f"✅ Found {len(customer_invoices)} Books Invoices")
        return "\n".join(section)
    
    return ""


async def search_live_facts(
    client: ZohoClient, 
    entity_id: str, 
    query_context: str,
    books_client = None,
    analytics_client = None
) -> str:
    """
    Retrieves live facts about a Zoho entity.
    
    Queries multiple modules (Notes, Einwände, Calendly, Deals, Books Invoices) and
    formats results as Markdown for LLM consumption.
    
    Args:
        client: ZohoClient instance
        entity_id: Zoho record ID (with "zoho_" prefix)
        query_context: Context about what information is needed
        books_client: Optional ZohoBooksClient for invoice queries (fallback)
        analytics_client: Optional ZohoAnalyticsClient for SQL queries (preferred)
        
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
    
    # Query Books Invoices (if available)
    if books_client or analytics_client:
        invoices_section = await query_books_invoices(
            crm_account_id=zoho_id,
            books_client=books_client,
            analytics_client=analytics_client
        )
        if invoices_section:
            sections.append(invoices_section)

    # Query CRM modules in PARALLEL for performance
    import asyncio

    crm_queries = await asyncio.gather(
        query_notes(client, zoho_id),
        query_einwaende(client, zoho_id),
        query_calendly_events(client, zoho_id),
        query_deals(client, zoho_id),
        return_exceptions=True  # Don't fail all if one fails
    )

    # Unpack results
    notes_section, einwaende_section, calendly_section, deals_section = crm_queries

    # Add successful results (skip exceptions)
    for section in [notes_section, einwaende_section, calendly_section, deals_section]:
        if section and not isinstance(section, Exception):
            sections.append(section)
    
    # Skip Finance modules - COQL not supported for Subscriptions__s
    logger.debug("⚠️ Skipping Finance/Subscriptions - COQL not supported for finance modules")
    
    # === Build final response ===
    if not sections:
        return f"""
# Live Facts for Entity: {entity_id}

No data found across all modules (Notes, Einwände, Calendly Events, Deals).

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

