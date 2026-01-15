"""
Query Building and Live Facts Retrieval for Twenty CRM.

Handles search_live_facts queries for Opportunities, Tasks, Notes, etc.
"""

import logging
from typing import Any, Dict, List, Optional

from app.integrations.twenty.client import TwentyClient, TwentyAPIError

logger = logging.getLogger(__name__)


def format_currency(amount_micros: Optional[int], currency: str = "EUR") -> str:
    """
    Format micros amount to currency string.

    Args:
        amount_micros: Amount in micros (1/1,000,000)
        currency: Currency code

    Returns:
        Formatted currency string (e.g., "EUR 1.234,56")
    """
    if not amount_micros:
        return f"{currency} 0,00"

    amount = amount_micros / 1_000_000

    # German number format
    integer_part = int(amount)
    decimal_part = int((amount - integer_part) * 100)

    # Format with thousands separator
    int_str = f"{integer_part:,}".replace(",", ".")

    return f"{currency} {int_str},{decimal_part:02d}"


async def query_opportunities(client: TwentyClient, entity_id: str, entity_type: str) -> str:
    """
    Queries Opportunities for an entity (Person or Company).

    Args:
        client: TwentyClient instance
        entity_id: Twenty record UUID
        entity_type: "person" or "company"

    Returns:
        Markdown formatted section
    """
    try:
        # Build filter based on entity type
        if entity_type == "company":
            filter_param = f"filter[companyId][eq]={entity_id}"
        elif entity_type == "person":
            filter_param = f"filter[pointOfContactId][eq]={entity_id}"
        else:
            return ""

        response = await client.get(
            "/rest/opportunities",
            params={filter_param.split("=")[0]: filter_param.split("=")[1], "limit": 20},
        )

        opportunities = response.get("data", {}).get("opportunities", [])

        if not opportunities:
            return "### Opportunities\n*Keine Opportunities gefunden*\n"

        section = ["### Opportunities\n"]

        total_value = 0
        open_count = 0

        for opp in opportunities:
            name = opp.get("name", "N/A")
            stage = opp.get("stage", "N/A")
            close_date = opp.get("closeDate", "")[:10] if opp.get("closeDate") else "N/A"

            amount = opp.get("amount", {})
            amount_micros = amount.get("amountMicros", 0)
            currency = amount.get("currencyCode", "EUR")

            if amount_micros:
                total_value += amount_micros

            if stage not in ["WON", "LOST"]:
                open_count += 1

            amount_str = format_currency(amount_micros, currency)
            section.append(f"- **{name}**: {amount_str} | Stage: {stage} | Close: {close_date}")

        # Summary
        total_str = format_currency(total_value, "EUR")
        section.insert(1, f"*{open_count} offene Opportunities, Gesamtwert: {total_str}*\n")

        return "\n".join(section)

    except Exception as e:
        logger.warning(f"Opportunities query failed: {e}")
        return "### Opportunities\n*(Query fehlgeschlagen)*\n"


async def query_tasks(client: TwentyClient, entity_id: str, entity_type: str) -> str:
    """
    Queries Tasks for an entity.

    Tasks are linked via taskTargets, so we need to check the targets.

    Args:
        client: TwentyClient instance
        entity_id: Twenty record UUID
        entity_type: "person", "company", or "opportunity"

    Returns:
        Markdown formatted section
    """
    try:
        # Fetch all tasks and filter by target
        # Note: Twenty API might not support direct filtering by target
        response = await client.get("/rest/tasks", params={"limit": 100})
        all_tasks = response.get("data", {}).get("tasks", [])

        # Filter tasks by target
        matching_tasks = []
        for task in all_tasks:
            targets = task.get("taskTargets", [])
            for target in targets:
                if entity_type == "person" and target.get("personId") == entity_id:
                    matching_tasks.append(task)
                    break
                elif entity_type == "company" and target.get("companyId") == entity_id:
                    matching_tasks.append(task)
                    break
                elif entity_type == "opportunity" and target.get("opportunityId") == entity_id:
                    matching_tasks.append(task)
                    break

        if not matching_tasks:
            return "### Tasks\n*Keine Tasks gefunden*\n"

        section = ["### Tasks\n"]

        for task in matching_tasks[:10]:  # Limit to 10
            title = task.get("title", "N/A")
            status = task.get("status", "N/A")
            due_at = task.get("dueAt", "")[:10] if task.get("dueAt") else "N/A"

            status_emoji = "" if status == "TODO" else "" if status == "DONE" else ""
            section.append(f"- {status_emoji} **{title}** | Status: {status} | Due: {due_at}")

        return "\n".join(section)

    except Exception as e:
        logger.warning(f"Tasks query failed: {e}")
        return "### Tasks\n*(Query fehlgeschlagen)*\n"


