# Pinpoint — product specification

Pinpoint is a small web app for collecting client feedback on architectural
visualization renders. A studio creates a review room, uploads the renders of a
delivery round, and shares one link. The client opens the link, drops numbered
pins on the images and writes what they want changed. The studio replies,
resolves pins, and uploads the corrected renders. Feedback stops living in
WhatsApp screenshots and email threads.

Working name: Pinpoint (placeholder).

## Problem

Archviz feedback today is a screenshot with a red circle, a voice note, or an
email saying "the lamp on the left — no, the other left". Comments are not
anchored to the image, nobody knows which ones are done, and the history is lost
when the next round arrives. Both sides waste time reconstructing what was asked.

## Users

- **Studio user** — has an account. Creates rooms, uploads images, replies to
  pins, resolves them, closes the room.
- **Client** — no account. Opens a guest link, enters a display name once (kept
  in the browser), places pins, comments, replies, approves the round.

## Core concepts

- **Room** — one review round for one project: title, client name, status
  (`open` / `approved` / `closed`), a guest token, a set of images.
- **Image** — a render inside a room: file, title, order, status
  (`active` / `superseded`). Uploaded as JPG or PNG, max 15 MB, stored in the
  database for v1.
- **Pin** — a point on an image, stored as percentages of width and height so
  it survives resizing. Has a sequential number within the image, a type
  (`fix` / `question` / `like`), a status (`open` / `resolved`; `like` pins have
  no status), and a thread of comments.
- **Comment** — text, author display name, author role (`studio` / `client`),
  timestamp. The first comment is created together with the pin.

## User stories

### Studio

1. As a studio user I can sign up and log in with email and password.
2. I can see my rooms with title, client name, created date, status and the
   count of open pins.
3. I can create a room with a title and client name.
4. I can upload one or more images to a room and give each a title.
5. I can copy the room's guest link.
6. I can open an image, see all pins with their numbers and types, and read
   each thread.
7. I can reply in a pin's thread.
8. I can mark a pin resolved and reopen it.
9. I can mark an image superseded when I upload the corrected render; its pins
   stay readable for history.
10. I can export the open pins of a room as a plain list (text/Markdown) grouped
    by image, to paste into a task tracker.
11. I can close a room; a closed room is read-only for the client.
12. I can filter the pins of an image: all / open / fix / question / like.
13. I see, on the image switcher, how many open pins each image has.

### Client

14. As a client I can open the guest link without an account and enter a display
    name once.
15. I can switch between the images of the room.
16. I can click a point on an image to create a pin, choose its type, and write
    the first comment.
17. I can reply in any thread.
18. I can see a pin's status and reopen a resolved pin by replying to it.
19. I can press **Approve round** when everything is fine; the room becomes
    `approved` and the studio sees it. If a client adds a new `fix` or
    `question` pin afterwards, the room goes back to `open`.
20. I see new pins and replies without a full page reload (light polling).

## Acceptance criteria (MVP)

- Guest link works in a fresh private window with no login.
- A pin placed at 40 % / 60 % appears at the same spot on a resized window.
- Pin numbers are per image and stable (deleting is not in v1).
- `like` pins show no resolve control; `fix` and `question` do.
- Client cannot resolve pins, close rooms, upload or supersede images.
- Studio cannot act on rooms that are not theirs; a guest token only opens its
  own room.
- The pin filter and the per-image open-pin count agree with the pin list.
- A closed room rejects new pins and comments from the client with a visible
  message.
- Upload rejects files that are not JPG/PNG or exceed 15 MB with a clear error.
- Data survives a backend restart (persistence).
- All of the above works through `docker compose up --build` with no manual
  steps.

## Manual test scenario

1. Sign up as the studio in window A, create room "Villa K — round 1", upload
   two renders, copy the guest link.
2. Open the guest link in a private window B, enter the name "Client".
3. In B, place a `fix` pin on image 1 with "Change the sofa fabric to linen" and
   a `like` pin on image 2.
4. In A, see both pins, reply to the fix pin, resolve it.
5. In B, see the reply and the resolved state without reloading; reply again
   and see it reopen.
6. In A, upload a third image, mark image 1 superseded, export open pins.
7. In B, press **Approve round**; in A, see the room as approved; close it.
8. Restart the backend; everything is still there.

## Non-goals (v1)

- Image versioning / compare view (new render = new image, old one superseded)
- Realtime via WebSockets (polling is enough)
- Client accounts, teams, roles beyond studio/client
- Notifications (email, Slack), @mentions
- Drawing tools, arrows, regions — a pin is a point
- Deleting or moving pins
- Billing, white-label, multi-studio tenancy
- File storage outside the database (S3 etc.)

Ideas that were cut or came up later live in `_local/make-it-better.md` (local, not committed).
