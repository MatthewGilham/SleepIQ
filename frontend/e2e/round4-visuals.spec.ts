import {expect,test} from "@playwright/test";
// P31 / R4-3. The synthetic store (scripts/preview-charts.py) gives Analytics a default 30-day range: a 30-night chart.
async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.locator(".brush")).toBeVisible();}
async function strip(page:any){await page.locator(".brush").scrollIntoViewIfNeeded();return (await page.locator(".brush").boundingBox())!;}
const days=(page:any)=>page.locator(".range-label");
const rgb=(c:string)=>c.replace(/\s/g,"");

test("KPI changes are coloured good or bad, never the old gold/ice",async({page})=>{
 await open(page);
 const spans=page.locator(".kpi-sub span:not(.muted)");const n=await spans.count();expect(n).toBeGreaterThan(0);
 for(let i=0;i<n;i++){
  const text=(await spans.nth(i).innerText()).trim(),cls=await spans.nth(i).getAttribute("class"),colour=rgb(await spans.nth(i).evaluate(e=>getComputedStyle(e).color));
  expect(text).toMatch(/^[▲▼±] /);
  if(text.startsWith("▲")){expect(cls).toContain("good");expect(colour).toBe("rgb(143,207,159)");}
  if(text.startsWith("▼")){expect(cls).toContain("bad");expect(colour).toBe("rgb(224,120,143)");}
 }
});

test("no range sliders; handles start at the strip ends and read dates",async({page})=>{
 await open(page);
 await expect(page.locator("input[type=range]")).toHaveCount(0);
 await expect(page.getByText("Zoom start",{exact:true})).toHaveCount(0);
 const s=page.getByRole("slider",{name:"Zoom start"}),e=page.getByRole("slider",{name:"Zoom end"});
 await expect(s).toHaveAttribute("aria-valuenow","0");await expect(e).toHaveAttribute("aria-valuenow","29");
 await expect(s).toHaveAttribute("aria-valuetext",/\d{4}/);
 await expect(page.getByRole("button",{name:"Reset zoom"})).toHaveCount(0);
});

test("keyboard moves the handles; Reset zoom appears only while zoomed",async({page})=>{
 await open(page);
 const s=page.getByRole("slider",{name:"Zoom start"}),e=page.getByRole("slider",{name:"Zoom end"});
 await s.focus();await page.keyboard.press("PageUp");await expect(s).toHaveAttribute("aria-valuenow","7");await expect(days(page)).toContainText("23 days");
 await page.keyboard.press("ArrowLeft");await expect(s).toHaveAttribute("aria-valuenow","6");
 await page.keyboard.press("End");await expect(s).toHaveAttribute("aria-valuenow","28");await expect(days(page)).toContainText("2 days");
 await page.keyboard.press("Home");await expect(s).toHaveAttribute("aria-valuenow","0");
 await expect(page.getByRole("button",{name:"Reset zoom"})).toHaveCount(0);
 await e.focus();await page.keyboard.press("PageDown");await expect(e).toHaveAttribute("aria-valuenow","22");
 await expect(page.getByRole("button",{name:"Reset zoom"})).toBeVisible();
 await page.getByRole("button",{name:"Reset zoom"}).click();await expect(days(page)).toContainText("30 days");await expect(page.getByRole("button",{name:"Reset zoom"})).toHaveCount(0);
});

test("dragging a handle resizes, the body pans, empty strip draws; handles cannot cross",async({page})=>{
 await open(page);
 let box=await strip(page);let y=box.y+box.height/2;
 const px=(i:number)=>box.x+box.width*(56+i/29*788)/900;
 await page.mouse.move(px(0),y);await page.mouse.down();await page.mouse.move(px(10),y,{steps:6});
 await expect(page.locator(".brush-label")).toContainText("days");await page.mouse.up();
 await expect(days(page)).toContainText("20 days");
 // pan left by 5 nights keeps the window length
 await page.mouse.move(px(20),y);await page.mouse.down();await page.mouse.move(px(15),y,{steps:6});await page.mouse.up();
 await expect(days(page)).toContainText("20 days");await expect(page.getByRole("slider",{name:"Zoom start"})).toHaveAttribute("aria-valuenow","5");
 // the end handle cannot pass the start handle
 await page.mouse.move(px(24),y);await page.mouse.down();await page.mouse.move(px(1),y,{steps:8});await page.mouse.up();
 await expect(days(page)).toContainText("2 days");
 await page.getByRole("button",{name:"Reset zoom"}).click();
 // drawing on empty strip
 box=await strip(page);y=box.y+box.height/2;
 await page.mouse.move(px(5),y);await page.mouse.down();await page.mouse.move(px(12),y,{steps:5});await page.mouse.up();
 await expect(days(page)).toContainText("8 days");
 await page.locator(".brush").dblclick();await expect(days(page)).toContainText("30 days");
});

test("switches keep checkbox semantics and look like switches",async({page})=>{
 await open(page);
 const box=page.getByRole("checkbox",{name:"Show averages"});await expect(box).toBeChecked();
 await box.focus();await page.keyboard.press("Space");await expect(box).not.toBeChecked();
 const track=page.locator(".an-switch span").first();const b=(await track.boundingBox())!;expect(Math.round(b.width)).toBe(30);expect(Math.round(b.height)).toBe(17);
});

test("390 px: a handle is grabbable from 10 px away and the page does not scroll sideways",async({page})=>{
 await page.setViewportSize({width:390,height:844});await open(page);
 const box=await strip(page),y=box.y+box.height/2,startX=box.x+box.width*56/900;
 // 10 px inside the strip from the start handle still resizes (a new window would have moved the end handle).
 await page.mouse.move(startX+10,y);await page.mouse.down();await page.mouse.move(startX+60,y,{steps:5});await page.mouse.up();
 await expect(page.getByRole("slider",{name:"Zoom end"})).toHaveAttribute("aria-valuenow","29");
 expect(Number(await page.getByRole("slider",{name:"Zoom start"}).getAttribute("aria-valuenow"))).toBeGreaterThan(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
