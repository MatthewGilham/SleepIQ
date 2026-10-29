import {useState} from "react";
import {axisTicks,clock,consistencyNote,contribution,duration,missingText,number,offsetLabel,physiologyDetail,shortDay,stageBar,units} from "./dashboardModel";
import type {DashboardData,Latest,Stage} from "./dashboardModel";

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
// Python derives every value; this view only formats and positions them.
export function Dashboard({data}:{data:DashboardData}){
 const [range,setRange]=useState(30);
 const night=data.latest;
 if(!night)return <section className="panel placeholder"><span className="empty-moon">☾</span><h2>Your nights will find a home here.</h2><p>No sleep history available. After a successful import, your latest recorded night will appear here.</p></section>;
 const score=night.score,scored=score?.status==="scored"&&score.overall!==null;
 const total=score?Object.values(score.components).reduce((sum,c)=>sum+c.weight,0)||100:100;
 const trend=data.trend.asleep_h.slice(-range),dates=data.trend.dates.slice(-range);
 const stageTotals:[Stage,number][]=[["Awake",night.awake_s],["REM",night.rem_s],["Core",night.core_s],["Deep",night.deep_s]];
 const baseline=score?.consistency_detail;
 const minutes=Math.round(night.asleep_s/60);
 return <>
 <div className="hero-grid"><section className="panel score-panel"><div className="panel-title"><h2>SleepIQ score</h2><span className="pill">PILOT SCORE</span></div>
  <div className="score-content"><div className="score-ring" style={{"--progress":scored?`${score!.overall!*3.6}deg`:"0deg"} as React.CSSProperties}><div>{scored?<><strong>{number(score!.overall)}</strong><span>/ 100</span></>:<strong className="no-score">Insufficient<br/>data</strong>}</div></div>
   <div className="score-description"><h3>{scored?"Your night at a glance.":"This night has no overall score."}</h3><p>{scored?"Duration, timing and efficiency, brought together in one transparent score.":missingText(score?.missing??[])||"The score has not been computed for this night."}</p>{night.flags.length>0&&<span className="subtle-tag">Flags: {night.flags.map(f=>f.replace(/_/g," ")).join(", ")}</span>}</div></div>
  <div className="score-footer"><span>Version <b>{score?.version??data.versions[1]}</b></span>{score&&<span>Pilot ceiling <b>{number(score.ceiling)}</b> <span title="Deep, REM and physiology use neutral pilot values.">ⓘ</span></span>}</div></section>
 <section className="panel night-panel"><div className="panel-title"><h2>The shape of your night</h2><span aria-hidden="true">☾</span></div><div className="sleep-total">{Math.floor(minutes/60)}<span>h</span> {String(minutes%60).padStart(2,"0")}<span>m</span></div><p className="muted">Total time asleep</p>
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
 <div className="bottom-grid"><section className="panel"><div className="panel-title"><div><h2>Time asleep, over time</h2><p className="muted">Nightly duration · hours · gaps are nights not recorded</p></div><div className="segmented" aria-label="Chart range">{[7,30].map(n=><button key={n} aria-pressed={range===n} onClick={()=>setRange(n)}>{n}D</button>)}</div></div>
  <div className="trend-bars" role="group" aria-label={`${range} days of sleep durations`}>{trend.map((h,i)=><div key={dates[i]}>{h===null?<span style={{height:0}} tabIndex={0} title={`${dates[i]}: no recording`}/>:<span style={{height:`${Math.min(100,h/10*100)}%`}} tabIndex={0} title={`${dates[i]}: ${h.toFixed(1)} hours`}/>}</div>)}</div>
  <div className="trend-axis"><span>{shortDay(`${dates[0]}T00:00`)}</span><span>{shortDay(`${dates[dates.length-1]}T00:00`)}</span></div><p className="muted">Individual nights · no rolling average applied</p></section>
 <section className="panel breakdown"><div className="panel-title"><h2>Behind the score</h2><span className="pill">TRANSPARENT BY DESIGN</span></div>
  {names.map(name=>{const c=score?.components[name];return <div className="breakdown-row" key={name}><span>{labels[name]}{c?.neutral?" · pilot-neutral":""}</span><small>{c?`${c.weight}%`:"—"}</small><b>{c?contribution(c,total):"—"}</b></div>;})}
  <p className="muted">Contributions to the 100-point score. Neutral components score 75/100. Not clinically calibrated. {scored?"":missingText(score?.missing??[])}</p></section></div>
 </>;
}
