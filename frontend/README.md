# Render Review

Create "Pinpoint", a web app for client feedback on architectural visualization renders.

SPEC
Two kinds of users. A STUDIO user has an account (email + password): they see a list of their review rooms (title, client name, created date, status open/approved/closed, count of open pins), create a room, open a room, upload one or more JPG/PNG renders (max 15 MB each) with a title, copy the room's guest link, switch between the room's images, see numbered pins on each image, read and reply in each pin's comment thread, mark a pin resolved or reopen it, mark an image "superseded" when a corrected render replaces it (its pins stay readable), export the open pins of the room as a plain-text list grouped by image, and close the room.
A CLIENT has no account: they open the guest link, type a display name once (remembered in the browser), switch between images, click a point on an image to create a pin, choose the pin type (fix / question / like), write the first comment, reply in any thread, and press "Approve round" when everything is fine. Clients cannot resolve pins, upload, supersede or close.
A PIN is a point stored as percentages of image width/height so it stays in place when the window resizes; it has a sequential number per image, a type (fix / question / like, shown as marker colour), a status open/resolved (like-pins have no status), and a thread of comments (text, author name, author role studio/client, timestamp). A closed room is read-only for the client with a visible message. New pins and replies should appear without a full page reload (poll every few seconds).

TECHNICAL REQUIREMENTS
- React + TypeScript + Vite. Keep the app a plain client-side SPA (no server-side rendering, no Lovable Cloud / Supabase, no edge functions): the backend will be a separate FastAPI service built later from an OpenAPI contract.
- Centralize every backend call in one services layer under src/lib/api/ (one typed client interface) and create a mock implementation of it with seeded demo data (one studio user, two rooms, a few images and pins) so the whole app runs without a real backend. Nothing outside src/lib/api/ may call the network.
- Pin coordinate math (click position ↔ percentages) must live in a pure, testable module.
- Add tests (Vitest) for the pin coordinate math and for the API client/mock.
- Clean, calm, image-first UI: the render is the hero, pins are small numbered markers, the thread opens in a side panel. Desktop first, usable on a tablet.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/a04f11df-5098-45a9-bb88-75e92cf10153).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
