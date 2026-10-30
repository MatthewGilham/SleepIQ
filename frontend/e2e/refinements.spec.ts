import {expect,test} from "@playwright/test";
// Round 3 refinements (DECISIONS P29, PLAN.md "Improvements, round 3"). Synthetic preview store only.

// Gaps inside the dashboard duration: number to unit (each group) and hour group to minute group.
async function durationGaps(page:any){
 return page.locator(".night-panel .sleep-total").evaluate((total:Element)=>{
  const parts=Array.from(total.querySelectorAll(".dur-part"));
  const unitGap=(part:Element)=>{const digits=document.createRange();digits.selectNodeContents(part.firstChild!);
   return part.querySelector(".dur-unit")!.getBoundingClientRect().left-digits.getBoundingClientRect().right;};
  return {units:parts.map(unitGap),groups:parts[1].getBoundingClientRect().left-parts[0].getBoundingClientRect().right};
 });
}

for(const width of [1440,390])test(`U09 duration units sit tight to their numbers with one even gap at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.goto("/");
 await expect(page.locator(".sleep-total")).toHaveText("7h 09m");
 const gaps=await durationGaps(page);
 for(const gap of gaps.units){expect(gap).toBeGreaterThanOrEqual(0);expect(gap).toBeLessThanOrEqual(4);}
 expect(gaps.groups).toBeGreaterThanOrEqual(8);expect(gaps.groups).toBeLessThanOrEqual(16);
});

test("U09 the three top panel titles line up",async({page})=>{
 await page.setViewportSize({width:1440,height:900});await page.goto("/");
 const tops=await page.locator(".hero-grid > .panel > .panel-title h2").evaluateAll((els:Element[])=>els.map(e=>e.getBoundingClientRect().top));
 expect(tops).toHaveLength(3);
 expect(Math.max(...tops)-Math.min(...tops)).toBeLessThanOrEqual(2);
 await page.locator(".hero-grid").screenshot({path:"../.cache/u09-hero.png"});
});
