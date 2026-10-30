import {useRef,useState} from "react";
import {TREND_RANGES,axisTicks,clock,consistencyNote,contribution,duration,hourTicks,missingText,number,offsetLabel,physiologyDetail,shortDay,stageBar,tickDays,trendWindow,units} from "./dashboardModel";
import type {DashboardData,Latest,Stage,TrendRange} from "./dashboardModel";

const order:Stage[]=["Awake","REM","Core","Deep"];
const colors:Record<Stage,string>={Awake:"var(--stage-awake)",REM:"var(--stage-rem)",Core:"var(--stage-core)",Deep:"var(--stage-deep)"};
const names=["duration","consistency","efficiency","deep","rem","physiology"] as const;
const labels:Record<string,string>={duration:"Duration",consistency:"Consistency",efficiency:"Efficiency",deep:"Deep",rem:"REM",physiology:"HR / HRV"};

function Metric({label,value,unit,detail}:{label:string;value:string|null;unit?:string;detail:string}){
 return <article className="metric"><p>{label}</p><div className={value===null?"missing":"metric-value"}>{value??"Missing data"} {value!==null&&<small>{unit}</small>}</div><span>{detail}</span></article>;
}
function Timeline({night}:{night:Latest}){
 const session=Math.max(1,night.session_s);
 return <div className="timeline"><svg viewBox="0 0 960 172" role="img" aria-label={`Sleep stages from ${clock(night.onset_local)} to ${clock(night.wake_local)}, ${duration(night.session_s)} recorded window`}>
  {order.map((stage,i)=><g key={stage}><text x="0" y={25+i*36}>{stage}</text><line x1="72" x2="950" y1={20+i*36} y2={20+i*36} className="gridline"/></g>)}
  {night.stages.map((s,i)=>{const bar=stageBar(s.start_s,s.duration_s,session);return <rect key={i} tabIndex={0} x={bar.x} y={8+order.indexOf(s.stage)*36} width={bar.width} height="24" rx="4" fill={colors[s.stage]}><title>{s.stage}: {Math.round(s.duration_s/60)} minutes; {Math.round(s.start_s/60)} minutes after onset</title></rect>;})}
 </svg><div className="axis">{axisTicks(night.onset_local,night.session_s).map((t,i)=><span key={i}>{t}</span>)}</div></div>;
}
/** Nightly duration with a labelled hours axis (U14) over 7/30/90 days, a year or All (U15): bars up to a month, then an
 * area line that breaks at unrecorded nights. Exported so the design preview draws the same chart. */
