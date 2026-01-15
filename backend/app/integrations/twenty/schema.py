"""
Twenty CRM Schema Mapping Configuration.

Defines the mapping between Twenty CRM objects and our Knowledge Graph schema.
"""

from typing import Any, Dict, List

# Complete schema mapping for Twenty CRM objects
SCHEMA_MAPPING: Dict[str, Dict[str, Any]] = {
    "people": {
        "label": "Contact",
        "endpoint": "/rest/people",
        "data_key": "people",
        "fields": {
            # Nested field paths -> flat property names
            "id": "id",
            "name.firstName": "first_name",
            "name.lastName": "last_name",
            "emails.primaryEmail": "email",
            "phones.primaryPhoneNumber": "phone",
            "phones.primaryPhoneCallingCode": "phone_calling_code",
            "jobTitle": "job_title",
            "city": "city",
            "companyId": "company_id",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        "relations": [
            {
                "field": "companyId",
                "edge": "WORKS_AT",
                "target_label": "Account",
                "direction": "OUTGOING",
            }
        ],
        "name_template": "{first_name} {last_name}",
    },
    "companies": {
        "label": "Account",
        "endpoint": "/rest/companies",
        "data_key": "companies",
        "fields": {
            "id": "id",
            "name": "name",
            "domainName.primaryLinkUrl": "website",
            "employees": "employees",
            "address.addressStreet1": "street",
            "address.addressCity": "city",
            "address.addressPostcode": "postcode",
            "address.addressCountry": "country",
            "annualRecurringRevenue.amountMicros": "annual_revenue_micros",
            "annualRecurringRevenue.currencyCode": "currency",
            "linkedinLink.primaryLinkUrl": "linkedin",
            "idealCustomerProfile": "is_icp",
            "accountOwnerId": "owner_id",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        "relations": [
            {
                "field": "accountOwnerId",
                "edge": "HAS_OWNER",
                "target_label": "User",
                "direction": "OUTGOING",
            }
        ],
        "name_template": "{name}",
    },
    "opportunities": {
        "label": "Deal",
        "endpoint": "/rest/opportunities",
        "data_key": "opportunities",
        "fields": {
            "id": "id",
            "name": "name",
            "amount.amountMicros": "amount_micros",
            "amount.currencyCode": "currency",
            "stage": "stage",
            "closeDate": "close_date",
            "companyId": "company_id",
            "pointOfContactId": "contact_id",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        "relations": [
            {
                "field": "companyId",
                "edge": "HAS_DEAL",
                "target_label": "Account",
                "direction": "INCOMING",
            },
            {
                "field": "pointOfContactId",
                "edge": "ASSOCIATED_WITH",
                "target_label": "Contact",
                "direction": "OUTGOING",
            },
        ],
        "name_template": "{name}",
    },
    "tasks": {
        "label": "Task",
        "endpoint": "/rest/tasks",
        "data_key": "tasks",
        "fields": {
            "id": "id",
            "title": "title",
            "bodyV2.markdown": "body",
            "status": "status",
            "dueAt": "due_at",
            "assigneeId": "assignee_id",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        "relations": [
            {
                "field": "assigneeId",
                "edge": "ASSIGNED_TO",
                "target_label": "User",
                "direction": "OUTGOING",
            }
        ],
        # taskTargets handled separately in processor
        "has_targets": True,
        "target_field": "taskTargets",
        "name_template": "{title}",
    },
    "notes": {
        "label": "Note",
        "endpoint": "/rest/notes",
        "data_key": "notes",
        "fields": {
            "id": "id",
            "title": "title",
            "bodyV2.markdown": "body",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        "relations": [],
        # noteTargets handled separately in processor
        "has_targets": True,
        "target_field": "noteTargets",
        "name_template": "{title}",
    },
}


def get_schema_config(entity_type: str) -> Dict[str, Any]:
    """
    Get schema configuration for an entity type.

    Args:
        entity_type: Entity type name (e.g., "people", "companies")

    Returns:
        Schema configuration dict

    Raises:
        KeyError: If entity type not found
    """
    return SCHEMA_MAPPING[entity_type]


def get_all_entity_types() -> List[str]:
    """
    Get list of all configured entity types.

    Returns:
        List of entity type names
    """
    return ["companies", "people", "opportunities", "tasks", "notes"]


def get_endpoint(entity_type: str) -> str:
    """
    Get REST API endpoint for an entity type.

    Args:
        entity_type: Entity type name

    Returns:
        API endpoint path
    """
    return SCHEMA_MAPPING[entity_type]["endpoint"]


def get_data_key(entity_type: str) -> str:
    """
    Get data key in API response for an entity type.

    Args:
        entity_type: Entity type name

    Returns:
        Data key (e.g., "people", "companies")
    """
    return SCHEMA_MAPPING[entity_type]["data_key"]


def get_graph_label(entity_type: str) -> str:
    """
    Get Knowledge Graph label for an entity type.

    Args:
        entity_type: Entity type name

    Returns:
        Graph node label (e.g., "Contact", "Account")
    """
    return SCHEMA_MAPPING[entity_type]["label"]


def has_targets(entity_type: str) -> bool:
    """
    Check if entity type has target relationships (Notes, Tasks).

    Args:
        entity_type: Entity type name

    Returns:
        True if entity has targets, False otherwise
    """
    return SCHEMA_MAPPING[entity_type].get("has_targets", False)
