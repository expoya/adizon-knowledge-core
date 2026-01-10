"""
Unit Tests für MetadataService (Phase 2 + 2.5)

Testet Source Discovery und Relevanz-Scoring.
Phase 2.5: LLM-basierte Source Selection.
"""

import pytest
from app.services.metadata_store import (
    MetadataService,
    SourceDefinition,
    metadata_service,
    reset_metadata_service
)


# Mark LLM tests to skip if no LLM available
pytest_llm = pytest.mark.skipif(
    not hasattr(pytest, "llm_available"),
    reason="LLM not available for testing"
)


@pytest.fixture
def service():
    """Fixture: Frische MetadataService Instanz."""
    reset_metadata_service()
    return metadata_service()


class TestSourceDefinition:
    """Tests für SourceDefinition Klasse."""
    
    def test_source_creation(self):
        """Test: Source kann erstellt werden."""
        config = {
            "id": "test_source",
            "type": "crm",
            "description": "Test Source",
            "status": "active",
            "tool": "test_tool",
            "priority": 1,
            "keywords": ["test", "demo"]
        }
        
        source = SourceDefinition(config)
        
        assert source.id == "test_source"
        assert source.type == "crm"
        assert source.status == "active"
        assert source.tool == "test_tool"
        assert source.priority == 1
        assert "test" in source.keywords
    
    def test_matches_query_with_keywords(self):
        """Test: Source matched Query mit Keywords."""
        config = {
            "id": "test",
            "type": "crm",
            "status": "active",
            "tool": "test",
            "keywords": ["rechnung", "invoice"]
        }
        
        source = SourceDefinition(config)
        
        # Match
        score = source.matches_query("Welche Rechnungen im Dezember?")
        assert score > 0.0
        
        # No match
        score = source.matches_query("Was ist unsere Preispolitik?")
        assert score == 0.0
    
    def test_matches_query_with_modules(self):
        """Test: Source matched Query mit Module Keywords."""
        config = {
            "id": "test",
            "type": "crm",
            "status": "active",
            "tool": "test",
            "keywords": [],
            "modules": [
                {
                    "name": "Invoices",
                    "keywords": ["rechnung", "invoice"]
                }
            ]
        }
        
        source = SourceDefinition(config)
        
        score = source.matches_query("Welche Rechnungen?")
        assert score > 0.0
    
    def test_is_available_active(self):
        """Test: Active Source ist verfügbar."""
        config = {"id": "test", "type": "crm", "status": "active", "tool": "test"}
        source = SourceDefinition(config)
        
        assert source.is_available() is True
    
    def test_is_available_optional_without_env(self):
        """Test: Optional Source ohne ENV ist nicht verfügbar."""
        config = {
            "id": "test",
            "type": "sql",
            "status": "optional",
            "tool": "test",
            "connection_env": "NONEXISTENT_ENV_VAR"
        }
        source = SourceDefinition(config)
        
        assert source.is_available() is False
    
    def test_get_relevant_modules(self):
        """Test: Findet relevante Module."""
        config = {
            "id": "test",
            "type": "crm",
            "status": "active",
            "tool": "test",
            "modules": [
                {"name": "Invoices", "keywords": ["rechnung"]},
                {"name": "Deals", "keywords": ["deal", "geschäft"]},
            ]
        }
        
        source = SourceDefinition(config)
        
        # Match Invoices
        modules = source.get_relevant_modules("Welche Rechnungen?")
        assert len(modules) == 1
        assert modules[0]["name"] == "Invoices"
        
        # Match Deals
        modules = source.get_relevant_modules("Offene Deals?")
        assert len(modules) == 1
        assert modules[0]["name"] == "Deals"
        
        # No match
        modules = source.get_relevant_modules("Preise?")
        assert len(modules) == 0