export function TrendPanel({trend,note}:{trend:DashboardData["trend"];note:string}){
 const [range,setRange]=useState<TrendRange>(30),[hover,setHover]=useState<number|null>(null);const svg=useRef<SVGSVGElement>(null);
 const {dates,hours}=trendWindow(trend,range),n=dates.length;
 const ticks=hourTicks(Math.max(0,...hours.filter((h):h is number=>h!==null))),top=ticks[ticks.length-1];
 const pct=(h:number)=>`${Math.min(100,h/top*100)}%`,y=(h:number)=>100-Math.min(100,h/top*100);
 const label=(i:number)=>hours[i]===null?`${dates[i]}: no recording`:`${dates[i]}: ${hours[i]!.toFixed(1)} hours`;
 const bars=n<=31,ends=tickDays(dates,n?[...new Set([0,n-1])]:[]);
 // Consecutive recorded nights form one run; a gap ends the line, so missing nights are never bridged.
 const runs:number[][]=[];hours.forEach((h,i)=>{if(h===null)return;const last=runs[runs.length-1];if(last&&last[last.length-1]===i-1)last.push(i);else runs.push([i]);});
 const points=(run:number[])=>run.length===1?[[run[0]+.15,y(hours[run[0]]!)],[run[0]+.85,y(hours[run[0]]!)]]:run.map(i=>[i+.5,y(hours[i]!)]);
 return <section className="panel trend-panel"><div className="panel-title"><div><h2>Time asleep, over time</h2><p className="muted">{note}</p></div>
  <div className="segmented" role="group" aria-label="Chart range">{TREND_RANGES.map(([name,r])=><button key={name} aria-pressed={range===r} onClick={()=>{setRange(r);setHover(null);}}>{name}</button>)}</div></div>
  <div className="trend-chart">
   <div className="trend-yaxis" aria-hidden="true">{ticks.map(t=><span key={t} style={{bottom:pct(t)}}>{t}h</span>)}</div>
   <div className="trend-plot">{ticks.map(t=><i key={t} className="trend-grid" style={{bottom:pct(t)}}/>)}
    {bars?<div className="trend-bars" role="group" aria-label={`${n} days of sleep durations`}>{hours.map((h,i)=><div key={dates[i]}><span style={{height:h===null?0:pct(h)}} tabIndex={0} title={label(i)}/></div>)}</div>
    :<svg ref={svg} className="trend-line" viewBox={`0 0 ${n} 100`} preserveAspectRatio="none" role="img" aria-label={`${n} days of sleep durations, ${hours.filter(h=>h!==null).length} nights recorded; gaps are nights not recorded`}
      onPointerMove={e=>{const box=svg.current?.getBoundingClientRect();if(box?.width)setHover(Math.max(0,Math.min(n-1,Math.floor((e.clientX-box.left)/box.width*n))));}} onPointerLeave={()=>setHover(null)}>
     {runs.map(run=>{const p=points(run),line=p.map(([px,py],k)=>`${k?"L":"M"}${px} ${py}`).join(" ");
      return <g key={run[0]} data-run={run.length}><path className="trend-area" d={`${line} L${p[p.length-1][0]} 100 L${p[0][0]} 100 Z`}/><path className="trend-stroke" d={line} vectorEffect="non-scaling-stroke"/></g>;})}
     {hover!==null&&<line className="trend-cursor" x1={hover+.5} x2={hover+.5} y1="0" y2="100" vectorEffect="non-scaling-stroke"/>}
    </svg>}
   </div>
  </div>
  <div className="trend-axis">{[...ends.values()].map((d,i)=><span key={i}>{d}</span>)}</div>
  {!bars&&<p className="trend-readout" aria-live="polite">{hover===null?"Hover the chart for one night's duration":label(hover)}</p>}
  <p className="muted">Individual nights · no rolling average applied</p></section>;
}

