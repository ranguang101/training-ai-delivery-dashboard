import { defineConfig } from '@playwright/test';

const testPort = process.env.PLAYWRIGHT_PORT ?? '8765';
const testBaseURL = `http://127.0.0.1:${testPort}`;

export default defineConfig({
  testDir: './e2e/tests',
  use: {
    baseURL: testBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `.\\.venv\\Scripts\\python.exe -m scripts.start_e2e_server`,
    url: `${testBaseURL}/health`,
    reuseExistingServer: !process.env.CI,
  },
});