async def query_notes(client: TwentyClient, entity_id: str, entity_type: str) -> str:
    """
    Queries Notes for an entity.

    Notes are linked via noteTargets.

    Args:
        client: TwentyClient instance
        entity_id: Twenty record UUID
        entity_type: "person", "company", or "opportunity"

    Returns:
        Markdown formatted section
    """
    try:
        response = await client.get("/rest/notes", params={"limit": 100})
        all_notes = response.get("data", {}).get("notes", [])

        # Filter notes by target
        matching_notes = []
        for note in all_notes:
            targets = note.get("noteTargets", [])
            for target in targets:
                if entity_type == "person" and target.get("personId") == entity_id:
                    matching_notes.append(note)
                    break
                elif entity_type == "company" and target.get("companyId") == entity_id:
                    matching_notes.append(note)
                    break
                elif entity_type == "opportunity" and target.get("opportunityId") == entity_id:
                    matching_notes.append(note)
                    break

        if not matching_notes:
            return "### Notes\n*Keine Notizen gefunden*\n"

        section = ["### Notes\n"]

        for note in matching_notes[:5]:  # Limit to 5
            title = note.get("title", "Untitled")
            body = note.get("bodyV2", {}).get("markdown", "")
            created = note.get("createdAt", "")[:10] if note.get("createdAt") else ""

            # Truncate body
            if len(body) > 200:
                body = body[:200] + "..."

            section.append(f"#### {title} ({created})")
            if body:
                section.append(f"{body}\n")

        return "\n".join(section)

    except Exception as e:
        logger.warning(f"Notes query failed: {e}")
        return "### Notes\n*(Query fehlgeschlagen)*\n"


async def query_related_people(client: TwentyClient, company_id: str) -> str:
    """
    Queries People related to a Company.

    Args:
        client: TwentyClient instance
        company_id: Company UUID

    Returns:
        Markdown formatted section
    """
    try:
        response = await client.get(
            "/rest/people",
            params={"filter[companyId][eq]": company_id, "limit": 20},
        )

        people = response.get("data", {}).get("people", [])

        if not people:
            return "### Kontakte\n*Keine Kontakte gefunden*\n"

        section = ["### Kontakte\n"]

        for person in people:
            name = person.get("name", {})
            first_name = name.get("firstName", "")
            last_name = name.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip() or "N/A"

            job_title = person.get("jobTitle", "")
            email = person.get("emails", {}).get("primaryEmail", "")

            line = f"- **{full_name}**"
            if job_title:
                line += f" ({job_title})"
            if email:
                line += f" - {email}"

            section.append(line)

        return "\n".join(section)

    except Exception as e:
        logger.warning(f"Related people query failed: {e}")
        return "### Kontakte\n*(Query fehlgeschlagen)*\n"


