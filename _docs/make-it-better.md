# Make it better

Ideas that are out of scope for the course MVP. Nothing here is a commitment.
Add to the list whenever something comes up; decide after submission.

| # | Idea | Why it was cut | Notes |
|---|------|----------------|-------|
| 1 | Image versioning: an image has versions, pins belong to a version, side-by-side compare, "carry open pins to the new version" | A day of work; v1 uses supersede instead | Needed before any real studio use |
| 2 | Realtime updates over WebSockets (pins and replies appear instantly) | Polling is enough for v1; one less thing to break on Render | Alexey's canvas app shows the pattern |
| 3 | Delete / move a pin (studio), edit own comment within 5 minutes | Keeps numbering and history simple in v1 | |
| 4 | Pin regions (rectangles) and arrows, not only points | Scope | |
| 5 | Email notification to the studio on new client pins, to the client on replies | Scope | |
| 6 | Export open pins as PDF / CSV, and as tasks into a tracker | v1 exports plain text / Markdown | |
| 7 | Client-side filters: show only open / only fix / only mine | Scope | |
| 8 | Store images outside the database (S3-compatible) with thumbnails | DB storage is fine for a demo | Needed for real file sizes |
| 9 | Multiple studio users per studio, roles | Scope | |
| 10 | Room templates: "exterior round", "interior round" with preset image titles | Scope | |
| 11 | Pins carry a "render view" tag (camera name) so the export groups by view | Scope | |

## Candidates to fold into the EW Assistant client portal (private)

- Pins-on-image as a component inside the portal's delivery view
- Options Room (client chooses between alternatives) — see the separate note; it
  stays out of this repo on purpose
