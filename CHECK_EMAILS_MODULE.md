# Check: Ist "Emails" ein Modul in Zoho CRM?

## Problem
`GET /crm/v2/Emails` gibt 403 NO_PERMISSION mit "Crm_Implied_View_Emails".

## Mögliche Ursachen

### 1. User Profile Permission fehlt
**Symptom:** 403 NO_PERMISSION mit "Crm_Implied_View_Emails"

**Check:**
1. Zoho CRM → Setup → Users and Control → Profiles
2. API User Profile → Module Permissions
3. Suche nach "Emails" oder "Activities"
4. Prüfe ob "View" aktiviert ist

**Fix:**
- Admin muss Email-Rechte im User Profile aktivieren

---

### 2. Emails ist KEIN Modul (Related List only)
**Symptom:** 403 oder INVALID_MODULE

**Theorie:**
Emails existiert nur als Related List zu Leads/Contacts/Accounts/Deals.

**Wenn das der Fall ist, müssen wir Emails so abrufen:**
```
GET /crm/v2/Leads/{lead_id}/Emails
GET /crm/v2/Contacts/{contact_id}/Emails
GET /crm/v2/Accounts/{account_id}/Emails
GET /crm/v2/Deals/{deal_id}/Emails
```

**Implementierung würde bedeuten:**
1. Alle Leads/Contacts/Accounts/Deals durchlaufen
2. Für jeden Record die Related Emails abrufen
3. Emails als separate Nodes im Graph speichern
4. Relationship zu Parent-Record erstellen

**Aufwand:** Hoch (muss für jedes Entity-Type separat implementiert werden)

---

### 3. Emails benötigt spezielle API oder Settings
**Symptom:** 403 trotz korrektem Scope

**Möglichkeit:**
- Zoho Email Integration muss aktiviert sein
- Emails werden über andere API abgerufen (z.B. Activities API)

---

## 🧪 Schneller Test in Zoho CRM UI

### Test 1: Emails Modul finden
1. Zoho CRM einloggen
2. Navigation links → Suche nach "Emails"
3. **Falls vorhanden:** Emails ist ein eigenständiges Modul
4. **Falls NICHT vorhanden:** Emails ist nur Related List

### Test 2: Related List prüfen
1. Öffne einen Lead/Contact/Account
2. Scroll nach unten zu "Related Lists"
3. Suche nach "Emails" oder "Activities"
4. **Falls vorhanden:** Emails sind als Related List verfügbar

---

## 📊 Entscheidungsbaum

```
Ist "Emails" in Navigation sichtbar?
│
├─ JA → Emails ist ein Modul
│   │
│   └─ Check User Profile Permissions
│       │
│       ├─ Email Permission fehlt → Admin muss aktivieren
│       └─ Permission OK → API Version Problem (v2, v3, v6?)
│
└─ NEIN → Emails ist nur Related List
    │
    └─ Implementiere Related List Fetching
        - Für jeden Lead/Contact/Account/Deal
        - GET /crm/v2/{module}/{id}/Emails
        - Merge alle Emails in Graph
```

---

## 💡 Empfehlung

### Sofort:
1. **User im CRM prüfen:** Sind Emails in der Navigation sichtbar?
2. **Falls JA:** Profile Permissions prüfen lassen (Admin)
3. **Falls NEIN:** Emails sind Related Lists → Komplexere Implementation nötig

### Später (Falls Related List):
1. Neue Fetching-Strategie für Related Lists
2. Batch-Processing (alle Leads holen, dann Related Emails)
3. Performance-Optimierung (Rate Limiting!)

---

## 🎯 Nächster Schritt

**Bitte prüfe in Zoho CRM UI:**
- Ist "Emails" in der linken Navigation als eigenes Modul sichtbar?
- Screenshot schicken wenn möglich

Das gibt uns die Antwort ob wir:
- A) Nur Permissions fixen müssen
- B) Ganze Fetching-Logik umbauen müssen

