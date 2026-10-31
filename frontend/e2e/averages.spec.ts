import {expect,test} from "@playwright/test";
// U08 average lines. Independent reference for the synthetic store built by scripts/preview-charts.py (see analytics-redesign.spec.ts):
// night i (none where i%13===0) wakes on 2026-07-01 + i days; asleep = 390 + i%40 minutes; HRV = 35 + i%23 ms except where i%9===0.
// The default 30-day range is i = 90..119.
const recorded=(i:number)=>i%13!==0;
const last30=Array.from({length:30},(_,k)=>90+k);
const mean=(v:number[])=>v.reduce((s,x)=>s+x,0)/v.length;
const sd=(v:number[])=>Math.sqrt(mean(v.map(x=>(x-mean(v))**2)));
const hm=(minutes:number)=>{const m=Math.round(minutes);return `${Math.floor(m/60)}h ${String(m%60).padStart(2,"0")}m`;};
const asleepH=last30.filter(recorded).map(i=>(390+i%40)/60);
const hrv=last30.filter(i=>recorded(i)&&i%9!==0).map(i=>35+i%23);
// Chart geometry shared with Analytics.tsx: plot from y=14 to y=270.
const T=14,IH=256;
const yAt=(v:number,lo:number,hi:number)=>T+IH-(v-lo)/(hi-lo)*IH;
const padded=(values:number[]):[number,number]=>{const lo=Math.min(...values),hi=Math.max(...values),pad=(hi-lo)*0.15;return [lo-pad,hi+pad];};
const ASLEEP_LABEL=`avg ${hm(mean(asleepH)*60)}`,HRV_LABEL=`avg ${mean(hrv).toFixed(0)} ms`;

async function open(page:any){await page.goto("/");await page.getByRole("button",{name:/^Analytics/}).click();await expect(page.locator(".main-svg")).toBeVisible();await expect(page.locator(".an-body")).toHaveAttribute("aria-busy","false");}
const avg=(page:any,id:string)=>page.locator(`.main-svg .average[data-average="${id}"]`);
const y1=async(line:any)=>Number(await line.getAttribute("y1"));
const chip=(page:any,name:string)=>page.getByRole("checkbox",{name,exact:true});

test("one dotted average line per metric at the independently derived mean",async({page})=>{
 await open(page);
 await expect(page.locator(".main-svg .average-line")).toHaveCount(2);
 const sleep=avg(page,"asleep_s").locator("line"),beat=avg(page,"hrv_mean").locator("line");
 for(const [line,ink] of [[sleep,"#ff695b"],[beat,"#7fd3ff"]] as const){
  expect(await line.getAttribute("y1")).toBe(await line.getAttribute("y2"));
  expect(await line.getAttribute("stroke")).toBe(ink);
  expect(await line.getAttribute("stroke-dasharray")).toBe("1 5");
 }
 // Hours start at zero (top = 1.1 × highest night); HRV is padded 15% of its spread either side.
 expect(Math.abs(await y1(sleep)-yAt(mean(asleepH),0,Math.max(...asleepH)*1.1))).toBeLessThanOrEqual(1);
 const [lo,hi]=padded(hrv);expect(Math.abs(await y1(beat)-yAt(mean(hrv),lo,hi))).toBeLessThanOrEqual(1);
 await expect(avg(page,"asleep_s").locator(".average-label")).toHaveText(ASLEEP_LABEL);
 await expect(avg(page,"hrv_mean").locator(".average-label")).toHaveText(HRV_LABEL);
 // Rolling lines stay dashed, so the two kinds of line remain distinct.
 await page.getByRole("group",{name:"Rolling average"}).getByRole("button",{name:"7-day avg"}).click();
 await expect(page.locator(".main-svg .rolling-line").first()).toHaveAttribute("stroke-dasharray","5 5");
});

