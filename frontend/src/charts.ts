export type Metric = {id:string;label:string;unit:string;method:string;clock:boolean};
export type Range = "7"|"30"|"90"|"365"|"all"|"custom";
export type Selection = {metrics:string[];range:Range;start:string|null;end:string|null;mode:"actual"|"normalized";rolling:"off"|"7"|"30"};
export type Preset = Selection & {id:string;name:string;default:boolean;revision:number};
// Python computes rolling means over trailing calendar windows; null values mean below the observed-night minimum.
export type Rolling = {window:number;minimum:number;values:(number|null)[]|null;counts:number[]|null;reason:string|null};
export type Series = Metric & {values:(number|null)[];raw:(number|null)[];details:{n:number|null;flags:string[];offset_minutes:number|null}[];normalization:{n:number;mean:number|null;sd:number|null;reason:string|null;method:string};rolling:Rolling|null};
export type ChartData = {synthetic?:boolean;dates:string[];start:string|null;end:string|null;series:Series[];versions:string[]};
export type Pair = {date:string;x:number;y:number};
export type Correlation = {synthetic?:boolean;x:Metric;y:Metric;start:string|null;end:string|null;days:number;pairs:Pair[];n:number;excluded:{missing_x:number;missing_y:number;neither:number};r:number|null;fit:{slope:number;intercept:number}|null;reason:string|null;method:string;versions:string[]};
export type GridCell={x:string;y:string;r:number|null;n:number;reason:string|null};
export type CorrelationGrid={synthetic?:boolean;metrics:Pick<Metric,"id"|"label"|"unit">[];cells:GridCell[];start:string|null;end:string|null;days:number;method:string;versions:string[]};
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

// ---------- Analytics redesign (U05): pure helpers so geometry and limits are unit-testable ----------
export type Pt=[number,number];
export type Bezier=[Pt,Pt,Pt,Pt];
export type Run={points:Pt[];segments:Bezier[]};
/** Split at nulls (gaps are never bridged), then join each run with monotone cubic segments.
 * Tangents are 0 at local extremes and the harmonic mean of neighbouring slopes elsewhere (Fritsch-Carlson),
 * so every segment stays between its two end points: the curve never overshoots a reading. */
