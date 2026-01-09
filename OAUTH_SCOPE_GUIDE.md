# OAuth Scope & Authentication Guide

## 🎯 Ziel
Zugriff auf:
1. **Emails** - aus Zoho CRM
2. **Invoices** - aus Zoho Books (nicht CRM!)
3. **Subscriptions** - aus Zoho Billing (falls vorhanden)

---

## ✅ Teil 1: Emails - Zoho CRM

### Status
**⚠️ NO_PERMISSION** - OAuth Scope fehlt

### Exakter OAuth Scope (BESTÄTIGT)
```
ZohoCRM.modules.emails.ALL
```
oder nur lesend:
```
ZohoCRM.modules.emails.READ
```

### Dokumentation
- **Quelle:** https://www.zoho.com/crm/developer/docs/api/v8/scopes.html
- **Endpoint:** `GET /crm/v6/Emails`
- **Modul:** Emails (Standard CRM-Modul)

### Aktueller OAuth Scope (vermutlich)
```
ZohoCRM.modules.ALL
ZohoCRM.users.READ
ZohoCRM.settings.fields.READ
```

### Neuer OAuth Scope (benötigt)
```
ZohoCRM.modules.ALL
ZohoCRM.modules.emails.ALL    ← HINZUFÜGEN
ZohoCRM.users.READ
ZohoCRM.settings.fields.READ
```

### ✅ Bestätigung
**JA** - Mit `ZohoCRM.modules.emails.ALL` werden wir Emails erreichen!

---

## ❌ Teil 2: Invoices - Zoho Books (KOMPLEX!)

### Problem
Ihr nutzt **Zoho Books** (professionell), nicht das CRM-Invoices-Modul!

### Unterschied

| Feature | Zoho CRM Invoices | Zoho Books |
|---------|-------------------|------------|
| Typ | Einfaches CRM-Modul | Vollständiges Buchhaltungssystem |
| API | `/crm/v6/Invoices` | `/books/v3/invoices` |
| OAuth | CRM Token | **SEPARATER Token erforderlich!** |
| Parameter | - | `organization_id` **PFLICHT** |
| Daten | Minimal (Test-Data) | Vollständig (echte Rechnungen) |

### Zoho Books API - Separate Authentifizierung!

#### OAuth Scope für Books
```
ZohoBooks.fullaccess.all
```

#### **KRITISCH:** Zoho Books benötigt:
1. **Separate OAuth App** oder erweiterte Scopes
2. **organization_id** Parameter bei JEDEM Request
3. **Eigener API Endpoint:** `https://www.zohoapis.eu/books/v3/...`
4. **Kann NICHT mit CRM OAuth Token alleine genutzt werden!**

#### Authentifizierungsoptionen

**Option A: Multi-Service OAuth Token (EMPFOHLEN)**
- **Ein** OAuth Token für **mehrere** Zoho Services
- Scopes kombinieren:
  ```
  ZohoCRM.modules.ALL,ZohoCRM.modules.emails.ALL,ZohoBooks.fullaccess.all
  ```
- **GLEICHE** Client ID/Secret wie CRM
- **NEUER** Refresh Token mit erweiterten Scopes

**Option B: Separater Zoho Books OAuth Token**
- **Zweite** OAuth App in Zoho API Console
- Eigene Client ID/Secret für Books
- Eigener Refresh Token
- **KOMPLEX:** 2 Token-Management-Systeme

### organization_id - WO FINDE ICH DAS?

1. **Zoho Books einloggen**
2. URL anschauen:
   ```
   https://books.zoho.eu/app/...#/home/dashboard?org_id=123456789
   ```
3. `organization_id` = **123456789**

Oder via API:
```bash
GET https://www.zohoapis.eu/books/v3/organizations
Authorization: Zoho-oauthtoken YOUR_ACCESS_TOKEN
```

### Zoho Books API Request Struktur
```http
GET https://www.zohoapis.eu/books/v3/invoices
  ?organization_id=YOUR_ORG_ID
  &page=1
  &per_page=200
Headers:
  Authorization: Zoho-oauthtoken YOUR_ACCESS_TOKEN
```

