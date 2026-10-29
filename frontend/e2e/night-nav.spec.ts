import {expect,test} from "@playwright/test";
// Independent reference for the synthetic store built by scripts/preview-charts.py: night i (i = 0..119, skipping every i divisible by 13)
// wakes on 2026-07-01 + i days and sleeps Core 120+i%40, Deep 60, REM 70, Core 140 minutes, so asleep = 390 + i%40 minutes; HRV is 35 + i%23 ms,
// except nights where i%9 === 0, which have no HRV sample.
const nights=Array.from({length:120},(_,i)=>i).filter(i=>i%13!==0).map(i=>{
 const d=new Date(Date.UTC(2026,6,1+i));const asleep=390+i%40;
 return {date:d.toISOString().slice(0,10),label:`${d.getUTCDate()} ${["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getUTCMonth()]}`,
  total:`${Math.floor(asleep/60)}h ${String(asleep%60).padStart(2,"0")}m`,hrv:i%9===0?null:35+i%23};
});
const latest=nights[nights.length-1];
const at=(back:number)=>nights[nights.length-1-back];
const shows=async(page:any,n:{label:string;total:string})=>{
 await expect(page.getByLabel("Night navigation").locator("strong")).toHaveText(`Night ending ${n.label}`);
 await expect(page.locator(".sleep-total")).toHaveText(n.total);
};
test("reference nights are what the tests assume (gaps at 26 Oct)",()=>{
 expect(latest.date).toBe("2026-10-28");expect(at(1).date).toBe("2026-10-27");expect(at(2).date).toBe("2026-10-25");expect(at(3).date).toBe("2026-10-24");
});
test("previous x3 then next x1 shows the expected nights in order, skipping unrecorded days",async({page})=>{
 await page.goto("/");await shows(page,latest);
 for(const back of [1,2,3]){await page.getByRole("button",{name:"Previous night"}).click();await shows(page,at(back));}
 await page.getByRole("button",{name:"Next night"}).click();await shows(page,at(2));
 await expect(page.locator("time")).toHaveText("Sunday, 25 October");
});
test("arrow keys move between nights, but not while a form field has focus",async({page})=>{
 await page.goto("/");await shows(page,latest);
 await page.keyboard.press("ArrowLeft");await shows(page,at(1));
 await page.keyboard.press("ArrowLeft");await shows(page,at(2));
 await page.keyboard.press("ArrowRight");await shows(page,at(1));
 await page.evaluate(()=>{const i=document.createElement("input");i.id="probe";document.body.appendChild(i);i.focus();});
 await page.keyboard.press("ArrowLeft");await page.keyboard.press("ArrowLeft");await page.waitForTimeout(300);
 await shows(page,at(1));
});
test("the night is kept in the address: reload stays, Latest clears it",async({page})=>{
 await page.goto("/");await page.getByRole("button",{name:"Previous night"}).click();await shows(page,at(1));
 await expect(page).toHaveURL(/\?night=2026-10-27$/);
 await page.reload();await shows(page,at(1));await expect(page).toHaveURL(/\?night=2026-10-27$/);
 await page.getByRole("button",{name:"Latest",exact:true}).click();await shows(page,latest);
 expect(new URL(page.url()).search).toBe("");
 await page.goBack();await shows(page,at(1));
});
test("buttons are disabled at the ends of the history",async({page})=>{
 await page.goto("/");
 await expect(page.getByRole("button",{name:"Next night"})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Latest",exact:true})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Previous night"})).toBeEnabled();
 await page.keyboard.press("ArrowRight");await shows(page,latest);
 const oldest=nights[0];
 await page.goto(`/?night=${oldest.date}`);await shows(page,oldest);
 await expect(page.getByRole("button",{name:"Previous night"})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Next night"})).toBeEnabled();
 await expect(page.getByRole("button",{name:"Latest",exact:true})).toBeEnabled();
});
test("a slow response keeps page height and scroll position, and marks old content busy",async({page})=>{
 await page.route("**/api/v1/dashboard*",async(route:any)=>{await new Promise(f=>setTimeout(f,150));await route.continue();});
 await page.goto("/");await shows(page,latest);
 await page.evaluate(()=>window.scrollTo(0,300));await page.waitForTimeout(100);
 await page.evaluate(()=>{const w=window as any;w.__frames=[];const tick=()=>{w.__frames.push([scrollY,document.documentElement.scrollHeight]);if(!w.__stop)requestAnimationFrame(tick);};w.__stop=false;requestAnimationFrame(tick);});
 const before=await page.evaluate(()=>[scrollY,document.documentElement.scrollHeight]);
 const region=page.locator("main [aria-busy]");
 await expect(region).toHaveAttribute("aria-busy","false");
 await page.getByRole("button",{name:"Previous night"}).click();
 await expect(region).toHaveAttribute("aria-busy","true");
 await expect(page.locator(".sleep-total")).toHaveText(latest.total); // old content still shown while loading
 await shows(page,at(1));await expect(region).toHaveAttribute("aria-busy","false");
 const frames:number[][]=await page.evaluate(()=>{const w=window as any;w.__stop=true;return w.__frames;});
 expect(Math.min(...frames.map(f=>f[0])),"scroll position jumped").toBe(before[0]);
 expect(Math.min(...frames.map(f=>f[1])),"page height dropped").toBeGreaterThanOrEqual(before[1]);
});
test("a night without HRV says so and never shows zero",async({page})=>{
 const noHrv=nights.find(n=>n.hrv===null&&n.date>"2026-10-01")!;
 await page.goto(`/?night=${noHrv.date}`);await shows(page,noHrv);
 const card=page.locator(".metric",{hasText:"Overnight HRV"});
 await expect(card).toContainText("Missing data");await expect(card).toContainText("No overnight samples");
 await expect(card).not.toContainText(/\b0\b/);
});
test("an address naming an unrecorded night explains and offers the latest",async({page})=>{
 await page.goto("/?night=2026-10-26");
 await expect(page.getByRole("alert")).toContainText("No sleep was recorded for that night.");
 await page.getByRole("button",{name:"Show latest night"}).click();await shows(page,latest);
});