// P32: the line, its label and the tooltip describe the nights on screen. i = 90..119 is the unzoomed range.
const win=(from:number,to:number)=>Array.from({length:to-from+1},(_,k)=>from+k);
const labels=(idx:number[])=>({sleep:`avg ${hm(mean(idx.filter(recorded).map(i=>390+i%40)))}`,hrv:`avg ${mean(idx.filter(i=>recorded(i)&&i%9!==0).map(i=>35+i%23)).toFixed(0)} ms`});
const WIN_20_29=win(110,119),WIN_0_22=win(90,111),WIN_10_19=win(100,109);
async function strip(page:any){await page.locator(".brush").scrollIntoViewIfNeeded();return (await page.locator(".brush").boundingBox())!;}
async function expectLabels(page:any,idx:number[]){
 const want=labels(idx);
 await expect(avg(page,"asleep_s").locator(".average-label")).toHaveText(want.sleep);
 await expect(avg(page,"hrv_mean").locator(".average-label")).toHaveText(want.hrv);
}

test("the average follows the zoom: handles, panning and reset",async({page})=>{
 await open(page);
 // The stretches must really differ, or the test could pass without the line moving.
 expect(labels(WIN_20_29).sleep).not.toBe(labels(last30).sleep);expect(labels(WIN_20_29).hrv).not.toBe(labels(last30).hrv);
 await expectLabels(page,last30);
 await page.getByRole("slider",{name:"Zoom start"}).focus();for(let k=0;k<20;k++)await page.keyboard.press("ArrowRight");
 await expect(page.locator(".range-label")).toContainText("10 days");
 await expectLabels(page,WIN_20_29);
 // The line sits at the visible mean on its own axis (hours start at zero; top = 1.1 x the highest visible night).
 const visibleH=WIN_20_29.filter(recorded).map(i=>(390+i%40)/60);
 expect(Math.abs(await y1(avg(page,"asleep_s").locator("line"))-yAt(mean(visibleH),0,Math.max(...visibleH)*1.1))).toBeLessThanOrEqual(1);
 // Tooltip repeats the same text as the label.
 await page.locator(".chart-frame").focus();
 await expect(page.locator('.chart-tip .tip-row.average[data-average="asleep_s"] span').last()).toHaveText(labels(WIN_20_29).sleep);
 await expect(page.locator('.chart-tip .tip-row.average[data-average="hrv_mean"] span').last()).toHaveText(labels(WIN_20_29).hrv);
 // Panning the window 10 nights to the left.
 const box=await strip(page),y=box.y+box.height/2,px=(k:number)=>box.x+box.width*(56+k/29*788)/900;
 await page.mouse.move(px(25),y);await page.mouse.down();await page.mouse.move(px(15),y,{steps:8});await page.mouse.up();
 await expect(page.locator(".range-label")).toContainText("10 days");await expectLabels(page,WIN_10_19);
 // Reset zoom returns to the whole range.
 await page.getByRole("button",{name:"Reset zoom"}).click();await expect(page.locator(".range-label")).toContainText("30 days");await expectLabels(page,last30);
 // The end handle also moves the line.
 await page.getByRole("slider",{name:"Zoom end"}).focus();await page.keyboard.press("PageDown");await page.keyboard.press("ArrowLeft");
 await expect(page.locator(".range-label")).toContainText("22 days");await expectLabels(page,WIN_0_22);
});

test("zoom to fit keeps every average line in the plot, zoomed or not",async({page})=>{
 await open(page);
 await page.getByRole("checkbox",{name:"Zoom to fit hours axis"}).check();
 const inside=async()=>{for(const line of await page.locator(".main-svg .average-line").all()){const y=await y1(line);expect(y).toBeGreaterThanOrEqual(T);expect(y).toBeLessThanOrEqual(T+IH);}};
 await inside();
 await page.getByRole("slider",{name:"Zoom start"}).focus();for(let k=0;k<20;k++)await page.keyboard.press("ArrowRight");
 await expectLabels(page,WIN_20_29);await inside();
});

