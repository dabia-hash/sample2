# Service Request System — Design Notes

Working notes for the IT Service Request (ticketing) system. Status: **brainstorming, not approved**.
These notes capture the decisions made so far, the open questions, and the proposed module layout.
They are not an implementation plan — that comes after this document is agreed.

Date started: 2026-09-09

---

## 1. Problem

Staff across several offices need to raise IT service requests — password/account resets,
network failures, and other IT services — and IT staff need to triage, assign, work, and close
them, with reporting on volume and resolution time.

---

## 2. Decisions Locked

| #   | Question                        | Decision                                                                                                                                                     |
| --- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | How are requests submitted?     | **Backend only** — every requester is a logged-in internal Odoo user. No portal, no website form, no email gateway in v1.                                      |
| 2   | What is an "office"?            | **A dedicated `trn.office` model.** Not `hr.department`, not `res.company`, not a free-text field.                                                              |
| 3   | How is the service list defined? | **A configurable catalog model** an IT admin edits in the UI. Each service carries its own default team, default priority, and target resolution time. No per-service custom questions in v1. |
| 4   | Lifecycle                       | **Simple ticket flow:** New → Assigned → In Progress → Resolved → Closed, plus Cancelled. No approval step. No requester re-confirmation before closing.        |
| 5   | Assignment                      | **IT teams + manual assignment.** The catalog entry sets a default team; a team lead or manager assigns an individual. No auto-routing.                         |
| 6   | V1 features                     | All four: **priority + target resolution deadline**, **chatter + email notifications**, **reporting dashboard**, **satisfaction rating**.                       |
| 7   | Visibility                      | **Own + office head + IT.** Requester sees only their own; office head sees their whole office; IT officers and managers see everything. Enforced by record rules. |
| 8   | Apps-menu visibility            | **No starter module.** Both modules stay `application=False` per `module-visibility.md`; install by clearing the Apps filter. Keeps the layout at two modules. |
| 9   | Priority representation         | **Selection for the UI, vocabulary code for reporting** — but derived, not duplicated. See "Priority without drift" below. |
| 10  | Manifest `category`             | **Match the shipped code:** `trn/Core` for `trn_office`, `trn/Operations` for `trn_service_request`. The principle docs (`Training Sample/{Domain}`) should be corrected to match in a separate cleanup. |

### Priority without drift

Decision 9 asks for two representations of priority. Storing both as independently editable fields
would let them disagree, so only one is writable:

- `priority` — `fields.Selection` (`low` / `normal` / `high` / `urgent`), **canonical**. Drives
  Odoo's star widget, inline list editing, and sorting.
- `priority_code_id` — `Many2one` to `trn.vocabulary.code`, **computed and stored, readonly**,
  mapped from `priority` via the `urn:trn:vocab:service-priority` vocabulary. Used by pivot/graph
  reporting and available to future integrations.

Because the vocabulary code is derived, the two cannot drift. Adding a priority level still means a
code change (the Selection), which is the trade-off accepted here — priority levels are stable in a
way that service categories are not.

### Consequences of these decisions

- Edition is **Odoo 19 Community** (the Docker image builds Odoo from source), so Enterprise
  Helpdesk is unavailable. We build our own models. This is also the cleaner fit for the `trn_*`
  conventions.
- No `portal`, `website`, or `mail.alias` work in v1. `mail` is still required for chatter.
- Because there is no approval step, `state` is a plain workflow selection — the one case
  `odoo-python.md` explicitly permits a static `fields.Selection`.

---

## 3. Proposed Module Layout

Two modules. The split follows the layer diagram in `docs/principles/module-architecture.md`,
where `trn_area` (Geographic management) already sits in Layer 1 — `trn.office` is the same shape
of concept and belongs at the same layer.

```
Layer 2  CAPABILITIES
└── trn_service_request     catalog, teams, requests, deadlines, ratings, reports
        │  depends
        ▼
Layer 1  FOUNDATION
├── trn_office              trn.office + res.users.office_id
└── trn_vocabulary          (exists) priority & category code lists
        │
        ▼
Layer 0  ODOO CORE          base, mail
```

