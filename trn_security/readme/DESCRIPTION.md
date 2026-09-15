Foundation module (Layer 1) owning the security vocabulary the domain modules share.

Two things live here and nowhere else:

- **`ir.module.category` records.** Categories group privileges in the user settings UI.
  Defining them centrally keeps one category per domain instead of each module inventing
  its own, which is what `./odoo-project audit-security` enforces.
- **`group_trn_admin`.** A single administrator group that implies every domain module's
  manager group, so one assignment grants administration across the whole suite rather
  than ticking a box per module.

Domain modules depend on this module, reference its categories from their own
`res.groups.privilege` records, and link their manager group into `group_trn_admin`.

### Dependencies

- `base` only
