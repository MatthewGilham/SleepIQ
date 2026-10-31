import {expect,test} from "@playwright/test";
// P31 / R4-1: version text and filler text are gone from every page; kept lines (group C, honesty notes) are still there.
const GONE=[/\b(pilot|derive)-\d/i,/PILOT SCORE/,/pilot-neutral/i,/\bVersion\b/,/Source-local time/,/source-local clock/,/Individual nights/,/Hover or focus the chart/,/Hover the chart for/,/Hover, or focus the plot/,/Hover a cell for/,/Drag to focus on a stretch/,/Each dot is one night/,/select a cell to explore/,/Sleep onset and wake time are not offered/,/Metrics that share a unit/,/Z-score =/,/Dotted line:/,/Dashed line:/,/Stage-based ·/,/One row per recorded night/,/gaps are nights not recorded/];
const pages=["Dashboard","Analytics","Correlations","Data & Settings"];
for(const name of pages)test(`${name}: no version or filler text`,async({page})=>{
 await page.goto("/");if(name!=="Dashboard")await page.getByRole("button",{name,exact:true}).click();await page.waitForTimeout(800);
 const text=await page.locator("body").innerText();
 for(const re of GONE)expect(text,String(re)).not.toMatch(re);
 await expect(page.locator(".status .version")).toHaveCount(0);
 await expect(page.getByText("Sync",{exact:false}).first()).toBeVisible();
});
test("kept lines are still present",async({page})=>{
 await page.goto("/");
 await expect(page.getByText("Pilot ceiling")).toBeVisible();
 await expect(page.getByText("Not clinically calibrated.")).toBeVisible();
 await expect(page.getByText("TRANSPARENT BY DESIGN")).toBeVisible();
 await expect(page.getByText("Local-first by design")).toBeVisible();
 await page.getByRole("button",{name:"Correlations",exact:true}).click();
 await expect(page.getByText("Exploratory only.")).toBeVisible();
 await expect(page.getByText("Shows association, not cause; unreliable with few nights.")).toBeVisible();
 await expect(page.getByText("Each line is scaled to its own range")).toBeVisible();
 await page.getByRole("button",{name:"Analytics",exact:true}).click();
 await expect(page.getByText("Deep and REM are descriptive, not targets.")).toBeVisible();
});
test("dashboard score card rows are plain names",async({page})=>{
 await page.goto("/");
 const rows=await page.locator(".breakdown-row > span").allInnerTexts();
 expect(rows).toEqual(["Duration","Consistency","Efficiency","Deep","REM","HR / HRV"]);
});
