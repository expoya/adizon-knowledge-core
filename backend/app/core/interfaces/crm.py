"""
Abstract CRM Provider Interface.
Defines the contract that all CRM integrations must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class CRMProvider(ABC):
    """
    Abstract base class for CRM system integrations.
    
    This interface ensures that all CRM providers implement a consistent API,
    allowing the core system to remain agnostic to the specific CRM being used.
    """

    @abstractmethod
    def check_connection(self) -> bool:
        """
        Verifies that the CRM API is reachable and credentials are valid.
        
        Returns:
            True if connection successful, False otherwise
            
        Example:
            >>> provider = get_crm_provider()
            >>> if provider.check_connection():
            ...     print("CRM connected!")
        """
        pass

    @abstractmethod
    def fetch_skeleton_data(self, entity_types: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches basic master data (ID, Name, Type) for graph import.
        
        This method retrieves lightweight records from the CRM that can be
        imported into the knowledge graph. It should return minimal data
        suitable for entity nodes.
        
        Args:
            entity_types: List of entity types to fetch (e.g., ["Contact", "Account", "Deal"])
            
        Returns:
            List of dictionaries with at minimum:
            - id: Unique identifier in the CRM
            - name: Display name
            - type: Entity type
            - Additional fields can be included
            
        Example:
            >>> provider.fetch_skeleton_data(["Contact", "Account"])
            [
                {"id": "123", "name": "John Doe", "type": "Contact", "email": "john@example.com"},
                {"id": "456", "name": "Acme Corp", "type": "Account", "industry": "Tech"}
            ]
        """
        pass

    @abstractmethod
    def search_live_facts(self, entity_id: str, query_context: str) -> str:
        """
        Retrieves live facts about a specific entity from the CRM.
        
        This method is called when the agent needs up-to-date information
        about an entity (e.g., current deal status, recent activities).
        
        Args:
            entity_id: The CRM identifier for the entity
            query_context: Context about what information is needed (for filtering)
            
        Returns:
            Formatted string with relevant facts, ready for LLM consumption
            
        Example:
            >>> provider.search_live_facts("123", "deals and revenue")
            '''
            Contact: John Doe (ID: 123)
            - Open Deals: 2 (Total Value: $50,000)
            - Last Activity: Meeting on 2026-01-05
            - Total Revenue: $150,000
            '''
        """
        pass

    @abstractmethod
    def execute_raw_query(self, query: str) -> Any:
        """
        Executes a raw query against the CRM API.
        
        This method is for advanced use cases, admin tools, or complex analyses.
        The query format depends on the specific CRM provider.
        
        Args:
            query: CRM-specific query (e.g., COQL for Zoho, SOQL for Salesforce)
            
        Returns:
            Raw query results (format depends on CRM)
            
        Example:
            >>> # Zoho COQL example
            >>> provider.execute_raw_query("SELECT First_Name, Last_Name FROM Contacts WHERE Email is not null")
            [{"First_Name": "John", "Last_Name": "Doe"}, ...]
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Returns the name of the CRM provider.
        
        Returns:
            Provider name (e.g., "Zoho CRM", "Salesforce", "HubSpot")
        """
        pass

    @abstractmethod
    def get_available_modules(self) -> List[str]:
        """
        Returns list of available CRM modules/entity types.
        
        Returns:
            List of module names supported by this CRM
            
        Example:
            >>> provider.get_available_modules()
            ["Contacts", "Accounts", "Deals", "Tasks", "Notes"]
        """
        pass

