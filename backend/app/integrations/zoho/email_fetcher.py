"""
Email Fetching via Related Lists.

Emails are not a standalone module in Zoho CRM but Related Lists.
We fetch them per entity (Account, Contact).
"""

import asyncio
import logging
from typing import Any, Dict, List

from app.integrations.zoho.client import ZohoAPIError, ZohoClient

logger = logging.getLogger(__name__)


async def fetch_emails_for_account(
    client: ZohoClient,
    account_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch emails related to an Account.
    
    Args:
        client: ZohoClient instance
        account_id: Account ID (without zoho_ prefix)
        limit: Max emails to fetch per account
        
    Returns:
        List of email records
    """
    try:
        # Zoho API: GET /crm/v3/Accounts/{account_id}/Emails
        response = await client.get(
            f"/crm/v3/Accounts/{account_id}/Emails",
            params={"per_page": min(limit, 200)}  # Max 200 per page
        )
        
        emails = response.get("data", [])
        return emails
        
    except ZohoAPIError as e:
        # No permission or no emails - both are fine
        logger.debug(f"No emails for Account {account_id}: {e}")
        return []
    except Exception as e:
        logger.debug(f"Error fetching emails for Account {account_id}: {e}")
        return []


async def fetch_emails_for_contact(
    client: ZohoClient,
    contact_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch emails related to a Contact.
    
    Args:
        client: ZohoClient instance
        contact_id: Contact ID (without zoho_ prefix)
        limit: Max emails to fetch per contact
        
    Returns:
        List of email records
    """
    try:
        # Zoho API: GET /crm/v3/Contacts/{contact_id}/Emails
        response = await client.get(
            f"/crm/v3/Contacts/{contact_id}/Emails",
            params={"per_page": min(limit, 200)}  # Max 200 per page
        )
        
        emails = response.get("data", [])
        return emails
        
    except ZohoAPIError as e:
        # No permission or no emails - both are fine
        logger.debug(f"No emails for Contact {contact_id}: {e}")
        return []
    except Exception as e:
        logger.debug(f"Error fetching emails for Contact {contact_id}: {e}")
        return []


async def fetch_all_emails_for_entities(
    client: ZohoClient,
    accounts: List[Dict[str, Any]],
    contacts: List[Dict[str, Any]],
    limit_per_entity: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch all emails for a list of Accounts and Contacts.
    
    Args:
        client: ZohoClient instance
        accounts: List of account records (must have 'id' field)
        contacts: List of contact records (must have 'id' field)
        limit_per_entity: Max emails per Account/Contact
        
    Returns:
        List of all email records with parent reference
    """
    logger.info(f"📧 Fetching emails for {len(accounts)} Accounts and {len(contacts)} Contacts...")
    
    all_emails = []
    
    # Fetch emails for Accounts
    logger.info(f"  📧 Fetching emails for {len(accounts)} Accounts...")
    for account in accounts:
        account_id = account.get("id")
        if not account_id:
            continue
        
        emails = await fetch_emails_for_account(client, account_id, limit_per_entity)
        
        # Add parent reference to each email
        for email in emails:
            email["_parent_type"] = "Account"
            email["_parent_id"] = account_id
        
        all_emails.extend(emails)
        
        # Rate limiting (100 calls/min = 0.6s)
        await asyncio.sleep(0.6)
    
    logger.info(f"    ✅ Fetched {len(all_emails)} emails from Accounts")
    
    # Fetch emails for Contacts
    logger.info(f"  📧 Fetching emails for {len(contacts)} Contacts...")
    contact_email_count = 0
    for contact in contacts:
        contact_id = contact.get("id")
        if not contact_id:
            continue
        
        emails = await fetch_emails_for_contact(client, contact_id, limit_per_entity)
        
        # Add parent reference to each email
        for email in emails:
            email["_parent_type"] = "Contact"
            email["_parent_id"] = contact_id
        
        all_emails.extend(emails)
        contact_email_count += len(emails)
        
        # Rate limiting
        await asyncio.sleep(0.6)
    
    logger.info(f"    ✅ Fetched {contact_email_count} emails from Contacts")
    logger.info(f"  ✅ Total emails fetched: {len(all_emails)}")
    
    return all_emails


def process_email_record(
    email: Dict[str, Any],
    label: str = "Email"
) -> Dict[str, Any]:
    """
    Process an email record into graph schema format.
    
    Args:
        email: Raw email record from Related List API
        label: Target node label
        
    Returns:
        Processed record dict
    """
    # Extract properties
    properties = {
        "zoho_id": email.get("id"),
        "name": email.get("Subject", "Email"),
        "subject": email.get("Subject"),
        "from": email.get("from", {}).get("email") if isinstance(email.get("from"), dict) else email.get("from"),
        "to": ", ".join([t.get("email", "") for t in email.get("to", [])]) if isinstance(email.get("to"), list) else email.get("to"),
        "sent_time": email.get("sent_time") or email.get("time"),
        "content": email.get("content"),
    }
    
    # Extract relations
    relations = []
    
    # Link to parent (Account or Contact)
    parent_type = email.get("_parent_type")
    parent_id = email.get("_parent_id")
    
    if parent_type and parent_id:
        relations.append({
            "target_id": f"zoho_{parent_id}",
            "edge_type": "HAS_EMAIL",
            "target_label": parent_type,
            "direction": "INCOMING"
        })
    
    return {
        "source_id": f"zoho_email_{email.get('id')}",
        "label": label,
        "properties": properties,
        "relations": relations
    }