export function curveRuns(points:(Pt|null)[]):Run[]{
 const runs:Pt[][]=[];let cur:Pt[]=[];
 points.forEach(p=>{if(p===null){if(cur.length)runs.push(cur);cur=[];}else cur.push(p);});if(cur.length)runs.push(cur);
 return runs.map(s=>{
  const n=s.length;if(n<2)return {points:s,segments:[]};
  const dx:number[]=[],m:number[]=[],t:number[]=[];
  for(let i=0;i<n-1;i++){dx[i]=s[i+1][0]-s[i][0];m[i]=(s[i+1][1]-s[i][1])/dx[i];}
  t[0]=m[0];t[n-1]=m[n-2];for(let i=1;i<n-1;i++){const a=m[i-1],b=m[i];t[i]=a*b<=0?0:2*a*b/(a+b);}
  const segments:Bezier[]=[];for(let i=0;i<n-1;i++){const h=dx[i]/3;segments.push([s[i],[s[i][0]+h,s[i][1]+t[i]*h],[s[i+1][0]-h,s[i+1][1]-t[i+1]*h],s[i+1]]);}
  return {points:s,segments};
 });
}
export function runPath(run:Run):string{
 const f=(p:Pt)=>`${p[0].toFixed(2)},${p[1].toFixed(2)}`;
 return `M${f(run.points[0])}`+run.segments.map(([,a,b,c])=>`C${f(a)} ${f(b)} ${f(c)}`).join("");
}
export function bezierAt([p0,p1,p2,p3]:Bezier,t:number):Pt{
 const u=1-t,k=[u*u*u,3*u*u*t,3*u*t*t,t*t*t];
 return [k[0]*p0[0]+k[1]*p1[0]+k[2]*p2[0]+k[3]*p3[0],k[0]*p0[1]+k[1]*p1[1]+k[2]*p2[1]+k[3]*p3[1]];
}
/** Sleep durations share one hours axis, whatever unit the catalog stores them in (P27). */
export const DURATIONS=new Set(["asleep_s","deep_s","rem_s","awake_s","core_s"]);
export const MAX_LINES=6,MAX_AXES=2;
export function axisUnit(m:Pick<Metric,"id"|"unit">,normalized=false):string{return normalized?"z":DURATIONS.has(m.id)?"h":m.unit;}
/** Catalog value -> axis value. Only a unit change (minutes to hours); never a different measurement. */
export function toAxis(m:Pick<Metric,"id"|"unit">,v:number|null):number|null{return v===null?null:DURATIONS.has(m.id)&&m.unit==="min"?v/60:v;}
export type Axis={unit:string;ids:string[]};
/** Same-unit metrics share an axis; first unit on the left, second on the right. */
export function groupAxes(ids:string[],unitOf:(id:string)=>string):Axis[]{
 const axes:Axis[]=[];ids.forEach(id=>{const u=unitOf(id),a=axes.find(x=>x.unit===u);if(a)a.ids.push(id);else axes.push({unit:u,ids:[id]});});return axes;
}
/** Why `id` cannot join the chart, or null when it can. */
export function refusal(ids:string[],id:string,unitOf:(id:string)=>string):string|null{
 if(ids.includes(id))return null;
 if(ids.length>=MAX_LINES)return `The chart shows at most ${MAX_LINES} lines. Remove one first.`;
 const units=groupAxes(ids,unitOf).map(a=>a.unit);
 if(!units.includes(unitOf(id))&&units.length>=MAX_AXES)return `The chart has two axes, already used by ${units.map(unitName).join(" and ")}. Remove one of those, or switch Display to Normalized to compare more units.`;
 return null;
}
/** Keep a saved or edited selection within the chart's limits, in order, dropping what does not fit. */
export function fitMetrics(ids:string[],allowed:Set<string>,unitOf:(id:string)=>string):string[]{
 const out:string[]=[];ids.filter(id=>allowed.has(id)).forEach(id=>{if(!refusal(out,id,unitOf))out.push(id);});return out;
}
export function unitName(unit:string):string{return unit==="h"?"Hours":unit==="z"?"Standard deviations (z)":unit;}
export function hoursText(h:number):string{const total=Math.round(h*60),sign=total<0?"−":"";const a=Math.abs(total);return `${sign}${Math.floor(a/60)}h ${String(a%60).padStart(2,"0")}m`;}
export function clockText(minutes:number):string{const m=((Math.round(minutes)%1440)+1440)%1440;return `${String(Math.floor(m/60)).padStart(2,"0")}:${String(m%60).padStart(2,"0")}`;}
const DIGITS:Record<string,number>={"/100":1,"%":1,ms:0,bpm:1,"breaths/min":1,"°C":2};
/** One formatter for chart labels, tooltips and the table, so the table always matches the chart. */
export function display(m:Pick<Metric,"id"|"unit"|"clock">,v:number|null,normalized=false):string{
 if(v===null)return "no reading";
 if(normalized)return `${v.toFixed(2)} z`;
 if(m.clock)return clockText(v);
 const a=toAxis(m,v)!;if(DURATIONS.has(m.id))return hoursText(a);
 return `${a.toFixed(DIGITS[m.unit]??2)} ${m.unit}`;
}
/** Mean of the nights that have a reading in the (sliced) series, in the metric's own units; null when none (P32).
 * Computed from the nights on screen, so it follows the zoom. Missing nights are left out, never counted as zero. */
export function visibleMean(s:Pick<Series,"raw">):number|null{
 const seen=s.raw.filter((v):v is number=>v!==null);
 return seen.length?seen.reduce((sum,v)=>sum+v,0)/seen.length:null;
}
/** Average label for the main chart and tooltip (U08, P32): the mean of the nights currently shown. Normalized mode keeps
 * one reference line at 0; clock times have no average. */
export function averageText(s:Pick<Series,"id"|"unit"|"clock"|"raw">,normalized=false):string|null{
 if(s.clock)return null;
 const mean=visibleMean(s);
 if(mean===null)return "no reading";
 return normalized?"average (0)":`avg ${display(s,mean)}`;
}
export type MetricSummary={mean:number|null;n:number;min:number|null;max:number|null;previous_mean:number|null;previous_n:number;delta:number|null};
export type ClockSummary={n:number;q1:number|null;median:number|null;q3:number|null};
export type Summary={synthetic?:boolean;start:string|null;end:string|null;days:number;nights:number;ceiling:number;previous:{start:string;end:string;days:number;nights:number}|null;
 metrics:Record<string,MetricSummary>;stages:Record<"deep"|"rem"|"core"|"awake",{minutes:number|null;percent:number|null}>|null;clock:{onset:ClockSummary;wake:ClockSummary}|null;versions:string[]};

