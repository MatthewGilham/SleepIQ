import {expect,test} from "@playwright/test";
// Expected counts derive from scripts/preview-charts.py: night i exists unless i%13==0; HRV absent when i%9==0; Deep is constant.
async function open(page:any,name:string){await page.goto("/");await page.getByRole("button",{name,exact:true}).click();}
test("rolling averages show coverage, skip clock times and persist in presets",async({page})=>{
 await open(page,"Analytics");await expect(page.getByRole("heading",{name:"Multi-metric exploration"})).toBeVisible();
 await page.getByLabel("Rolling average").selectOption("7");
 const asleep=page.locator("section.panel",{has:page.getByRole("heading",{name:"Total asleep",exact:true})});
 await expect(page.getByRole("group",{name:"Total asleep chart",exact:true}).locator(".rolling-line").first()).toBeAttached();
 await expect(page.getByText(/Dashed line: trailing 7-day calendar mean/)).toBeVisible();
 await page.getByRole("heading",{name:"Multi-metric exploration"}).screenshot({path:"../.cache/rolling-heading.png"});await page.screenshot({path:"../.cache/rolling-desktop.png",fullPage:true});
 await asleep.getByText("Accessible data table").click();
 await expect(asleep.getByRole("columnheader",{name:"7-day mean"})).toBeVisible();
 await expect(asleep.getByRole("cell",{name:/^7-day mean [\d.]+ h \([4-7]\/7 nights recorded\)$/}).first()).toBeVisible();
 await page.getByLabel("Display",{exact:true}).selectOption("normalized");
 await expect(page.getByRole("group",{name:"Overnight HRV chart",exact:true}).locator(".rolling-line").first()).toBeAttached();
 await page.getByLabel("Display",{exact:true}).selectOption("actual");
 await page.getByRole("checkbox",{name:"Sleep onset",exact:true}).check();
 const onset=page.locator("section.panel",{has:page.getByRole("heading",{name:"Sleep onset",exact:true})});
 await onset.getByText("Accessible data table").click();
 await expect(onset.getByRole("cell",{name:"7-day mean: Not available for clock times"}).first()).toBeVisible();
 await expect(page.getByRole("group",{name:"Sleep onset chart",exact:true}).locator(".rolling-line")).toHaveCount(0);
 await page.getByLabel("Rolling average").selectOption("30");
 await page.getByLabel("Preset name",{exact:true}).fill("Rolling trend");await page.getByRole("checkbox",{name:"Default on opening Analytics"}).check();await page.getByRole("button",{name:"Save as new"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.reload();await open(page,"Analytics");await expect(page.getByLabel("Rolling average")).toHaveValue("30");
 await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Confirm delete"}).click();await expect(page.getByText("Preset deleted.",{exact:true})).toBeVisible();
});
test("correlation explorer pairs nights, reports exclusions and unavailable cases",async({page})=>{
 await open(page,"Correlations");await expect(page.getByRole("heading",{name:"Correlation explorer"})).toBeVisible();
 const summary=page.locator(".correlation-summary");
 await expect(summary.locator("dd").nth(0)).toHaveText("74");
 await expect(summary.locator("dd").nth(1)).toHaveText("0");await expect(summary.locator("dd").nth(2)).toHaveText("9");await expect(summary.locator("dd").nth(3)).toHaveText("7");
 await expect(page.locator(".correlation-r")).toHaveText(/^-?[01]\.\d\d$/);
 const scatter=page.getByRole("group",{name:"Scatter plot of Overnight HRV against Sleeping heart rate"});
 await expect(scatter.locator("circle")).toHaveCount(74);
 await scatter.locator("circle").first().focus();await expect(page.locator(".chart-detail")).toContainText("2026-07-31");
 await expect(page.getByText(/not evidence of cause/)).toBeVisible();
 expect(await page.getByLabel("X axis metric").locator("option").allTextContents()).not.toContain("Sleep onset (local time)");
 await page.screenshot({path:"../.cache/correlations-desktop.png",fullPage:true});
 await page.getByLabel("X axis metric").selectOption("deep_s");
 await expect(page.locator(".correlation-r")).toHaveText("Unavailable");await expect(page.getByText("Unavailable: a metric has no variation across the paired nights")).toBeVisible();
 await page.getByLabel("X axis metric").selectOption("hr_mean");await page.getByLabel("Date range").selectOption("custom");
 await page.getByLabel("From",{exact:true}).fill("2026-10-27");await page.getByLabel("To",{exact:true}).fill("2026-10-28");
 await expect(summary.locator("dd").nth(0)).toHaveText("2");await expect(page.getByText("Unavailable: fewer than 3 paired nights")).toBeVisible();
 await page.getByLabel("Y axis metric").selectOption("hr_mean");await expect(page.getByRole("alert")).toContainText("Choose two different metrics.");
 await page.getByLabel("Y axis metric").selectOption("hrv_mean");await page.getByLabel("Date range").selectOption("all");
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole("heading",{name:"Correlation explorer"})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:"../.cache/correlations-mobile.png",fullPage:true});
});
// Regression: clearing results at request start collapsed the page, so the browser jumped the scroll position.
async function steady(page:any,action:()=>Promise<unknown>,done:()=>Promise<unknown>){
 await page.evaluate(()=>window.scrollTo(0,500));await page.waitForTimeout(100);
 await page.evaluate(()=>{const w=window as any;w.__frames=[];const tick=()=>{w.__frames.push([scrollY,document.documentElement.scrollHeight]);if(!w.__stop)requestAnimationFrame(tick);};w.__stop=false;requestAnimationFrame(tick);});
 const before=await page.evaluate(()=>[scrollY,document.documentElement.scrollHeight]);
 const loading=page.getByText(/^(Loading nightly measurements|Calculating paired correlation)…$/);
 await action();await expect(loading).toBeVisible();await done();await expect(loading).toHaveCount(0);
 const frames:number[][]=await page.evaluate(()=>{const w=window as any;w.__stop=true;return w.__frames;});
 expect(Math.min(...frames.map(f=>f[0])),"scroll position jumped").toBe(before[0]);expect(Math.min(...frames.map(f=>f[1]))).toBeGreaterThanOrEqual(before[1]);
}
test("changing options keeps charts in place instead of jumping the page",async({page})=>{
 await page.route("**/api/v1/analytics/*",async(route:any)=>{await new Promise(f=>setTimeout(f,300));await route.continue();});
 await open(page,"Analytics");await expect(page.getByRole("heading",{name:"Multi-metric exploration"})).toBeVisible();
 await steady(page,()=>page.getByLabel("Rolling average").selectOption("7"),()=>expect(page.locator(".rolling-line").first()).toBeAttached());
 await steady(page,()=>page.getByLabel("Date range").selectOption("90"),()=>expect(page.getByText(/2026-07-31 — 2026-10-28/)).toBeVisible());
 await steady(page,()=>page.getByRole("checkbox",{name:"Sleeping heart rate",exact:true}).check(),()=>expect(page.getByRole("heading",{name:"Sleeping heart rate",exact:true})).toBeVisible());
 // Stale charts keep the mode they were fetched in: the z-axis label appears only with normalized data.
 await page.getByLabel("Display",{exact:true}).selectOption("normalized");await expect(page.getByText("Standard deviations (z)",{exact:true})).toHaveCount(0);await expect(page.getByText("Standard deviations (z)",{exact:true})).toBeVisible();
 await open(page,"Correlations");await expect(page.locator(".correlation-r")).toHaveText(/\d/);
 await steady(page,()=>page.getByLabel("Date range").selectOption("all"),()=>expect(page.getByText(/^2026-07-0\d — 2026-10-28/)).toBeVisible());
});
