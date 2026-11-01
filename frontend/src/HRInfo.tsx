import {useId,useState} from "react";

export type HRQuality={method:string|null;n:number;eligible_n?:number|null;contributing_n?:number|null;covered_s:number|null;window_s:number|null;coverage:number|null;fallback_reason:string|null};
const reasons:Record<string,string>={insufficient_points:"Too few readings to connect.",long_gaps:"Readings are too far apart to connect.",low_coverage:"Too little of the night can be connected.",ambiguous_source:"The recording source is unclear.",ambiguous_timestamp:"Readings disagree at the same time.",unsupported_interval:"The measurement periods cannot be weighted reliably."};
const time=(seconds:number)=>{const m=Math.round(seconds/60);return `${Math.floor(m/60)}h ${String(m%60).padStart(2,"0")}m`;};
export function hrQualityText(q:HRQuality):string{
 if(q.n===0)return "No overnight heart-rate readings.";
 const method=q.method==="time_weighted_linear"?"Time-weighted estimate":"Simple average";
 const coverage=q.coverage===null||q.covered_s===null||q.window_s===null?"Duration coverage unknown.":`Estimated coverage: ${time(q.covered_s)} of ${time(q.window_s)} (${Math.round(q.coverage*100)}%).`;
 return `${method} · ${q.n} ${q.n===1?"sample":"samples"}. ${q.fallback_reason?`${reasons[q.fallback_reason]??"Weighting unavailable."} `:""}${coverage}`;
}
export function HRInfo({quality}:{quality:HRQuality}){
 const [open,setOpen]=useState(false),id=useId();
 return <span className="hr-info"><button type="button" aria-label="How sleeping heart rate is calculated" aria-expanded={open} aria-describedby={open?id:undefined} onClick={()=>setOpen(!open)} onBlur={()=>setOpen(false)} onKeyDown={e=>{if(e.key==="Escape")setOpen(false);}}>ⓘ</button>{open&&<span id={id} role="note" className="hr-pop">{hrQualityText(quality)}</span>}</span>;
}
