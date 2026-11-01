import {expect,test} from "@playwright/test";
// Independent reference for the synthetic store built by scripts/preview-charts.py: night i (0..119, none where i%13===0) wakes on
// 2026-07-01 + i days; asleep = 390 + i%40 minutes; HRV = 35 + i%23 ms except where i%9===0; sleeping HR = 50 + i%11 bpm.
// The default 30-day range is 29 Sep (i=90) to 28 Oct (i=119).
const iso=(i:number)=>new Date(Date.UTC(2026,6,1+i)).toISOString().slice(0,10);
const recorded=(i:number)=>i%13!==0;
const range=(a:number,b:number)=>Array.from({length:b-a+1},(_,k)=>a+k);
const mean=(v:number[])=>v.reduce((s,x)=>s+x,0)/v.length;
const hm=(minutes:number)=>{const m=Math.round(minutes);return `${Math.floor(m/60)}h ${String(m%60).padStart(2,"0")}m`;};
const last30=range(90,119),prev30=range(60,89);
const asleepMin=(days:number[])=>days.filter(recorded).map(i=>390+i%40);
const hrvMs=(days:number[])=>days.filter(i=>recorded(i)&&i%9!==0).map(i=>35+i%23);
// Chart geometry shared with Analytics.tsx: viewBox width 900, plot from x=56 to x=844.
const plotX=(box:{x:number;width:number},i:number,n:number)=>box.x+(56+i/(n-1)*788)/900*box.width;

async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.locator(".main-svg")).toBeVisible();await expect(page.locator(".kpis")).toBeVisible();}
const chip=(page:any,name:string)=>page.getByRole("checkbox",{name,exact:true});
const tip=(page:any)=>page.locator(".chart-tip");

test("reference: 27 of 30 nights recorded in the default range",()=>{expect(last30.filter(recorded)).toHaveLength(27);expect(iso(90)).toBe("2026-09-29");expect(iso(119)).toBe("2026-10-28");});

test("KPI row: average sleep, score gauge, HRV and nights recorded match independent values",async({page})=>{
 await open(page);
 const kpi=(id:string)=>page.locator(`[data-kpi="${id}"]`);
 await expect(kpi("asleep_s").locator(".kpi-value")).toHaveText(hm(mean(asleepMin(last30))));
 const delta=Math.round(mean(asleepMin(last30))-mean(asleepMin(prev30)));
 await expect(kpi("asleep_s").locator(".kpi-sub")).toHaveText(`${delta>0?"▲":"▼"} ${Math.abs(delta)} min vs previous 30 days`);
 await expect(kpi("asleep_s")).toContainText("n=27");
 await expect(kpi("hrv_mean").locator(".kpi-value")).toHaveText(`${mean(hrvMs(last30)).toFixed(0)} ms`);
 await expect(kpi("hrv_mean")).toContainText(`n=${hrvMs(last30).length}`);
 await expect(kpi("nights").locator(".kpi-value")).toHaveText("27 of 30");
 await expect(kpi("nights")).toContainText("3 days with no recorded sleep");
 // Scores come from the versioned scoring engine, so the reference averages the stored nightly scores from the per-night series
 // endpoint (a separate code path from the summary), excluding unscored nights.
 const series=await (await page.request.post("/api/v1/analytics/timeseries",{data:{metrics:["overall"],range:"30"},headers:{origin:"http://127.0.0.1:8766","x-sleepiq-request":"charts"}})).json();
 const scores=(series.series[0].raw as (number|null)[]).filter((v):v is number=>v!==null);
 await expect(kpi("overall").locator(".kpi-value")).toHaveText(`${mean(scores).toFixed(1)} /100`);
 await expect(kpi("overall")).toContainText(`n=${scores.length}`);
 await expect(kpi("overall").locator(".gauge-value")).toBeAttached();
 await expect(kpi("overall").getByRole("img",{name:/maximum 100\.0/})).toBeVisible();
});

test("tiles: the nine agreed metrics (no wrist temperature since U12), no Core or resting heart rate, and a click focuses the main chart",async({page})=>{
 await open(page);
 const titles=await page.locator(".tiles .tile h3 > span:first-child").allTextContents();
 expect(titles).toEqual(["Total asleep","Deep","REM","Awake","SleepIQ score","Sleeping heart rate","Overnight HRV","Sleep efficiency","Respiratory rate"]);
 expect(titles).not.toContain("Core");expect(titles.join()).not.toMatch(/Resting/);
 await expect(chip(page,"Core")).toHaveCount(0);
 await expect(page.locator('[data-tile="deep_s"] .tile-val')).toHaveText("1h 00m avg");
 await page.locator('[data-tile="hr_mean"]').click();
 await expect(page.locator("#main-heading")).toHaveText("Sleeping heart rate");
 await expect(page.locator(".main-svg g[data-metric]")).toHaveCount(1);
 await expect(page.locator('.main-svg g[data-metric="hr_mean"]')).toBeAttached();
 await expect(chip(page,"Sleeping heart rate")).toBeChecked();await expect(chip(page,"Total asleep")).not.toBeChecked();
});

