import {expect,test} from "vitest";
import {chartSegments,fileNameFrom,formatValue,rollingNote,scatterLayout,sliceSeries,withDefaults} from "./charts";
import type {Series} from "./charts";
test("rolling notes always show coverage and never invent a mean",()=>{
 const rolling={window:7,minimum:4,values:[null,55],counts:[3,5],reason:null};
 expect(rollingNote(rolling,0,v=>v.toFixed(1))).toBe("7-day mean unavailable (3/7 nights recorded; needs 4)");
 expect(rollingNote(rolling,1,v=>v.toFixed(1))).toBe("7-day mean 55.0 (5/7 nights recorded)");
 expect(rollingNote({window:30,minimum:15,values:null,counts:null,reason:"Not available for clock times"},0,String)).toBe("30-day mean: Not available for clock times");
});
test("zoom slices rolling values with points; old presets load with rolling off",()=>{
 const s={id:"hr_mean",label:"HR",unit:"bpm",method:"m",clock:false,values:[1,2,3],raw:[1,2,3],details:[0,1,2].map(n=>({n,flags:[],offset_minutes:null})),normalization:{n:3,mean:2,sd:1,reason:null,method:"z"},rolling:{window:7,minimum:4,values:[null,4,5],counts:[3,4,5],reason:null}} satisfies Series;
 const cut=sliceSeries(s,1,2);
 expect(cut.values).toEqual([2,3]);expect(cut.rolling?.values).toEqual([4,5]);expect(cut.rolling?.counts).toEqual([4,5]);
 expect(withDefaults({metrics:["hr_mean"],range:"7",start:null,end:null,mode:"actual"}).rolling).toBe("off");
});
test("scatter positions are proportional and constant axes are padded",()=>{
 const layout=scatterLayout([{date:"a",x:0,y:10},{date:"b",x:10,y:20}]);
 expect(layout.points.map(p=>[p.cx,p.cy])).toEqual([[60,290],[620,30]]);
 expect(scatterLayout([{date:"a",x:5,y:5},{date:"b",x:5,y:7}]).x).toEqual([4,6]);
 expect(scatterLayout([]).points).toEqual([]);
});
test("calendar gaps break lines, zero remains a measurement",()=>{
 expect(chartSegments([0,1,null,3],0,3)).toEqual(["M48.00,170.00 L328.00,123.33","M888.00,30.00"]);
 expect(chartSegments([null,null],0,1)).toEqual([]);
});
test("clock timestamps format separately from missing measurements",()=>{
 const metric={id:"onset_minute",label:"Onset",unit:"local time",method:"Source-local",clock:true};
 expect(formatValue(1435,metric)).toBe("23:55");
 expect(formatValue(null,metric)).toBe("Missing data");
 expect(formatValue(0,metric)).toBe("00:00");
});
test("export file names come only from the server's safe pattern",()=>{
 expect(fileNameFrom('attachment; filename="sleepiq-nightly-2026-09-29_2026-10-28.csv"')).toBe("sleepiq-nightly-2026-09-29_2026-10-28.csv");
 expect(fileNameFrom('attachment; filename="../../evil.bat"')).toBe("sleepiq-nightly.csv");
 expect(fileNameFrom("")).toBe("sleepiq-nightly.csv");
});
