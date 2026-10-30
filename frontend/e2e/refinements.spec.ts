import {expect,test} from "@playwright/test";
// Round 3 refinements (DECISIONS P29, PLAN.md "Improvements, round 3"). Synthetic preview store only.

// Gaps inside the dashboard duration: number to unit (each group) and hour group to minute group.
async function durationGaps(page:any){
 return page.locator(".night-panel .sleep-total").evaluate((total:Element)=>{
  const parts=Array.from(total.querySelectorAll(".dur-part"));
  const unitGap=(part:Element)=>{const digits=document.createRange();digits.selectNodeContents(part.firstChild!);
   return part.querySelector(".dur-unit")!.getBoundingClientRect().left-digits.getBoundingClientRect().right;};
  return {units:parts.map(unitGap),groups:parts[1].getBoundingClientRect().left-parts[0].getBoundingClientRect().right};
 });
}

for(const width of [1440,390])test(`U09 duration units sit tight to their numbers with one even gap at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.goto("/");
 await expect(page.locator(".sleep-total")).toHaveText("7h 09m");
 const gaps=await durationGaps(page);
 for(const gap of gaps.units){expect(gap).toBeGreaterThanOrEqual(0);expect(gap).toBeLessThanOrEqual(4);}
 expect(gaps.groups).toBeGreaterThanOrEqual(8);expect(gaps.groups).toBeLessThanOrEqual(16);
});

test("U09 the three top panel titles line up",async({page})=>{
 await page.setViewportSize({width:1440,height:900});await page.goto("/");
 const tops=await page.locator(".hero-grid > .panel > .panel-title h2").evaluateAll((els:Element[])=>els.map(e=>e.getBoundingClientRect().top));
 expect(tops).toHaveLength(3);
 expect(Math.max(...tops)-Math.min(...tops)).toBeLessThanOrEqual(2);
 await page.locator(".hero-grid").screenshot({path:"../.cache/u09-hero.png"});
});

// Analytics helpers. Synthetic store (scripts/preview-charts.py): the default 30-day range is 2026-09-29 to 2026-10-28.
async function analytics(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.locator(".main-svg")).toBeVisible();await expect(page.locator(".kpis")).toBeVisible();}
const HEADERS={origin:"http://127.0.0.1:8766","x-sleepiq-request":"charts"};
async function scores(page:any,start:string,end:string):Promise<number[]>{
 const body=await (await page.request.post("/api/v1/analytics/timeseries",{data:{metrics:["overall"],range:"custom",start,end},headers:HEADERS})).json();
 return (body.series[0].raw as (number|null)[]).filter((v):v is number=>v!==null);
}
const mean=(v:number[])=>v.reduce((s,x)=>s+x,0)/v.length;

test("U10 the score change is shown in points without /100; the headline keeps /100",async({page})=>{
 await analytics(page);
 const kpi=page.locator('[data-kpi="overall"]');
 // Reference: stored nightly scores for this and the previous 30 calendar days, read through the per-night series endpoint.
 const delta=mean(await scores(page,"2026-09-29","2026-10-28"))-mean(await scores(page,"2026-08-30","2026-09-28"));
 await expect(kpi.locator(".kpi-sub")).toHaveText(`${delta>0?"▲":delta<0?"▼":"±"} ${Math.abs(delta).toFixed(1)} vs previous 30 days`);
 await expect(kpi.locator(".kpi-sub")).not.toContainText("/100");
 await expect(kpi.locator(".kpi-value")).toHaveText(/ \/100$/);
 // Other KPI changes keep their units.
 await expect(page.locator('[data-kpi="asleep_s"] .kpi-sub')).toHaveText(/^[▲▼±] \d+ min vs previous 30 days$/);
 await expect(page.locator('[data-kpi="hrv_mean"] .kpi-sub')).toHaveText(/^[▲▼±] \d+ ms vs previous 30 days$/);
});

test("U11 Analytics has no table view; exact values come from the keyboard tooltip",async({page})=>{
 await analytics(page);
 await expect(page.getByRole("button",{name:/Show as table|Hide table/})).toHaveCount(0);
 await expect(page.locator(".main-card table")).toHaveCount(0);
 await page.locator(".chart-frame").focus();
 await expect(page.locator(".chart-tip")).toBeVisible();
 await expect(page.locator(".chart-tip time")).toHaveAttribute("datetime","2026-10-28");
});
