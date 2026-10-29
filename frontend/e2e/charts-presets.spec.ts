import {expect,test} from "@playwright/test";
async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByRole("heading",{name:"Multi-metric exploration"})).toBeVisible();}
test("charts ranges, normalized view, gaps, clock exclusion, zoom and keyboard",async({page})=>{
 await open(page);
 for(const range of ["7","90","all","30"]){await page.getByLabel("Date range").selectOption(range);await expect(page.getByRole("group",{name:"Total asleep chart",exact:true})).toBeVisible();}
 await page.getByLabel("Date range").selectOption("custom");
 await page.getByLabel("From",{exact:true}).fill("2026-10-01");await page.getByLabel("To",{exact:true}).fill("2026-10-28");
 const chart=page.getByRole("group",{name:"Overnight HRV chart",exact:true});await expect(chart).toBeVisible();await expect(chart.locator("path")).not.toHaveCount(1);
 await chart.locator("circle").first().focus();await expect(chart.locator("circle").first()).toBeFocused();
 await page.getByLabel("Display",{exact:true}).selectOption("normalized");await expect(page.getByText("Standard deviations (z)",{exact:true})).toBeVisible();await expect(page.getByRole("checkbox",{name:"Sleep onset (actual only)",exact:true})).toBeDisabled();
 await page.getByRole("slider",{name:"Zoom start"}).focus();await page.keyboard.press("ArrowRight");await expect(page.getByLabel("From",{exact:true})).toHaveValue("2026-10-01");await page.getByRole("button",{name:"Reset zoom"}).click();
 await page.screenshot({path:"../.cache/charts-desktop.png",fullPage:true});
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole("heading",{name:"Explore your nights"})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:"../.cache/charts-mobile.png",fullPage:true});
});
test("presets create default reload rename cancel and delete",async({page})=>{
 await open(page);await page.getByLabel("Preset name",{exact:true}).fill("Browser test");await page.getByRole("checkbox",{name:"Default on opening Analytics"}).check();await page.getByRole("button",{name:"Save as new"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.reload();await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByLabel("Preset name",{exact:true})).toHaveValue("Browser test");
 await page.getByLabel("Preset name",{exact:true}).fill("Renamed browser test");await page.getByRole("button",{name:"Update selected"}).click();await page.getByRole("button",{name:"Confirm update"}).click();await expect(page.getByText("Preset saved.",{exact:true})).toBeVisible();
 await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Cancel",exact:true}).click();await expect(page.getByLabel("Preset name",{exact:true})).toHaveValue("Renamed browser test");
 await page.getByRole("button",{name:"Delete selected"}).click();await page.getByRole("button",{name:"Confirm delete"}).click();await expect(page.getByText("Preset deleted.",{exact:true})).toBeVisible();
});
test("charts empty and failed responses have intentional states",async({page})=>{
 await page.route("**/api/v1/analytics/timeseries",route=>route.fulfill({json:{dates:[],series:[],start:null,end:null,versions:[]}}));await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByRole("heading",{name:"No recorded nights yet"})).toBeVisible();
 await page.unroute("**/api/v1/analytics/timeseries");await page.route("**/api/v1/analytics/timeseries",route=>route.fulfill({status:503,json:{detail:"Unavailable"}}));await page.getByLabel("Date range").selectOption("7");await expect(page.getByRole("alert")).toContainText("not configured");
});