### Why split `trn_office` out

Checked against the **Module Consolidation Decision** table in `module-architecture.md`:

- _Keep separate when:_ "lots of stored data (complex migration)" — yes, offices are master data.
- _Keep separate when:_ "high fan-out (many dependents)" — yes. Any future HR, inventory, or
  reporting module will want offices, and none of them should have to depend on a helpdesk.
- _Consolidate when:_ "mostly Python code, minimal DB schema" — does not apply.

Cost of the split: a second manifest, ACL file, and test suite. Roughly half a day of scaffolding.

### Why NOT split further

Rejected sub-modules, and why:

| Rejected                                                    | Reason                                                                                                                                                                              |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `trn_service_catalog` / `trn_service_team` as separate modules | A catalog entry and a team have no meaning without requests. They are always installed together and maintained by the same people — the consolidation table says merge.               |
| `trn_service_request_report`                                | The dashboard is pivot + graph **views on the existing model** — roughly 40 lines of XML, no new model, no new ACL. A separate module is only warranted if we later add a dedicated read-only SQL report model for heavy analytics. |
| `trn_service_request_rating`                                | Small enough (one wizard plus two fields) that a module boundary costs more than it saves. See the `auto_install` trap below.                                                        |

> **`auto_install` trap:** per `module-visibility.md`, a single-dependency extension module gets
> `auto_install=True` — meaning it installs automatically and is therefore _not_ optional in
> practice. Splitting rating out to "make it optional" would not actually make it optional under
> the project's own conventions. Another reason to keep it in.

---

## 4. Models

### `trn_office`

**`trn.office`** — a physical or organisational office that raises requests.

| Field            | Type                    | Notes                                    |
| ---------------- | ----------------------- | ---------------------------------------- |
| `name`           | Char                    | required, translate                      |
| `code`           | Char                    | required, unique (SQL constraint)        |
| `office_head_id` | Many2one `res.users`    | drives the office-head record rule       |
| `partner_id`     | Many2one `res.partner`  | address of the office                    |
| `parent_id`      | Many2one `trn.office`   | optional hierarchy (HQ → branch)         |
| `active`         | Boolean                 | archive instead of delete                |

**`res.users`** (inherit) — adds `office_id`, the default office for requests this user raises.

Groups: `group_office_manager` (configure offices). Read access for all internal users via
`base.group_user`, matching the pattern `trn_vocabulary` already uses.

### `trn_service_request`

**`trn.service.catalog`** — `_description = "Service Catalog Entry"` — one offered IT service.

| Field                     | Type                            | Notes                                 |
| ------------------------- | ------------------------------- | ------------------------------------- |
| `name`                    | Char                            | "Account Reset", "Network Failure"    |
| `code`                    | Char                            | unique                                |
| `category_id`             | Many2one `trn.vocabulary.code`  | vocabulary-backed, not a Selection    |
| `default_team_id`         | Many2one `trn.service.team`     |                                       |
| `default_priority_id`     | Many2one `trn.vocabulary.code`  |                                       |
| `target_resolution_hours` | Integer                         | feeds the deadline computation        |
| `description`, `sequence`, `active` |                       |                                       |

Seeded via data file: Account Reset, Network Failure, Hardware Repair, Software Installation,
Email Access, Printer Issue, Other.

**`trn.service.team`** — an IT team.

`name`, `code`, `team_lead_id` (`res.users`), `member_ids` (M2M `res.users`), `active`.

**`trn.service.request`** — the ticket. Inherits `mail.thread` and `mail.activity.mixin`.