// ---------- Correlations redesign (U17): pure helpers; Python computes r, n, exclusions and the best-fit line ----------
/** Chip groups for the pair composer; metrics the catalog adds later fall into OTHER. */
export const CORRELATION_GROUPS:[string,string[]][]=[["SLEEP",["asleep_s","deep_s","rem_s","core_s","awake_s","efficiency"]],["SCORES",["overall","consistency"]],["BODY",["hr_mean","hrv_mean","resp_mean","temp_mean"]]];
export function groupMetrics(metrics:Metric[]):[string,Metric[]][]{
 const known=new Set(CORRELATION_GROUPS.flatMap(([,ids])=>ids));
 const groups=CORRELATION_GROUPS.map(([name,ids]):[string,Metric[]]=>[name,ids.map(id=>metrics.find(m=>m.id===id)).filter((m):m is Metric=>!!m)]);
 const other=metrics.filter(m=>!known.has(m.id));
 return [...groups,...(other.length?[["OTHER",other] as [string,Metric[]]]:[])].filter(([,ms])=>ms.length>0);
}
export const SHORT_LABEL:Record<string,string>={asleep_s:"Asleep",awake_s:"Awake",core_s:"Core",deep_s:"Deep",rem_s:"REM",efficiency:"Efficiency",overall:"Score",consistency:"Consistency",hr_mean:"Heart rate",hrv_mean:"HRV",resp_mean:"Resp. rate",temp_mean:"Wrist temp"};
/** r with an explicit sign and a true minus, e.g. "−0.75", "+0.12", "0.00". */
export function rText(r:number):string{return Math.abs(r)<.005?"0.00":`${r>0?"+":"−"}${Math.abs(r).toFixed(2)}`;}
/** A paired value in the catalog's own unit (minutes stay minutes, hours read as "7h 09m"). */
export function pairText(m:Pick<Metric,"id"|"unit"|"clock">,v:number|null):string{return v!==null&&m.unit==="min"?`${Math.round(v)} min`:display(m,v);}
export type NiceAxis={lo:number;hi:number;ticks:number[];decimals:number};
/** Round axis steps (1, 2, 2.5 or 5 x 10^k) covering the values, so labels read 40, 50, 60 rather than 41.6, 48.2. */
export function niceAxis(values:number[],count=5):NiceAxis{
 let lo=values.length?Math.min(...values):0,hi=values.length?Math.max(...values):1;if(lo===hi){lo-=1;hi+=1;}
 const raw=(hi-lo)/(count-1),p=10**Math.floor(Math.log10(raw)),f=raw/p,mult=f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10,step=mult*p;
 const a=Math.floor(lo/step+1e-9)*step,b=Math.ceil(hi/step-1e-9)*step,ticks:number[]=[];
 for(let v=a;v<=b+step/2;v+=step)ticks.push(Number(v.toFixed(10)));
 return {lo:a,hi:b,ticks,decimals:Math.max(0,-Math.floor(Math.log10(step)+1e-9)+(mult===2.5?1:0))};
}
/** Point colour by age within the selected range: slate (oldest) to coral (newest). */
export function ageColour(date:string,start:string,end:string):string{
 const a=Date.parse(start),span=Math.max(1,Date.parse(end)-a),t=Math.min(1,Math.max(0,(Date.parse(date)-a)/span));
 const from=[0x56,0x63,0x7f],to=[0xff,0x7a,0x62];return `rgb(${from.map((v,i)=>Math.round(v+(to[i]-v)*t)).join(",")})`;
}
/** Steady hover: the nearest point within `reach` px, but the current one is kept until another is clearly closer,
 * so neighbouring points never flicker. Returns a date or null. */
export function nearestPoint(points:{date:string;cx:number;cy:number}[],x:number,y:number,current:string|null,reach=30,keep=34):string|null{
 const d=(p:{cx:number;cy:number})=>(p.cx-x)**2+(p.cy-y)**2;let best:string|null=null,bd=Infinity;
 for(const p of points){const v=d(p);if(v<bd){bd=v;best=p.date;}}
 const cur=points.find(p=>p.date===current);if(cur&&d(cur)<keep*keep&&d(cur)<=bd+40)return current;
 return bd<reach*reach?best:null;
}
/** Scatter plot height in pixels: proportional to its width, capped so the card fits one screen height (P29 U16),
 * and never so short on a phone that points crowd together. */
export function scatterHeight(width:number,viewportHeight:number):number{
 return Math.round(Math.max(Math.min(width*.62,viewportHeight-260),Math.min(260,width*.85)));
}

/** Metrics where a higher period average is better. Deep and REM are descriptive (S17/S18), so they get no tone. */
const HIGHER_IS_BETTER=new Set(["asleep_s","overall","hrv_mean"]);
export type Tone="good"|"bad"|"neutral";
/** Colour meaning of a change against the previous period: good, bad or neutral; null when there is nothing to judge. */
export function deltaTone(id:string,delta:number|null):Tone|null{
 if(delta===null||!HIGHER_IS_BETTER.has(id))return null;
 return delta===0?"neutral":delta>0?"good":"bad";
}
