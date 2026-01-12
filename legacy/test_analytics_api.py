"""
Test script for Zoho Analytics API.

Tests:
1. Connection to Analytics API
2. Customer-CRM mapping query
3. Invoice query for specific account
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.integrations.zoho.analytics_client import ZohoAnalyticsClient


async def test_analytics_connection():
    """Test basic Analytics API connection and SQL query."""
    
    print("=" * 80)
    print("🧪 ZOHO ANALYTICS API TEST")
    print("=" * 80)
    
    # Get credentials from env
    client_id = os.getenv("ZOHO_CLIENT_ID")
    client_secret = os.getenv("ZOHO_CLIENT_SECRET")
    refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
    workspace_name = os.getenv("ZOHO_ANALYTICS_WORKSPACE_NAME", "Zoho CRM Reports")
    
    if not all([client_id, client_secret, refresh_token]):
        print("❌ ERROR: Missing environment variables!")
        print("   Required: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN")
        return
    
    print(f"\n📋 Configuration:")
    print(f"   Workspace: {workspace_name}")
    print(f"   Client ID: {client_id[:20]}...")
    print(f"   API URL: https://analyticsapi.zoho.eu")
    
    # Initialize client
    print(f"\n🔧 Initializing Analytics Client...")
    client = ZohoAnalyticsClient(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        workspace_name=workspace_name,
        api_base_url="https://analyticsapi.zoho.eu"
    )
    
    # TEST 1: Simple query to verify connection
    print(f"\n" + "=" * 80)
    print("📊 TEST 1: Connection Test (LIMIT 3)")
    print("=" * 80)
    
    sql = """
    SELECT "Kunden-ID", "CRM-Referenz-ID", "Kundenname"
    FROM "Kunden (Zoho Finance)"
    WHERE "CRM-Referenz-ID" IS NOT NULL
    LIMIT 3
    """
    
    print(f"\n💡 SQL Query:")
    print(sql)
    
    try:
        print(f"\n🔄 Executing query...")
        result = await client.execute_sql(sql)
        
        print(f"✅ SUCCESS! Returned {len(result)} rows:")
        print("-" * 80)
        
        for i, row in enumerate(result, 1):
            print(f"\nRow {i}:")
            for key, value in row.items():
                print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print(f"\nℹ️ Possible issues:")
        print(f"   1. Workspace name incorrect (try with ID instead)")
        print(f"   2. Table 'Kunden (Zoho Finance)' doesn't exist")
        print(f"   3. Column names are different")
        print(f"   4. OAuth scopes missing (ZohoAnalytics.fullaccess.all)")
        return
    
    # TEST 2: Full customer mapping
    print(f"\n" + "=" * 80)
    print("📊 TEST 2: Full Customer Mapping")
    print("=" * 80)
    
    try:
        print(f"\n🔄 Building customer mapping...")
        mapping = await client.get_customer_crm_mapping()
        
        print(f"✅ SUCCESS! Mapped {len(mapping)} customers")
        
        if mapping:
            print(f"\n📋 Sample mappings (first 5):")
            print("-" * 80)
            for i, (books_id, crm_id) in enumerate(list(mapping.items())[:5], 1):
                print(f"   {i}. Books Customer {books_id} → CRM Account {crm_id}")
        else:
            print(f"⚠️ WARNING: Mapping is empty!")
            print(f"   This means either:")
            print(f"   - No customers have CRM mapping")
            print(f"   - Field names are different")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return
    
    # TEST 3: Invoice query for specific account
    print(f"\n" + "=" * 80)
    print("📊 TEST 3: Invoice Query for Lumix Solutions (CRM Account 506156000032560038)")
    print("=" * 80)
    
    lumix_crm_id = "506156000032560038"
    
    try:
        print(f"\n🔄 Fetching invoices for CRM Account {lumix_crm_id}...")
        invoices = await client.get_invoices_for_account(lumix_crm_id)
        
        if invoices:
            print(f"✅ SUCCESS! Found {len(invoices)} invoices:")
            print("-" * 80)
            
            for i, invoice in enumerate(invoices, 1):
                print(f"\nInvoice {i}:")
                for key, value in invoice.items():
                    print(f"   {key}: {value}")
        else:
            print(f"⚠️ No invoices found for this account")
            print(f"   Possible reasons:")
            print(f"   - Account has no invoices")
            print(f"   - CRM-Referenz-ID doesn't match")
            print(f"   - Books customer not linked to CRM")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Cleanup
    await client.close()
    
    print(f"\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_analytics_connection())


