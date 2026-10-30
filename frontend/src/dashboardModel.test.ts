import {expect,test} from "vitest";
import {axisTicks,clock,consistencyNote,contribution,duration,fullDay,hourTicks,importText,longDay,missingText,number,offsetLabel,shortDay,stageBar,tickDays,trendWindow} from "./dashboardModel";

test("durations and source-local strings are formatted without time-zone conversion",()=>{
 expect(duration(7*3600+20*60)).toBe("7h 20m");expect(duration(5*3600+5*60)).toBe("5h 05m");
 expect(clock("2026-10-27T23:12")).toBe("23:12");expect(shortDay("2026-10-27T23:12")).toBe("27 Oct");
 expect(longDay("2026-10-28")).toBe("Wednesday, 28 October");
 expect(offsetLabel(60)).toBe("UTC+01:00");expect(offsetLabel(-330)).toBe("UTC-05:30");expect(offsetLabel(0)).toBe("UTC+00:00");
 expect(axisTicks("2026-10-27T23:00",8*3600)).toEqual(["23:00","01:00","03:00","05:00","07:00"]);
});
test("zero is a value and null stays missing",()=>{
 expect(number(0)).toBe("0");expect(number(null)).toBeNull();expect(number(54.04)).toBe("54");expect(number(14.26)).toBe("14.3");
});
test("stage bars span the 878-unit track exactly",()=>{
 expect(stageBar(0,100,200)).toEqual({x:72,width:439});expect(stageBar(100,100,200).x+stageBar(100,100,200).width).toBe(950);
});
test("score breakdown shows contributions, and a dash where a component does not exist",()=>{
 expect(contribution({score:100,weight:30,neutral:false},100)).toBe("30.0");expect(contribution({score:75,weight:10,neutral:true},100)).toBe("7.5");
 expect(contribution(undefined,100)).toBe("—");
});
test("withheld scores explain what is missing",()=>{
 expect(missingText(["overnight_hrv"])).toBe("No overall score because of missing: overnight HRV.");
 expect(missingText(["consistency:insufficient_history","sleeping_hr"])).toContain("enough history for consistency, sleeping heart rate");
 expect(missingText([])).toBe("");
 expect(consistencyNote({available:false,reason:"insufficient_history",baseline_nights:3})).toContain("3 prior nights");
 expect(consistencyNote({available:true,provisional:true})).toContain("Provisional");
});
test("import status never invents a date",()=>{
 expect(importText({batches:0,last_received_utc:null,nights:0})).toBe("No imports yet");
 expect(importText({batches:2,last_received_utc:Date.UTC(2026,9,28)/1000,nights:90})).toBe("90 nights · last import 2026-10-28");
});
test("chart dates carry the year on the first tick and wherever the year changes (U13)",()=>{
 expect(fullDay("2026-10-29")).toBe("29 Oct 2026");expect(fullDay("2025-09-01T23:00")).toBe("1 Sep 2025");
 const dates=["2025-12-30","2025-12-31","2026-01-01","2026-01-02","2026-01-03"];
 expect([...tickDays(dates,[0,2,4]).values()]).toEqual(["30 Dec 2025","1 Jan 2026","3 Jan"]);
 expect([...tickDays(dates,[1,3]).values()]).toEqual(["31 Dec 2025","2 Jan 2026"]);
 expect([...tickDays(["2026-10-01","2026-10-15","2026-10-28"],[0,1,2]).values()]).toEqual(["1 Oct 2026","15 Oct","28 Oct"]);
 expect(tickDays([],[]).size).toBe(0);
});
test("the trend hours axis runs from 0 to at least 10 h in 2 h steps (U14)",()=>{
 expect(hourTicks(9.1)).toEqual([0,2,4,6,8,10]);expect(hourTicks(0)).toEqual([0,2,4,6,8,10]);
 expect(hourTicks(10)).toEqual([0,2,4,6,8,10]);expect(hourTicks(11.3)).toEqual([0,2,4,6,8,10,12]);
 expect(hourTicks(13)).toEqual([0,2,4,6,8,10,12,14]);
});
test("trend windows slice calendar days, pad before the history and start All at the first stored night (U15)",()=>{
 const trend={dates:["2026-10-24","2026-10-25","2026-10-26","2026-10-27","2026-10-28"],asleep_h:[null,7,null,6.5,8]};
 expect(trendWindow(trend,"all")).toEqual({dates:["2026-10-25","2026-10-26","2026-10-27","2026-10-28"],hours:[7,null,6.5,8]});
 const week=trendWindow(trend,7);
 expect(week.dates).toEqual(["2026-10-22","2026-10-23","2026-10-24","2026-10-25","2026-10-26","2026-10-27","2026-10-28"]);
 expect(week.hours).toEqual([null,null,null,7,null,6.5,8]);
 // Padding crosses month and year boundaries by calendar day.
 expect(trendWindow({dates:["2026-01-01"],asleep_h:[7]},7).dates[0]).toBe("2025-12-26");
 const long={dates:Array.from({length:400},(_,i)=>new Date(Date.UTC(2025,8,24+i)).toISOString().slice(0,10)),asleep_h:Array.from({length:400},(_,i)=>i%5?7:null)};
 for(const r of [7,30,90,365] as const){const w=trendWindow(long,r);expect(w.dates).toHaveLength(r);expect(w.dates.at(-1)).toBe(long.dates[399]);expect(w.hours).toEqual(long.asleep_h.slice(-r));}
 expect(trendWindow({dates:[],asleep_h:[]},30)).toEqual({dates:[],hours:[]});
});
