import {expect,test} from "@playwright/test";
import {readFileSync} from "node:fs";
// Same synthetic store as the other specs: night i exists unless i%13==0 (i=0..119, wake 2026-07-01+i); HRV absent when i%9==0.
// 120 nights minus i in {0,13,...,117} (10 values) = 110 stored nights, so 2026-07-01 (i=0) and 2026-10-26 (i=117) are absent; the latest is 2026-10-28.
async function open(page:any){await page.goto("/");await page.getByRole("button",{name:"Data & Settings",exact:true}).click();await expect(page.getByRole("heading",{name:"Export nightly metrics"})).toBeVisible();}
test("exports every metric for all history as a CSV with blanks for missing readings",async({page})=>{
 await open(page);
 const [download]=await Promise.all([page.waitForEvent("download"),page.getByRole("button",{name:"Download CSV"}).click()]);
 expect(download.suggestedFilename()).toBe("sleepiq-nightly-2026-07-02_2026-10-28.csv");
 const text=readFileSync(await download.path()!,"utf8");
 const lines=text.replace(/^﻿/,"").trim().split("\r\n");
 expect(lines).toHaveLength(111);
 expect(lines[0].split(",")[0]).toBe("wake_date");expect(lines[0]).toContain("Overnight HRV (ms)");expect(lines[0]).toContain("Sleep onset (HH:MM source-local)");
 expect(lines[0].endsWith("score_status,derivation_version,score_version")).toBe(true);
 const hrv=lines[0].split(",").indexOf("Overnight HRV (ms)");
 // Night i=9 (wake 2026-07-10) has no HRV: the cell is empty, not zero.
 expect(lines.find(l=>l.startsWith("2026-07-10,"))!.split(",")[hrv]).toBe("");
 expect(lines.find(l=>l.startsWith("2026-10-28,"))!.split(",")[hrv]).toBe("39.0");
 await expect(page.getByText("Downloaded 110 nights as sleepiq-nightly-2026-07-02_2026-10-28.csv.")).toBeVisible();
 expect(text).not.toMatch(/token|secret|password/i);
});
test("selected metrics and a custom range limit the file; invalid choices are blocked",async({page})=>{
 await open(page);
 await page.getByRole("button",{name:"Clear"}).click();
 await expect(page.getByRole("button",{name:"Download CSV"})).toBeDisabled();await expect(page.getByText("Choose at least one metric.")).toBeVisible();
 await page.getByRole("checkbox",{name:"Total asleep (h)"}).check();await page.getByRole("checkbox",{name:"Sleep onset (HH:MM)"}).check();
 await page.getByLabel("Export range").selectOption("custom");
 await expect(page.getByRole("button",{name:"Download CSV"})).toBeDisabled();
 await page.getByLabel("From",{exact:true}).fill("2026-10-20");await page.getByLabel("To",{exact:true}).fill("2026-10-28");
 const [download]=await Promise.all([page.waitForEvent("download"),page.getByRole("button",{name:"Download CSV"}).click()]);
 const lines=readFileSync(await download.path()!,"utf8").replace(/^﻿/,"").trim().split("\r\n");
 expect(lines[0]).toBe("wake_date,Total asleep (h),Sleep onset (HH:MM source-local),flags,score_status,derivation_version,score_version");
 expect(lines).toHaveLength(9); // 20..28 Oct is 9 days; 26 Oct (i=117) has no record, so 8 nights plus the header
 expect(lines[1].startsWith("2026-10-20,")).toBe(true);expect(lines.some(l=>l.startsWith("2026-10-26,"))).toBe(false);expect(lines[1].split(",")[2]).toBe("23:00");
 await page.getByLabel("To",{exact:true}).fill("2026-10-01");await expect(page.getByText("Choose a valid start and end date.")).toBeVisible();
 await expect(page.getByRole("button",{name:"Download CSV"})).toBeDisabled();
});
test("a failed export shows a message and leaves the page usable",async({page})=>{
 await open(page);
 await page.route("**/api/v1/analytics/export",r=>r.fulfill({status:500,json:{detail:"x"}}));
 await page.getByRole("button",{name:"Download CSV"}).click();
 await expect(page.getByRole("alert")).toContainText("Export failed (500)");await expect(page.getByRole("button",{name:"Download CSV"})).toBeEnabled();
});
test("keyboard operation and narrow screens",async({page})=>{
 await open(page);
 await page.getByRole("button",{name:"Select all"}).focus();await expect(page.getByRole("button",{name:"Select all"})).toBeFocused();
 await page.keyboard.press("Tab");await expect(page.getByRole("button",{name:"Clear"})).toBeFocused();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:"../.cache/export-mobile.png",fullPage:true});
});
