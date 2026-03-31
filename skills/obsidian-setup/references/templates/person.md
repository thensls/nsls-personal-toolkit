---
role:
org: NSLS
---

# person

> **To use**: Duplicate this file, rename it to the person's full name, then update the Dataview query below — replace `[[person]]` with `[[Their Name]]`.

## Projects Together
```dataview
TABLE status, priority AS "Pri", next-action AS "Next Action", last-touched AS "Last Touched"
FROM "20-projects"
WHERE type = "project" AND contains(collaborators, [[person]])
SORT priority ASC
```

## 1:1 Notes
-

## Background
- **Role**:
- **Email**:
