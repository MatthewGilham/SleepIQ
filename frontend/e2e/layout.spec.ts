import {expect,test} from "@playwright/test";
// U07: every piece of text stays inside its card at every width (DECISIONS P28).
const WIDTHS=[390,900,1000,1100,1200,1366,1440,1720,1920];
const CARDS=".an-card, .tile, .metric, .panel";

// Returns one line per problem: text outside its card (1 px tolerance) or an element wider than its own box.
async function overflow(page:any):Promise<string[]>{
 return page.evaluate((selector:string)=>{
  const problems:string[]=[];
  const name=(el:Element)=>`${el.tagName.toLowerCase()}${el.className&&typeof el.className==="string"?"."+el.className.trim().split(/\s+/).join("."):""} "${(el.textContent??"").trim().slice(0,40)}"`;
  for(const card of Array.from(document.querySelectorAll(selector))){
   const box=card.getBoundingClientRect();if(!box.width)continue;
   for(const el of [card,...Array.from(card.querySelectorAll("*"))]){
    if(el.closest(".sr-only,[hidden],.chart-table"))continue;
    const own=Array.from(el.childNodes).some(n=>n.nodeType===3&&n.textContent!.trim());
    if(own&&el!==card){const r=el.getBoundingClientRect();
     if(r.width&&(r.left<box.left-1||r.right>box.right+1||r.top<box.top-1||r.bottom>box.bottom+1))problems.push(`${name(el)} outside ${name(card).slice(0,60)}`);}
    if(el instanceof HTMLElement&&el.scrollWidth>el.clientWidth+1&&getComputedStyle(el).display!=="inline")problems.push(`${name(el)} scrollWidth ${el.scrollWidth} > ${el.clientWidth}`);
   }
  }
  return problems;
 },CARDS);
}
async function nav(page:any,name:string){await page.getByRole("button",{name:new RegExp(`^${name}`)}).click();}
async function analytics(page:any,range:string){
 await nav(page,"Analytics");await page.getByRole("group",{name:"Date range"}).getByRole("button",{name:range,exact:true}).click();
 await expect(page.locator(".kpis")).toBeVisible();await expect(page.locator(".main-svg")).toBeVisible();await expect(page.locator(".an-body")).toHaveAttribute("aria-busy","false");
}

for(const width of WIDTHS)test(`text stays inside cards at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});await page.goto("/");
 await expect(page.locator(".metric").first()).toBeVisible();
 expect(await overflow(page),"Dashboard").toEqual([]);
 for(const range of ["30 days","All"]){await analytics(page,range);expect(await overflow(page),`Analytics ${range}`).toEqual([]);}
 if(width===390)expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
});

test("worst-case KPI values stay inside their cards at 1000px",async({page})=>{
 await page.route("**/api/v1/analytics/summary",async(route:any)=>{
  const body=await(await route.fetch()).json();
  body.days=1000;body.nights=1000;
  // The summary reports durations in hours.
  body.metrics.asleep_s={...body.metrics.asleep_s,mean:10+59/60,delta:2};
  body.metrics.overall={...body.metrics.overall,mean:100};
  body.metrics.hrv_mean={...body.metrics.hrv_mean,mean:250};
  await route.fulfill({json:body});
 });
 await page.setViewportSize({width:1000,height:1000});await page.goto("/");await analytics(page,"30 days");
 const kpis=page.locator(".kpis");
 for(const text of ["10h 59m","100.0 /100","250 ms","1000 of 1000","▲ 120 min vs previous 1000 days"])await expect(kpis).toContainText(text);
 expect(await overflow(page)).toEqual([]);
});
