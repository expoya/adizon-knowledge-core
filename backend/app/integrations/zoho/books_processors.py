"""
Data Processing Logic for Zoho Books Records.

Extracts properties and relationships from Zoho Books API responses.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def process_books_invoice(
    invoice: Dict[str, Any],
    label: str = "BooksInvoice",
    customer_mapping: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Processes a Zoho Books Invoice record into graph schema format.
    
    Args:
        invoice: Raw Books invoice record
        label: Target node label (default: BooksInvoice)
        customer_mapping: Dict mapping Books customer_id -> CRM account_id
        
    Returns:
        Processed record dict with source_id, label, properties, relations
    """
    invoice_id = invoice.get("invoice_id")
    customer_id = str(invoice.get("customer_id", "")) if invoice.get("customer_id") else None
    customer_name = invoice.get("customer_name")
    
    # Extract properties
    properties = {
        "zoho_books_id": invoice_id,
        "invoice_number": invoice.get("invoice_number"),
        "name": invoice.get("invoice_number", f"Invoice {invoice_id}"),
        "status": invoice.get("status"),
        "total": invoice.get("total"),
        "balance": invoice.get("balance"),
        "date": invoice.get("date"),
        "due_date": invoice.get("due_date"),
        "currency_code": invoice.get("currency_code"),
        "customer_name": customer_name,
        "customer_id": customer_id,
    }
    
    # Extract relations
    relations = []
    
    # Link to CRM Account via zcrm_account_id mapping
    if customer_id and customer_mapping:
        crm_account_id = customer_mapping.get(customer_id)
        
        if crm_account_id:
            # ✅ Correct CRM Account ID!
            relations.append({
                "target_id": f"zoho_{crm_account_id}",
                "edge_type": "HAS_INVOICE",
                "target_label": "Account",
                "direction": "INCOMING"
            })
            logger.debug(f"      ✅ Invoice {invoice_id} → CRM Account {crm_account_id}")
        else:
            # Customer exists in Books but not synced to CRM
            logger.warning(
                f"      ⚠️ Invoice {invoice_id}: Books Customer '{customer_name}' (ID: {customer_id}) "
                "has no CRM Account mapping. Invoice will not be linked to Account."
            )
            # Store unmapped info for debugging
            properties["unmapped_customer_id"] = customer_id
            properties["unmapped_reason"] = "no_crm_mapping"
    elif customer_id and not customer_mapping:
        # No mapping provided at all
        logger.warning(
            f"      ⚠️ Invoice {invoice_id}: No customer mapping provided. "
            "Invoice will not be linked to Account."
        )
        properties["unmapped_customer_id"] = customer_id
        properties["unmapped_reason"] = "no_mapping_provided"
    else:
        # No customer_id in invoice
        logger.warning(
            f"      ⚠️ Invoice {invoice_id}: Missing customer_id. "
            "Invoice will not be linked to Account."
        )
        properties["unmapped_reason"] = "missing_customer_id"
    
    return {
        "source_id": f"zoho_books_invoice_{invoice_id}",
        "label": label,
        "properties": properties,
        "relations": relations
    }



