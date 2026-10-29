import {expect,test} from "@playwright/test";
// Latest night derives from scripts/preview-charts.py: night 119 (wake 2026-10-28) = Core 159, Deep 60, REM 70, Awake 10, Core 140 minutes from 23:00,
// so asleep 429 min (7h 09m), window 439 min (7h 19m), efficiency 429/439 = 97.7%, wake 06:19, HRV one sample of 35+119%23 = 39 ms.
test("dashboard shows the latest stored night from the configured store",async({page})=>{
 await page.goto("/");
 await expect(page.getByText("Generated test data - not your health records")).toBeVisible();
 await expect(page.getByRole("heading",{name:"A little clarity, every morning."})).toBeVisible();
 await expect(page.locator("time")).toHaveText("Wednesday, 28 October");
 await expect(page.locator(".sleep-total")).toHaveText("7h 09m");
 await expect(page.locator(".sleep-times strong")).toHaveText(["23:00","06:19"]);
 await expect(page.getByRole("img",{name:/Sleep stages from 23:00 to 06:19, 7h 19m recorded window/})).toBeVisible();
 await expect(page.locator(".stage-summary")).toContainText("Deep1h 00m");
 await expect(page.locator(".metric",{hasText:"Sleep efficiency"})).toContainText("97.7");
 await expect(page.locator(".metric",{hasText:"Overnight HRV"})).toContainText("39");
 await expect(page.locator(".status")).toContainText("nights · last import");await expect(page.locator(".status")).toContainText("Backup Not connected");
 await expect(page.locator(".trend-bars > div")).toHaveCount(30);
 await page.getByRole("button",{name:"7D"}).click();await expect(page.locator(".trend-bars > div")).toHaveCount(7);
 // The window ends at the latest night; 2026-10-27 is night 118 and exists, so only genuinely unrecorded days are empty (none expected here).
 await expect(page.getByText("Design preview")).toHaveCount(0);
 await page.screenshot({path:"../.cache/dashboard-desktop.png",fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:"../.cache/dashboard-mobile.png",fullPage:true});
});
test("dashboard keyboard: stage bars and trend bars are focusable with text equivalents",async({page})=>{
 await page.goto("/");
 const bar=page.locator(".timeline rect").first();await bar.focus();await expect(bar).toBeFocused();
 await expect(bar.locator("title")).toHaveText(/Core: \d+ minutes; 0 minutes after onset/);
 await page.locator(".trend-bars span").last().focus();await expect(page.locator(".trend-bars span").last()).toBeFocused();
});
const night={wake_date:"2026-10-28",source:"Watch",onset_local:"2026-10-27T23:00",wake_local:"2026-10-28T07:00",start_offset_min:0,end_offset_min:0,session_s:28800,asleep_s:26400,core_s:14400,deep_s:3600,rem_s:4200,awake_s:1200,efficiency:0.9565,flags:["revised"],
 stages:[{stage:"Core",start_s:0,duration_s:14400},{stage:"Awake",start_s:14400,duration_s:1200}],
 physiology:[{id:"hr",label:"Sleeping heart rate",value:54,n:6},{id:"hrv",label:"Overnight HRV",value:null,n:0},{id:"resp",label:"Respiratory rate",value:null,n:0},{id:"temp",label:"Sleeping wrist temperature",value:null,n:0}],
 score:{status:"insufficient_data",overall:null,consistency:null,version:"pilot-1",ceiling:92.5,missing:["overnight_hrv","consistency:insufficient_history"],components:{duration:{score:100,weight:30,neutral:false},deep:{score:75,weight:10,neutral:true}},consistency_detail:{available:false,reason:"insufficient_history",baseline_nights:3}}};
const body={synthetic:false,versions:["derive-1","pilot-1"],import:{batches:1,last_received_utc:1793000000,nights:3},latest:night,trend:{dates:["2026-10-27","2026-10-28"],asleep_h:[null,7.33]}};
test("partial, unscored night stays visible with missing data labelled, not zero",async({page})=>{
 await page.route("**/api/v1/dashboard",r=>r.fulfill({json:body}));await page.goto("/");
 await expect(page.getByText("Local dashboard")).toBeVisible();
 await expect(page.locator(".score-ring")).toContainText("Insufficient");
 await expect(page.getByText("No overall score because of missing: overnight HRV, enough history for consistency.").first()).toBeVisible();
 await expect(page.locator(".metric",{hasText:"Overnight HRV"})).toContainText("Missing data");
 await expect(page.locator(".metric",{hasText:"Resting heart rate"})).toHaveCount(0);
 await expect(page.getByText("Flags: revised")).toBeVisible();
 await expect(page.locator(".trend-bars span").first()).toHaveAttribute("title","2026-10-27: no recording");
 await expect(page.getByText("Not enough history yet (3 prior nights; needs at least 7)")).toBeVisible();
});
test("empty store shows the no-history state",async({page})=>{
 await page.route("**/api/v1/dashboard",r=>r.fulfill({json:{...body,latest:null,trend:{dates:[],asleep_h:[]},import:{batches:0,last_received_utc:null,nights:0}}}));await page.goto("/");
 await expect(page.getByText("No sleep history available")).toBeVisible();await expect(page.locator(".status")).toContainText("No imports yet");
});
test("a failing dashboard request shows a retryable error, then recovers",async({page})=>{
 let fail=true;
 await page.route("**/api/v1/dashboard",r=>fail?r.fulfill({status:500,json:{detail:"x"}}):r.fulfill({json:body}));await page.goto("/");
 await expect(page.getByRole("alert")).toContainText("The dashboard could not load.");await expect(page.locator(".status")).toContainText("Sync Unavailable");
 await expect(page.getByText("87.5")).toHaveCount(0);
 fail=false;await page.getByRole("button",{name:"Retry"}).click();await expect(page.locator(".score-ring")).toContainText("Insufficient");
});
test("without a configured store the labelled synthetic design preview remains",async({page})=>{
 await page.route("**/api/v1/dashboard",r=>r.fulfill({status:503,json:{detail:"Chart store not configured"}}));await page.goto("/");
 await expect(page.getByText("Synthetic examples - no personal health data")).toBeVisible();await expect(page.getByText("87.5")).toBeVisible();
});

test("metrics grid has five cards, none for resting heart rate, fully visible at desktop and phone widths",async({page})=>{
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});await page.goto("/");
  const grid=page.getByLabel("Nightly metrics");
  await expect(grid.locator(".metric")).toHaveCount(5);
  await expect(page.getByText("Resting heart rate")).toHaveCount(0);
  const cards=grid.locator(".metric");
  for(let i=0;i<5;i++){
   const box=await cards.nth(i).boundingBox();expect(box).not.toBeNull();
   expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(width);expect(box!.height).toBeGreaterThan(40);
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
 }
});