async def get_entity_details(
    client: TwentyClient,
    entity_id: str,
    entity_type: str,
) -> Dict[str, Any]:
    """
    Fetches detailed entity information.

    Args:
        client: TwentyClient instance
        entity_id: Entity UUID
        entity_type: "person", "company", or "opportunity"

    Returns:
        Entity data dict
    """
    endpoint_map = {
        "person": "/rest/people",
        "company": "/rest/companies",
        "opportunity": "/rest/opportunities",
    }

    endpoint = endpoint_map.get(entity_type)
    if not endpoint:
        return {}

    try:
        response = await client.get(f"{endpoint}/{entity_id}")

        # Extract singular key
        singular_map = {
            "person": "person",
            "company": "company",
            "opportunity": "opportunity",
        }

        return response.get("data", {}).get(singular_map[entity_type], {})

    except Exception as e:
        logger.warning(f"Entity details query failed: {e}")
        return {}


def detect_entity_type(entity_id: str, entity_data: Dict[str, Any]) -> str:
    """
    Detects entity type from data structure.

    Args:
        entity_id: Entity UUID
        entity_data: Entity data dict

    Returns:
        Entity type string
    """
    # Check for type-specific fields
    if "name" in entity_data and isinstance(entity_data.get("name"), dict):
        if "firstName" in entity_data["name"]:
            return "person"

    if "employees" in entity_data or "domainName" in entity_data:
        return "company"

    if "stage" in entity_data or "closeDate" in entity_data:
        return "opportunity"

    return "unknown"


async def search_live_facts(
    client: TwentyClient,
    entity_id: str,
    query_context: str,
) -> str:
    """
    Main function to retrieve live facts about a Twenty entity.

    Args:
        client: TwentyClient instance
        entity_id: Entity ID (with "twenty_" prefix)
        query_context: Context about what information is needed

    Returns:
        Formatted Markdown string with entity facts
    """
    # Remove prefix
    if entity_id.startswith("twenty_"):
        twenty_id = entity_id[7:]  # Remove "twenty_"
    else:
        twenty_id = entity_id

    logger.info(f"Searching live facts for entity: {twenty_id}")

    # Try to fetch entity from different endpoints
    entity_data = None
    entity_type = None

    for try_type in ["company", "person", "opportunity"]:
        data = await get_entity_details(client, twenty_id, try_type)
        if data:
            entity_data = data
            entity_type = try_type
            break

    if not entity_data:
        return f"*Entity {entity_id} nicht gefunden*"

    # Build response sections
    sections = []

    # Header with entity info
    if entity_type == "person":
        name = entity_data.get("name", {})
        full_name = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
        job_title = entity_data.get("jobTitle", "")
        email = entity_data.get("emails", {}).get("primaryEmail", "")

        header = f"## {full_name}"
        if job_title:
            header += f" - {job_title}"
        sections.append(header)

        if email:
            sections.append(f"*Email: {email}*\n")

    elif entity_type == "company":
        name = entity_data.get("name", "Unknown Company")
        employees = entity_data.get("employees", 0)
        city = entity_data.get("address", {}).get("addressCity", "")

        header = f"## {name}"
        sections.append(header)

        meta = []
        if employees:
            meta.append(f"{employees} Mitarbeiter")
        if city:
            meta.append(city)
        if meta:
            sections.append(f"*{', '.join(meta)}*\n")

    elif entity_type == "opportunity":
        name = entity_data.get("name", "Unknown Opportunity")
        stage = entity_data.get("stage", "")
        amount = entity_data.get("amount", {})
        amount_str = format_currency(
            amount.get("amountMicros"),
            amount.get("currencyCode", "EUR"),
        )

        header = f"## {name}"
        sections.append(header)
        sections.append(f"*Stage: {stage} | Wert: {amount_str}*\n")

    # Add related data sections
    if entity_type == "company":
        sections.append(await query_related_people(client, twenty_id))
        sections.append(await query_opportunities(client, twenty_id, "company"))

    elif entity_type == "person":
        sections.append(await query_opportunities(client, twenty_id, "person"))

    # Add Tasks and Notes for all entity types
    sections.append(await query_tasks(client, twenty_id, entity_type))
    sections.append(await query_notes(client, twenty_id, entity_type))

    return "\n\n".join(filter(None, sections))
