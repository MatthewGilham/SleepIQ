import {expect,test} from "vitest";
import {bezierAt,chartSegments,curveRuns,display,fileNameFrom,fitMetrics,formatValue,groupAxes,refusal,rollingNote,scatterLayout,sliceSeries,toAxis,withDefaults} from "./charts";
import type {Pt} from "./charts";
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
test("the curve never leaves its readings' range and a null splits the line",()=>{
 const ys=[5,9,2,2.5,8,8,1,7,null,3,6];
 const pts=ys.map((y,i)=>y===null?null:[i*10,y] as Pt);
 const runs=curveRuns(pts);
 expect(runs).toHaveLength(2);expect(runs[0].points).toHaveLength(8);expect(runs[1].points).toHaveLength(2);
 // No segment joins the last point before the gap to the first after it.
 expect(runs.flatMap(r=>r.segments).some(([a,,,b])=>a[0]===70&&b[0]===90)).toBe(false);
 const observed=ys.filter((v):v is number=>v!==null),lo=Math.min(...observed),hi=Math.max(...observed);
 for(const run of runs)for(const seg of run.segments){
  const ends=[seg[0][1],seg[3][1]];
  for(let t=0;t<=1.0001;t+=0.01){const [,y]=bezierAt(seg,t);
   expect(y).toBeGreaterThanOrEqual(lo-1e-9);expect(y).toBeLessThanOrEqual(hi+1e-9);
   // Stronger: each segment stays between its own two readings (monotone, no overshoot).
   expect(y).toBeGreaterThanOrEqual(Math.min(...ends)-1e-9);expect(y).toBeLessThanOrEqual(Math.max(...ends)+1e-9);}
 }
 expect(curveRuns([[0,1],null,[2,3]]).map(r=>r.segments.length)).toEqual([0,0]);
});
const units:Record<string,string>={asleep_s:"h",deep_s:"h",rem_s:"h",awake_s:"h",hr_mean:"bpm",hrv_mean:"ms",resp_mean:"breaths/min",overall:"/100",consistency:"/100"};
const unitOf=(id:string)=>units[id];
test("same-unit metrics share an axis; a third unit and a seventh line are refused",()=>{
 expect(groupAxes(["asleep_s","hr_mean","deep_s","rem_s"],unitOf)).toEqual([{unit:"h",ids:["asleep_s","deep_s","rem_s"]},{unit:"bpm",ids:["hr_mean"]}]);
 expect(refusal(["asleep_s","hr_mean"],"deep_s",unitOf)).toBeNull();
 expect(refusal(["asleep_s","hr_mean"],"hrv_mean",unitOf)).toMatch(/two axes, already used by Hours and bpm/);
 const six=["asleep_s","deep_s","rem_s","awake_s","overall","consistency"];
 expect(groupAxes(six,unitOf)).toHaveLength(2);
 expect(refusal(six,"hr_mean",unitOf)).toMatch(/at most 6 lines/);
 expect(refusal(six.slice(0,5),"consistency",unitOf)).toBeNull();
 expect(fitMetrics(["asleep_s","core_s","hr_mean","hrv_mean","deep_s"],new Set(Object.keys(units)),unitOf)).toEqual(["asleep_s","hr_mean","deep_s"]);
});
test("durations are shown in hours and missing values say so",()=>{
 const deep={id:"deep_s",unit:"min",clock:false},hr={id:"hr_mean",unit:"bpm",clock:false};
 expect(toAxis(deep,90)).toBe(1.5);expect(display(deep,90)).toBe("1h 30m");
 expect(display({id:"asleep_s",unit:"h",clock:false},7.25)).toBe("7h 15m");
 expect(display(hr,0)).toBe("0.0 bpm");expect(display(hr,null)).toBe("no reading");
 expect(display({id:"onset_minute",unit:"local time",clock:true},1439.6)).toBe("00:00");
 expect(display(hr,0.5,true)).toBe("0.50 z");
});