// Python derives every value; this view only formats and positions them.
export function Dashboard({data}:{data:DashboardData}){
 const night=data.latest;
 if(!night)return <section className="panel placeholder"><span className="empty-moon">☾</span><h2>Your nights will find a home here.</h2><p>No sleep history available. After a successful import, your latest recorded night will appear here.</p></section>;
 const score=night.score,scored=score?.status==="scored"&&score.overall!==null;
 const total=score?Object.values(score.components).reduce((sum,c)=>sum+c.weight,0)||100:100;
 const stageTotals:[Stage,number][]=[["Awake",night.awake_s],["REM",night.rem_s],["Core",night.core_s],["Deep",night.deep_s]];
 const baseline=score?.consistency_detail;
 const minutes=Math.round(night.asleep_s/60);
 return <>
 <div className="hero-grid"><section className="panel score-panel"><div className="panel-title"><h2>SleepIQ score</h2><span className="pill">PILOT SCORE</span></div>
  <div className="score-content"><div className="score-ring" style={{"--progress":scored?`${score!.overall!*3.6}deg`:"0deg"} as React.CSSProperties}><div>{scored?<><strong>{number(score!.overall)}</strong><span>/ 100</span></>:<strong className="no-score">Insufficient<br/>data</strong>}</div></div>
   <div className="score-description"><h3>{scored?"Your night at a glance.":"This night has no overall score."}</h3><p>{scored?"Duration, timing and efficiency, brought together in one transparent score.":missingText(score?.missing??[])||"The score has not been computed for this night."}</p>{night.flags.length>0&&<span className="subtle-tag">Flags: {night.flags.map(f=>f.replace(/_/g," ")).join(", ")}</span>}</div></div>
  <div className="score-footer"><span>Version <b>{score?.version??data.versions[1]}</b></span>{score&&<span>Pilot ceiling <b>{number(score.ceiling)}</b> <span title="Deep, REM and physiology use neutral pilot values.">ⓘ</span></span>}</div></section>
 <section className="panel night-panel"><div className="panel-title"><h2>The shape of your night</h2><span aria-hidden="true">☾</span></div><div className="sleep-total"><span className="dur-part">{Math.floor(minutes/60)}<span className="dur-unit">h</span></span> <span className="dur-part">{String(minutes%60).padStart(2,"0")}<span className="dur-unit">m</span></span></div><p className="muted">Total time asleep</p>
  <div className="night-track"><span>☾</span><i/><span>☀</span></div><div className="sleep-times"><div><small>Sleep onset · {shortDay(night.onset_local)}</small><strong>{clock(night.onset_local)}</strong></div><div><small>Wake time · {shortDay(night.wake_local)}</small><strong>{clock(night.wake_local)}</strong></div></div><p className="night-note">Source-local time · {offsetLabel(night.end_offset_min)}</p></section>
 <section className="panel consistency"><div className="panel-title"><h2>Consistency</h2><span>◷</span></div>
  {score?.consistency!=null?<div className="consistency-number">{number(score.consistency)} <small>/ 100</small></div>:<div className="missing">Missing data</div>}
  <p>{baseline?.available?<>Onset <strong>{number(baseline.onset_deviation_min??null,0)} min</strong> and wake <strong>{number(baseline.wake_deviation_min??null,0)} min</strong> from your usual</>:consistencyNote(baseline??{})}</p>
  <span className="muted">{baseline?.available?`${consistencyNote(baseline)} · ${baseline.baseline_nights} qualifying nights`:"Consistency needs earlier nights."}</span></section></div>
 <section className="panel stages-panel"><div className="panel-title"><div><h2>A journey through sleep</h2><p className="muted">Sleep stages · {duration(night.session_s)} recorded window</p></div><div className="legend">{order.map(s=><span key={s}><i style={{background:colors[s]}}/>{s}</span>)}</div></div><Timeline night={night}/>
  <div className="stage-summary">{stageTotals.map(([s,v])=><div key={s}><i style={{background:colors[s]}}/><span>{s}</span><strong>{duration(v)}</strong></div>)}</div></section>
 <div className="section-heading"><h2>The details that matter</h2><span>Overnight measurements · {night.wake_date}</span></div>
 <section className="metrics-grid" aria-label="Nightly metrics"><Metric label="Sleep efficiency" value={number(night.efficiency*100)} unit="%" detail="Stage-based · asleep / recorded stages"/>
  {night.physiology.map(p=><Metric key={p.id} label={p.label} value={number(p.value)} unit={units[p.id]} detail={p.value===null?(p.id==="temp"?"No reading attributed to this night":"No overnight samples"):`${physiologyDetail[p.id]} · ${p.n} sample${p.n===1?"":"s"}`}/>)}</section>
 <div className="bottom-grid"><TrendPanel trend={data.trend} note="Nightly duration · hours · gaps are nights not recorded"/>
 <section className="panel breakdown"><div className="panel-title"><h2>Behind the score</h2><span className="pill">TRANSPARENT BY DESIGN</span></div>
  {names.map(name=>{const c=score?.components[name];return <div className="breakdown-row" key={name}><span>{labels[name]}{c?.neutral?" · pilot-neutral":""}</span><small>{c?`${c.weight}%`:"—"}</small><b>{c?contribution(c,total):"—"}</b></div>;})}
  <p className="muted">Contributions to the 100-point score. Neutral components score 75/100. Not clinically calibrated. {scored?"":missingText(score?.missing??[])}</p></section></div>
 </>;
}
