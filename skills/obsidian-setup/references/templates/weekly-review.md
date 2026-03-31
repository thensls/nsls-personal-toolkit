# Week <% tp.date.now("YYYY-[W]WW") %>

## SLT Meeting Debrief
- Meeting type: Tactical / Strategic
- Key decisions:
- My assessment:
- Coaching themes to watch:

## Portfolio Review
![[20-projects/_portfolio-index]]

## Projects Touched This Week
```dataview
LIST
FROM "20-projects"
WHERE last-touched >= date(today) - dur(7 days)
SORT last-touched DESC
```

## Projects NOT Touched This Week
```dataview
LIST
FROM "20-projects"
WHERE status = "active" AND last-touched < date(today) - dur(7 days)
SORT priority ASC
```

## Next Week Priorities
1.
2.
3.

## Personal Reflection
> (Move to encrypted journal if needed)