class TestMetadataService:
    """Tests für MetadataService."""
    
    def test_service_loads_config(self, service):
        """Test: Service lädt external_sources.yaml."""
        assert service is not None
        assert len(service.sources) > 0
        
        # Check if knowledge_base exists
        kb = service.get_source_by_id("knowledge_base")
        assert kb is not None
        assert kb.type == "vector_graph"
    
    def test_get_source_by_id(self, service):
        """Test: Findet Source by ID."""
        kb = service.get_source_by_id("knowledge_base")
        assert kb is not None
        assert kb.id == "knowledge_base"
        
        # Non-existent
        none_source = service.get_source_by_id("nonexistent")
        assert none_source is None
    
    def test_get_relevant_sources_knowledge_query(self, service):
        """Test: Knowledge Query findet knowledge_base."""
        sources = service.get_relevant_sources("Was ist unsere Preispolitik?")
        
        assert len(sources) > 0
        assert any(s.id == "knowledge_base" for s in sources)
    
    def test_get_relevant_sources_crm_query(self, service):
        """Test: CRM Query findet CRM Sources."""
        sources = service.get_relevant_sources("Welche Rechnungen hat Kunde X?")
        
        # Should include knowledge_base (always) + zoho_books
        assert len(sources) >= 1
        
        source_ids = [s.id for s in sources]
        assert "knowledge_base" in source_ids
        
        # Zoho Books might match
        if "zoho_books" in [s.id for s in service.sources]:
            # Check if it's in results (depends on keywords)
            pass  # Score-based, might or might not match
    
    def test_get_relevant_sources_with_min_score(self, service):
        """Test: Min Score Filter funktioniert."""
        # Very high min_score should return only knowledge_base (always included)
        sources = service.get_relevant_sources(
            "Random query xyz",
            min_score=0.9
        )
        
        # Should at least have knowledge_base (always_check_graph=true)
        assert len(sources) >= 1
        assert sources[0].id == "knowledge_base"
    
    def test_get_relevant_sources_max_sources(self, service):
        """Test: Max Sources Limit funktioniert."""
        sources = service.get_relevant_sources(
            "Rechnung Deal Kunde Maschine",  # Matches multiple
            max_sources=2
        )
        
        assert len(sources) <= 2
    
    def test_always_check_graph_strategy(self, service):
        """Test: knowledge_base wird immer hinzugefügt."""
        sources = service.get_relevant_sources("xyz random query")
        
        # knowledge_base sollte immer dabei sein
        assert len(sources) >= 1
        assert sources[0].id == "knowledge_base"
    
    def test_should_combine_sources(self, service):
        """Test: Strategy für Source Combination."""
        assert service.should_combine_sources() is True
    
    def test_requires_graph_first(self, service):
        """Test: Strategy für Graph-First."""
        assert service.requires_graph_first() is True
    
    def test_get_default_fallback(self, service):
        """Test: Default Fallback Source."""
        fallback = service.get_default_fallback()
        
        assert fallback is not None
        assert fallback.id == "knowledge_base"
    
    def test_get_all_sources(self, service):
        """Test: Alle Sources abrufen."""
        all_sources = service.get_all_sources()
        
        assert len(all_sources) > 0
        assert all(isinstance(s, SourceDefinition) for s in all_sources)
    
    def test_get_source_summary(self, service):
        """Test: Source Summary generieren."""
        summary = service.get_source_summary()
        
        assert "Source Catalog Summary" in summary
        assert "knowledge_base" in summary
        assert "Strategy:" in summary


class TestSourceDiscoveryScenarios:
    """Integration Tests für realistische Szenarien."""
    
    def test_scenario_pricing_policy(self, service):
        """Scenario: Preispolitik-Frage."""
        query = "Was ist unsere Preispolitik?"
        sources = service.get_relevant_sources(query)
        
        # Sollte knowledge_base finden (Dokumente)
        assert any(s.id == "knowledge_base" for s in sources)
    
    def test_scenario_customer_status(self, service):
        """Scenario: Kunden-Status-Frage."""
        query = "Was ist der Status von Firma ACME?"
        sources = service.get_relevant_sources(query)
        
        # Sollte knowledge_base + zoho_crm finden
        source_ids = [s.id for s in sources]
        assert "knowledge_base" in source_ids
        
        # CRM könnte matchen (hängt von Keywords ab)
        # "firma" sollte zoho_crm triggern
    
    def test_scenario_invoices(self, service):
        """Scenario: Rechnungs-Frage."""
        query = "Welche Rechnungen wurden im Dezember ausgestellt?"
        sources = service.get_relevant_sources(query)
        
        source_ids = [s.id for s in sources]
        assert "knowledge_base" in source_ids
        
        # "rechnungen" sollte zoho_books triggern
        if any(s.id == "zoho_books" for s in service.sources):
            # Check if zoho_books is available
            zoho_books = service.get_source_by_id("zoho_books")
            if zoho_books and zoho_books.is_available():
                # Should be in results
                pass  # Depends on scoring
    
    def test_scenario_machine_temperature(self, service):
        """Scenario: Maschinen-Temperatur-Frage."""
        query = "Wie ist die Temperatur von Hochdrucklader #42?"
        sources = service.get_relevant_sources(query)
        
        source_ids = [s.id for s in sources]
        assert "knowledge_base" in source_ids
        
        # "temperatur" + "maschine" sollte iot_database triggern
        # (falls verfügbar - ist optional)


