"""
Zoho CRM Schema Mapping Configuration.

Defines the mapping between Zoho CRM modules and our Knowledge Graph schema.
"""

from typing import Any, Dict

# Complete schema mapping for all Zoho CRM modules
SCHEMA_MAPPING: Dict[str, Dict[str, Any]] = {
    "Users": {
        "label": "User",
        "module_name": "Users",
        "fields": ["id", "full_name", "email"],
        "relations": [],
        "use_api": True  # Special: Use /users API instead of COQL
    },
    "Leads": {
        "label": "Lead",
        "module_name": "Leads",
        "fields": ["id", "Last_Name", "First_Name", "Company", "Email", "Owner", "Converted_Account", "Created_Time"],
        "relations": [
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"},
            {"field": "Converted_Account", "edge": "IS_CONVERTED_FROM", "target_label": "Account", "direction": "INCOMING"}
        ]
    },
    "Accounts": {
        "label": "Account",
        "module_name": "Accounts",
        "fields": ["id", "Account_Name", "Owner", "Parent_Account"],
        "relations": [
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"},
            {"field": "Parent_Account", "edge": "PARENT_OF", "target_label": "Account", "direction": "INCOMING"}
        ]
    },
    "Contacts": {
        "label": "Contact",
        "module_name": "Contacts",
        "fields": ["id", "Last_Name", "First_Name", "Email", "Account_Name", "Owner"],
        "relations": [
            {"field": "Account_Name", "edge": "WORKS_AT", "target_label": "Account", "direction": "OUTGOING"},
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
        ]
    },
    "Deals": {
        "label": "Deal",
        "module_name": "Deals",
        "fields": ["id", "Deal_Name", "Account_Name", "Contact_Name", "Stage", "Amount", "Owner", "Closing_Date"],
        "relations": [
            {"field": "Account_Name", "edge": "HAS_DEAL", "target_label": "Account", "direction": "INCOMING"},
            {"field": "Contact_Name", "edge": "ASSOCIATED_WITH", "target_label": "Contact", "direction": "OUTGOING"},
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
        ]
    },
    "Tasks": {
        "label": "Task",
        "module_name": "Tasks",
        "fields": ["id", "Subject", "Status", "Who_Id", "What_Id", "Owner"],
        "relations": [
            {"field": "Who_Id", "edge": "HAS_TASK", "target_label": "CRMEntity", "direction": "INCOMING"},
            {"field": "What_Id", "edge": "HAS_TASK", "target_label": "CRMEntity", "direction": "INCOMING"},
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
        ]
    },
    "Notes": {
        "label": "Note",
        "module_name": "Notes",
        "fields": ["id", "Note_Title", "Note_Content", "Parent_Id", "Owner"],
        "relations": [
            {"field": "Parent_Id", "edge": "HAS_NOTE", "target_label": "CRMEntity", "direction": "INCOMING"},
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
        ]
    },
    "Events": {
        "label": "CalendlyEvent",
        "module_name": "calendlyforzohocrm__Calendly_Events",
        "fields": ["id", "Name", "calendlyforzohocrm__Lead", "calendlyforzohocrm__Contact", "Verkn_pfter_Account", "calendlyforzohocrm__Status", "calendlyforzohocrm__Start_Time"],
        "relations": [
            {"field": "calendlyforzohocrm__Lead", "edge": "HAS_EVENT", "target_label": "Lead", "direction": "INCOMING"},
            {"field": "calendlyforzohocrm__Contact", "edge": "HAS_EVENT", "target_label": "Contact", "direction": "INCOMING"},
            {"field": "Verkn_pfter_Account", "edge": "HAS_EVENT", "target_label": "Account", "direction": "INCOMING"}
        ]
    },
    "Einwaende": {
        "label": "Einwand",
        "module_name": "Einw_nde",
        "fields": ["id", "Name", "Lead", "Einwand_Kategorie", "Gespr_chszeitpunkt", "Einwandbeschreibung"],
        "relations": [
            {"field": "Lead", "edge": "HAS_OBJECTION", "target_label": "Lead", "direction": "INCOMING"}
        ]
    },
    "Attachments": {
        "label": "Attachment",
        "module_name": "Attachments",
        "fields": ["id", "File_Name", "Parent_Id"],
        "relations": [
            {"field": "Parent_Id", "edge": "HAS_DOCUMENTS", "target_label": "CRMEntity", "direction": "INCOMING"}
        ]
    },
    "Invoices": {
        "label": "Invoice",
        "module_name": "Invoices",
        "fields": ["id", "Subject", "Account_Name", "Grand_Total", "Status", "Invoice_Date"],
        "relations": [
            {"field": "Account_Name", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_rest_api": True  # Finance module uses REST API, not COQL
    },
    "Subscriptions": {
        "label": "Subscription",
        "module_name": "Subscriptions",
        "fields": ["id", "Name", "Account_Name", "Amount", "Status", "Start_Date"],
        "relations": [
            {"field": "Account_Name", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_rest_api": True  # Finance module uses REST API, not COQL
    },
    "Emails": {
        "label": "Email",
        "module_name": "Emails",
        "fields": ["id", "Subject", "from", "to", "Parent_Id", "Owner"],
        "relations": [
            {"field": "Parent_Id", "edge": "HAS_EMAIL", "target_label": "CRMEntity", "direction": "INCOMING"},
            {"field": "Owner", "edge": "HAS_OWNER", "target_label": "User", "direction": "OUTGOING"}
        ],
        "use_rest_api": True  # Emails use REST API, not COQL
    },
    
    # Zoho Books Modules (separate from CRM)
    "BooksInvoices": {
        "label": "Invoice",
        "module_name": "BooksInvoices",  # Logical name
        "fields": ["invoice_id", "invoice_number", "customer_name", "total", "status", "date"],
        "relations": [
            {"field": "customer_id", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_books_api": True  # Zoho Books API (/books/v3/invoices)
    },
    "BooksSubscriptions": {
        "label": "Subscription",
        "module_name": "BooksSubscriptions",  # Logical name
        "fields": ["subscription_id", "subscription_number", "customer_name", "amount", "status", "start_date"],
        "relations": [
            {"field": "customer_id", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_books_api": True  # Zoho Books/Billing API
    },
    
    # Aliases for alternative naming (module names vs friendly names)
    "Zoho_Books": {  # Alias for Invoices (old name)
        "label": "Invoice",
        "module_name": "Invoices",
        "fields": ["id", "Subject", "Account_Name", "Grand_Total", "Status", "Invoice_Date"],
        "relations": [
            {"field": "Account_Name", "edge": "HAS_INVOICE", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_rest_api": True
    },
    "Einw_nde": {  # Alias for Einwaende
        "label": "Einwand",
        "module_name": "Einw_nde",
        "fields": ["id", "Name", "Lead", "Einwand_Kategorie", "Gespr_chszeitpunkt", "Einwandbeschreibung"],
        "relations": [
            {"field": "Lead", "edge": "HAS_OBJECTION", "target_label": "Lead", "direction": "INCOMING"}
        ]
    },
    "calendlyforzohocrm__Calendly_Events": {  # Alias for Events (full module name)
        "label": "CalendlyEvent",
        "module_name": "calendlyforzohocrm__Calendly_Events",
        "fields": ["id", "Name", "calendlyforzohocrm__Lead", "calendlyforzohocrm__Contact", "Verkn_pfter_Account", "calendlyforzohocrm__Status", "calendlyforzohocrm__Start_Time"],
        "relations": [
            {"field": "calendlyforzohocrm__Lead", "edge": "HAS_EVENT", "target_label": "Lead", "direction": "INCOMING"},
            {"field": "calendlyforzohocrm__Contact", "edge": "HAS_EVENT", "target_label": "Contact", "direction": "INCOMING"},
            {"field": "Verkn_pfter_Account", "edge": "HAS_EVENT", "target_label": "Account", "direction": "INCOMING"}
        ]
    },
    "Subscriptions__s": {  # Alias for Subscriptions (old name)
        "label": "Subscription",
        "module_name": "Subscriptions",
        "fields": ["id", "Name", "Account_Name", "Amount", "Status", "Start_Date"],
        "relations": [
            {"field": "Account_Name", "edge": "HAS_SUBSCRIPTION", "target_label": "Account", "direction": "INCOMING"}
        ],
        "use_rest_api": True
    }
}


def get_schema_config(entity_type: str) -> Dict[str, Any]:
    """
    Get schema configuration for an entity type.
    
    Args:
        entity_type: Entity type name (e.g., "Accounts", "Leads")
        
    Returns:
        Schema configuration dict or raises KeyError if not found
    """
    return SCHEMA_MAPPING[entity_type]


def get_all_entity_types() -> list[str]:
    """
    Get list of all configured entity types (excluding aliases).
    
    Returns:
        List of entity type names (primary names only, no duplicates)
    """
    # Return only primary entity types, not aliases
    return [
        "Users",
        "Leads",
        "Accounts",
        "Contacts",
        "Deals",
        "Tasks",
        "Notes",
        "Events",           # calendlyforzohocrm__Calendly_Events
        "Einwaende",        # Einw_nde
        "Attachments",
        "Invoices",         # CRM Invoices (simple)
        # "Emails",         # DISABLED: Related Lists only (requires complex implementation)
        "BooksInvoices",    # Zoho Books Invoices (professional)
        "BooksSubscriptions",  # Zoho Books/Billing Subscriptions
    ]


def is_rest_api_module(entity_type: str) -> bool:
    """
    Check if an entity type uses REST API instead of COQL.
    
    Args:
        entity_type: Entity type name
        
    Returns:
        True if module uses REST API, False otherwise
    """
    config = get_schema_config(entity_type)
    return config.get("use_rest_api", False)


def is_special_api_module(entity_type: str) -> bool:
    """
    Check if an entity type uses special API endpoint (like Users).
    
    Args:
        entity_type: Entity type name
        
    Returns:
        True if module uses special API, False otherwise
    """
    config = get_schema_config(entity_type)
    return config.get("use_api", False)


def is_books_api_module(entity_type: str) -> bool:
    """
    Check if an entity type uses Zoho Books API.
    
    Args:
        entity_type: Entity type name
        
    Returns:
        True if module uses Books API, False otherwise
    """
    config = get_schema_config(entity_type)
    return config.get("use_books_api", False)

