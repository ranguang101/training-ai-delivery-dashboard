import { defineConfig } from '@playwright/test';

const testPort = process.env.PLAYWRIGHT_PORT ?? '8765';
const testBaseURL = `http://127.0.0.1:${testPort}`;

export default defineConfig({
  testDir: './e2e/dashboard',
  use: {
    baseURL: testBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `.\\.venv\\Scripts\\python.exe -m tools.project_dashboard.run --host 127.0.0.1 --port ${testPort} --project-root .\\fixtures\\demo-project`,
    url: `${testBaseURL}/api/v1/project-status/dashboard/r3/workspaces/collaboration`,
    env: {
      DASHBOARD_TEST_NOW: '2026-08-24T00:00:00+00:00',
    },
    reuseExistingServer: !process.env.CI,
  },
});
