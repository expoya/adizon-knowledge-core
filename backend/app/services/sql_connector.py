"""
SQL Connector Service für externe Datenquellen.
Verwaltet SQLAlchemy Engine Connections zu externen Datenbanken.
"""

import logging
import os
from functools import lru_cache
from typing import Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.services.metadata_store import metadata_service

logger = logging.getLogger(__name__)


class SQLConnectorService:
    """
    Service zum Verwalten von Datenbankverbindungen zu externen Quellen.
    Cached Engines für Performance.
    """

    def __init__(self):
        """Initialisiert den SQLConnectorService."""
        self._engines: Dict[str, Engine] = {}
        self._metadata_service = metadata_service()

    def get_engine(self, source_id: str) -> Engine:
        """
        Gibt eine SQLAlchemy Engine für die angeforderte Source ID zurück.
        
        Die Engine wird gecached, um nicht bei jedem Aufruf neu zu verbinden.
        Die Connection-URL wird aus der Environment Variable geladen, die in
        der external_sources.yaml für diese Source definiert ist.
        
        Args:
            source_id: Die ID der Datenquelle aus external_sources.yaml
            
        Returns:
            SQLAlchemy Engine für die Datenquelle
            
        Raises:
            ValueError: Wenn die Source nicht gefunden wurde
            RuntimeError: Wenn die Connection URL nicht gesetzt ist
        """
        # Prüfe ob Engine bereits gecached ist
        if source_id in self._engines:
            logger.debug(f"♻️ Using cached engine for source: {source_id}")
            return self._engines[source_id]
        
        # Hole Source Config aus Metadata Service
        source = self._metadata_service.get_source_by_id(source_id)
        if not source:
            raise ValueError(f"Source '{source_id}' nicht in external_sources.yaml gefunden")
        
        # Hole Connection URL aus Environment Variable
        connection_env = source.get("connection_env")
        if not connection_env:
            raise ValueError(f"Keine 'connection_env' für Source '{source_id}' definiert")
        
        connection_url = os.getenv(connection_env)
        if not connection_url:
            raise RuntimeError(
                f"Environment Variable '{connection_env}' für Source '{source_id}' nicht gesetzt. "
                f"Bitte setze sie in der .env Datei."
            )
        
        # Erstelle Engine
        logger.info(f"🔌 Creating new SQL engine for source: {source_id}")
        engine = create_engine(
            connection_url,
            pool_pre_ping=True,  # Test connection before using
            pool_size=5,
            max_overflow=10,
        )
        
        # Cache die Engine
        self._engines[source_id] = engine
        
        logger.info(f"✅ SQL engine created and cached for: {source_id}")
        return engine

    def get_all_source_ids(self) -> list[str]:
        """
        Gibt alle verfügbaren Source IDs zurück.
        
        Returns:
            Liste aller Source IDs aus der Konfiguration
        """
        return [source.get("id") for source in self._metadata_service.get_all_sources()]

    def close_all(self) -> None:
        """
        Schließt alle gecachten Datenbankverbindungen.
        Sollte beim Shutdown der Anwendung aufgerufen werden.
        """
        logger.info("🔌 Closing all SQL engines")
        for source_id, engine in self._engines.items():
            try:
                engine.dispose()
                logger.debug(f"✅ Closed engine for: {source_id}")
            except Exception as e:
                logger.error(f"❌ Error closing engine for {source_id}: {e}")
        
        self._engines.clear()


@lru_cache
def get_sql_connector_service() -> SQLConnectorService:
    """
    Singleton-Funktion für den SQLConnectorService.
    
    Returns:
        Gecachte Instanz des SQLConnectorService
    """
    return SQLConnectorService()