test("normalized mode keeps one line at 0 while zooming",async({page})=>{
 await open(page);
 await page.getByRole("group",{name:"Display"}).getByRole("button",{name:"Normalized",exact:true}).click();
 await expect(page.locator(".main-svg .average-line")).toHaveCount(1);
 await page.getByRole("slider",{name:"Zoom start"}).focus();for(let k=0;k<20;k++)await page.keyboard.press("ArrowRight");
 await expect(page.locator(".range-label")).toContainText("10 days");
 await expect(page.locator(".main-svg .average-line")).toHaveCount(1);await expect(page.locator(".main-svg .average-label")).toHaveText("average (0)");
});

test("Show averages is on by default, toggles every line and is not remembered",async({page})=>{
 await open(page);
 const box=page.getByRole("checkbox",{name:"Show averages"});
 await expect(box).toBeChecked();
 await box.uncheck();await expect(page.locator(".main-svg .average-line")).toHaveCount(0);await expect(page.locator(".main-svg .average-label")).toHaveCount(0);
 await box.check();await expect(page.locator(".main-svg .average-line")).toHaveCount(2);
 await box.uncheck();await page.reload();await open(page);
 await expect(page.getByRole("checkbox",{name:"Show averages"})).toBeChecked();
});

test("normalized mode shows one shared line at zero",async({page})=>{
 await open(page);
 await page.getByRole("group",{name:"Display"}).getByRole("button",{name:"Normalized"}).click();
 await expect(page.locator(".main-svg .average-line")).toHaveCount(1);
 await expect(page.locator(".main-svg .average-label")).toHaveText("average (0)");
 const z=(v:number[])=>v.map(x=>(x-mean(v))/sd(v));
 const [lo,hi]=padded([...z(asleepH),...z(hrv),0]);
 expect(Math.abs(await y1(page.locator(".main-svg .average-line"))-yAt(0,lo,hi))).toBeLessThanOrEqual(1);
 await chip(page,"Sleeping heart rate").check();await expect(page.locator(".main-svg g[data-metric=\"hr_mean\"]")).toBeAttached();
 await expect(page.locator(".main-svg .average-line")).toHaveCount(1);
});

test("clock times get no average; other metrics keep theirs",async({page})=>{
 await open(page);
 await chip(page,"Overnight HRV").uncheck();await chip(page,"Sleep onset").check();await chip(page,"Wake time").uncheck();
 await expect(page.locator(".main-svg g[data-metric=\"onset_minute\"]")).toBeAttached();
 await expect(page.locator(".main-svg .average-line")).toHaveCount(1);
 await expect(avg(page,"asleep_s")).toHaveCount(1);await expect(avg(page,"onset_minute")).toHaveCount(0);
});

test("the tooltip repeats the label text",async({page})=>{
 await open(page);
 await page.locator(".chart-frame").focus();
 await expect(page.locator('.chart-tip .tip-row.average[data-average="asleep_s"] span').last()).toHaveText(ASLEEP_LABEL);
 await expect(page.locator('.chart-tip .tip-row.average[data-average="hrv_mean"] span').last()).toHaveText(HRV_LABEL);
});

test("a metric with no readings draws no average and its tooltip says so",async({page})=>{
 await open(page);
 // The synthetic store has no wrist-temperature readings.
 await chip(page,"Overnight HRV").uncheck();await chip(page,"Sleeping wrist temperature").check();
 await expect(page.locator(".main-svg g[data-metric=\"temp_mean\"]")).toBeAttached();
 await expect(avg(page,"temp_mean")).toHaveCount(0);await expect(page.locator(".main-svg .average-line")).toHaveCount(1);
 await page.locator(".chart-frame").focus();
 await expect(page.locator('.chart-tip .tip-row.average[data-average="temp_mean"] span').last()).toHaveText("no reading");
});
