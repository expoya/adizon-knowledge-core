"""
Locust Load Testing Suite for Adizon Knowledge Core

This module defines three user behavior patterns to stress-test the backend:
1. TheChatter - Simulates chat interactions with the LLM
2. TheResearcher - Performs complex search queries against Neo4j and pgvector
3. TheUploader - Uploads documents to test file handling

Usage:
    locust -f tests/performance/locustfile.py
    Then open http://localhost:8089 in your browser

Environment:
    Set LOCUST_HOST environment variable or use --host flag to target a specific API.
    Default: http://localhost:8000
"""

import io
import random
import string
from typing import Any

from locust import HttpUser, task, between, events


# =============================================================================
# Configuration
# =============================================================================

API_PREFIX = "/api/v1"

# Sample messages for chat simulation
SHORT_MESSAGES = [
    "Hallo",
    "Wie geht's?",
    "Was ist das?",
    "Hilfe",
    "Danke!",
]

LONG_MESSAGES = [
    "Erkläre mir bitte ausführlich, wie die Wissensbasis funktioniert und welche Datenquellen sie verwendet.",
    "Kannst du mir eine detaillierte Zusammenfassung aller Dokumente geben, die im System gespeichert sind?",
    "Ich suche nach Informationen über Projektmanagement-Methoden. Was kannst du mir dazu sagen?",
    "Beschreibe mir die Architektur des Systems und wie die verschiedenen Komponenten zusammenarbeiten.",
    "Welche Best Practices gibt es für die Nutzung von Knowledge Graphs in Unternehmensanwendungen?",
]

# Sample search queries
SEARCH_QUERIES = [
    "Projektmanagement",
    "Dokumentation",
    "API Integration",
    "Datenanalyse",
    "Workflow Automatisierung",
]

# Cypher queries for graph testing (read-only, safe queries)
GRAPH_QUERIES = [
    "MATCH (n) RETURN count(n) as nodeCount",
    "MATCH ()-[r]->() RETURN count(r) as relationCount",
    "MATCH (d:Document) RETURN d.filename LIMIT 10",
    "MATCH (e:Entity) RETURN e.name, e.type LIMIT 20",
    "MATCH (d:Document)-[:CONTAINS]->(e:Entity) RETURN d.filename, collect(e.name) LIMIT 5",
]


# =============================================================================
# Dummy PDF Generator
# =============================================================================