### Benötigte Env Variables (NEU)
```bash
# Existing (CRM)
ZOHO_CLIENT_ID=xxx
ZOHO_CLIENT_SECRET=xxx
ZOHO_REFRESH_TOKEN=xxx  # ← Mit erweiterten Scopes!

# New (Books)
ZOHO_BOOKS_ORGANIZATION_ID=123456789  # ← NEU!
ZOHO_BOOKS_API_BASE=https://www.zohoapis.eu/books/v3  # ← NEU!
```

---

## ⚠️ Teil 3: Subscriptions - Unklar

### Error
```
INVALID_MODULE: "the module name given seems to be invalid"
```

### Mögliche Ursachen

1. **Zoho Billing nicht aktiviert**
   - Subscriptions sind Teil von **Zoho Billing** (separates Produkt)
   - Muss in CRM aktiviert/integriert sein
   - Kostet extra!

2. **Modulname ist anders**
   - Vielleicht: `Subscriptions__s` (mit Suffix)
   - Custom-Name in eurer Instanz

3. **Ihr nutzt keine Subscriptions**
   - Nicht jedes Unternehmen hat Abos
   - Voltage macht vielleicht nur one-time Sales

### Lösung: In Zoho CRM prüfen
1. **Setup** → **Modules and Fields**
2. Nach "Subscriptions", "Abonnements", "Billing" suchen
3. Falls nicht vorhanden → **Deaktivieren**

---

## 📋 Zusammenfassung & Aktionsplan

### Was funktioniert JETZT
| Modul | Status | Endpoint | Token |
|-------|--------|----------|-------|
| Users | ✅ OK | `/crm/v6/users` | CRM |
| Accounts | ✅ OK | COQL | CRM |
| Leads | ✅ OK | COQL | CRM |
| Contacts | ✅ OK | COQL | CRM |
| Deals | ✅ OK | COQL | CRM |
| Tasks | ✅ OK | COQL | CRM |
| Notes | ✅ OK | COQL | CRM |
| Events | ✅ OK | COQL | CRM |
| Einwände | ✅ OK | COQL | CRM |
| Attachments | ✅ OK | COQL | CRM |
| **CRM Invoices** | ✅ OK | `/crm/v6/Invoices` | CRM |

### Was fehlt
| Modul | Status | Problem | Lösung |
|-------|--------|---------|--------|
| **Emails** | ⚠️ PERMISSION | OAuth Scope fehlt | Token erweitern |
| **Books Invoices** | ❌ FALSCHE QUELLE | Nutzen CRM statt Books | Separate Integration |
| **Subscriptions** | ❌ INVALID_MODULE | Modul existiert nicht | In CRM prüfen oder deaktivieren |

---

## 🎯 Empfohlene Reihenfolge

### Phase 1: Emails aktivieren (15 Min)
**Warum zuerst?**
- Nutzt GLEICHEN OAuth Token wie CRM
- Nur Scope erweitern, kein neues System
- **Hoher Value:** Emails sind kritisch für RAG

**Schritte:**
1. Zoho API Console öffnen: https://api-console.zoho.eu/
2. Eure CRM App → **Generate Token**
3. Scopes auswählen:
   ```
   ZohoCRM.modules.ALL
   ZohoCRM.modules.emails.ALL
   ZohoCRM.users.READ
   ZohoCRM.settings.fields.READ
   ```
4. **Authorization Code** kopieren
5. Refresh Token generieren (via API oder Console)
6. **Railway Env Variable `ZOHO_REFRESH_TOKEN`** updaten
7. Service neu deployen
8. **Test:** Emails sollten importieren!

### Phase 2: Subscriptions klären (5 Min)
**Schritte:**
1. Zoho CRM einloggen
2. **Setup** → **Modules and Fields**
3. Subscriptions suchen
4. **Falls nicht vorhanden:** Modul aus `schema.py` entfernen

### Phase 3: Zoho Books Integration (1-2 Stunden)
**Warum später?**
- Benötigt separate Integration
- Komplex (organization_id, neue Endpoints)
- Kann parallel zu Phase 1/2 laufen

**Schritte:**
1. **Multi-Service Token generieren:**
   - Scopes: `ZohoCRM....,ZohoBooks.fullaccess.all`
   - Neuer Refresh Token
2. **organization_id** aus Zoho Books holen
3. **Neue Env Variables** in Railway:
   ```
   ZOHO_BOOKS_ORGANIZATION_ID=xxx
   ```
