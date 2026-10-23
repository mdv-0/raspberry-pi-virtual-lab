import { test, expect } from "@playwright/test";
import fs from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const exec = promisify(execFile);

test("host-only consoles: UI controls real QEMU and exposes a working PTY", async ({
  page,
  request,
}, testInfo) => {
  const sockets: string[] = [];
  page.on("websocket", (ws) => sockets.push(ws.url()));
  const initial = await (await request.get("/api/status")).json();
  expect(initial.power).toBe("OFF");
  const sshPort = initial.network.ssh.match(/-p (\d+)/)[1];
  const guest = async (command: string) =>
    (
      await exec(
        "ssh",
        [
          "-i",
          "../images/lab_key",
          "-p",
          sshPort,
          "-o",
          "StrictHostKeyChecking=no",
          "-o",
          "UserKnownHostsFile=/dev/null",
          "-o",
          "ConnectTimeout=2",
          "-o",
          "BatchMode=yes",
          "root@127.0.0.1",
          command,
        ],
        { timeout: 5000 },
      )
    ).stdout;
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Board workspace" }),
  ).toBeVisible();
  await expect(page.locator("canvas,.xterm,.console-panel")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Use browser console", exact: true }),
  ).toHaveCount(0);
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /Storage images/ })
    .click();
  await page.getByLabel("Disk name").fill("Host terminal integration");
  await page.getByRole("button", { name: "Create disk", exact: false }).click();
  const disk = page
    .locator(".disk")
    .filter({ hasText: "Host terminal integration" })
    .last();
  await expect(disk).toBeVisible();
  await disk.getByRole("button", { name: "Insert", exact: true }).click();
  await expect(disk).toContainText("INSERTED");
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Workspace", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Connect to host", exact: true })
    .click();
  const endpoint = page.getByTestId("uart-endpoint");
  await expect(endpoint).toBeVisible();
  const path = await endpoint.innerText();
  expect(fs.statSync(path).isCharacterDevice()).toBe(true);
  await page.getByRole("button", { name: "Power on", exact: true }).click();
  await expect(page.getByTestId("power-state")).toContainText("RUNNING");
  await expect
    .poll(
      async () => {
        try {
          return await guest("uname -m");
        } catch {
          return "";
        }
      },
      { timeout: 60000 },
    )
    .toContain("aarch64");
  // Run a real serial client outside the browser, as in a VS Code host terminal.
  const script = `import serial,sys,time
port=serial.Serial(sys.argv[1],115200,timeout=.2)
def until(token):
 data=bytearray(); deadline=time.monotonic()+20
 while token not in data:
  if time.monotonic()>deadline: raise RuntimeError(repr(data))
  data.extend(port.read(4096))
 return bytes(data)
try:
 port.write(b'\\r'); until(b'login:')
 port.write(b'student\\r'); until(b'Password:')
 port.write(b'student\\r'); until(b'$')
 port.write(b"printf 'EXTERNAL_%s\\\\n' VERIFIED\\r")
 assert b'EXTERNAL_VERIFIED' in until(b'EXTERNAL_VERIFIED')
 print('host PTY verified')
finally: port.close()
`;
  expect(
    (
      await exec("../.venv/bin/python", ["-c", script, path], {
        timeout: 90000,
      })
    ).stdout,
  ).toContain("host PTY verified");
  await page.getByRole("button", { name: "DISPLAY", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Open monitor", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator("canvas,.xterm,.console-panel")).toHaveCount(0);
  expect(sockets).toEqual([]);
  expect(
    (await request.post("/api/uart", { data: { mode: "browser" } })).status(),
  ).toBe(422);
  await page.getByRole("button", { name: "ETHERNET", exact: true }).click();
  await page
    .getByRole("button", { name: "Disconnect Ethernet", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/status")).json()).network.link,
    )
    .toBe(false);
  await page
    .getByRole("button", { name: "Connect Ethernet", exact: true })
    .click();
  await expect
    .poll(
      async () => {
        try {
          return (await guest("cat /sys/class/net/eth0/carrier")).trim();
        } catch {
          return "";
        }
      },
      { timeout: 30000 },
    )
    .toBe("1");
  await page.getByRole("button", { name: "Shut down", exact: true }).click();
  await expect(page.getByTestId("power-state")).toContainText("OFF", {
    timeout: 30000,
  });
  await page.getByRole("button", { name: "UART", exact: true }).click();
  await page.screenshot({
    path: testInfo.outputPath("ui-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("ui-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("themes persist and image deletion requires eject and confirmation", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("heading", { name: "Board workspace" }).waitFor();
  const initialTheme = await page.locator("html").getAttribute("data-theme");
  await page.getByRole("button", { name: /Switch to .* theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute(
    "data-theme",
    initialTheme === "light" ? "dark" : "light",
  );
  await page.reload();
  await page.getByRole("heading", { name: "Board workspace" }).waitFor();
  await expect(page.locator("html")).toHaveAttribute(
    "data-theme",
    initialTheme === "light" ? "dark" : "light",
  );
  await page.getByRole("button", { name: /Storage images/ }).click();
  await page.getByLabel("Disk name").fill("Storage controls");
  await page.getByRole("button", { name: /Create disk/ }).click();
  const disk = page.locator(".disk").filter({ hasText: "Storage controls" });
  await disk.getByRole("button", { name: "Insert", exact: true }).click();
  await expect(
    disk.getByRole("button", { name: "Delete", exact: true }),
  ).toBeDisabled();
  await disk.getByRole("button", { name: "Eject", exact: true }).click();
  await disk.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(disk).toBeVisible();
  await disk.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(disk).toHaveCount(0);
  await page.getByRole("button", { name: "Workspace", exact: true }).click();
  await page
    .getByRole("button", { name: "Select boot image", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Storage images", exact: true }),
  ).toBeVisible();
});