| Field                                                            | Type                           | Notes                                                     |
| ---------------------------------------------------------------- | ------------------------------ | --------------------------------------------------------- |
| `name`                                                           | Char                           | `ir.sequence`, e.g. `SR/2026/00001`                        |
| `title`                                                          | Char                           | required, one-line summary                                 |
| `description`                                                    | Text                           |                                                            |
| `requester_id`                                                   | Many2one `res.users`           | defaults to current user                                   |
| `office_id`                                                      | Many2one `trn.office`          | defaults from requester, stored, editable                  |
| `catalog_id`                                                     | Many2one `trn.service.catalog` | required; sets team, priority, deadline                    |
| `priority`                                                       | Selection                      | `low`/`normal`/`high`/`urgent`, canonical, star widget      |
| `priority_code_id`                                               | Many2one `trn.vocabulary.code` | computed + stored from `priority`, readonly, for reporting  |
| `team_id`                                                        | Many2one `trn.service.team`    | default from catalog                                       |
| `assigned_user_id`                                               | Many2one `res.users`           | view domain narrows to `team_id.member_ids`; a Python `@api.constrains` enforces it, since a domain alone is not enforcement |
| `state`                                                          | Selection                      | `new` / `assigned` / `in_progress` / `resolved` / `closed` / `cancelled` |
| `submitted_date`, `assigned_date`, `resolved_date`, `closed_date` | Datetime                      | `{event}_date` per naming rules                            |
| `deadline_date`                                                  | Datetime                       | computed: `submitted_date + catalog.target_resolution_hours` |
| `is_overdue`                                                     | Boolean                        | computed, searchable, drives list/kanban decoration        |
| `resolution`                                                     | Text                           | required to leave `resolved`                               |
| `rating_value`                                                   | Selection `1`–`5`              | writable only by `requester_id`, only while `state = closed` |
| `rating_comment`                                                 | Text                           | optional, accompanies the rating                            |

Actions: `action_assign`, `action_start`, `action_resolve`, `action_close`, `action_cancel`,
`action_submit_rating`. Extension hooks `_pre_assign_hook()` / `_post_resolve_hook()` per the
project's hook-method pattern.

---

## 5. Security Matrix

Four groups in `trn_service_request`:

| Group                              | Read                          | Create | Write                            | Delete |
| ---------------------------------- | ----------------------------- | ------ | -------------------------------- | ------ |
| `group_service_request_user`       | own requests only             | yes    | own, while `new`                 | no     |
| `group_service_request_supervisor` | all requests from their office | yes    | no                               | no     |
| `group_service_request_officer`    | all                           | yes    | all (work the ticket)            | no     |
| `group_service_request_manager`    | all                           | yes    | all + configure catalog / teams  | yes    |

Record rules on `trn.service.request`:

- user — `['|', ('requester_id','=',user.id), ('assigned_user_id','=',user.id)]`
- office head — `[('office_id.office_head_id','=',user.id)]`
- officer / manager — unrestricted

Per `CLAUDE.md` **Known Pitfalls**, ACLs are the most common failure here. Every model gets a row
in `ir.model.access.csv` — including `trn.service.catalog` and `trn.service.team`, which are easy
to forget — and the security tests run as each group, never as admin.

---

## 6. Proposed File Tree

```
trn_office/
├── __init__.py  __manifest__.py
├── models/          office.py  res_users.py
├── views/           office_views.xml  res_users_views.xml  menus.xml
├── security/        security_groups.xml  ir.model.access.csv
├── demo/            office_demo.xml
├── tests/           test_office.py  test_security.py
└── readme/          DESCRIPTION.md

trn_service_request/
├── __init__.py  __manifest__.py
├── models/          service_catalog.py  service_team.py  service_request.py
├── views/           service_request_views.xml      (list/form/kanban/search/pivot/graph)
│                    service_catalog_views.xml  service_team_views.xml  menus.xml
├── wizard/          service_request_rating_wizard.py + view
├── security/        security_groups.xml  ir.model.access.csv  record_rules.xml
├── data/            ir_sequence.xml  service_vocabulary.xml  service_catalog_data.xml
│                    mail_template.xml
├── demo/            service_request_demo.xml
├── tests/           test_service_request.py   lifecycle + state transitions
│                    test_security.py          one case per group
│                    test_catalog.py           defaults propagate to the request
│                    test_deadline.py          computation + overdue flag
│                    test_rating.py
│                    test_demo_data.py
└── readme/          DESCRIPTION.md
```

