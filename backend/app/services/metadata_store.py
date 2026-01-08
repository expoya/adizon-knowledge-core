"""
MetadataService für externe Datenquellen.
Lädt und verwaltet Metadaten aus external_sources.yaml.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml


class MetadataService:
    """
    Service zum Verwalten von Metadaten externer Datenquellen.
    Lädt Konfiguration aus external_sources.yaml und bietet
    Methoden zur intelligenten Tabellensuche.
    """

    def __init__(self):
        """Initialisiert den MetadataService und lädt die Konfiguration."""
        self.sources: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        """Lädt die external_sources.yaml Konfigurationsdatei."""
        config_path = Path(__file__).parent.parent / "config" / "external_sources.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Konfigurationsdatei nicht gefunden: {config_path}"
            )
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            self.sources = config.get("sources", [])

    def get_relevant_tables(self, query: str) -> str:
        """
        Findet relevante Tabellen basierend auf der Query.
        
        Primitive Implementierung: Prüft, ob Wörter aus der Query
        in den Beschreibungen der Tabellen vorkommen.
        
        Args:
            query: Die Suchanfrage des Benutzers
            
        Returns:
            Ein formatierter String mit dem Schema der gefundenen Tabellen
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        relevant_tables = []
        
        for source in self.sources:
            source_id = source.get("id", "unknown")
            source_type = source.get("type", "unknown")
            source_desc = source.get("description", "")
            tables = source.get("tables", [])
            
            for table in tables:
                table_name = table.get("name", "")
                table_desc = table.get("description", "")
                
                # Primitive Prüfung: Gibt es Überschneidungen?
                desc_lower = (source_desc + " " + table_desc).lower()
                
                # Prüfe ob einzelne Wörter aus der Query vorkommen
                if any(word in desc_lower for word in query_words if len(word) > 3):
                    relevant_tables.append({
                        "source": source_id,
                        "type": source_type,
                        "table": table_name,
                        "description": table_desc,
                        "connection_env": source.get("connection_env", "")
                    })
        
        # Formatiere als String für LLM Prompt
        if not relevant_tables:
            return "Keine relevanten Tabellen gefunden."
        
        result_lines = ["Relevante externe Datenquellen:\n"]
        
        for idx, table_info in enumerate(relevant_tables, 1):
            result_lines.append(
                f"{idx}. Quelle: {table_info['source']} (Typ: {table_info['type']})\n"
                f"   Tabelle: {table_info['table']}\n"
                f"   Beschreibung: {table_info['description']}\n"
                f"   Connection: {table_info['connection_env']}\n"
            )
        
        return "".join(result_lines)

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Gibt alle konfigurierten Datenquellen zurück.
        
        Returns:
            Liste aller Datenquellen mit ihren Metadaten
        """
        return self.sources

    def get_source_by_id(self, source_id: str) -> Dict[str, Any] | None:
        """
        Findet eine Datenquelle anhand ihrer ID.
        
        Args:
            source_id: Die ID der Datenquelle
            
        Returns:
            Die Datenquelle oder None, wenn nicht gefunden
        """
        for source in self.sources:
            if source.get("id") == source_id:
                return source
        return None


@lru_cache
def metadata_service() -> MetadataService:
    """
    Singleton-Funktion für den MetadataService.
    
    Returns:
        Gecachte Instanz des MetadataService
    """
    return MetadataService()

