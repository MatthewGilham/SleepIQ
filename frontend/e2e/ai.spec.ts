import {expect,test} from "@playwright/test";
// Tests share one server and its usage counter, so counts are compared relative to a baseline.
// The preview server uses a canned local provider (scripts/preview-charts.py); no AI service is ever contacted.
async function usage(page:any){return (await (await page.request.get("/api/v1/analysis/status")).json()).usage;}
async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Analytics",exact:true}).click();await expect(page.getByRole("heading",{name:"Ask about these nights"})).toBeVisible();}
test("opening Analytics, changing options and navigating never trigger an AI request",async({page})=>{
 const posts:string[]=[];page.on("request",r=>{if(r.url().includes("/api/v1/analysis")&&r.method()!=="GET")posts.push(r.url());});
 const before=(await usage(page)).today;
 await open(page);
 await page.getByRole("group",{name:"Rolling average"}).getByRole("button",{name:"7-day avg"}).click();await page.getByRole("group",{name:"Display"}).getByRole("button",{name:"Normalized"}).click();
 await page.getByRole("button",{name:"Correlations",exact:true}).click();await page.getByRole("button",{name:"Dashboard",exact:true}).click();
 await page.getByRole("button",{name:"Analytics",exact:true}).click();
 await page.getByLabel("Your question about the selected metrics and range").fill("Is HRV related to sleep time?");
 await page.waitForTimeout(300);
 expect(posts).toEqual([]);expect((await usage(page)).today).toBe(before);
 await expect(page.getByRole("button",{name:"Analyze"})).toBeEnabled();
});
test("Analyze is disabled until a question is typed, then answers and shows the evidence sent",async({page})=>{
 const before=(await usage(page)).today;
 await open(page);
 await expect(page.getByText("Clicking Analyze sends one request to OpenAI")).toBeVisible();
 await expect(page.getByText("SleepIQ does not store your question or the answer.")).toBeVisible();
 await expect(page.getByRole("button",{name:"Analyze"})).toBeDisabled();await expect(page.getByText("Type a question (at least 3 characters).")).toBeVisible();
 await page.getByLabel("Your question about the selected metrics and range").fill("Is HRV related to sleep time?");
 await page.getByRole("button",{name:"Analyze"}).click();
 await expect(page.getByText("SYNTHETIC preview answer.")).toBeVisible();
 await expect(page.getByText(`Used today ${before+1}/20`).first()).toBeVisible();
 await page.getByText("Evidence sent for this answer").click();
 await expect(page.getByRole("cell",{name:"Total asleep (h)"})).toBeVisible();await expect(page.getByRole("cell",{name:"Overnight HRV (ms)"})).toBeVisible();
 // 30-day default range ending 2026-10-28; HRV absent when i%9==0, nights absent when i%13==0.
 await expect(page.getByText("2026-09-29 to 2026-10-28 · 30 calendar days")).toBeVisible();
 await expect(page.getByRole("cell",{name:"Total asleep / Overnight HRV"})).toBeVisible();
 expect((await usage(page)).today).toBe(before+1);
 await page.screenshot({path:"../.cache/ai-desktop.png",fullPage:true});
});
test("a provider failure shows a safe message, counts the attempt and leaves charts working",async({page})=>{
 const before=(await usage(page)).today;
 await open(page);
 await page.getByLabel("Your question about the selected metrics and range").fill("FAIL please");
 await page.getByRole("button",{name:"Analyze"}).click();
 await expect(page.getByRole("alert")).toContainText("The AI service did not answer in time.");
 await expect(page.locator('.main-svg g[data-metric="asleep_s"]')).toBeAttached();
 await expect(page.getByText(`used today ${before+1}/20`)).toBeVisible();
});
test("the chart never selects more metrics than the AI accepts (6)",async({page})=>{
 await open(page);
 await page.getByLabel("Your question about the selected metrics and range").fill("Anything at all");
 await page.getByRole("checkbox",{name:"Overnight HRV",exact:true}).uncheck();
 for(const name of ["Recorded awake","Deep","REM","SleepIQ score","Consistency"])await page.getByRole("checkbox",{name,exact:true}).check();
 await expect(page.getByText("6 metrics selected")).toBeVisible();await expect(page.getByRole("button",{name:"Analyze"})).toBeEnabled();
 await page.getByRole("checkbox",{name:"Sleeping heart rate",exact:true}).click({force:true});
 await expect(page.locator(".chip-note")).toContainText("at most 6 lines");await expect(page.getByText("6 metrics selected")).toBeVisible();
 await expect(page.getByText("Select at most 6 metrics to analyze.")).toHaveCount(0);
});
test("narrow screen keeps the AI panel inside the page",async({page})=>{
 await open(page);await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
