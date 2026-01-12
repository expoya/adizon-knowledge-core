# Legacy Files

This folder contains debug scripts and deprecated code that was used during development but is no longer part of the main codebase.

## Contents

### Debug Scripts (2026-01-12)

| File | Description | Why Legacy |
|------|-------------|------------|
| `test_analytics_api.py` | Tests Zoho Analytics API connection and SQL queries | Debug script used during Analytics integration - credentials hardcoded |
| `test_zoho_analytics_debug.py` | Step-by-step Zoho Analytics API debugging | Used to discover org_id and workspace_id - one-time setup |

## When to Reference

These files may be useful if:
- You need to debug Zoho Analytics API issues
- You need to discover new workspace IDs or org IDs
- You want to understand the API exploration process

## Production Configuration

For production, use these environment variables instead:
```
ZOHO_ANALYTICS_WORKSPACE_ID=170896000000004002
ZOHO_ANALYTICS_ORG_ID=20084738965
ZOHO_ANALYTICS_API_BASE_URL=https://analyticsapi.zoho.eu
```
