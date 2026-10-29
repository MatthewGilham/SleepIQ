import {expect,test} from "vitest";
import {axisTicks,clock,consistencyNote,contribution,duration,importText,longDay,missingText,number,offsetLabel,shortDay,stageBar} from "./dashboardModel";

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
