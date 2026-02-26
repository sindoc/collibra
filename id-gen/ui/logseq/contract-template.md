---
title: "Data Contract: {{contract-id}}"
template: data-contract
tags: collibra, data-contract, c-namespace, workflow
---

# Data Contract: `{{contract-id}}`

## Identity
- **ID**: `{{contract-id}}`  *(c.* — Collibra-privileged namespace)*
- **Kind**: {{kind}}
- **Status**: [[{{status}}]]
- **Topic**: [[{{topic-label}}]]  → `{{topic-id}}`
- **Collibra Case**: `{{collibra-case-id}}`
- **Git Tag**: `id-gen/{{contract-id}}`
- **SSH Identity**: `{{ssh-fingerprint}}`
- **Created**: {{created-at}}

---

## Namespace mapping
| Prefix | Namespace | Note |
|--------|-----------|------|
| `c.*`  | Collibra  | **Privileged** — sourced from or registered in Collibra |
| `a.*`  | Reserved-A | Reserved namespace A |
| `b.*`  | Reserved-B | Reserved namespace B |

> Project = Topic → `c.topic.*` (privileged)

---

## 7-Step Workflow Progress

- [ ] **Step 0** — INIT: Contract created
- [ ] **Step 1** — EXTRACT: Collibra asset types enumerated
- [ ] **Step 2** — CLASSIFY: Types → SBVR Concept Types
- [ ] **Step 3** — RELATE: ORM binary fact types identified
- [ ] **Step 4** — CONSTRAIN: Uniqueness + mandatory constraints applied
- [ ] **Step 5** — VERBALIZE: SBVR business rules expressed
- [ ] **Step 6** — ALIGN: Vocabulary cross-references applied
- [ ] **Step 7** — CONTRACT: Finalized, IDs tracked

Progress: `{{workflow-step}}/7` = `{{workflow-progress}}%`

$$\text{progress} = \frac{{{workflow-step}} \times 100}{7} \approx {{workflow-progress}}\%$$

---

## SPARQL Source Query

```sparql
{{sparql-query}}
```

---

## ORM Fact Types

| Subject | Verb | Object | Mandatory | Uniqueness |
|---------|------|--------|-----------|------------|
{{#orm-fact-types}}
| {{subject}} | {{verb}} | {{object}} | {{mandatory}} | {{uniqueness}} |
{{/orm-fact-types}}

---

## SBVR Business Rules

{{#sbvr-rules}}
- {{.}}
{{/sbvr-rules}}

---

## Vocabulary Alignment

| Vocabulary | URI | Use |
|------------|-----|-----|
| SKOS  | http://www.w3.org/2004/02/skos/core# | Concept hierarchies, preferred labels |
| DCAT  | http://www.w3.org/ns/dcat# | Dataset / DataService descriptions |
| ODRL  | http://www.w3.org/ns/odrl/2/ | Usage policies, access agreements |
| PROV-O| http://www.w3.org/ns/prov# | Provenance, attribution |
| OWL   | http://www.w3.org/2002/07/owl# | Ontological grounding |
| SBVR  | https://www.omg.org/spec/SBVR/1.5/ | Business vocabulary and rules |
| ORM2  | http://www.orm.net/ORM2/ | Fact-oriented modeling |
| BPMN2 | http://www.omg.org/spec/BPMN/2.0/ | Workflow modeling |

---

## Schema

### Normalized
```json
{{schema-normalized}}
```

### Denormalized
```json
{{schema-denormalized}}
```

---

## Activity Log

{{#logs}}
- `[{{timestamp}}]` **{{step-label}}** — {{message}}
{{/logs}}

---

## References
- [[Collibra Base URL]]: `https://api-vlab.collibra.com`
- [[Community]]: `0193febe-98bd-78ba-9301-7199dcb1607a`
- [[Workflow Docs]]: https://developer.collibra.com/workflows/workflow-documentation
- [[BPMN 2.0 Guide]]: https://www.omg.org/spec/BPMN/2.0/
