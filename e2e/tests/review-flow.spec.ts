import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Full scenario from _docs/test-scenario.md, driven through two isolated
// BrowserContexts (studio + guest) against the real compose stack. One
// test: the steps are inherently sequential and share one room/guest link,
// so splitting them would just duplicate setup without real independence.
//
// This file never reloads the page (no such call appears anywhere below)
// — every "without reload" assertion relies solely on the app's own
// 3-second polling (POLL_MS in frontend/src/lib/queries.ts) plus
// Playwright's auto-retrying `expect`.

const FIXTURE = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "render.jpg");

test("studio and guest review a room end to end", async ({ browser }) => {
  const studio = await browser.newContext();
  const guest = await browser.newContext();
  const studioPage = await studio.newPage();
  const guestPage = await guest.newPage();

  const uniqueEmail = `studio+${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.pinpoint.test`;
  const studioPassword = "e2e-test-password";
  const roomTitle = `E2E Villa — ${Date.now()}`;
  const clientName = "E2E Client";
  const guestDisplayName = `Guest ${Math.random().toString(36).slice(2, 7)}`;

  // --- Studio: sign up a fresh account -------------------------------
  await studioPage.goto("/login");
  await studioPage.getByRole("button", { name: "New studio? Create an account" }).click();
  await studioPage.getByLabel("Email").fill(uniqueEmail);
  await studioPage.getByLabel("Password").fill(studioPassword);
  await studioPage.getByRole("button", { name: "Create account" }).click();
  await expect(studioPage).toHaveURL("/");

  // --- Studio: create a room ------------------------------------------
  await studioPage.getByRole("button", { name: "New room" }).click();
  await studioPage.getByLabel("Title").fill(roomTitle);
  await studioPage.getByLabel("Client name").fill(clientName);
  await studioPage.getByRole("button", { name: "Create room" }).click();
  await expect(studioPage).toHaveURL(/\/rooms\/.+/);

  // --- Studio: upload the fixture render -------------------------------
  await studioPage.getByRole("button", { name: "Upload renders" }).click();
  await studioPage.locator('input[type="file"]').setInputFiles(FIXTURE);
  const titleInput = studioPage.locator('input[id^="t"]').first();
  await expect(titleInput).not.toHaveValue("");
  await studioPage.getByRole("button", { name: /^Upload \(1\)$/ }).click();
  await expect(studioPage.getByRole("button", { name: "Upload renders" })).toBeVisible();

  // --- Studio: click "Guest link" and read the URL from the toast -----
  await studioPage.getByRole("button", { name: "Guest link" }).click();
  const toast = studioPage.getByText(/\/g\//).first();
  await expect(toast).toBeVisible();
  const toastText = (await toast.textContent()) ?? "";
  const match = toastText.match(/https?:\/\/\S+\/g\/\S+/);
  if (!match) throw new Error(`Could not find guest URL in toast text: "${toastText}"`);
  const guestUrl = match[0];

  // --- Guest: open the guest link, set display name --------------------
  await guestPage.goto(guestUrl);
  await guestPage.getByLabel("Your name").fill(guestDisplayName);
  await guestPage.getByRole("button", { name: "Continue" }).click();

  // --- Guest: place a pin at 40%/60% of the image, write the first comment, submit ---
  const guestImage = guestPage.locator("img").first();
  await expect(guestImage).toBeVisible();
  const guestBox = await guestImage.boundingBox();
  if (!guestBox) throw new Error("Image bounding box not available");
  await guestPage.mouse.click(guestBox.x + guestBox.width * 0.4, guestBox.y + guestBox.height * 0.6);

  const fixRadio = guestPage.getByRole("radio", { name: "Fix" });
  await expect(fixRadio).toHaveAttribute("aria-checked", "true");
  const firstCommentText = "Change the sofa fabric to linen";
  await guestPage.getByPlaceholder("What should change?").fill(firstCommentText);
  await guestPage.getByRole("button", { name: "Add pin" }).click();

  // --- Studio: see the pin without reloading, reply, resolve ----------
  const studioPinButton = studioPage.getByRole("button", { name: /^Pin 1:/ });
  await expect(studioPinButton).toBeVisible();
  await studioPinButton.click();
  await expect(studioPage.getByText(firstCommentText)).toBeVisible();

  const studioReplyText = "We'll switch the sofa to linen in the next pass.";
  await studioPage.getByPlaceholder("Reply…").fill(studioReplyText);
  await studioPage.getByRole("button", { name: "Reply" }).click();
  await expect(studioPage.getByText(studioReplyText)).toBeVisible();

  await studioPage.getByRole("button", { name: "Resolve" }).click();

  // --- Guest: see the reply and resolved status without reloading -----
  await expect(guestPage.getByText(studioReplyText)).toBeVisible();
  const guestStatusText = guestPage.locator("div.capitalize.text-muted-foreground");
  await expect(guestStatusText).toHaveText("resolved");

  const guestReplyText = "Thanks — one more thing, can we also lighten the rug?";
  await guestPage.getByPlaceholder("Reply…").fill(guestReplyText);
  await guestPage.getByRole("button", { name: "Reply" }).click();
  await expect(guestStatusText).toHaveText("open");

  // --- Guest: approve the round ----------------------------------------
  await guestPage.getByRole("button", { name: "Approve round" }).click();
  await expect(guestPage.getByRole("button", { name: "Round approved" })).toBeVisible();

  // --- Studio: see approved status + "approved by" text, close the room ---
  await expect(studioPage.getByText("approved", { exact: true })).toBeVisible();
  await expect(studioPage.getByText(`· approved by ${guestDisplayName}`)).toBeVisible();

  await studioPage.getByRole("button", { name: "Close room" }).click();
  await studioPage.getByRole("alertdialog").getByRole("button", { name: "Close room" }).click();
  await expect(studioPage.getByText("This room is closed and read-only.")).toBeVisible();

  // --- Guest: see the closed-room banner without reloading -------------
  await expect(
    guestPage.getByText(
      "This review room has been closed by the studio. You can still look, but no new feedback can be added.",
    ),
  ).toBeVisible();

  await studio.close();
  await guest.close();
});
