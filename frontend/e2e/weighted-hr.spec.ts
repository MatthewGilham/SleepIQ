import {expect,test} from "@playwright/test";

test("HR information is keyboard accessible and distinguishes weighting from fallback",async({page})=>{
 await page.route("**/api/v1/dashboard*",async route=>{
  const response=await route.fetch(),body=await response.json();
  const hr=body.latest.physiology.find((p:any)=>p.id==="hr");
  hr.quality={method:"time_weighted_linear",n:18,eligible_n:18,contributing_n:18,covered_s:22320,window_s:28800,coverage:0.775,fallback_reason:null};
  await route.fulfill({response,json:body});
 });
 await page.goto("/");
 const info=page.getByRole("button",{name:"How sleeping heart rate is calculated"});
 await info.focus();await info.press("Space");
 await expect(info).toHaveAttribute("aria-expanded","true");
 await expect(page.getByRole("note")).toContainText("Time-weighted estimate · 18 samples");
 await expect(page.getByRole("note")).toContainText("6h 12m of 8h 00m (78%)");
 await page.screenshot({path:"../.cache/weighted-hr-info.png",fullPage:true});
 await info.press("Escape");await expect(page.getByRole("note")).toHaveCount(0);
 await page.getByRole("button",{name:"Analytics",exact:true}).click();
 await page.getByRole("checkbox",{name:"Overnight HRV",exact:true}).uncheck();
 await page.getByRole("checkbox",{name:"Sleeping heart rate",exact:true}).check();
 await page.locator(".chart-frame").focus();
 await expect(page.locator(".chart-tip .hr-quality")).toContainText("Simple average");
 await expect(page.locator(".chart-tip .hr-quality")).toContainText("Duration coverage unknown");
});
