"""
Data Processing Logic for Zoho Books Records.

Extracts properties and relationships from Zoho Books API responses.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def process_books_invoice(
    invoice: Dict[str, Any],
    label: str = "Invoice"
) -> Dict[str, Any]:
    """
    Processes a Zoho Books Invoice record into graph schema format.
    
    Args:
        invoice: Raw Books invoice record
        label: Target node label
        
    Returns:
        Processed record dict with source_id, label, properties, relations
    """
    # Extract properties
    properties = {
        "zoho_books_id": invoice.get("invoice_id"),
        "invoice_number": invoice.get("invoice_number"),
        "name": invoice.get("invoice_number", f"Invoice {invoice.get('invoice_id')}"),
        "status": invoice.get("status"),
        "total": invoice.get("total"),
        "balance": invoice.get("balance"),
        "date": invoice.get("date"),
        "due_date": invoice.get("due_date"),
        "currency_code": invoice.get("currency_code"),
        "customer_name": invoice.get("customer_name"),
        "customer_id": invoice.get("customer_id"),
    }
    
    # Extract relations
    relations = []
    
    # Link to Account (if customer_id matches CRM Account)
    customer_id = invoice.get("customer_id")
    if customer_id:
        relations.append({
            "target_id": f"zoho_books_customer_{customer_id}",  # Books customer ID
            "edge_type": "HAS_INVOICE",
            "target_label": "Account",  # Will try to match with CRM Account
            "direction": "INCOMING"
        })
    
    return {
        "source_id": f"zoho_books_invoice_{invoice.get('invoice_id')}",
        "label": label,
        "properties": properties,
        "relations": relations
    }



