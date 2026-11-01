export type Stage = "Awake"|"REM"|"Core"|"Deep";
import type {HRQuality} from "./HRInfo";
export type Physiology = {id:string;label:string;value:number|null;n:number;quality?:HRQuality};
export type Component = {score:number|null;weight:number;neutral:boolean};
export type DashboardScore = {status:"scored"|"insufficient_data";overall:number|null;consistency:number|null;version:string;ceiling:number;missing:string[];components:Record<string,Component>;consistency_detail:{available?:boolean;reason?:string|null;baseline_nights?:number;provisional?:boolean;onset_deviation_min?:number|null;wake_deviation_min?:number|null}};
export type Latest = {wake_date:string;source:string;onset_local:string;wake_local:string;start_offset_min:number;end_offset_min:number;session_s:number;asleep_s:number;core_s:number;deep_s:number;rem_s:number;awake_s:number;efficiency:number;physiology:Physiology[];flags:string[];stages:{stage:Stage;start_s:number;duration_s:number}[];score:DashboardScore|null};
export type DashboardData = {synthetic:boolean;versions:string[];import:{batches:number;last_received_utc:number|null;nights:number};latest:Latest|null;trend:{dates:string[];asleep_h:(number|null)[]};previous_night?:string|null;next_night?:string|null};
export const units:Record<string,string>={hr:"bpm",hrv:"ms",resp:"breaths/min",temp:"°C"};
export const physiologyDetail:Record<string,string>={hr:"Unweighted mean · overnight samples",hrv:"Mean SDNN · overnight samples",resp:"Overnight mean",temp:"Overnight mean"};
const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],days=["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
export function duration(seconds:number):string{const m=Math.round(seconds/60);return `${Math.floor(m/60)}h ${String(m%60).padStart(2,"0")}m`;}
// Local strings are source-local "YYYY-MM-DDTHH:MM"; they are sliced, never re-zoned by the browser.
export const clock=(local:string)=>local.slice(11,16);
export const shortDay=(local:string)=>`${Number(local.slice(8,10))} ${months[Number(local.slice(5,7))-1]}`;
/** "29 Oct 2026": date labels where the year matters (chart ranges and tooltips, U13). */
export const fullDay=(local:string)=>`${shortDay(local)} ${local.slice(0,4)}`;
/** Axis tick labels for the dates at `shown` indices: the first tick and any tick in a new year carry the year (U13). */
export function tickDays(dates:string[],shown:number[]):Map<number,string>{
 const labels=new Map<number,string>();let year="";
 for(const i of shown){const y=dates[i].slice(0,4);labels.set(i,y===year?shortDay(dates[i]):fullDay(dates[i]));year=y;}
 return labels;
}
export function longDay(date:string):string{const d=new Date(`${date}T00:00:00Z`);return `${days[d.getUTCDay()]}, ${d.getUTCDate()} ${["January","February","March","April","May","June","July","August","September","October","November","December"][d.getUTCMonth()]}`;}
export type TrendRange=7|30|90|365|"all";
export const TREND_RANGES:[string,TrendRange][]=[["7D",7],["30D",30],["90D",90],["1Y",365],["All","all"]];
const daysBefore=(iso:string,n:number)=>new Date(Date.parse(`${iso}T00:00:00Z`)-n*86_400_000).toISOString().slice(0,10);
/** The last `range` calendar days of the duration trend, padded with unrecorded days before the stored history,
 * or All: from the first stored night (U15). Python supplies one entry per calendar day ending on the viewed night. */
export function trendWindow(trend:DashboardData["trend"],range:TrendRange):{dates:string[];hours:(number|null)[]}{
 const {dates,asleep_h}=trend;
 if(range==="all"){const i=asleep_h.findIndex(h=>h!==null);return i<0?{dates:[],hours:[]}:{dates:dates.slice(i),hours:asleep_h.slice(i)};}
 const missing=dates.length?Math.max(0,range-dates.length):0,pad=Array.from({length:missing},(_,k)=>daysBefore(dates[0],missing-k));
 return {dates:[...pad,...dates.slice(-range)],hours:[...pad.map(()=>null),...asleep_h.slice(-range)]};
}
/** Hours axis for the duration trend: 0 up to at least 10 h, rounded up to an even hour, a tick every 2 h (U14). */
export function hourTicks(maxHours:number):number[]{
 const top=Math.max(10,Math.ceil(maxHours/2)*2);
 return Array.from({length:top/2+1},(_,i)=>i*2);
}
export function offsetLabel(minutes:number):string{const a=Math.abs(minutes);return `UTC${minutes<0?"-":"+"}${String(Math.floor(a/60)).padStart(2,"0")}:${String(a%60).padStart(2,"0")}`;}
export function axisTicks(onset:string,sessionSeconds:number):string[]{
 const base=Date.parse(`${onset}:00Z`);
 return [0,1,2,3,4].map(i=>clock(new Date(base+sessionSeconds*1000*i/4).toISOString()));
}
// Position of a stage bar inside the 960-wide timeline: x from 72 to 950.
export function stageBar(start:number,length:number,session:number){return {x:72+start/session*878,width:Math.max(1,length/session*878)};}
export function number(value:number|null,digits=1):string|null{return value===null?null:String(Number(value.toFixed(digits)));}
export function contribution(component:Component|undefined,total:number):string{return component?.score!=null?(component.score*component.weight/total).toFixed(1):"—";}
export function consistencyNote(detail:DashboardScore["consistency_detail"]):string{
 if(detail.available)return detail.provisional?"Provisional: fewer than 14 qualifying nights":"Previous 30 calendar days";
 return detail.reason==="insufficient_history"?`Not enough history yet (${detail.baseline_nights??0} prior nights; needs at least 7)`:"Unavailable";
}
export function missingText(missing:string[]):string{
 const parts=missing.map(m=>m==="sleeping_hr"?"sleeping heart rate":m==="overnight_hrv"?"overnight HRV":m.startsWith("consistency:")?"enough history for consistency":m);
 return parts.length?`No overall score because of missing: ${parts.join(", ")}.`:"";
}
export function importText(info:DashboardData["import"]):string{
 if(!info.batches||info.last_received_utc===null)return "No imports yet";
 return `${info.nights} nights · last import ${new Date(info.last_received_utc*1000).toISOString().slice(0,10)}`;
}
export const NIGHT_PATTERN=/^\d{4}-\d{2}-\d{2}$/;
/** The `?night=` value in an address bar search string, only when it is shaped like a date. */
export function nightFromSearch(search:string):string|null{const n=new URLSearchParams(search).get("night");return n&&NIGHT_PATTERN.test(n)?n:null;}
/** Address-bar search string for a night; the latest night carries no parameter. */
export function searchForNight(night:string|null):string{return night?`?night=${night}`:"";}
export function arrowDirection(e:{key:string;target:unknown;altKey?:boolean;ctrlKey?:boolean;metaKey?:boolean;shiftKey?:boolean}):-1|1|0{
 if(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey||(e.key!=="ArrowLeft"&&e.key!=="ArrowRight"))return 0;
 const t=e.target as {tagName?:string;isContentEditable?:boolean}|null;
 if(t&&(t.isContentEditable||["INPUT","TEXTAREA","SELECT"].includes(t.tagName??"")))return 0;
 return e.key==="ArrowLeft"?-1:1;
}
export async function loadDashboard(signal:AbortSignal,night:string|null=null):Promise<DashboardData|"unconfigured">{
 const response=await fetch(night?`/api/v1/dashboard?night=${encodeURIComponent(night)}`:"/api/v1/dashboard",{signal});
 if(response.status===404&&night)throw new Error("No sleep was recorded for that night.");
 if(response.status===503||response.status===404)return "unconfigured";
 if(!response.ok)throw new Error(`Dashboard request failed (${response.status}).`);
 return await response.json() as DashboardData;
}
