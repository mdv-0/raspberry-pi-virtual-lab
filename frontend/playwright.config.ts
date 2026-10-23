import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  timeout: 240000,
  workers: 1,
  webServer: process.env.RPI_LAB_TEST_URL
    ? undefined
    : {
        command: "bash ../scripts/test-browser-server.sh",
        url: "http://127.0.0.1:8001/api/instance",
        reuseExistingServer: false,
        timeout: 30000,
      },
  use: {
    baseURL: process.env.RPI_LAB_TEST_URL || "http://127.0.0.1:8001",
    viewport: { width: 1440, height: 1200 },
    trace: "retain-on-failure",
  },
  reporter: "list",
});
