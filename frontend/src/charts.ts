export type Metric = {id:string;label:string;unit:string;method:string;clock:boolean};
export type Range = "7"|"30"|"90"|"all"|"custom";
export type Selection = {metrics:string[];range:Range;start:string|null;end:string|null;mode:"actual"|"normalized";rolling:"off"|"7"|"30"};
export type Preset = Selection & {id:string;name:string;default:boolean;revision:number};
// Python computes rolling means over trailing calendar windows; null values mean below the observed-night minimum.
export type Rolling = {window:number;minimum:number;values:(number|null)[]|null;counts:number[]|null;reason:string|null};
export type Series = Metric & {values:(number|null)[];raw:(number|null)[];details:{n:number|null;flags:string[];offset_minutes:number|null}[];normalization:{n:number;mean:number|null;sd:number|null;reason:string|null;method:string};rolling:Rolling|null};
export type ChartData = {synthetic?:boolean;dates:string[];start:string|null;end:string|null;series:Series[];versions:string[]};
export type Pair = {date:string;x:number;y:number};
export type Correlation = {synthetic?:boolean;x:Metric;y:Metric;start:string|null;end:string|null;days:number;pairs:Pair[];n:number;excluded:{missing_x:number;missing_y:number;neither:number};r:number|null;reason:string|null;method:string;versions:string[]};
export async function chartRequest<T>(path:string, method="GET", body?:unknown, signal?:AbortSignal):Promise<T>{
 const response=await fetch(`/api/v1/${path}`,{method,signal,headers:method==="GET"?{}:{"Content-Type":"application/json","X-SleepIQ-Request":"charts"},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok){throw new Error(response.status===409?"Preset changed or name already exists. Reload presets before retrying.":response.status===503?"Chart store is not configured. Open the local chart preview or configured application.":`Request failed (${response.status}). Check your selection and local service.`);}
 return await response.json() as T;
}
export const initialSelection:Selection={metrics:["asleep_s","hrv_mean"],range:"30",start:null,end:null,mode:"actual",rolling:"off"};
// Presets saved before rolling averages existed load with rolling off.
export function withDefaults(saved:Partial<Selection>):Selection{return {...initialSelection,...saved,rolling:saved.rolling??"off"};}
export function sliceSeries(s:Series,from:number,to:number):Series{
 const cut=<T,>(items:T[])=>items.slice(from,to+1);
 return {...s,values:cut(s.values),raw:cut(s.raw),details:cut(s.details),rolling:s.rolling&&{...s.rolling,values:s.rolling.values&&cut(s.rolling.values),counts:s.rolling.counts&&cut(s.rolling.counts)}};
}
export function rollingNote(rolling:Rolling,i:number,format:(v:number)=>string):string{
 if(!rolling.values||!rolling.counts)return `${rolling.window}-day mean: ${rolling.reason??"unavailable"}`;
 const count=`${rolling.counts[i]}/${rolling.window} nights recorded`,value=rolling.values[i];
 if(value===null)return `${rolling.window}-day mean unavailable (${count}; needs ${rolling.minimum})${rolling.reason?`; ${rolling.reason}`:""}`;
 return `${rolling.window}-day mean ${format(value)} (${count})`;
}
export function formatValue(value:number|null,metric:Metric):string {
 if(value===null)return "Missing data";
 if(metric.clock){const minutes=Math.round(value)%1440;return `${String(Math.floor(minutes/60)).padStart(2,"0")}:${String(minutes%60).padStart(2,"0")}`;}
 return `${value.toFixed(2)} ${metric.unit}`;
}
// Indexes correspond to every calendar day supplied by Python, including missing days.
export function chartSegments(values:(number|null)[],low:number,high:number):string[]{
 const paths:string[]=[];let current="";
 values.forEach((v,i)=>{if(v===null){if(current)paths.push(current);current="";return;}
 const x=48+i/Math.max(1,values.length-1)*840;const y=170-(v-low)/(high-low||1)*140;
 current+=`${current?" L":"M"}${x.toFixed(2)},${y.toFixed(2)}`;});
 if(current)paths.push(current);return paths;
}
// Scatter axes pad constant extents so points never divide by zero; values are only positioned, never altered.
export function scatterLayout(pairs:Pair[]){
 const bounds=(v:number[])=>{const lo=Math.min(...v),hi=Math.max(...v);return lo===hi?[lo-1,hi+1]:[lo,hi];};
 const [xl,xh]=pairs.length?bounds(pairs.map(p=>p.x)):[0,1],[yl,yh]=pairs.length?bounds(pairs.map(p=>p.y)):[0,1];
 return {x:[xl,xh],y:[yl,yh],points:pairs.map(p=>({...p,cx:60+(p.x-xl)/(xh-xl)*560,cy:290-(p.y-yl)/(yh-yl)*260}))};
}
export type ExportBody={metrics:string[];range:Range;start:string|null;end:string|null};
export async function exportRequest(body:ExportBody):Promise<{blob:Blob;name:string;rows:number}>{
 const response=await fetch("/api/v1/analytics/export",{method:"POST",headers:{"Content-Type":"application/json","X-SleepIQ-Request":"charts"},body:JSON.stringify(body)});
 if(!response.ok)throw new Error(response.status===503?"Chart store is not configured. Open the configured application to export.":`Export failed (${response.status}). Check your selection and try again.`);
 return {blob:await response.blob(),name:response.headers.get("Content-Disposition")??"",rows:Number(response.headers.get("X-SleepIQ-Rows")??0)};
}
// The server names the file; accept only a plain safe name so a header can never choose a path.
export function fileNameFrom(disposition:string):string{const m=/filename="(sleepiq-nightly-[0-9A-Za-z_.-]+\.csv)"/.exec(disposition);return m?m[1]:"sleepiq-nightly.csv";}
