### Updated Template Sentence (Zero "-ing" Verbs)

When exported to reports, use this template:

> **"[Originating Element] requires [Fulfilling Element] in order to [Operative Purpose], which [Operative Mechanism]."**

---

### Field Specification 1: Operative Purpose (The "Why")

* **Role:** States the active goal, required capability, or desired outcome driving the originating element.
* **Grammatical Fragment:** **Bare infinitive verb phrase** (base-form action verb + object/modifier).
* **Part of Speech Pattern:** `[Base Verb] + [Direct Object / Prepositional Modifier]`
* **Negative Constraint:** No leading `"to"`, no inflected forms (*-ed*, *-s*), and strictly **no *-ing* words**.
* **Field Description / Authoring Prompt:**
> *"State the active goal as a sentence fragment beginning with a base action verb. Do not include 'to', nouns as subjects, or words ending in -ing. (e.g., 'maintain state consistency', 'verify identity tokens', 'preserve childhood memories')."*



---

### Field Specification 2: Operative Mechanism (The "How")

* **Role:** States the operational solution, method, or direct action provided by the fulfilling element to satisfy the goal.
* **Grammatical Fragment:** **Third-person singular present indicative verb phrase** (agrees directly with the relative pronoun *"which"* in the template).
* **Part of Speech Pattern:** `[Present Tense Verb ending in -s/-es] + [Object / Instrumental Modifier]`
* **Negative Constraint:** Strictly **no *-ing* words** (gerunds or participles). Must use direct, finite verbs.
* **Field Description / Authoring Prompt:**
> *"State how this element satisfies the goal as a sentence fragment beginning with a third-person present verb (ending in -s or -es). Do not include subject nouns, 'by', or any verbs ending in -ing. (e.g., 'synchronizes distributed nodes across regions', 'validates cryptographic signatures via public key', 'stores digital files in encrypted vaults')."*



---

### Part-of-Speech Verification Matrix

| Target Field | Opening Part of Speech | Structure Rule | Disallowed Forms | Valid Fragment Example |
| --- | --- | --- | --- | --- |
| **Operative Purpose** *(Why)* | **Base Verb** (Bare Infinitive) | `VERB(base) + NOUN_PHRASE` | No leading *"to"*, no *-ing*, no *-ed* | `encrypt customer records` |
| **Operative Mechanism** *(How)* | **Verb (3rd-Person Singular)** | `VERB(present, -s/-es) + NOUN_PHRASE` | No *-ing*, no leading *"by"*, no infinitives | `applies AES-256 cipher blocks` |

---

### Cross-Domain Export Test

#### Human Domain (Parent & Photo Goal)

* **[Originating Element]:** Parent
* **[Fulfilling Element]:** Cloud Archive
* **[Operative Purpose]:** `preserve family milestones`
* **[Operative Mechanism]:** `organizes media uploads into chronological galleries`
* **Compiled Export:**
> *"Parent requires Cloud Archive in order to **preserve family milestones**, which **organizes media uploads into chronological galleries**."*



#### Technical Domain (Service Dependency)

* **[Originating Element]:** Auth Service
* **[Fulfilling Element]:** Token Validator SDK
* **[Operative Purpose]:** `verify client credentials`
* **[Operative Mechanism]:** `inspects cryptographic signatures against cached certificates`
* **Compiled Export:**
> *"Auth Service requires Token Validator SDK in order to **verify client credentials**, which **inspects cryptographic signatures against cached certificates**."*
