import {expect,test} from "@playwright/test";
async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByRole("heading",{name:"Your sleep, over time"})).toBeVisible();await expect(page.locator(".main-svg")).toBeVisible();}
// Segmented controls replace the old selects (U05); presets live behind the Presets menu.
const choose=(page:any,group:string,name:string)=>page.getByRole("group",{name:group}).getByRole("button",{name,exact:true}).click();
const presets=(page:any)=>page.locator(".preset-menu > summary").click();
test("charts ranges, normalized view, gaps, clock exclusion, zoom and keyboard",async({page})=>{
 await open(page);
 // Ranges end on the latest stored wake date (28 Oct); "All" starts at the first stored night (2 Jul, i=1).
 for(const [name,days] of [["7 days","7"],["90 days","90"],["All","119"],["30 days","30"]]){await choose(page,"Date range",name);await expect(page.locator(".range-label")).toHaveText(new RegExp(`28 Oct · ${days} days$`));}
 await choose(page,"Date range","Custom");
 await page.getByLabel("From",{exact:true}).fill("2026-10-01");await page.getByLabel("To",{exact:true}).fill("2026-10-28");
 await expect(page.locator(".range-label")).toHaveText("1 Oct – 28 Oct · 28 days");
 // Unrecorded nights (13 Oct, 26 Oct) break the HRV line into separate runs rather than bridging them.
 await expect.poll(()=>page.locator('.main-svg g[data-metric="hrv_mean"] path.series-line').count()).toBeGreaterThan(1);
 const frame=page.locator(".chart-frame");await frame.focus();await expect(frame).toBeFocused();await expect(page.locator(".chart-tip time")).toHaveAttribute("datetime","2026-10-28");
 await choose(page,"Display","Normalized");await expect(page.getByText("Standard deviations (z)",{exact:true})).toBeVisible();await expect(page.getByRole("checkbox",{name:"Sleep onset (actual only)",exact:true})).toBeDisabled();
 await page.getByRole("slider",{name:"Zoom start"}).focus();await page.keyboard.press("ArrowRight");await expect(page.getByLabel("From",{exact:true})).toHaveValue("2026-10-01");await page.getByRole("button",{name:"Reset zoom"}).click();
 await page.screenshot({path:"../.cache/charts-desktop.png",fullPage:true});
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole("heading",{name:"Your sleep, over time"})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:"../.cache/charts-mobile.png",fullPage:true});
});
test("presets create default reload rename cancel and delete",async({page})=>{
 await open(page);await presets(page);await page.getByLabel("Preset name",{exact:true}).fill("Browser test");await page.getByRole("checkbox",{name:"Default on opening Analytics"}).check();await page.getByRole("button",{name:"Save as new"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.reload();await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.locator(".preset-menu > summary")).toContainText("Browser test");await presets(page);await expect(page.getByLabel("Preset name",{exact:true})).toHaveValue("Browser test");
 await page.getByLabel("Preset name",{exact:true}).fill("Renamed browser test");await page.getByRole("button",{name:"Update selected"}).click();await page.getByRole("button",{name:"Confirm update"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Cancel",exact:true}).click();await expect(page.getByLabel("Preset name",{exact:true})).toHaveValue("Renamed browser test");
 await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Confirm delete"}).click();await expect(page.getByText("Preset deleted.",{exact:true})).toBeVisible();
});
test("charts empty and failed responses have intentional states",async({page})=>{
 await page.route("**/api/v1/analytics/timeseries",route=>route.fulfill({json:{dates:[],series:[],start:null,end:null,versions:[]}}));await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByRole("heading",{name:"No recorded nights yet"})).toBeVisible();
 await page.unroute("**/api/v1/analytics/timeseries");await page.route("**/api/v1/analytics/timeseries",route=>route.fulfill({status:503,json:{detail:"Unavailable"}}));await choose(page,"Date range","7 days");await expect(page.getByRole("alert")).toContainText("not configured");
});
