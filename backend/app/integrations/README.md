# CRM Integration Plugin System

Modulares, erweiterbares Plugin-System für CRM-Integrationen.

## 🎯 Architektur

```
Core (Agnostic)
    ↓
CRMProvider Interface (Abstract)
    ↓
Factory Pattern (crm_factory.py)
    ↓
Concrete Implementations (zoho/, salesforce/, ...)
```

## 📁 Struktur

```
app/
├── core/interfaces/
│   └── crm.py                    # Abstract CRMProvider interface
├── services/
│   └── crm_factory.py            # Factory for loading providers
└── integrations/
    ├── zoho/                     # Zoho CRM Plugin (Expoya Addon)
    │   ├── __init__.py
    │   ├── client.py             # OAuth2 client with token refresh
    │   └── provider.py           # ZohoCRMProvider implementation
    └── [future providers]/
```

## 🔌 Interface Contract

Alle CRM-Provider müssen `CRMProvider` implementieren:

### Pflicht-Methoden

1. **`check_connection() -> bool`**
   - Prüft API-Erreichbarkeit
   - Validiert Credentials

2. **`fetch_skeleton_data(entity_types: list[str]) -> list[dict]`**
   - Lädt Stammdaten für Graph-Import
   - Format: `{"id": "...", "name": "...", "type": "..."}`

3. **`search_live_facts(entity_id: str, query_context: str) -> str`**
   - Holt aktuelle Daten zu einer Entity
   - LLM-freundliches String-Format

4. **`execute_raw_query(query: str) -> any`**
   - Führt provider-spezifische Queries aus
   - Zoho: COQL, Salesforce: SOQL, etc.

5. **`get_provider_name() -> str`**
   - Gibt Provider-Namen zurück

6. **`get_available_modules() -> list[str]`**
   - Listet verfügbare Entity-Typen

## 🚀 Verwendung

### Basic Usage

```python
from app.services.crm_factory import get_crm_provider, is_crm_available

# Check if CRM is configured
if is_crm_available():
    provider = get_crm_provider()
    
    # Check connection
    if provider.check_connection():
        print(f"Connected to {provider.get_provider_name()}")
        
        # Fetch data
        contacts = provider.fetch_skeleton_data(["Contacts"])
        print(f"Found {len(contacts)} contacts")
```

### In API Endpoints

```python
from app.services.crm_factory import get_crm_provider

@router.get("/crm/contacts")
async def get_crm_contacts():
    provider = get_crm_provider()
    
    if not provider:
        raise HTTPException(404, "No CRM configured")
    
    contacts = provider.fetch_skeleton_data(["Contacts"])
    return {"contacts": contacts}
```

### Live Facts Search

```python
# Get current information about an entity
provider = get_crm_provider()
facts = provider.search_live_facts(
    entity_id="3652397000000649013",
    query_context="deals and revenue information"
)
print(facts)
```

## ⚙️ Configuration

### Environment Variables

```bash
# === CRM Provider Selection ===
ACTIVE_CRM_PROVIDER=zoho        # Options: zoho, none

# === Zoho CRM Credentials ===
ZOHO_CLIENT_ID=your_client_id
ZOHO_CLIENT_SECRET=your_client_secret
ZOHO_REFRESH_TOKEN=your_refresh_token
ZOHO_API_BASE_URL=https://www.zohoapis.eu  # Region-specific
```

### Zoho Setup

1. **Create OAuth Client**
   - Go to: https://api-console.zoho.eu/
   - Create "Server-based Application"
   - Note Client ID and Client Secret

