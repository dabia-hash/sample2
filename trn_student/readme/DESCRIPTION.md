Core student records for a registrar: a unique ID number, the student's name, the
course they are enrolled in, and their year.

Each student is keyed by an ID number the registrar types in — the number the
institution already issues — and a database constraint refuses a second student with
the same one. Courses are their own records, so a course is renamed once and every
student follows.

### Key Models

- `trn.student` — the student record
- `trn.course` — one course offered, e.g. BSIT

### Dependencies

- `base` only
