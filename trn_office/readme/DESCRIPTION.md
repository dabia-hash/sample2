Office reference data for trn modules.

Provides a single model, `trn.office`, representing a place of work that raises and owns
operational records. Offices are deliberately independent of `hr.department` and
`res.company`: a module can scope records to an office without pulling in the HR app or
multi-company machinery.

Staff are linked to an office through an `office_id` field added to `res.users`. Downstream
modules read that field to default the office on records a user creates, and use
`office_head_id` to build record rules that give an office head visibility of their own
office's records.

### Key Capabilities

- Define offices with a unique short code, shown as `[CODE] Name` in pickers
- Optional parent/child hierarchy for organisations with branch structures, protected
  against cycles
- Nominate an office head, the anchor for downstream office-scoped record rules
- Link an office to a `res.partner` for its physical address
- Archive retired offices without losing the records that reference them

### Key Models

- `trn.office` — office definition with code, hierarchy, and office head

### Configuration

Settings > Offices > Offices

### UI Location

Settings > Offices > Offices (list and form views)
The office of a user is set on Settings > Users & Companies > Users.

### Security

- `group_office_manager` — create, edit and delete offices
- Read access for all internal users comes from the `base.group_user` ACL row, so office
  pickers resolve without granting edit rights

### Extension Points

- **Inheritable model**: `trn.office` can be extended via `_inherit`
- **`office_id` on `res.users`**: registered in `SELF_READABLE_FIELDS`, so an ordinary user
  can read their own office — required for defaulting an office on records they create
- **View extension group**: the office form includes an invisible `<group>`
  (`additional_office_details`) for downstream modules to inject fields

### Dependencies

- `base` — Odoo core