4. **Code anpassen:**
   - Neue `ZohoBooksClient` Klasse
   - Separate API Calls zu `/books/v3/invoices`
   - `organization_id` Parameter bei jedem Request
5. **Schema anpassen:**
   - `books_invoices` vs `crm_invoices`
   - Mapping zu gleichen Graph-Nodes
6. Deploy & Test

---

## ✅ Sofort-Empfehlung

**PHASE 1 JETZT MACHEN:**
1. OAuth Scope für Emails erweitern ✅
2. Subscriptions deaktivieren (temporär) ✅
3. **LIMIT 10000** aktivieren ✅
4. **Full Import** mit 11 Modulen + Emails = **12 Module!** 🎉

**PHASE 3 SPÄTER:**
- Zoho Books Integration ist ein eigenes Mini-Projekt
- Sollte separat geplant und umgesetzt werden
- **Nutzen vs. Aufwand:** Wie viele Books-Invoices habt ihr?

---

## 📚 Dokumentation Links

### Zoho CRM
- OAuth Scopes: https://www.zoho.com/crm/developer/docs/api/v8/scopes.html
- Emails API: https://www.zoho.com/crm/developer/docs/api/v8/view-email.html
- OAuth Token Generation: https://www.zoho.com/crm/developer/docs/api/v2/auth-request.html

### Zoho Books
- API Overview: https://www.zoho.com/books/api/v3/
- Invoices API: https://www.zoho.com/books/api/v3/invoices/
- OAuth: https://www.zoho.com/books/api/v3/oauth/
- Organizations API: https://www.zoho.com/books/api/v3/organizations/

### Zoho API Console
- EU: https://api-console.zoho.eu/
- US: https://api-console.zoho.com/

---

## 🔐 OAuth Token Generation - Step by Step

### Schritt 1: API Console öffnen
```
https://api-console.zoho.eu/
```

### Schritt 2: Self Client finden
- **API Credentials** → Eure App
- Oder: **Create New Client** (falls noch keine existiert)

### Schritt 3: Generate Code
1. **Client ID** & **Client Secret** notieren
2. **Scopes** definieren:
   ```
   ZohoCRM.modules.ALL,ZohoCRM.modules.emails.ALL,ZohoCRM.users.READ,ZohoCRM.settings.fields.READ
   ```
3. **Generate Code** klicken
4. **Authorization Code** kopieren (verfällt in 5 Min!)

### Schritt 4: Refresh Token generieren
**Via cURL:**
```bash
curl -X POST \
  'https://accounts.zoho.eu/oauth/v2/token' \
  -d 'grant_type=authorization_code' \
  -d 'client_id=YOUR_CLIENT_ID' \
  -d 'client_secret=YOUR_CLIENT_SECRET' \
  -d 'redirect_uri=YOUR_REDIRECT_URI' \
  -d 'code=YOUR_AUTHORIZATION_CODE'
```

**Response:**
```json
{
  "access_token": "...",
  "refresh_token": "1000.xxx...",  ← DAS BRAUCHEN WIR!
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### Schritt 5: Railway Env Variable updaten
```bash
ZOHO_REFRESH_TOKEN=1000.xxx...
```

### Schritt 6: Service neu deployen
Railway erkennt Env-Change → Auto-Redeploy

### Schritt 7: Testen!
```bash
POST /api/v1/crm-sync
{
  "entity_types": ["Emails"]
}
```

---

## ✅ Checkliste

### Vor Token-Erneuerung
- [ ] Zoho API Console Zugang geprüft
- [ ] Client ID & Client Secret verfügbar
- [ ] Redirect URI bekannt
- [ ] Scopes definiert: `ZohoCRM.modules.emails.ALL`

### Nach Token-Erneuerung
- [ ] Neuer Refresh Token in Railway gesetzt
- [ ] Service neu deployed
- [ ] Email-Import getestet
- [ ] Keine Permission-Fehler mehr

### Zoho Books (optional)
- [ ] organization_id ermittelt
- [ ] Multi-Service Token generiert (mit `ZohoBooks.fullaccess.all`)
- [ ] Neue Env Variables gesetzt
- [ ] Code angepasst (`ZohoBooksClient`)
- [ ] Books-Invoices importiert

---

**Bereit für Phase 1?** 🚀