Keeping each model in its own file matters here: `service_request.py` carries the lifecycle, the
deadline computation, and the assignment rules, and is the file most likely to grow past the point
where it can be held in context at once. If it does, the deadline logic is the first thing to lift
into an abstract `trn.service.deadline.mixin`.

---

## 7. Open Questions

1. **Office hierarchy.** Is `parent_id` on `trn.office` actually needed in v1, or is a flat list
   enough? Proposed default: include the field, leave it unused — it is cheap to add now and
   awkward to add after offices carry data.
2. **Who closes a ticket?** The chosen lifecycle has no requester confirmation, so IT moves
   Resolved → Closed. Proposed default: IT closes manually in v1; automatic closure after N days
   is a scheduled-action feature that can be added later without a schema change.

### Deviations from the principle docs, to be reconciled

Both were resolved in favour of shipping, and both leave `docs/principles/` out of date:

- **`module-architecture.md`** uses priority as its worked example of "never use a Selection".
  Decision 9 makes a documented exception. The principle doc should record the exception rather
  than have the code silently contradict it.
- **`module-visibility.md`** mandates `Training Sample/{Domain}` categories, which no shipped
  module follows. Decision 10 follows the code instead.

---

## 8. Suggested Sequencing

Large enough to be worth two implementation plans rather than one:

1. **`trn_office`** — small, self-contained, no dependency on anything unbuilt. Ships and is
   testable on its own, and proves the security-group pattern before the harder module uses it.
2. **`trn_service_request`** — catalog and teams first (they are plain master data), then the
   request lifecycle, then deadlines, chatter, rating, and the pivot/graph views.

---

## 9. Implementation Notes

What the build changed relative to the design above.

### Odoo 19 demo data is off by default

`--with-demo` has `my_default=False` in Odoo 19's `tools/config.py`, so `--without-demo` is
now the default for new databases. No demo file loads during `./odoo-project test`, which
means a test asserting demo records exist can never pass in this harness.

`demo/service_request_demo.xml` still ships (five requests spanning New through Closed, for
`./odoo-project start`), but the planned `test_demo_data.py` was replaced by
**`test_seed_data.py`**, which covers the `data/` records that load on every install: the
sequence, both vocabularies, every catalogue entry's routing and target time, and the
derived priority code. Validating the demo file itself would need a `--with-demo` option on
`odoo-project test`, which does not exist yet.

### Odoo 19 API corrections found by running the tests

- Search views: `<group expand="0" string="Group By">` is rejected by the RNG schema.
  Odoo 19 uses `<group name="group_by">`.
- `web_ribbon` belongs to the `web` module; using it in `trn_office` would have meant
  declaring a `web` dependency for decoration, so the widget was dropped instead.
- Chatter is `<chatter/>`, confirmed against core views.
- `SELF_READABLE_FIELDS` is a `@property` returning a list, extended with
  `super().SELF_READABLE_FIELDS + ["office_id"]`.
- `ir.sequence.next_by_code` needs only read access, which `base.group_user` has, so
  request numbering needs no `sudo()`.

### Additions to the model sketch

- **`team_member_ids`** on `trn.service.request` — a related Many2many to
  `team_id.member_ids`, used only to narrow the assignee picker in the form. Enforcement
  stays in `_check_assignee_is_team_member`.
- **Read and write record rules are separate.** `rule_service_request_own_write` restricts
  a requester to their own New requests. Without a write rule, model-level write access
  would let a requester edit any request whose id they could guess — the read rule alone
  does not prevent that.
- **The rating wizard reads through `sudo()`** before checking authorisation, so an
  unauthorised caller gets a clear `UserError` instead of an opaque `AccessError`, then
  writes only the two rating fields.

### Test results

| Module | Tests |
| ------ | ----- |
| `trn_office` | 12 passing |
| `trn_service_request` | 60 passing |

---

## 10. Explicitly Out of Scope for V1

Portal and website submission · email-to-ticket via `mail.alias` · SLA escalation and breach
notifications · auto-assignment and round-robin routing · per-service custom question forms ·
knowledge base and canned responses · multi-company · time tracking and billing · REST API.