test("same-unit metrics share an axis: four lines on hours and bpm; a third unit is refused with a reason",async({page})=>{
 await open(page);
 await chip(page,"Overnight HRV").uncheck();
 for(const name of ["Deep","REM","Sleeping heart rate"])await chip(page,name).check();
 await expect(page.locator(".main-svg g[data-metric]")).toHaveCount(4);
 await expect(page.locator('.main-svg g[data-axis="left"]')).toHaveCount(3);await expect(page.locator('.main-svg g[data-axis="right"]')).toHaveCount(1);
 await expect(page.locator('.main-svg .axis-left')).toHaveAttribute("data-unit","h");await expect(page.locator('.main-svg .axis-right')).toHaveAttribute("data-unit","bpm");
 await expect(page.locator(".caption-left")).toHaveText("Hours");await expect(page.locator(".caption-right")).toHaveText("bpm");
 await chip(page,"Overnight HRV").click({force:true});
 await expect(chip(page,"Overnight HRV")).not.toBeChecked();
 await expect(page.locator(".chip-note")).toHaveText(/two axes, already used by Hours and bpm.*Normalized/);
 await expect(page.locator(".main-svg g[data-metric]")).toHaveCount(4);
});

test("hovering a night lists every visible line with value and unit, and 'no reading' when missing",async({page})=>{
 await open(page);
 const box=(await page.locator(".main-svg").boundingBox())!;const y=box.y+box.height*0.5;
 // 17 Oct is i=108: recorded, HRV missing (108%9===0); index 18 of 30.
 await page.mouse.move(plotX(box,18,30),y);
 await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-17");
 await expect(tip(page).locator('[data-metric="asleep_s"]')).toHaveText(`● Total asleep${hm(390+108%40)}`);
 await expect(tip(page).locator('[data-metric="hrv_mean"]')).toHaveText("● Overnight HRVno reading");
 // 20 Oct is i=111: HRV 35+111%23 = 54 ms.
 await page.mouse.move(plotX(box,21,30),y);
 await expect(tip(page).locator('[data-metric="hrv_mean"]')).toHaveText(`● Overnight HRV${35+111%23} ms`);
 // 26 Oct is i=117: not recorded at all.
 await page.mouse.move(plotX(box,27,30),y);
 await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-26");
 await expect(tip(page).locator('[data-metric="asleep_s"]')).toHaveText("● Total asleepno reading");
 await expect(tip(page)).toContainText("No recorded sleep this night");
});

test("dragging across the zoom strip narrows the main chart; double-click restores the full range",async({page})=>{
 await open(page);
 const range=page.locator(".range-label time");
 await expect(range.first()).toHaveAttribute("datetime","2026-09-29");await expect(range.last()).toHaveAttribute("datetime","2026-10-28");
 const strip=(await page.locator(".brush").boundingBox())!;const y=strip.y+strip.height/2;
 await page.mouse.move(plotX(strip,5,30),y);await page.mouse.down();await page.mouse.move(plotX(strip,12,30),y,{steps:4});await page.mouse.move(plotX(strip,20,30),y,{steps:4});await page.mouse.up();
 await expect(range.first()).toHaveAttribute("datetime",iso(95));await expect(range.last()).toHaveAttribute("datetime",iso(110));
 await expect(page.locator(".range-label")).toContainText("16 days");
 await page.locator(".brush").dblclick();
 await expect(range.first()).toHaveAttribute("datetime","2026-09-29");await expect(range.last()).toHaveAttribute("datetime","2026-10-28");
});

test("'Zoom to fit' lifts the hours axis off zero; turning it off restores zero",async({page})=>{
 await open(page);
 const lowest=page.locator(".main-svg .axis-left text").last();
 await expect(lowest).toHaveText("0.0");
 await page.getByRole("checkbox",{name:"Zoom to fit hours axis"}).check();
 await expect.poll(async()=>Number(await lowest.textContent())).toBeGreaterThan(0);
 await page.getByRole("checkbox",{name:"Zoom to fit hours axis"}).uncheck();
 await expect(lowest).toHaveText("0.0");
});

test("keyboard moves the crosshair night by night and the tooltip lists every value, including missing ones",async({page})=>{
 await open(page);
 await page.locator(".chart-frame").focus();
 await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-28");
 await page.keyboard.press("ArrowLeft");await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-27");
 await page.keyboard.press("ArrowLeft");await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-26");
 await page.keyboard.press("ArrowRight");await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-27");
 const tipValues=await tip(page).locator(".tip-row[data-metric] span:last-child").allTextContents();
 expect(tipValues).toEqual([hm(390+118%40),`${35+118%23} ms`]);
 // Home/End reach both ends of the 30-day range; a night without HRV (i=108, 2026-10-17) says "no reading".
 await page.keyboard.press("Home");await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-09-29");
 await page.keyboard.press("End");await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-28");
 await page.keyboard.press("Home");for(let k=0;k<18;k++)await page.keyboard.press("ArrowRight");
 await expect(tip(page).locator("time")).toHaveAttribute("datetime","2026-10-17");
 expect(await tip(page).locator(".tip-row[data-metric] span:last-child").allTextContents()).toEqual([hm(390+108%40),"no reading"]);
 // The table view was removed in U11 (P29).
 await expect(page.getByRole("button",{name:/Show as table|Hide table/})).toHaveCount(0);
});

test("narrow screens do not scroll sideways and reduced motion turns off the line drawing",async({page})=>{
 await open(page);
 expect(await page.locator(".series-line").first().evaluate(e=>getComputedStyle(e).animationName)).toBe("an-draw");
 await page.setViewportSize({width:390,height:844});await expect(page.locator(".main-svg")).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
 await page.screenshot({path:"../.cache/analytics-mobile.png",fullPage:true});
 await page.emulateMedia({reducedMotion:"reduce"});
 await expect.poll(()=>page.locator(".series-line").first().evaluate(e=>getComputedStyle(e).animationName)).toBe("none");
});
