IT service request ticketing for staff across multiple offices.

Staff raise a request against a configurable service — account reset, network failure,
hardware repair and so on — and IT triages, assigns, works and closes it. The chosen
service drives routing, urgency and the resolution deadline, so requesters do not have to
know which team handles what.

Requests run through New → Assigned → In Progress → Resolved → Closed, and may be
cancelled before closure. Each transition is guarded: a request cannot be assigned without
an owner, started before assignment, resolved without a resolution note, or closed before
it is resolved.

### Key Capabilities

- Configurable service catalogue with per-service default team, default priority and
  target resolution time
- Automatic deadline from the service's target resolution hours, with a searchable
  `is_overdue` flag that drives red decoration in list and kanban views
- Assignment restricted to members of the handling team, enforced by a Python constraint
- Chatter, followers and activity tracking on every request; the requester is notified by
  email when their request is resolved
- Satisfaction rating left by the requester after closure, through a wizard that verifies
  the caller before recording the score
- Email intake: a team may own an address, and mail sent to it opens a request routed to
  that team
- Pivot and graph analysis by office, service, category, team and status

### Key Models

- `trn.service.request` — the ticket, inheriting `mail.thread` and `mail.activity.mixin`
- `trn.service.catalog` — one offered IT service and its defaults
- `trn.service.team` — an IT team; the team lead is always a member
- `trn.service.request.rating.wizard` — records a requester's satisfaction score

### Configuration

Service Requests > Configuration > Service Catalog
Service Requests > Configuration > Teams

Offices are configured in the `trn_office` module, at Settings > Offices > Offices.

### UI Location

Service Requests > Requests > All Requests (list, kanban, form, pivot, graph)
Service Requests > Reporting > Analysis (pivot and graph)

### Security

- `group_service_request_user` — raise requests; see and edit only your own, and only
  while the request is still New
- `group_service_request_supervisor` — additionally see every request raised by the
  office whose `office_head_id` is this user
- `group_service_request_officer` — see and work every request from any office
- `group_service_request_manager` — additionally configure the catalogue and teams, and
  delete requests

Read and write are separated in the record rules: `rule_service_request_own_read` grants
sight of your own and assigned requests, while `rule_service_request_own_write` narrows
editing to your own requests that are still New. Without that second rule, model-level
write access would let a requester edit any request whose id they could guess.

### Email Intake

A team may be given an email address (`alias_name` plus `alias_domain_id`, from Odoo's
`mail.alias.mixin.optional`). Mail sent there opens a request routed to that team, using
the team's `default_catalog_id` as the service — a team with an address must have one,
because `catalog_id` is required and a missing default would otherwise fail deep inside the
mail gateway.

**Only known internal users may raise a request by email.** `_alias_get_error` on
`trn.service.team` resolves the sender against active, non-portal `res.users` by normalised
email and bounces anything else, so an outsider cannot fill the queue. The rejection is
raised as a non-config `AliasError`, which bounces the message without flagging the alias
itself as broken.

Replies thread onto the existing request as chatter. `message_update` strips `state`,
`priority`, `resolution`, `assigned_user_id`, `team_id`, `catalog_id` and the rating fields
from inbound updates: an email is a comment, never a command.

Production use needs a configured `mail.alias.domain` and working inbound (catchall) mail.
The tests drive the gateway directly, so they pass without either.

### Priority

`priority` is a static `fields.Selection`, which Odoo's star widget and queue ordering
require. `priority_code_id` is computed and stored from it against the
`urn:trn:vocab:service-priority` vocabulary, giving reporting and integrations a stable
coded value. Because the code is derived rather than entered, the two cannot disagree.
This is a deliberate, documented exception to the vocabulary-over-selection rule in
`docs/principles/module-architecture.md`.

### Extension Points

- **Hook methods**: `_pre_assign_hook()` and `_post_resolve_hook()` on
  `trn.service.request`
- **Inheritable models**: all four models can be extended via `_inherit`
- **View extension groups**: the request, catalogue and team forms each include an
  invisible `<group>` (`additional_request_details`, `additional_catalog_details`,
  `additional_team_details`) for downstream modules to inject fields

### Demo Data

`demo/service_request_demo.xml` ships five requests spanning New through Closed. Odoo 19
does not install demo data in new databases unless `--with-demo` is passed, so these
records will not appear in a default install or in the module's test runs.

### Dependencies

- `mail` — chatter, followers, activities and the resolution email
- `trn_office` — offices and the `office_id` field on `res.users`
- `trn_vocabulary` — priority and service-category code lists
