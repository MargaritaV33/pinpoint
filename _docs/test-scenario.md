# Manual test scenario

This is the scenario we run by hand after every milestone. It becomes the
integration tests and the Playwright end-to-end test.

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
