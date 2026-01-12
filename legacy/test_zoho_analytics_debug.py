#!/usr/bin/env python3
"""
Debug script to test Zoho Analytics API v2.

Run this script locally to:
1. Get access token
2. List organizations (get org_id)
3. List workspaces (get workspace_id)
4. Test SQL query export

Usage:
    python test_zoho_analytics_debug.py
"""

import asyncio
import json
import os
import urllib.parse

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
API_BASE = "https://analyticsapi.zoho.eu"  # EU region
AUTH_URL = "https://accounts.zoho.eu/oauth/v2/token"


async def get_access_token(client: httpx.AsyncClient) -> str:
    """Get fresh access token."""
    print("\n" + "=" * 60)
    print("STEP 1: Getting Access Token")
    print("=" * 60)

    response = await client.post(
        AUTH_URL,
        data={
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
    )

    print(f"Status: {response.status_code}")
    data = response.json()

    if "access_token" in data:
        token = data["access_token"]
        print(f"Token: {token[:20]}...{token[-10:]}")
        return token
    else:
        print(f"ERROR: {data}")
        raise Exception("Failed to get access token")


async def get_organizations(client: httpx.AsyncClient, token: str) -> list:
    """List all organizations."""
    print("\n" + "=" * 60)
    print("STEP 2: Getting Organizations")
    print("=" * 60)

    url = f"{API_BASE}/restapi/v2/orgs"
    print(f"URL: {url}")

    response = await client.get(
        url,
        headers={"Authorization": f"Zoho-oauthtoken {token}"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

    if response.status_code == 200:
        data = response.json()
        orgs = data.get("data", {}).get("orgs", [])

        print("\nOrganizations found:")
        for org in orgs:
            print(f"  - {org.get('orgName')} (ID: {org.get('orgId')}) - {org.get('planName')} - Workspaces: {org.get('numberOfWorkspaces')}")

        return orgs
    return []


async def get_workspaces(client: httpx.AsyncClient, token: str, org_id: str) -> list:
    """List all workspaces in an organization."""
    print("\n" + "=" * 60)
    print(f"STEP 3: Getting Workspaces (org_id: {org_id})")
    print("=" * 60)

    url = f"{API_BASE}/restapi/v2/workspaces"
    print(f"URL: {url}")

    response = await client.get(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "ZANALYTICS-ORGID": org_id,
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:1000]}")

    if response.status_code == 200:
        data = response.json()
        # Combine owned and shared workspaces
        owned = data.get("data", {}).get("ownedWorkspaces", []) or []
        shared = data.get("data", {}).get("sharedWorkspaces", []) or []
        workspaces = owned + shared

        print(f"\nWorkspaces found ({len(owned)} owned, {len(shared)} shared):")
        for ws in workspaces:
            if isinstance(ws, dict):
                print(f"  - {ws.get('workspaceName')} (ID: {ws.get('workspaceId')})")

        return workspaces
    return []


async def test_bulk_sql_export(
    client: httpx.AsyncClient,
    token: str,
    org_id: str,
    workspace_id: str
):
    """Test bulk SQL export (async - returns job ID)."""
    print("\n" + "=" * 60)
    print(f"STEP 4: Testing Bulk SQL Export")
    print(f"  Workspace ID: {workspace_id}")
    print(f"  Org ID: {org_id}")
    print("=" * 60)

    # Simple test query
    sql_query = 'SELECT * FROM "Kunden (Zoho Finance)" LIMIT 5'

    config = {
        "sqlQuery": sql_query,
        "responseFormat": "json"
    }

    config_encoded = urllib.parse.quote(json.dumps(config))

    url = f"{API_BASE}/restapi/v2/bulk/workspaces/{workspace_id}/data?CONFIG={config_encoded}"

    print(f"\nRequest URL: {url[:100]}...")
    print(f"SQL Query: {sql_query}")

    response = await client.get(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "ZANALYTICS-ORGID": org_id,
        }
    )

    print(f"\nStatus: {response.status_code}")
    print(f"Response: {response.text[:1000]}")

    if response.status_code == 200:
        data = response.json()
        job_id = data.get("data", {}).get("jobId")
        if job_id:
            print(f"\nJob created! Job ID: {job_id}")
            # Wait and check job status
            await check_job_status(client, token, org_id, workspace_id, job_id)


async def check_job_status(
    client: httpx.AsyncClient,
    token: str,
    org_id: str,
    workspace_id: str,
    job_id: str
):
    """Check export job status and download if ready."""
    print("\n" + "=" * 60)
    print(f"STEP 5: Checking Job Status (job_id: {job_id})")
    print("=" * 60)

    import time

    for attempt in range(10):
        url = f"{API_BASE}/restapi/v2/bulk/workspaces/{workspace_id}/exportjobs/{job_id}"

        response = await client.get(
            url,
            headers={
                "Authorization": f"Zoho-oauthtoken {token}",
                "ZANALYTICS-ORGID": org_id,
            }
        )

        print(f"\nAttempt {attempt + 1}: Status {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)[:500]}")

        job_status = data.get("data", {}).get("jobStatus", "")
        if "COMPLETED" in job_status:
            print("\nJob completed! Downloading data...")
            await download_job_data(client, token, org_id, workspace_id, job_id)
            return
        elif "FAILED" in job_status:
            print("\nJob FAILED!")
            return

        print("Waiting 2 seconds...")
        time.sleep(2)


async def download_job_data(
    client: httpx.AsyncClient,
    token: str,
    org_id: str,
    workspace_id: str,
    job_id: str
):
    """Download exported data."""
    print("\n" + "=" * 60)
    print(f"STEP 6: Downloading Data (job_id: {job_id})")
    print("=" * 60)

    url = f"{API_BASE}/restapi/v2/bulk/workspaces/{workspace_id}/exportjobs/{job_id}/data"

    response = await client.get(
        url,
        headers={
            "Authorization": f"Zoho-oauthtoken {token}",
            "ZANALYTICS-ORGID": org_id,
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Data preview:\n{response.text[:2000]}")


async def main():
    print("=" * 60)
    print("ZOHO ANALYTICS API v2 DEBUG SCRIPT")
    print("=" * 60)

    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("ERROR: Missing environment variables!")
        print(f"  ZOHO_CLIENT_ID: {'SET' if CLIENT_ID else 'MISSING'}")
        print(f"  ZOHO_CLIENT_SECRET: {'SET' if CLIENT_SECRET else 'MISSING'}")
        print(f"  ZOHO_REFRESH_TOKEN: {'SET' if REFRESH_TOKEN else 'MISSING'}")
        return

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Step 1: Get access token
            token = await get_access_token(client)

            # Step 2: Get organizations
            orgs = await get_organizations(client, token)

            if not orgs:
                print("\nNo organizations found!")
                return

            # Use org with workspaces (prefer CRM Plus)
            org = None
            for o in orgs:
                if o.get("numberOfWorkspaces", 0) > 0:
                    org = o
                    break
            if not org:
                org = orgs[0]

            org_id = str(org.get("orgId"))
            print(f"\nUsing org: {org.get('orgName')} (ID: {org_id}, Workspaces: {org.get('numberOfWorkspaces')})")

            # Step 3: Get workspaces
            workspaces = await get_workspaces(client, token, org_id)

            if not workspaces:
                print("\nNo workspaces found!")
                return

            # Find the right workspace - prefer "Zoho CRM Reports"
            workspace_id = None
            for ws in workspaces:
                if not isinstance(ws, dict):
                    continue
                ws_name = ws.get("workspaceName", "")
                # Exact match for CRM Reports first
                if "CRM Reports" in ws_name:
                    workspace_id = str(ws.get("workspaceId"))
                    print(f"\nSelected workspace: {ws_name} (ID: {workspace_id})")
                    break

            if not workspace_id:
                # Fallback: look for Finance or CRM
                for ws in workspaces:
                    if not isinstance(ws, dict):
                        continue
                    ws_name = ws.get("workspaceName", "")
                    if "Finance" in ws_name:
                        workspace_id = str(ws.get("workspaceId"))
                        print(f"\nSelected workspace: {ws_name} (ID: {workspace_id})")
                        break

            if not workspace_id:
                # Use first workspace
                workspace_id = str(workspaces[0].get("workspaceId"))
                print(f"\nUsing first workspace (ID: {workspace_id})")

            # Step 4: Test SQL export
            await test_bulk_sql_export(client, token, org_id, workspace_id)

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
