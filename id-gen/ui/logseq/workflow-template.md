---
title: "Workflow Log: {{contract-id}}"
template: workflow-log
tags: workflow, progress, 7-step, collibra
---

# Workflow Log: `{{contract-id}}`

> **Topic**: [[{{topic-label}}]] | **Status**: [[{{status}}]] | **Step**: `{{step}}/7`

---

## Step-by-Step Activity

### Step 0 — INIT
- **Status**: DRAFT
- **Timestamp**: {{step-0-ts}}
- Contract `{{contract-id}}` created
- Git tag: `id-gen/{{contract-id}}`
- SSH principal: `{{ssh-fingerprint}}`
- SPARQL query received and embedded

---

### Step 1 — EXTRACT
- **Status**: DRAFT
- **Timestamp**: {{step-1-ts}}
- Collibra REST API polled for asset types
- Community: `{{collibra-community-id}}`
- Asset types enumerated:
  {{#asset-types}}
  - `c.assetType.{{id}}` — {{name}}
  {{/asset-types}}

---

### Step 2 — CLASSIFY
- **Status**: DRAFT
- **Timestamp**: {{step-2-ts}}
- Asset types mapped to SBVR Concept Types:
  - `Business Term` → `sbvr:BusinessVocabularyTerm`
  - `Data Asset` → `sbvr:ConceptType` / `dcat:Dataset`
  - `Policy` → `odrl:Policy`
  - `Use Case` → `sbvr:BusinessRule`
  - `Data Contract` → `odrl:Agreement` / `dcat:DataService`

---

### Step 3 — RELATE
- **Status**: DRAFT
- **Timestamp**: {{step-3-ts}}
- ORM binary fact types identified from Collibra metamodel
- See: [[ORM Fact Types]] in contract

---

### Step 4 — CONSTRAIN
- **Status**: PENDING_APPROVAL
- **Timestamp**: {{step-4-ts}}
- Uniqueness constraints applied
- Mandatory constraints applied
- Subset + ring constraints checked

---

### Step 5 — VERBALIZE
- **Status**: PENDING_APPROVAL
- **Timestamp**: {{step-5-ts}}
- SBVR business rules verbalized from ORM fact types
- Rules submitted for review

---

### Step 6 — ALIGN
- **Status**: PENDING_APPROVAL
- **Timestamp**: {{step-6-ts}}
- Vocabulary cross-references applied:
  - SKOS, DCAT, ODRL, PROV-O, OWL, SBVR
- Collibra ID namespace privileged: `c.*`
- Reserved: `a.*` / `b.*`

---

### Step 7 — CONTRACT
- **Status**: APPROVED
- **Timestamp**: {{step-7-ts}}
- Data contract finalized
- All IDs tracked with git tags
- Workflow progression: 100%

$$\text{progress} = \frac{7 \times 100}{7} = 100\%$$

---

## Decision Log (Merge Conflict Resolutions)

{{#conflict-resolutions}}
- `[{{timestamp}}]` **{{strategy}}** — `{{file}}`
  - Ours: {{ours-preview}}
  - Theirs: {{theirs-preview}}
  - **Decision**: {{resolution}}
{{/conflict-resolutions}}

> Conflict resolution priority: `c.*` IDs win over `b.*` win over `a.*` win over raw UUIDs.

---

## Progress Bar (terminal rendering)
```
[{{progress-bar}}] {{progress-pct}}%
```

## Linked Pages
- [[Contract: {{contract-id}}]]
- [[Topic: {{topic-label}}]]
- [[Collibra Community: {{collibra-community-id}}]]
- [[SPARQL Query: {{contract-id}}]]
