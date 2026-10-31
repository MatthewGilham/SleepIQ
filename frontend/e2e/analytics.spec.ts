import {expect,test} from "@playwright/test";
// Expected counts derive from scripts/preview-charts.py: night i exists unless i%13==0; HRV absent when i%9==0; Deep is constant.
async function open(page:any,name:string){await page.goto("/");await page.getByRole("button",{name,exact:true}).click();}
const choose=(page:any,group:string,name:string)=>page.getByRole("group",{name:group}).getByRole("button",{name,exact:true}).click();
// Clicks inside steady() use dispatchEvent so Playwright does not scroll to the control; only the app may move the page.
const press=(page:any,group:string,name:string)=>page.getByRole("group",{name:group}).getByRole("button",{name,exact:true}).dispatchEvent("click");
const line=(page:any,id:string)=>page.locator(`.main-svg g[data-metric="${id}"]`);
test("rolling averages show coverage, skip clock times and persist in presets",async({page})=>{
 await open(page,"Analytics");await expect(page.locator(".main-svg")).toBeVisible();
 await choose(page,"Rolling average","7-day avg");
 await expect(line(page,"asleep_s").locator(".rolling-line").first()).toBeAttached();
 await expect(page.getByText(/Dashed line:/)).toHaveCount(0);
 await page.screenshot({path:"../.cache/rolling-desktop.png",fullPage:true});
 // The crosshair tooltip carries the coverage text (the table view was removed in U11).
 await page.locator(".chart-frame").focus();
 await expect(page.locator(".chart-tip .tip-row.rolling",{hasText:"Total asleep"}).locator("span").last()).toHaveText(/^7-day mean \d+h \d\dm \([4-7]\/7 nights recorded\)$/);
 await page.locator(".chart-frame").blur();
 await choose(page,"Display","Normalized");
 await expect(line(page,"hrv_mean").locator(".rolling-line").first()).toBeAttached();
 await choose(page,"Display","Actual units");
 // Hours and ms already use both axes, so HRV makes way for the clock metric.
 await page.getByRole("checkbox",{name:"Overnight HRV",exact:true}).uncheck();
 await page.getByRole("checkbox",{name:"Sleep onset",exact:true}).check();
 await page.locator(".chart-frame").focus();
 await expect(page.locator(".chart-tip .tip-row.rolling",{hasText:"Sleep onset"})).toContainText("7-day mean: Not available for clock times");
 await page.locator(".chart-frame").blur();
 await expect(line(page,"onset_minute")).toBeAttached();await expect(line(page,"onset_minute").locator(".rolling-line")).toHaveCount(0);
 await choose(page,"Rolling average","30-day avg");
 await page.locator(".preset-menu > summary").click();
 await page.getByLabel("Preset name",{exact:true}).fill("Rolling trend");await page.getByRole("checkbox",{name:"Default on opening Analytics"}).check();await page.getByRole("button",{name:"Save as new"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.reload();await open(page,"Analytics");await expect(page.getByRole("group",{name:"Rolling average"}).getByRole("button",{name:"30-day avg"})).toHaveAttribute("aria-pressed","true");
 await expect(page.getByRole("checkbox",{name:"Sleep onset",exact:true})).toBeChecked();
 await page.locator(".preset-menu > summary").click();await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Confirm delete"}).click();await expect(page.getByText("Preset deleted.",{exact:true})).toBeVisible();
});
// The correlation explorer checks moved to correlations.spec.ts with the U17 redesign (same counts and unavailable cases).
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
 await open(page,"Analytics");await expect(page.locator(".main-svg")).toBeVisible();
 await steady(page,()=>press(page,"Rolling average","7-day avg"),()=>expect(page.locator(".rolling-line").first()).toBeAttached());
 await steady(page,()=>press(page,"Date range","90 days"),()=>expect(page.locator(".range-label")).toHaveText("31 Jul 2026 – 28 Oct 2026 · 90 days"));
 await steady(page,()=>page.getByRole("checkbox",{name:"Deep",exact:true}).dispatchEvent("click"),()=>expect(line(page,"deep_s")).toBeAttached());
 // Stale charts keep the mode they were fetched in: the z-axis label appears only with normalized data.
 await choose(page,"Display","Normalized");await expect(page.getByText("Standard deviations (z)",{exact:true})).toHaveCount(0);await expect(page.getByText("Standard deviations (z)",{exact:true})).toBeVisible();
 await open(page,"Correlations");await expect(page.locator(".cx-r")).toHaveText(/\d/);
 await steady(page,()=>press(page,"Date range","All"),()=>expect(page.locator(".cx-scatter-card .cx-sub")).toHaveText("2 Jul 2026 – 28 Oct 2026 · 119 days"));
});
