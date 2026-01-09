# Zoho Finance & Emails Integration - Research

## 🎯 Ziel
Vollständige Integration von:
1. **Invoices** (Rechnungen)
2. **Subscriptions** (Abonnements)
3. **Emails** (E-Mails)

---

## ✅ 1. Invoices - FUNKTIONIERT!

### Status
**✅ ERFOLGREICH** - 50 Invoices wurden im Smoke Test importiert!

### Endpoint
```
GET /crm/v6/Invoices
```

### Beweis
```json
{
  "entities_synced": 467,
  "entity_types": ["Lead", "CalendlyEvent", "Contact", "User", "Deal", "Account", "Invoice", ...]
}
```

### Implementierung
- Verwendet: **REST API** (nicht COQL)
- Status: **Production Ready ✅**
- Felder: `["id", "Subject", "Account_Name", "Grand_Total", "Status", "Invoice_Date"]`

### Zoho CRM vs. Zoho Books

**WICHTIG:**
- Zoho CRM **hat** ein Invoices-Modul (via REST API)
- Zoho Books ist ein **separates Produkt** mit eigener API
- **Wir nutzen CRM-Invoices** (einfacher, bereits integriert)

**Wenn später detailliertere Rechnungsdaten benötigt werden:**
- Zoho Books API: `GET /books/v3/invoices?organization_id=XXX`
- Benötigt: Separate OAuth-Token + organization_id
- **Empfehlung:** Erst bei Bedarf aktivieren

---

## ⚠️ 2. Subscriptions - INVALID_MODULE

### Error Log
```
Zoho API error: 400 - {
  "code": "INVALID_MODULE",
  "details": {"resource_path_index": 0},
  "message": "the module name given seems to be invalid",
  "status": "error"
}
```

### Analyse

**Problem:** 
Der Modulname "Subscriptions" existiert nicht in eurem Zoho CRM.

**Mögliche Ursachen:**

1. **Zoho Billing nicht aktiviert:**
   - Subscriptions sind Teil von **Zoho Billing** (ehemals Zoho Subscriptions)
   - Zoho Billing ist ein **separates Produkt**
   - Muss in Zoho CRM aktiviert/integriert werden

2. **Modulname ist anders:**
   - Eventuell: `Subscriptions__s` (mit Suffix)
   - Oder: Custom Module Name in eurer Zoho-Instanz

3. **Keine Subscriptions in CRM:**
   - Voltage nutzt vielleicht keine Abonnements
   - Oder: Werden in anderem System verwaltet

### Lösungsoptionen

#### Option A: In Zoho CRM prüfen (EMPFOHLEN)
1. Zoho CRM einloggen
2. **Setup** → **Modules and Fields**
3. Nach "Subscriptions" oder ähnlichen Modulen suchen
4. Modulname notieren und in `schema.py` eintragen

#### Option B: Zoho Billing API nutzen (KOMPLEX)
```
GET /billing/v1/subscriptions
```
- Benötigt: Separate Zoho Billing Instanz
- Benötigt: Eigene OAuth-Token
- Benötigt: Separate Konfiguration

#### Option C: Deaktivieren (QUICK FIX)
- Modul temporär aus `schema.py` entfernen
- Später reaktivieren, wenn Modulname bekannt

### Empfehlung
**→ Option C für jetzt, dann Option A klären**

---

## ❌ 3. Emails - NO_PERMISSION

### Error Log
```
Zoho API error: 403 - {
  "code": "NO_PERMISSION",
  "details": {"permissions": ["Crm_Implied_View_Emails"]},
  "message": "permission denied",
  "status": "error"
}
```

### Analyse

**Gute Nachricht:** 
Der Endpoint **existiert** (`/crm/v6/Emails`), aber der API User hat keine Berechtigung.

**Problem:**
OAuth Scope `Crm_Implied_View_Emails` fehlt im Access Token.

### Lösung: OAuth Scope hinzufügen

