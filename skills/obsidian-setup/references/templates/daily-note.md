# <% tp.date.now("YYYY-MM-DD — dddd") %>

## Morning Check-in
- Energy:
- Top 3 priorities today:
  1.
  2.
  3.

## Active Projects
```dataview
TABLE WITHOUT ID link(file.link, title) AS "Project", next-action AS "Next Action", collaborators AS "With"
FROM "20-projects"
WHERE type = "project" AND status = "active"
SORT priority ASC
```

<%* if (tp.date.now("dddd") === "Friday") { %>
## SLT Friday Topic Request
- Topic request goes out at 3 PM ET
- Any topics to submit or accountability items to flag?
<%* } %>

<%* if (tp.date.now("dddd") === "Monday") { %>
## SLT Monday Prep
- Review topic submissions in Slack
- Prepare weekly update + draft agenda
- Check Airtable for open action items
<%* } %>

<%* if (tp.date.now("dddd") === "Tuesday") { %>
## SLT Tuesday Meeting
- **Type**: <% parseInt(tp.date.now("W")) % 4 === 0 ? "Strategic (3-4 hours)" : "Tactical (90 min)" %>
- Pre-meeting: Finalize agenda → Google Doc → post link to Slack
- Post-meeting: Trigger assessment, review coaching DMs
<%* } %>

## Work Log
-

## End of Day
- What got done:
- What's carrying over:
- Any project state to dump: (update the relevant Project Home Note)
