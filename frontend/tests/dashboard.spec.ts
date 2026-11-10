import { expect, test } from '@playwright/test';

const dashboardPages = [
  { path: '/', heading: 'Dashboard Overview', marker: 'Total Routes' },
  { path: '/routes', heading: 'Route Explorer', marker: 'Search by route name or number' },
  { path: '/schedule', heading: 'Schedule & Frequency Analysis', marker: 'Route Frequency Statistics' },
  { path: '/coverage', heading: 'Route Coverage Analysis', marker: 'Stop Coverage Map' },
  { path: '/overlap', heading: 'Route Overlap Detection', marker: 'Filter Overlapping Pairs' },
  { path: '/clustering', heading: 'AI Route Clustering', marker: 'Cluster Characteristics' },
  { path: '/optimization', heading: 'Schedule Optimization', marker: 'Scenario controls' },
  { path: '/data-quality', heading: 'Data Quality & Provenance', marker: 'Sanitization audit' },
];

test.beforeEach(async ({ request }) => {
  const response = await request.get('/api/health');
  expect(response.ok(), 'FastAPI backend must be running at localhost:8000').toBeTruthy();
  expect((await response.json()).status).toBe('healthy');
});

test('all dashboard routes render their API-backed views', async ({ page }) => {
  const pageErrors: string[] = [];
  const failedApiResponses: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 400) {
      failedApiResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  for (const dashboardPage of dashboardPages) {
    await page.goto(dashboardPage.path);
    await expect(page.getByRole('heading', { name: dashboardPage.heading, exact: true })).toBeVisible();
    if (dashboardPage.path === '/routes') {
      await expect(page.getByPlaceholder(dashboardPage.marker)).toBeVisible();
    } else {
      await expect(page.getByText(dashboardPage.marker, { exact: false }).first()).toBeVisible();
    }
  }

  expect(pageErrors).toEqual([]);
  expect(failedApiResponses).toEqual([]);
});

test('route search opens the selected route details and schedule', async ({ page, request }) => {
  const response = await request.get('/api/routes?page=1&page_size=1');
  const routes = await response.json();
  const route = routes.items[0] as { route_id: string; route_short_name: string };

  await page.goto('/routes');
  await page.getByPlaceholder('Search by route name or number...').fill(route.route_id);
  await expect(page.getByText('1 routes total')).toBeVisible();
  await page.locator('button').filter({ hasText: route.route_short_name }).first().click();

  await expect(page.getByText(`Route ID: ${route.route_id}`, { exact: true })).toBeVisible();
  await expect(page.getByText('Scheduled Departures (from first stop)')).toBeVisible();
  await expect(page.getByText(/do not represent actual road paths/)).toBeVisible();
});

test('optimization form returns a schedule-estimate comparison', async ({ page }) => {
  await page.goto('/optimization');
  const routeSelect = page.locator('select');
  await expect(routeSelect.locator('option').nth(1)).toBeAttached();
  await routeSelect.selectOption({ index: 1 });
  await page.getByRole('button', { name: /Run schedule simulation/ }).click();

  await expect(page.getByText('Hypothetical scenario')).toBeVisible();
  await expect(page.getByText('Baseline', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Simulated', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Estimated peak fleet')).toBeVisible();
});

test('mobile navigation opens and navigates to route explorer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Route Explorer' }).click();
  await expect(page.getByRole('heading', { name: 'Route Explorer' })).toBeVisible();
});
