import {expect,test} from "@playwright/test";
// U17 Correlations redesign (DECISIONS P29). Synthetic store from scripts/preview-charts.py: night i (0..119) wakes on
// 2026-07-01 + i, none where i%13===0; HRV absent where i%9===0; sleeping HR = 50 + i%11 bpm; HRV = 35 + i%23 ms; Deep is constant.
// The default 90-day range is 31 Jul (i=30) to 28 Oct (i=119).
const recorded=(i:number)=>i%13!==0;
const range=(a:number,b:number)=>Array.from({length:b-a+1},(_,k)=>a+k);
const iso=(i:number)=>new Date(Date.UTC(2026,6,1+i)).toISOString().slice(0,10);
const HEADERS={origin:"http://127.0.0.1:8766","x-sleepiq-request":"charts"};

async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Correlations",exact:true}).click();await expect(page.locator(".cx-scatter")).toBeVisible();await expect(page.locator(".cx-main")).toHaveAttribute("aria-busy","false");}
const chip=(page:any,axis:"X axis"|"Y axis",name:string)=>page.getByRole("group",{name:axis}).getByRole("button",{name,exact:true});
const count=(page:any,label:string|RegExp)=>page.locator(".cx-counts div").filter({has:page.locator("dt",{hasText:label})}).locator("dd");
const rOf=async(page:any)=>Number(await page.locator(".cx-r").getAttribute("data-r"));

test("reference: 90-day HR/HRV pairing derived independently",()=>{
 const days=range(30,119),paired=days.filter(i=>recorded(i)&&i%9!==0);
 expect(paired).toHaveLength(74);expect(days.filter(i=>recorded(i)&&i%9===0)).toHaveLength(9);expect(days.filter(i=>!recorded(i))).toHaveLength(7);
});

test("pairs nights, reports exclusions, and handles unavailable cases (A01 behaviour kept)",async({page})=>{
 await open(page);
 await expect(page.getByRole("heading",{name:"How your nights move together"})).toBeVisible();
 await expect(page.locator("#cx-title")).toHaveText("Overnight HRV against Sleeping heart rate");
 await expect(count(page,"Paired nights")).toHaveText("74");await expect(count(page,"Sleeping heart rate missing")).toHaveText("0");
 await expect(count(page,"Overnight HRV missing")).toHaveText("9");await expect(count(page,"Both missing")).toHaveText("7");
 await expect(page.locator(".cx-scatter .cx-pt")).toHaveCount(74);
 await expect(page.locator(".cx-r")).toHaveText(/^([+−][01]\.\d\d|0\.00)$/);
 // r matches Python's endpoint for the same window.
 const api=await (await page.request.post("/api/v1/analytics/correlation",{data:{x:"hr_mean",y:"hrv_mean",range:"90"},headers:HEADERS})).json();
 expect(await rOf(page)).toBeCloseTo(api.r,10);
 await expect(page.getByText(/not a significance test or evidence of cause/)).toBeVisible();
 // Clock times are never offered.
 await expect(page.locator(".cx-chip",{hasText:/Sleep onset|Wake time/})).toHaveCount(0);
 // The measurement on one axis is disabled on the other.
 await expect(chip(page,"X axis","Overnight HRV")).toBeDisabled();await expect(chip(page,"Y axis","Sleeping heart rate")).toBeDisabled();
 await chip(page,"X axis","Deep").click();
 await expect(page.locator(".cx-r")).toHaveText("Unavailable");await expect(page.getByText("Unavailable: a metric has no variation across the paired nights")).toBeVisible();
 await expect(page.locator(".cx-fit")).toHaveAttribute("data-fit","off");
 await chip(page,"X axis","Sleeping heart rate").click();
 await page.getByRole("group",{name:"Date range"}).getByRole("button",{name:"Custom"}).click();
 await page.getByLabel("From",{exact:true}).fill("2026-10-27");await page.getByLabel("To",{exact:true}).fill("2026-10-28");
 await expect(count(page,"Paired nights")).toHaveText("2");await expect(page.getByText("Unavailable: fewer than 3 paired nights")).toBeVisible();
 await page.getByLabel("From",{exact:true}).fill("2026-10-29");await expect(page.getByRole("alert")).toContainText("Choose a valid start and end date.");
 // 1 year: 365 calendar days ending on the latest night.
 await page.getByRole("group",{name:"Date range"}).getByRole("button",{name:"1 year"}).click();
 await expect(page.locator(".cx-scatter-card .cx-sub")).toHaveText("29 Oct 2025 – 28 Oct 2026 · 365 days");
 await page.screenshot({path:"../.cache/correlations-desktop.png",fullPage:true});
});