#### Schritt 1: Zoho API Console öffnen
```
https://api-console.zoho.eu/
```

#### Schritt 2: Self Client finden
1. **API Credentials** → Eure CRM App
2. **Generate Token** oder **Edit Scopes**

#### Schritt 3: Scopes prüfen/hinzufügen
**Aktuell vermutlich:**
```
ZohoCRM.modules.ALL
ZohoCRM.users.READ
ZohoCRM.settings.fields.READ
```

**HINZUFÜGEN:**
```
ZohoCRM.modules.emails.ALL
```
oder spezifischer:
```
ZohoCRM.modules.emails.READ
```

#### Schritt 4: Neuen Refresh Token generieren
**WICHTIG:** Nach Scope-Änderung muss ein **neuer Refresh Token** generiert werden!

1. **Generate Token** klicken
2. Scopes auswählen (inkl. `ZohoCRM.modules.emails.READ`)
3. Authorization Code kopieren
4. **Neuen Refresh Token** via API oder Console generieren
5. **Railway Env Variable `ZOHO_REFRESH_TOKEN` updaten**

#### Schritt 5: Service neu deployen
Nach Token-Update → Railway Deployment neu starten

### Alternative: Zoho CRM Settings prüfen

Falls OAuth Scope bereits korrekt ist:

1. **Zoho CRM** → **Setup** → **Users and Control**
2. **Users** → Euren API User auswählen
3. **Profile** → Permissions prüfen
4. **Emails** Modul → **View** Permission aktivieren

---

## 📊 Zusammenfassung

| Modul          | Status | Endpoint                | Nächster Schritt                        |
|----------------|--------|-------------------------|-----------------------------------------|
| **Invoices**   | ✅ OK  | `/crm/v6/Invoices`      | Nichts - funktioniert!                  |
| **Subscriptions** | ❌ ERROR | `/crm/v6/Subscriptions` | In CRM prüfen oder deaktivieren         |
| **Emails**     | ⚠️ PERMISSION | `/crm/v6/Emails` | OAuth Scope hinzufügen + Token erneuern |

---

## 🎯 Empfohlene Vorgehensweise

### Sofort (5 Minuten):
1. **Subscriptions deaktivieren** (in `schema.py`)
2. **Emails behalten** (für späteren Fix)
3. **Auf LIMIT 10000 hochdrehen**
4. **Full Import starten**

### Danach (15-30 Minuten):
1. **Zoho CRM einloggen**
2. **Subscriptions-Modul suchen** (falls vorhanden)
3. **OAuth Scope für Emails erweitern**
4. **Neuen Refresh Token generieren**
5. **Railway Env Variable updaten**
6. **Neu deployen**
7. **Full Import mit Emails & Subscriptions**

---

## 📚 Zoho Dokumentation

### Invoices
- CRM API: https://www.zoho.com/crm/developer/docs/api/v2/invoices.html
- Books API: https://www.zoho.com/books/api/v3/invoices/

### Subscriptions
- Billing API: https://www.zoho.com/billing/api/v1/subscription/
- CRM Integration: Prüfen ob Zoho Billing aktiviert ist

### Emails
- CRM API: https://www.zoho.com/crm/developer/docs/api/v2/
- OAuth Scopes: https://www.zoho.com/crm/developer/docs/api/v2/scopes.html

### OAuth Token Management
- Console: https://api-console.zoho.eu/
- Token Generation: https://www.zoho.com/crm/developer/docs/api/v2/auth-request.html

---

## ✅ Nächste Schritte

**JA:**
- Invoices ✅ (funktioniert)
- Emails ⚠️ (Permission-Fix benötigt)

**NEIN (vorerst):**
- Subscriptions ❌ (Modulname unklar)

**EMPFEHLUNG:**
→ Subscriptions **deaktivieren**, Emails **Permission fixen**, dann **LIMIT 10000** und **Full Import**!