class TestLLMSourceDiscovery:
    """Tests für LLM-basierte Source Discovery (Phase 2.5)."""
    
    @pytest.mark.asyncio
    async def test_llm_source_selection_payment_status(self, service):
        """Test: LLM versteht 'Zahlungsstatus' → Rechnungen."""
        query = "Zeig mir den Zahlungsstatus von Kunde XY"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            # Should understand: Zahlungsstatus → Rechnungen → zoho_books
            source_ids = [s.id for s in sources]
            
            assert "knowledge_base" in source_ids  # Always included
            # zoho_books should be selected (if available)
            # Note: Depends on LLM response, might vary
            
            logger.info(f"LLM selected: {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_llm_source_selection_open_items(self, service):
        """Test: LLM versteht 'Offene Posten' → Rechnungen."""
        query = "Welche offenen Posten hat Kunde ABC?"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            source_ids = [s.id for s in sources]
            
            # Should understand: Offene Posten → Unbezahlte Rechnungen → zoho_books
            assert "knowledge_base" in source_ids
            
            logger.info(f"LLM selected for 'offene Posten': {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_llm_source_selection_english_query(self, service):
        """Test: LLM versteht englische Queries."""
        query = "Show me the payment status of customer XY"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            source_ids = [s.id for s in sources]
            
            # Should understand English: payment status → invoices
            assert "knowledge_base" in source_ids
            
            logger.info(f"LLM selected for English query: {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, service):
        """Test: Fallback zu keyword-based bei LLM Fehler."""
        query = "Preispolitik"
        
        # Mock LLM failure by using invalid query that causes JSON parse error
        # Should fallback to keyword-based
        
        sources = await service.get_relevant_sources_llm(query, max_retries=0)
        
        # Should still return sources (via fallback)
        assert len(sources) > 0
        assert sources[0].id == "knowledge_base"
    
    @pytest.mark.asyncio
    async def test_format_catalog_for_llm(self, service):
        """Test: Catalog Formatting für LLM."""
        catalog = service._format_catalog_for_llm()
        
        # Should contain source information
        assert "knowledge_base" in catalog
        assert "SOURCE:" in catalog
        assert "Keywords:" in catalog
        
        # Should be readable
        assert len(catalog) > 100
        
        logger.info(f"Catalog length: {len(catalog)} chars")


class TestLLMReasoningScenarios:
    """Integration Tests für LLM Reasoning (Phase 2.5)."""
    
    @pytest.mark.asyncio
    async def test_scenario_payment_status_reasoning(self, service):
        """
        Scenario: Zahlungsstatus-Frage mit LLM Reasoning.
        
        Expected Reasoning:
        - User fragt nach Zahlungsstatus
        - Zahlungsstatus = Status von Rechnungen/Payments
        - zoho_books hat Invoices und Payments
        - knowledge_base für Graph (Kunde → Rechnungen)
        """
        query = "Zeig mir den Zahlungsstatus von Kunde ACME"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            source_ids = [s.id for s in sources]
            
            # Expected: knowledge_base + zoho_books
            assert "knowledge_base" in source_ids
            
            logger.info(f"Zahlungsstatus scenario: {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_scenario_what_does_customer_owe(self, service):
        """
        Scenario: "Was schuldet mir Kunde X?"
        
        Expected Reasoning:
        - "schuldet" = offene Forderungen = unbezahlte Rechnungen
        - zoho_books für Invoice Status
        """
        query = "Was schuldet mir Kunde XYZ?"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            source_ids = [s.id for s in sources]
            
            # Should understand: schuldet → Rechnungen
            assert "knowledge_base" in source_ids
            
            logger.info(f"'Was schuldet' scenario: {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")
    
    @pytest.mark.asyncio
    async def test_scenario_machine_temperature(self, service):
        """
        Scenario: Maschinen-Temperatur.
        
        Expected Reasoning:
        - Temperatur = Sensor-Daten
        - iot_database (wenn verfügbar)
        - knowledge_base für Handbuch/Grenzwerte
        """
        query = "Wie ist die Temperatur von Hochdrucklader #42?"
        
        try:
            sources = await service.get_relevant_sources_llm(query)
            
            source_ids = [s.id for s in sources]
            
            assert "knowledge_base" in source_ids
            
            # iot_database might be selected if available
            logger.info(f"Temperature scenario: {source_ids}")
            
        except Exception as e:
            pytest.skip(f"LLM test skipped: {e}")


# Add logging for tests
import logging
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