test("swap exchanges the axes, keeps r, and the points glide rather than being replaced (F2, F3)",async({page})=>{
 await open(page);const before=await rOf(page);
 const point=page.locator('.cx-pt[data-date="2026-10-28"]'),handle=await point.elementHandle();
 expect(await point.evaluate((e:Element)=>getComputedStyle(e).transitionProperty)).toContain("cx");
 const start=await point.boundingBox();
 await page.getByRole("button",{name:"Swap the X and Y measurements"}).click();
 await expect(page.locator("#cx-title")).toHaveText("Sleeping heart rate against Overnight HRV");
 await expect(page.locator(".cx-x-title")).toHaveText("Overnight HRV (ms)");
 // Same element, now moving (mid-transition it is between where it was and where it ends).
 await page.waitForTimeout(250);const mid=await point.boundingBox();
 expect(await handle!.evaluate((e:Element)=>e.isConnected)).toBe(true);
 await expect.poll(()=>rOf(page)).toBeCloseTo(before,12);
 await page.waitForTimeout(800);const end=await point.boundingBox();
 expect(mid!.x).not.toBe(start!.x);expect(mid!.x).not.toBe(end!.x);
 expect(Math.min(start!.x,end!.x)-1).toBeLessThanOrEqual(mid!.x);expect(mid!.x).toBeLessThanOrEqual(Math.max(start!.x,end!.x)+1);
});

test("tooltip and keyboard read exact nights; hover is steady (F3)",async({page})=>{
 await open(page);
 await page.locator(".cx-scatter").focus();
 const tip=page.locator(".cx-tip");
 // Last paired night is i=119 (28 Oct): HR 50 + 119%11 = 59, HRV 35 + 119%23 = 39.
 await expect(tip.locator("time")).toHaveText("28 Oct 2026");await expect(tip).toContainText("59.0 bpm");await expect(tip).toContainText("39 ms");
 await page.keyboard.press("ArrowLeft");await expect(tip.locator("time")).toHaveAttribute("datetime","2026-10-27");
 await page.keyboard.press("Home");await expect(tip.locator("time")).toHaveAttribute("datetime",iso(range(30,119).find(i=>recorded(i)&&i%9!==0)!));
 await page.locator(".cx-scatter").blur();await expect(tip).not.toHaveClass(/on/);
 // A slow sweep never returns to a point it already left (no flicker between neighbours).
 // Sweep horizontally through the middle of the point cloud (median point height), edge to edge.
 const centres=await page.locator(".cx-pt").evaluateAll((els:Element[])=>els.map(e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2];}));
 const ys=centres.map(c=>c[1]).sort((a,b)=>a-b),midY=ys[Math.floor(ys.length/2)],xs=centres.map(c=>c[0]),x0=Math.min(...xs),x1=Math.max(...xs);
 const seen:string[]=[];let last="",returns=0;
 for(let k=0;k<=120;k++){await page.mouse.move(x0+(x1-x0)*k/120,midY);
  const now=await tip.evaluate((e:Element)=>e.classList.contains("on")?e.querySelector("time")?.getAttribute("datetime")??"":"");
  if(now!==last){if(now&&seen.includes(now))returns++;if(now)seen.push(now);last=now;}}
 expect(seen.length,"the sweep must actually visit several points").toBeGreaterThan(3);expect(returns).toBe(0);
});

test("best-fit line comes from Python and can be switched off (F4)",async({page})=>{
 await open(page);
 const fit=page.locator(".cx-fit");await expect(fit).toHaveAttribute("data-fit","on");
 await page.getByText("Best-fit line").click();await expect(fit).toHaveAttribute("data-fit","off");
 await expect.poll(()=>fit.evaluate((e:Element)=>getComputedStyle(e).opacity)).toBe("0");
 await page.getByText("Best-fit line").click();await expect(fit).toHaveAttribute("data-fit","on");
});

test("over-time strip links to the scatter and narrows the nights by dragging (F6)",async({page})=>{
 await open(page);
 await expect(page.locator(".cx-strip .cx-series")).toHaveCount(2);
 const strip=page.locator(".cx-strip");await strip.scrollIntoViewIfNeeded();const box=(await strip.boundingBox())!;
 // Hovering the strip's last night highlights that night's point in the scatter.
 await page.mouse.move(box.x+box.width-13,box.y+60);await expect(page.locator(".cx-tip time")).toHaveAttribute("datetime","2026-10-28");
 await page.mouse.move(box.x+box.width*.3,box.y+60);await page.mouse.down();await page.mouse.move(box.x+box.width*.6,box.y+60,{steps:8});
 await expect(page.locator(".cx-drag-label")).toContainText("days");await page.mouse.up();
 await expect(page.locator(".cx-narrow")).toContainText("Narrowed to");
 await expect(page.locator(".cx-main")).toHaveAttribute("aria-busy","false");
 const sub=await page.locator(".cx-scatter-card .cx-sub time").evaluateAll((t:Element[])=>t.map(e=>e.getAttribute("datetime")));
 const api=await (await page.request.post("/api/v1/analytics/correlation",{data:{x:"hr_mean",y:"hrv_mean",range:"custom",start:sub[0],end:sub[1]},headers:HEADERS})).json();
 await expect(count(page,"Paired nights")).toHaveText(String(api.n));expect(api.n).toBeLessThan(74);
 await page.getByRole("button",{name:"Use the whole range again"}).click();await expect(count(page,"Paired nights")).toHaveText("74");
});

