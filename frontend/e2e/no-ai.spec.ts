import {expect,test} from "@playwright/test";
// U06: the AI assistant was removed (DECISIONS P28); no page offers it or calls its endpoints.
test("no AI panel and no analysis request on any page",async({page})=>{
 const hits:string[]=[];
 page.on("request",r=>{if(r.url().includes("/api/v1/analysis"))hits.push(r.url());});
 await page.goto("/");
 for(const name of ["Dashboard","Analytics","Correlations"]){
  await page.getByRole("button",{name:new RegExp(`^${name}`)}).click();
  await expect(page.getByRole("heading",{name:/Ask about these nights/})).toHaveCount(0);
  await expect(page.getByRole("button",{name:/Analy[sz]e/})).toHaveCount(0);
  await page.waitForLoadState("networkidle");
 }
 await page.getByRole("button",{name:/^Analytics/}).click();
 await page.getByRole("group",{name:"Rolling average"}).getByRole("button",{name:"7-day avg"}).click();
 await page.getByRole("group",{name:"Display"}).getByRole("button",{name:"Normalized"}).click();
 await page.waitForLoadState("networkidle");
 expect(hits).toEqual([]);
});
