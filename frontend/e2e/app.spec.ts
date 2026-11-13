import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

test("walks through every transit dashboard screen with zero errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(`console.error: ${msg.text()}`);
    }
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      errors.push(`HTTP ${res.status()} on ${res.url()}`);
    }
  });

  // 1. Overview & Network Patterns
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Network Overview & Temporal Patterns/i })
  ).toBeVisible();
  await expect(page.getByText(/Official Test Runs Logged/i)).toBeVisible();
  await expect(page.getByText(/Period:/i)).toBeVisible();

  // Toggle split filter on Overview
  await page.getByRole("button", { name: "Test (Aug–Sep)" }).click();
  await page.getByRole("button", { name: "All Months" }).click();

  // 2. Route Detail & Forecast
  await page.getByRole("button", { name: "Route Detail" }).click();
  await expect(
    page.getByRole("heading", { name: /Route Profile & Forecast Diagnostics/i })
  ).toBeVisible();
  // Select M98 (no Sunday service -> verify "not available" renders instead of 0)
  await page.locator("#route-select").selectOption("M98");
  await expect(page.getByText(/not available/i).first()).toBeVisible();
  await page.locator("#route-select").selectOption("M15+");
  await page.getByRole("button", { name: "October Hourly Series" }).click();

  // 3. Route Groups (Map + PCA + Stability)
  await page.getByRole("button", { name: "Route Groups" }).click();
  await expect(
    page.getByRole("heading", { name: /Route Groups, Corridor Map & Clustering Validation/i })
  ).toBeVisible();
  await expect(page.getByText(/M35 Excluded as Outlier/i)).toBeVisible();

  // 4. Model Evaluation
  await page.getByRole("button", { name: "Model Evaluation" }).click();
  await expect(
    page.getByRole("heading", { name: /Model Evaluation:/i })
  ).toBeVisible();
  await expect(
    page.getByText(/did not beat the 4-week average baseline/i)
  ).toBeVisible();
  await page.getByRole("button", { name: "Validation (Jun–Jul)" }).click();
  await expect(page.getByText(/HistGradientBoosting/i).first()).toBeVisible();
  await page.getByRole("button", { name: "October Check (Oct 18–31)" }).click();
  await expect(page.getByText(/October Diagnostic & Pipeline Checks/i)).toBeVisible();

  // 5. Review List
  await page.getByRole("button", { name: "Review List" }).click();
  await expect(
    page.getByRole("heading", { name: /Aug–Oct 2026 Service Review List/i })
  ).toBeVisible();
  await page.getByPlaceholder("Filter by route (e.g. M15+)...").fill("M15+");
  await expect(page.getByRole("button", { name: "Simulate" }).first()).toBeVisible();

  // 6. Scenarios Calculator (jump via Review List or nav)
  await page.getByRole("button", { name: "Simulate" }).first().click();
  await expect(
    page.getByRole("heading", { name: /Service Scenario Calculator/i })
  ).toBeVisible();
  await expect(
    page.getByText(/riders stay the same when trips change/i)
  ).toBeVisible();
  await page.getByRole("button", { name: "+20%" }).click();
  await page.getByRole("button", { name: "Calculate Scenario" }).click();
  await expect(page.getByText(/Simulated Arithmetic Outcome/i)).toBeVisible();

  // 7. GTFS Upload Inspector
  await page.getByRole("button", { name: "GTFS Upload" }).click();
  await expect(
    page.getByRole("heading", { name: /GTFS Feed Upload & Safe Schedule Inspector/i })
  ).toBeVisible();
  await expect(
    page.getByText(/no ridership history, schedule analysis only/i)
  ).toBeVisible();

  // Check GTFS file upload end-to-end with sample synthetic zip fixture
  const sampleZipPath = fileURLToPath(new URL("./sample_gtfs.zip", import.meta.url));
  await page.locator("#gtfs-file-input").setInputFiles(sampleZipPath);
  await page.getByRole("button", { name: "Inspect GTFS Archive" }).click();
  await expect(page.getByText(/Referential Integrity/i)).toBeVisible();
  await expect(page.getByText("PASSED")).toBeVisible();
  await expect(page.getByText(/B44/)).toBeVisible();

  // Assert prohibited crowding terminology never appears anywhere in UI
  const bodyText = (await page.locator("body").innerText()).toLowerCase();
  for (const forbidden of ["overcrowded", "underused", "congested", "crowding"]) {
    expect(bodyText).not.toContain(forbidden);
  }

  expect(errors).toEqual([]);
});