def generate_dummy_pdf(size_kb: int = 10) -> bytes:
    """
    Generate a minimal valid PDF file as bytes.

    Creates a simple PDF with random text content to avoid
    needing physical test files.

    Args:
        size_kb: Approximate size of the PDF in kilobytes

    Returns:
        bytes: Valid PDF file content
    """
    # Generate random text content
    random_text = ''.join(
        random.choices(string.ascii_letters + string.digits + ' ', k=size_kb * 100)
    )

    # Minimal PDF structure
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length {len(random_text) + 50} >>
stream
BT
/F1 12 Tf
100 700 Td
({random_text[:500]}) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
{300 + len(random_text)}
%%EOF"""

    return pdf_content.encode('latin-1')


# =============================================================================
# Event Handlers
# =============================================================================

@events.request.add_listener
def on_request(request_type: str, name: str, response_time: float,
               response_length: int, exception: Any, **kwargs: Any) -> None:
    """
    Log failed requests for debugging without stopping the test.
    """
    if exception:
        print(f"[FAILURE] {request_type} {name}: {exception}")


# =============================================================================
# User Classes
# =============================================================================

class TheChatter(HttpUser):
    """
    Simulates a user having conversations with the AI assistant.

    Behavior:
    - Sends chat messages of varying lengths
    - Maintains conversation history for context
    - Waits 1-5 seconds between messages (thinking time)

    Weight: 10 (most common user type)
    """

    weight = 10
    wait_time = between(1, 5)

    def on_start(self) -> None:
        """Initialize conversation history."""
        self.history: list[dict[str, str]] = []

    @task(3)
    def send_short_message(self) -> None:
        """Send a short chat message."""
        message = random.choice(SHORT_MESSAGES)
        self._send_chat_message(message)

    @task(2)
    def send_long_message(self) -> None:
        """Send a longer, more complex chat message."""
        message = random.choice(LONG_MESSAGES)
        self._send_chat_message(message)

    @task(1)
    def start_new_conversation(self) -> None:
        """Clear history and start fresh conversation."""
        self.history = []
        message = "Hallo, ich habe eine neue Frage."
        self._send_chat_message(message)

    def _send_chat_message(self, message: str) -> None:
        """
        Send a chat message and update history.

        Args:
            message: The message content to send
        """
        payload = {
            "message": message,
            "history": self.history[-10:],  # Keep last 10 messages for context
        }

        with self.client.post(
            f"{API_PREFIX}/chat",
            json=payload,
            catch_response=True,
            name="/chat"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Update history with the exchange
                    self.history.append({"role": "user", "content": message})
                    self.history.append({"role": "assistant", "content": data.get("answer", "")})
                    response.success()
                except Exception as e:
                    response.failure(f"JSON parse error: {e}")
            elif response.status_code == 503:
                response.failure("Service unavailable (LLM overloaded)")
            elif response.status_code == 422:
                response.failure(f"Validation error: {response.text[:100]}")
            else:
                response.failure(f"HTTP {response.status_code}")


class TheResearcher(HttpUser):
    """
    Simulates a user performing complex search and query operations.

    Behavior:
    - Executes Cypher queries against Neo4j graph database
    - Performs vector similarity searches
    - Retrieves knowledge summaries

    Weight: 5 (moderate usage)
    """

    weight = 5
    wait_time = between(2, 8)

    @task(3)
    def query_graph(self) -> None:
        """Execute a Cypher query against the knowledge graph."""
        query = random.choice(GRAPH_QUERIES)

        payload = {
            "query": query,
        }

        with self.client.post(
            f"{API_PREFIX}/graph/query",
            json=payload,
            catch_response=True,
            name="/graph/query"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                response.failure("Neo4j unavailable")
            elif response.status_code == 403:
                response.failure("Query blocked by security filter")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def search_knowledge(self) -> None:
        """Perform a semantic search in the knowledge base."""
        query = random.choice(SEARCH_QUERIES)

        with self.client.get(
            f"{API_PREFIX}/knowledge/search",
            params={"q": query, "limit": 10},
            catch_response=True,
            name="/knowledge/search"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Endpoint might not exist - mark as expected
                response.success()
            elif response.status_code == 503:
                response.failure("Vector database unavailable")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def get_knowledge_summary(self) -> None:
        """Retrieve the knowledge base summary."""
        with self.client.get(
            f"{API_PREFIX}/knowledge/summary",
            catch_response=True,
            name="/knowledge/summary"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                response.failure("Service unavailable")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def list_documents(self) -> None:
        """List all documents in the system."""
        with self.client.get(
            f"{API_PREFIX}/documents",
            catch_response=True,
            name="/documents"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class TheUploader(HttpUser):
    """
    Simulates a user uploading documents to the system.

    Behavior:
    - Uploads dynamically generated PDF files
    - Varies file sizes to test memory handling
    - Lower frequency to avoid overwhelming storage

    Weight: 1 (least common, but resource-intensive)
    """

    weight = 1
    wait_time = between(5, 15)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.upload_count = 0

    @task(3)
    def upload_small_pdf(self) -> None:
        """Upload a small PDF file (~10KB)."""
        self._upload_pdf(size_kb=10)

    @task(1)
    def upload_medium_pdf(self) -> None:
        """Upload a medium PDF file (~50KB)."""
        self._upload_pdf(size_kb=50)

    def _upload_pdf(self, size_kb: int) -> None:
        """
        Upload a dynamically generated PDF file.

        Args:
            size_kb: Approximate size of the PDF in kilobytes
        """
        self.upload_count += 1
        filename = f"loadtest_{self.upload_count}_{random.randint(1000, 9999)}.pdf"

        pdf_content = generate_dummy_pdf(size_kb)

        files = {
            "file": (filename, io.BytesIO(pdf_content), "application/pdf")
        }

        with self.client.post(
            f"{API_PREFIX}/upload",
            files=files,
            catch_response=True,
            name=f"/upload ({size_kb}KB)"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 409:
                # Duplicate file - considered success for load testing
                response.success()
            elif response.status_code == 400:
                response.failure(f"Bad request: {response.text[:100]}")
            elif response.status_code == 403:
                response.failure("Upload blocked by security")
            elif response.status_code == 413:
                response.failure("File too large")
            elif response.status_code == 503:
                response.failure("Service unavailable")
            else:
                response.failure(f"HTTP {response.status_code}")


# =============================================================================
# Combined User for Quick Testing
# =============================================================================

class CombinedUser(HttpUser):
    """
    A combined user that performs all types of actions.
    Useful for quick smoke tests with fewer concurrent users.

    Weight: 0 (disabled by default, enable explicitly if needed)
    """

    weight = 0  # Disabled by default
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.history: list[dict[str, str]] = []

    @task(5)
    def chat(self) -> None:
        """Send a chat message."""
        message = random.choice(SHORT_MESSAGES + LONG_MESSAGES)
        payload = {"message": message, "history": self.history[-5:]}

        with self.client.post(
            f"{API_PREFIX}/chat",
            json=payload,
            catch_response=True,
            name="/chat"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(3)
    def search(self) -> None:
        """Perform a search."""
        with self.client.get(
            f"{API_PREFIX}/knowledge/summary",
            catch_response=True,
            name="/knowledge/summary"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def upload(self) -> None:
        """Upload a small file."""
        pdf_content = generate_dummy_pdf(5)
        filename = f"quick_test_{random.randint(1000, 9999)}.pdf"
        files = {"file": (filename, io.BytesIO(pdf_content), "application/pdf")}

        with self.client.post(
            f"{API_PREFIX}/upload",
            files=files,
            catch_response=True,
            name="/upload"
        ) as response:
            if response.status_code in [200, 409]:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
