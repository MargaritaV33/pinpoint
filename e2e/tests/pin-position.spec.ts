import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Independent test: its own studio signup, its own room, its own upload.
// Exercises frontend/src/lib/pins/coords.ts's percentToStyle (left/top as
// literal `%` CSS values on an absolutely-positioned marker inside a
// `relative` wrapper around the <img>) at three viewport sizes, to prove
// the mechanism — not just the stored percentage — survives resize.
//
// Note on scope (see the issue comment for the full explanation): the
// issue describes this as "studio can place its own pin via the same
// click-to-place flow Workspace/ImageViewer expose to the studio role —
// no guest context needed for this test". Against the real app, that flow
// does not exist for the studio role: `rooms.$roomId.tsx` never passes
// `onCreatePin` to `<Workspace role="studio" .../>`, so `canPin` is always
// false for the studio, and the only pin-creation endpoint in
// `openapi.yaml` is `POST /guest/{guestToken}/pins` — there is no studio
// equivalent. Pin creation is guest-only in the real running app. This
// test therefore places the pin from a guest context (the only context
// that can create one) and then measures the marker's position on that
// same page. The marker-rendering mechanism under test
// (`ImageViewer`/`percentToStyle`) is identical for both roles, so this
// still exercises exactly what the criterion names; only the "no guest
// context needed" clause could not be honored as written.

const FIXTURE = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "render.jpg");
const TOLERANCE = 0.5; // percentage points

async function measurePinPercent(page: import("@playwright/test").Page) {
  const pin = page.getByRole("button", { name: /^Pin 1:/ });
  const image = page.locator("img").first();
  const pinBox = await pin.boundingBox();
  const imageBox = await image.boundingBox();
  if (!pinBox || !imageBox) throw new Error("Could not read bounding boxes");
  const pinCenterX = pinBox.x + pinBox.width / 2;
  const pinCenterY = pinBox.y + pinBox.height / 2;
  const xPercent = ((pinCenterX - imageBox.x) / imageBox.width) * 100;
  const yPercent = ((pinCenterY - imageBox.y) / imageBox.height) * 100;
  return { xPercent, yPercent };
}

test("pin position survives viewport resize", async ({ browser }) => {
  const studio = await browser.newContext();
  const studioPage = await studio.newPage();

  const uniqueEmail = `studio+${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.pinpoint.test`;
  const studioPassword = "e2e-test-password";
  const roomTitle = `E2E Resize — ${Date.now()}`;

  await studioPage.goto("/login");
  await studioPage.getByRole("button", { name: "New studio? Create an account" }).click();
  await studioPage.getByLabel("Email").fill(uniqueEmail);
  await studioPage.getByLabel("Password").fill(studioPassword);
  await studioPage.getByRole("button", { name: "Create account" }).click();
  await expect(studioPage).toHaveURL("/");

  await studioPage.getByRole("button", { name: "New room" }).click();
  await studioPage.getByLabel("Title").fill(roomTitle);
  await studioPage.getByLabel("Client name").fill("E2E Resize Client");
  await studioPage.getByRole("button", { name: "Create room" }).click();
  await expect(studioPage).toHaveURL(/\/rooms\/.+/);

  await studioPage.getByRole("button", { name: "Upload renders" }).click();
  await studioPage.locator('input[type="file"]').setInputFiles(FIXTURE);
  await studioPage.getByRole("button", { name: /^Upload \(1\)$/ }).click();
  await expect(studioPage.getByRole("button", { name: "Upload renders" })).toBeVisible();

  await studioPage.getByRole("button", { name: "Guest link" }).click();
  const toast = studioPage.getByText(/\/g\//).first();
  await expect(toast).toBeVisible();
  const toastText = (await toast.textContent()) ?? "";
  const match = toastText.match(/https?:\/\/\S+\/g\/\S+/);
  if (!match) throw new Error(`Could not find guest URL in toast text: "${toastText}"`);
  const guestUrl = match[0];
  await studio.close();

  const guest = await browser.newContext();
  const page = await guest.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(guestUrl);
  await page.getByLabel("Your name").fill("Resize Tester");
  await page.getByRole("button", { name: "Continue" }).click();

  const image = page.locator("img").first();
  await expect(image).toBeVisible();
  const box = await image.boundingBox();
  if (!box) throw new Error("Image bounding box not available");
  await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.6);
  await page.getByPlaceholder("What should change?").fill("Resize check pin");
  await page.getByRole("button", { name: "Add pin" }).click();
  await expect(page.getByRole("button", { name: /^Pin 1:/ })).toBeVisible();

  const sizes = [
    { width: 1280, height: 800 },
    { width: 800, height: 600 },
    { width: 1600, height: 1000 },
  ];

  for (const size of sizes) {
    await page.setViewportSize(size);
    // Let the layout settle before measuring.
    await expect(page.getByRole("button", { name: /^Pin 1:/ })).toBeVisible();
    const { xPercent, yPercent } = await measurePinPercent(page);
    expect(xPercent).toBeGreaterThan(40 - TOLERANCE);
    expect(xPercent).toBeLessThan(40 + TOLERANCE);
    expect(yPercent).toBeGreaterThan(60 - TOLERANCE);
    expect(yPercent).toBeLessThan(60 + TOLERANCE);
  }

  await guest.close();
});