test("every-pair grid matches Python and opens a pair (F7)",async({page})=>{
 await open(page);
 const grid=await (await page.request.post("/api/v1/analytics/correlation/matrix",{data:{range:"90"},headers:HEADERS})).json();
 await expect(page.locator(".cx-cell")).toHaveCount(grid.cells.length);
 const cell=grid.cells.find((c:any)=>c.x==="asleep_s"&&c.y==="overall");
 const button=page.locator('.cx-cell[data-x="asleep_s"][data-y="overall"]');
 await expect(button).toHaveText(`${cell.r>0?"+":"−"}${Math.abs(cell.r).toFixed(2)}`);
 // Deep is constant in the fixture, so its cells are not calculated.
 await expect(page.locator(".cx-cell.na").first()).toBeDisabled();
 await button.hover();await expect(page.locator(".cx-cell-info")).toContainText(`${cell.n} paired nights`);
 await button.click();await expect(page.locator("#cx-title")).toHaveText("SleepIQ score against Total asleep");
 await expect.poll(()=>rOf(page)).toBeCloseTo(cell.r,10);await expect(button).toHaveClass(/sel/);
});

for(const [width,height] of [[1366,768],[1440,900],[1920,1080]])test(`fits the screen proportionally at ${width}x${height}`,async({page})=>{
 await page.setViewportSize({width,height});await open(page);
 const card=(await page.locator(".cx-scatter-card").boundingBox())!,side=(await page.locator(".cx-side").boundingBox())!,svg=(await page.locator(".cx-scatter").boundingBox())!;
 expect(card.height,"scatter card fits one screen").toBeLessThanOrEqual(height-24);
 expect(svg.height,"plot is not squashed").toBeGreaterThanOrEqual(300);
 expect(side.height,"readout column is no taller than the scatter").toBeLessThanOrEqual(card.height+1);
 // No dead space: the plot reaches down to the card's footer.
 const plot=(await page.locator(".cx-plot-box").boundingBox())!,foot=(await page.locator(".cx-foot").boundingBox())!;
 expect(foot.y-(plot.y+plot.height),"gap between plot and footer").toBeLessThanOrEqual(24);
 // Drawn at real pixel size: tick labels keep their size whatever the width.
 const tick=(await page.locator(".cx-scatter .cx-tick").first().boundingBox())!;expect(tick.height).toBeGreaterThan(9);expect(tick.height).toBeLessThan(16);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
 await page.screenshot({path:`../.cache/cx-${width}.png`,fullPage:true});
});

test("phone width: no sideways scroll, readable ticks, reduced motion stops animation",async({page})=>{
 await page.setViewportSize({width:390,height:844});await open(page);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
 const tick=(await page.locator(".cx-scatter .cx-tick").first().boundingBox())!;expect(tick.height).toBeGreaterThan(9);
 await page.screenshot({path:"../.cache/correlations-mobile.png",fullPage:true});
 await page.emulateMedia({reducedMotion:"reduce"});
 await expect.poll(()=>page.locator(".cx-pt").first().evaluate((e:Element)=>getComputedStyle(e).transitionDuration)).toBe("0s");
});

test("the page banner follows the data source, never claiming a design preview for stored nights",async({page})=>{
 // The test store is synthetic, so it is labelled as such on Correlations too.
 await open(page);
 await expect(page.locator("main > .preview-banner").first()).toContainText("Synthetic preview");
 await expect(page.getByText("Design preview")).toHaveCount(0);
 // A store holding the owner's nights (synthetic flag false) reads as local data on every page.
 await page.route("**/api/v1/dashboard*",async(route:any)=>{const body=await(await route.fetch()).json();await route.fulfill({json:{...body,synthetic:false}});});
 await page.goto("/");
 for(const [nav,label] of [["Correlations","Local correlations"],["Analytics","Local analytics"],["Data & Settings","Local data & settings"],["Dashboard","Local dashboard"]]){
  await page.getByRole("button",{name:new RegExp(`^${nav}`)}).click();
  const banner=page.locator("main > .preview-banner").first();
  await expect(banner).toContainText(label);await expect(banner).toContainText("Your stored nights; calculated locally");
  await expect(banner).not.toContainText(/preview|Synthetic examples/);
 }
});