2. **Generate Refresh Token**
   - Use OAuth2 flow to get authorization code
   - Exchange code for refresh token
   - Refresh token is long-lived (won't expire)

3. **Set Environment Variables**
   ```bash
   ZOHO_CLIENT_ID=1000.ABC123XYZ
   ZOHO_CLIENT_SECRET=abc123def456
   ZOHO_REFRESH_TOKEN=1000.abc123.def456.xyz789
   ```

## 🔧 Zoho CRM Plugin

### Features

- ✅ OAuth2 Refresh Token Flow
- ✅ Automatic token refresh (1-hour cache)
- ✅ Async HTTP client (httpx)
- ✅ Error handling and logging
- ✅ Region-specific API endpoints

### Client (zoho/client.py)

```python
from app.integrations.zoho.client import ZohoClient

# Create client
client = ZohoClient(
    client_id="...",
    client_secret="...",
    refresh_token="...",
    api_base_url="https://www.zohoapis.eu"
)

# Make requests
async with client:
    response = await client.get("/crm/v6/Contacts", params={"per_page": 10})
    print(response)
```

### Provider (zoho/provider.py)

Currently implements stubs for all interface methods:
- ⚠️ `check_connection()` - Returns True (stub)
- ⚠️ `fetch_skeleton_data()` - Returns sample data
- ⚠️ `search_live_facts()` - Returns placeholder string
- ⚠️ `execute_raw_query()` - Returns empty result
- ✅ `get_provider_name()` - Returns "Zoho CRM"
- ⚠️ `get_available_modules()` - Returns common modules

**Next Steps:** Implement actual API calls in each method.

## 🔮 Adding New Providers

### 1. Create Provider Directory

```bash
mkdir -p backend/app/integrations/salesforce
touch backend/app/integrations/salesforce/__init__.py
touch backend/app/integrations/salesforce/client.py
touch backend/app/integrations/salesforce/provider.py
```

### 2. Implement Provider

```python
# salesforce/provider.py
from app.core.interfaces.crm import CRMProvider

class SalesforceCRMProvider(CRMProvider):
    def check_connection(self) -> bool:
        # Implement Salesforce connection check
        pass
    
    # ... implement other methods
```

### 3. Update Factory

```python
# services/crm_factory.py

def get_crm_provider():
    # ...
    elif active_provider == "salesforce":
        return _load_salesforce_provider()

def _load_salesforce_provider() -> CRMProvider:
    from app.integrations.salesforce import SalesforceCRMProvider
    # Initialize and return provider
```

### 4. Add Configuration

```python
# core/config.py

salesforce_instance_url: str | None = Field(...)
salesforce_access_token: str | None = Field(...)
```

## 📊 Testing

### Unit Tests

```python
# tests/test_crm_factory.py
from app.services.crm_factory import get_crm_provider

def test_zoho_provider_loads():
    provider = get_crm_provider()
    assert provider is not None
    assert provider.get_provider_name() == "Zoho CRM"

def test_provider_interface():
    provider = get_crm_provider()
    assert hasattr(provider, "check_connection")
    assert hasattr(provider, "fetch_skeleton_data")
```

### Integration Tests

```python
# tests/test_zoho_integration.py
import pytest
from app.integrations.zoho import ZohoCRMProvider

@pytest.mark.asyncio
async def test_zoho_connection():
    provider = ZohoCRMProvider(
        client_id=os.getenv("ZOHO_CLIENT_ID"),
        client_secret=os.getenv("ZOHO_CLIENT_SECRET"),
        refresh_token=os.getenv("ZOHO_REFRESH_TOKEN")
    )
    
    assert provider.check_connection()
```

## 🛡️ Security

### Best Practices

1. **Never commit credentials**
   - Use `.env` files (gitignored)
   - Use environment variables in production

2. **Token Security**
   - Refresh tokens are long-lived but revocable
   - Access tokens are cached in memory only
   - No token persistence to disk

3. **API Rate Limits**
   - Implement rate limiting in clients
   - Use exponential backoff for retries

4. **Error Handling**
   - Never expose credentials in error messages
   - Log errors without sensitive data

## 📈 Performance

### Caching Strategy

- **Factory**: `@lru_cache` on `get_crm_provider()`
  - Provider instance cached app-wide
  - Clear cache: `clear_crm_provider_cache()`

- **Tokens**: In-memory cache with expiry
  - Access tokens cached for ~59 minutes
  - Automatic refresh on expiry

- **HTTP Client**: Persistent connection pool
  - Reuses connections via httpx.AsyncClient
  - Configurable timeout (default: 30s)

### Optimization Tips

1. **Batch Requests**: Fetch multiple entities in one call
2. **Field Selection**: Only request needed fields
3. **Pagination**: Use `per_page` parameter wisely

## 🐛 Troubleshooting

### "No CRM configured"

**Problem:** `get_crm_provider()` returns `None`

**Solution:** Set `ACTIVE_CRM_PROVIDER=zoho` in `.env`

---

### "Token refresh failed"

**Problem:** OAuth2 token refresh returns 400/401

**Solution:**
1. Verify `ZOHO_REFRESH_TOKEN` is valid
2. Check `ZOHO_CLIENT_ID` and `ZOHO_CLIENT_SECRET`
3. Ensure OAuth app is not revoked
4. Regenerate refresh token if needed

---

### "Connection check failed"

**Problem:** `check_connection()` returns `False`

**Solution:**
1. Check network connectivity
2. Verify API base URL is correct for your region
3. Check Zoho API status
4. Review logs for detailed error

---

### Region Issues

**Problem:** Getting 404 or invalid responses

**Solution:** Set correct `ZOHO_API_BASE_URL`:
- US: `https://www.zohoapis.com`
- EU: `https://www.zohoapis.eu`
- India: `https://www.zohoapis.in`
- Australia: `https://www.zohoapis.com.au`
- China: `https://www.zohoapis.com.cn`

## 🚀 Roadmap

### Phase 1: Zoho Implementation ✅
- [x] Abstract interface
- [x] Factory pattern
- [x] OAuth2 client with token refresh
- [x] Provider stubs
- [ ] Implement `fetch_skeleton_data()`
- [ ] Implement `search_live_facts()`
- [ ] Implement `execute_raw_query()`

### Phase 2: Graph Integration
- [ ] CRM entity → Neo4j node sync
- [ ] Relationship mapping
- [ ] Incremental updates

### Phase 3: Agent Tool
- [ ] `search_crm` tool for LangGraph
- [ ] Live fact retrieval in chat
- [ ] Cross-reference with knowledge graph

### Phase 4: Additional Providers
- [ ] Salesforce
- [ ] HubSpot
- [ ] Microsoft Dynamics
- [ ] Custom REST API provider

## 📚 References

- [Zoho CRM API v6 Docs](https://www.zoho.com/crm/developer/docs/api/v6/)
- [Zoho OAuth2 Guide](https://www.zoho.com/crm/developer/docs/api/v6/oauth-overview.html)
- [COQL Reference](https://www.zoho.com/crm/developer/docs/api/v6/COQL.html)

---

**Version:** 1.0  
**Status:** 🟡 Partially Implemented (Stubs)  
**Next Steps:** Complete Zoho provider implementation

