import {useEffect,useRef,useState} from "react";
import type {ReactNode} from "react";

import {averageText,axisUnit,chartRequest,clockText,curveRuns,display,fitMetrics,hoursText,initialSelection,refusal,rollingNote,runPath,sliceSeries,toAxis,unitName,withDefaults} from "./charts";
import {shortDay} from "./dashboardModel";
import type {ChartData,Metric,Preset,Selection,Series,Summary} from "./charts";

// Afterburn reds plus gold and ice-blue (P27). Fixed per metric so a metric keeps its colour everywhere.
const COLOR:Record<string,string>={asleep_s:"#ff695b",deep_s:"#d9606a",rem_s:"#ff9a8a",awake_s:"#ffd0b5",core_s:"#bb514e",efficiency:"#f08a6c",overall:"#ffc45a",consistency:"#e8a33d",hr_mean:"#ffb199",hrv_mean:"#7fd3ff",resp_mean:"#e0b1a9",temp_mean:"#a9c8ff",onset_minute:"#9fb8d9",wake_minute:"#ffe08a"};
const color=(id:string)=>COLOR[id]??"#ff8c80";
const STAGE_COLOR={deep:"#70363c",core:"#bb514e",rem:"#ff8575",awake:"#ffc5a5"};
// Core is neither a chip nor a tile (owner, P27); it stays in the stage views and the CSV export.
const NOT_CHARTED=new Set(["core_s"]);
const TILES:[string,string][]=[["asleep_s","Total asleep"],["deep_s","Deep"],["rem_s","REM"],["awake_s","Awake"],["overall","SleepIQ score"],["hr_mean","Sleeping heart rate"],["hrv_mean","Overnight HRV"],["efficiency","Sleep efficiency"],["resp_mean","Respiratory rate"],["temp_mean","Wrist temperature"]];
const WINDOW_METRICS=[...TILES.map(t=>t[0]),"core_s","onset_minute","wake_minute"];
const RANGES:[Selection["range"],string][]=[["7","7 days"],["30","30 days"],["90","90 days"],["all","All"],["custom","Custom"]];
const ROLLING:[Selection["rolling"],string][]=[["off","No average"],["7","7-day avg"],["30","30-day avg"]];
const MODES:[Selection["mode"],string][]=[["actual","Actual units"],["normalized","Normalized"]];
const BAR_DAYS=60;
const W=900,H=300,L=56,R=56,T=14,B=30,IW=W-L-R,IH=H-T-B;

type Win={summary:Summary;tiles:ChartData};
const finite=(v:number|null):v is number=>v!==null;
const xAt=(i:number,n:number,left=L,width=IW)=>left+(n<=1?width/2:i/(n-1)*width);
const indexAt=(svg:SVGSVGElement,clientX:number,n:number,viewWidth=W)=>{const r=svg.getBoundingClientRect();const sx=(clientX-r.left)/r.width*viewWidth;return Math.max(0,Math.min(n-1,Math.round((sx-L)/IW*(n-1))));};

function Segmented<T extends string>({label,options,value,onChange}:{label:string;options:[T,string][];value:T;onChange:(v:T)=>void}){
 return <div className="seg" role="group" aria-label={label}>{options.map(([v,text])=><button key={v} type="button" aria-pressed={value===v} onClick={()=>onChange(v)}>{text}</button>)}</div>;
}
function Lines({values,color:ink,x,y,area,className,dashed}:{values:(number|null)[];color:string;x:(i:number)=>number;y:(v:number)=>number;area?:number;className?:string;dashed?:boolean}){
 const runs=curveRuns(values.map((v,i)=>v===null?null:[x(i),y(v)]));
 return <>{area!==undefined&&<defs><linearGradient id={`fade-${ink.slice(1)}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={ink} stopOpacity="0.28"/><stop offset="100%" stopColor={ink} stopOpacity="0"/></linearGradient></defs>}{runs.map((run,k)=>run.segments.length?<g key={k}>
  {area!==undefined&&<path d={`${runPath(run)}L${run.points.at(-1)![0].toFixed(2)},${area}L${run.points[0][0].toFixed(2)},${area}Z`} fill={`url(#fade-${ink.slice(1)})`} className="series-area"/>}
  <path d={runPath(run)} fill="none" stroke={ink} strokeWidth={dashed?1.5:2.2} pathLength={dashed?undefined:1} strokeDasharray={dashed?"5 5":undefined} className={className} style={{color:ink}}/></g>
  :<circle key={k} cx={run.points[0][0]} cy={run.points[0][1]} r="2.6" fill={ink} className={className}/>)}</>;
}
function Spark({values,ink,width=110,height=44}:{values:(number|null)[];ink:string;width?:number;height?:number}){
 const ok=values.filter(finite);const lo=Math.min(...ok),hi=Math.max(...ok);
 return <svg viewBox={`0 0 ${width} ${height}`} className="spark" aria-hidden="true">{ok.length>0&&<Lines values={values} color={ink} area={height} x={i=>xAt(i,values.length,2,width-4)} y={v=>height-4-(v-lo)/(hi-lo||1)*(height-10)}/>}</svg>;
}
function Ring({fraction,ink,size=74,stroke=8}:{fraction:number;ink:string;size?:number;stroke?:number}){
 const r=size/2-stroke,c=2*Math.PI*r;
 return <svg viewBox={`0 0 ${size} ${size}`} width={size} aria-hidden="true"><circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--an-track)" strokeWidth={stroke}/><circle cx={size/2} cy={size/2} r={r} fill="none" stroke={ink} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${c*Math.max(0,Math.min(1,fraction))} ${c}`} transform={`rotate(-90 ${size/2} ${size/2})`} className="glow" style={{color:ink}}/></svg>;
}
function Gauge({value,ceiling}:{value:number|null;ceiling:number}){
 const at=(f:number)=>{const a=Math.PI*(1-f);return `${(45+36*Math.cos(a)).toFixed(2)},${(48-36*Math.sin(a)).toFixed(2)}`;};
 const [cx,cy]=at(ceiling/100).split(",").map(Number);
 return <svg viewBox="0 0 90 56" width="90" className="gauge" role="img" aria-label={`Gauge: ${value===null?"no score":value.toFixed(1)} of 100; pilot ceiling ${ceiling.toFixed(1)}`}>
  <path d={`M${at(0)} A36 36 0 0 1 ${at(1)}`} fill="none" stroke="var(--an-track)" strokeWidth="8" strokeLinecap="round"/>
  {value!==null&&value>0&&<path d={`M${at(0)} A36 36 0 0 1 ${at(Math.min(1,value/100))}`} fill="none" stroke={color("overall")} strokeWidth="8" strokeLinecap="round" className="glow gauge-value" style={{color:color("overall")}}/>}
  <circle cx={cx} cy={cy} r="2.5" fill="var(--an-text)" className="gauge-ceiling"><title>Pilot ceiling {ceiling.toFixed(1)}</title></circle></svg>;
}
function deltaText(id:string,m:Metric|undefined,delta:number|null,days:number):ReactNode{
 if(delta===null||!m)return <span className="muted">No earlier nights to compare</span>;
 const size=Math.abs(delta),amount=id==="asleep_s"||id.endsWith("_s")?`${Math.round((toAxis(m,size)??0)*60)} min`:display(m,size);
 return <><span className={delta>0?"up":delta<0?"down":""}>{delta>0?"▲":delta<0?"▼":"±"} {amount}</span> vs previous {days} days</>;
}

function Kpis({summary,tiles,catalog}:{summary:Summary;tiles:ChartData;catalog:Record<string,Metric>}){
 const series=(id:string)=>tiles.series.find(s=>s.id===id)?.raw??[];
 const item=(id:string)=>summary.metrics[id];
 const card=(id:string,title:string,visual:ReactNode,value:string)=><article className="an-card kpi-card" data-kpi={id} key={id}>
  <h3><span><i style={{background:color(id)}}/>{title}</span><span className="dim">n={item(id)?.n??0}</span></h3>
  <div className="kpi">{visual}<div><div className="kpi-value">{value}</div><div className="kpi-sub">{deltaText(id,catalog[id],item(id)?.delta??null,summary.days)}</div></div></div></article>;
 const sleep=item("asleep_s")?.mean??null,score=item("overall")?.mean??null,hrv=item("hrv_mean")?.mean??null;
 const missing=summary.days-summary.nights;
 return <section className="kpis" aria-label="Period summary">
  {card("asleep_s","Average sleep",<Spark values={series("asleep_s")} ink={color("asleep_s")}/>,sleep===null?"—":hoursText(sleep))}
  {card("overall","Average SleepIQ score",<Gauge value={score} ceiling={summary.ceiling}/>,score===null?"—":`${score.toFixed(1)} /100`)}
  {card("hrv_mean","Average overnight HRV",<Spark values={series("hrv_mean")} ink={color("hrv_mean")}/>,hrv===null?"—":`${hrv.toFixed(0)} ms`)}
  <article className="an-card kpi-card" data-kpi="nights"><h3><span>Nights recorded</span></h3><div className="kpi"><Ring fraction={summary.days?summary.nights/summary.days:0} ink={color("asleep_s")}/><div><div className="kpi-value">{summary.nights} of {summary.days}</div><div className="kpi-sub">{missing} day{missing===1?"":"s"} with no recorded sleep</div></div></div></article>
 </section>;
}

function axisDomain(unit:string,values:number[],fit:boolean):[number,number]{
 if(unit==="local time")return [0,1440];
 if(!values.length)return [0,1];
 const lo=Math.min(...values),hi=Math.max(...values);
 // Durations start at zero unless "zoom to fit" is on: an honest scale by default (P27).
 if(unit==="h"&&!fit)return [0,hi>0?hi*1.1:1];
 const pad=(hi-lo)*0.15||Math.max(Math.abs(hi)*0.05,0.5);
 return [unit==="h"?Math.max(0,lo-pad):lo-pad,hi+pad];
}
function tickLabel(unit:string,v:number,span:number){return unit==="local time"?clockText(v):v.toFixed(span<10?1:0);}

function MainChart({series,dates,normalized,fit,averages,recorded,onReset}:{series:Series[];dates:string[];normalized:boolean;fit:boolean;averages:boolean;recorded:Set<string>|null;onReset:()=>void}){
 const [cursor,setCursor]=useState<number|null>(null);const svg=useRef<SVGSVGElement>(null),box=useRef<HTMLDivElement>(null);
 const n=dates.length,c=cursor!==null&&cursor<n?cursor:null;
 const value=(s:Series,v:number|null)=>normalized?v:toAxis(s,v);
 // U08: dotted mean over the whole selected range (Python's normalization.mean), so zooming never moves it. Normalized series all average 0.
 const mean=(s:Series)=>!averages||s.clock||s.normalization.mean===null?null:normalized?0:toAxis(s,s.normalization.mean);
 const units:string[]=[];series.forEach(s=>{const u=axisUnit(s,normalized);if(!units.includes(u))units.push(u);});
 const axes=units.map((unit,k)=>{
  const members=series.filter(s=>axisUnit(s,normalized)===unit);
  const all=members.flatMap(s=>[...s.values.map(v=>value(s,v)),...(s.rolling?.values??[]).map(v=>value(s,v)),mean(s)]).filter(finite);
  const [lo,hi]=axisDomain(unit,all,fit);
  return {unit,side:k===0?"left":"right",lo,hi,ink:color(members[0].id),y:(v:number)=>T+IH-(v-lo)/(hi-lo||1)*IH};
 });
 const axisOf=(s:Series)=>axes.find(a=>a.unit===axisUnit(s,normalized))!;
 const x=(i:number)=>xAt(i,n);
 const step=Math.max(1,Math.ceil(n/8));
 const move=(to:number)=>setCursor(Math.max(0,Math.min(n-1,to)));
 const tipLeft=c===null?0:x(c)/W*100;
 return <div className="main-chart" ref={box}>
  <div className="chart-frame" tabIndex={0} role="group" aria-label={`Main chart, ${n} days. Left and Right arrow keys move between nights.`}
   onFocus={()=>{if(c===null&&n)setCursor(n-1);}} onBlur={()=>setCursor(null)} onDoubleClick={onReset}
   onKeyDown={e=>{if(!n)return;const keys:Record<string,number>={ArrowLeft:(c??n)-1,ArrowRight:(c??n-2)+1,Home:0,End:n-1};if(e.key in keys){e.preventDefault();move(keys[e.key]);}}}>
   <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="main-svg" aria-hidden="true">
    {[0,1,2,3,4].map(g=><line key={g} x1={L} x2={W-R} y1={T+g*IH/4} y2={T+g*IH/4} className="an-grid"/>)}
    {recorded&&dates.map((d,i)=>!recorded.has(d)&&<rect key={d} x={x(i)-2} y={T} width="4" height={IH} className="gap-band"/>)}
    {axes.map(a=><g key={a.unit} className={`axis-${a.side}`} data-unit={a.unit}>{[0,1,2,3,4].map(g=>{const v=a.lo+(a.hi-a.lo)*(4-g)/4;return <text key={g} x={a.side==="left"?L-8:W-R+8} y={T+g*IH/4+4} textAnchor={a.side==="left"?"end":"start"} fill={a.ink} className="tick">{tickLabel(a.unit,v,a.hi-a.lo)}</text>;})}</g>)}
    {series.map(s=>{const a=axisOf(s);return <g key={s.id} data-metric={s.id} data-axis={a.side}>
     <Lines values={s.values.map(v=>value(s,v))} color={color(s.id)} x={x} y={a.y} area={T+IH} className="series-line"/>
     {s.rolling?.values&&<Lines values={s.rolling.values.map(v=>value(s,v))} color="#f4eded" x={x} y={a.y} dashed className="rolling-line"/>}
    </g>;})}
    {normalized?(()=>{const s=series.find(v=>mean(v)!==null);return s?<AverageLine key="z" y={axisOf(s).y(0)} ink="#f4eded" text="average (0)"/>:null;})()
     :series.map(s=>{const m=mean(s);return m===null?null:<AverageLine key={`avg-${s.id}`} metric={s.id} y={axisOf(s).y(m)} ink={color(s.id)} text={averageText(s)!}/>;})}
    {dates.map((d,i)=>(i%step===0&&n-1-i>=step*0.6)||i===n-1?<text key={d} x={x(i)} y={H-8} textAnchor="middle" className="tick dim-tick">{shortDay(d)}</text>:null)}
    {c!==null&&<g className="crosshair"><line x1={x(c)} x2={x(c)} y1={T} y2={T+IH}/>{series.map(s=>{const v=value(s,s.values[c]);return v===null?null:<circle key={s.id} cx={x(c)} cy={axisOf(s).y(v)} r="5" stroke={color(s.id)}/>;})}</g>}
    <rect x={L} y={T} width={IW} height={IH} fill="transparent" className="hit"
     onPointerMove={e=>svg.current&&n&&setCursor(indexAt(svg.current,e.clientX,n))} onPointerLeave={()=>{if(document.activeElement!==box.current?.firstChild)setCursor(null);}}/>
   </svg>
   <div className="axis-captions">{axes.map(a=><span key={a.unit} className={`axis-caption caption-${a.side}`} style={{color:a.ink}}>{unitName(a.unit)}</span>)}</div>
   <div className="chart-tip" role="status" aria-live="polite" hidden={c===null} style={c===null?undefined:tipLeft>62?{right:`calc(${100-tipLeft}% + 14px)`}:{left:`calc(${tipLeft}% + 14px)`}}>
    {c!==null&&<><b>{shortDay(dates[c])} <time dateTime={dates[c]}>{dates[c]}</time></b>
     {series.map(s=><div key={s.id} className="tip-row" data-metric={s.id}><span style={{color:color(s.id)}}>● {s.label}</span><span>{display(s,s.values[c],normalized)}</span></div>)}
     {averages&&series.filter(s=>!s.clock).map(s=><div key={`a-${s.id}`} className="tip-row average" data-average={s.id}><span>{s.label} average</span><span>{averageText(s,normalized)}</span></div>)}
     {series.filter(s=>s.rolling).map(s=><div key={`r-${s.id}`} className="tip-row rolling"><span>{s.label}</span><span>{rollingNote(s.rolling!,c,v=>display(s,v,normalized))}</span></div>)}
     {recorded&&!recorded.has(dates[c])&&<div className="tip-row"><span>No recorded sleep this night</span></div>}</>}
   </div>
  </div>
 </div>;
}

function AverageLine({y,ink,text,metric}:{y:number;ink:string;text:string;metric?:string}){
 // The label sits just above the line at the right edge of the plot, or below it near the top.
 const above=y-T>14;
 return <g className="average" data-average={metric}><line x1={L} x2={W-R} y1={y} y2={y} stroke={ink} strokeWidth="1.6" strokeDasharray="1 5" strokeLinecap="round" className="average-line"/>
  <text x={W-R-6} y={above?y-6:y+14} textAnchor="end" fill={ink} className="tick average-label">{text}</text></g>;
}
function Brush({series,n,zoom,setZoom,normalized}:{series:Series|undefined;n:number;zoom:[number,number]|null;setZoom:(z:[number,number]|null)=>void;normalized:boolean}){
 const svg=useRef<SVGSVGElement>(null);const [drag,setDrag]=useState<[number,number]|null>(null);const h=54;
 const values=series?series.values.map(v=>normalized?v:toAxis(series,v)):[];const ok=values.filter(finite);const lo=Math.min(...ok),hi=Math.max(...ok);
 const x=(i:number)=>xAt(i,n);const shown=drag??zoom;
 const at=(clientX:number)=>svg.current?indexAt(svg.current,clientX,n):0;
 return <svg ref={svg} viewBox={`0 0 ${W} ${h}`} className="brush" role="img" aria-label="Zoom strip: drag across it to zoom the main chart; double-click to show the full range"
  onPointerDown={e=>{if(!n)return;svg.current?.setPointerCapture?.(e.pointerId);const i=at(e.clientX);setDrag([i,i]);}}
  onPointerMove={e=>{if(drag)setDrag([drag[0],at(e.clientX)]);}}
  onPointerUp={()=>{if(drag){const a=Math.min(...drag),b=Math.max(...drag);if(b-a>=1)setZoom([a,b]);setDrag(null);}}}
  onDoubleClick={()=>{setDrag(null);setZoom(null);}}>
  <rect x={L} y="2" width={IW} height={h-4} rx="6" className="brush-bg"/>
  {series&&ok.length>0&&<Lines values={values} color={color(series.id)} x={x} y={v=>h-8-(v-lo)/(hi-lo||1)*(h-18)}/>}
  {shown&&<rect x={x(Math.min(...shown))} y="2" width={Math.max(2,x(Math.max(...shown))-x(Math.min(...shown)))} height={h-4} rx="4" className="brush-sel"/>}
 </svg>;
}

function Composition({summary}:{summary:Summary}){
 const parts=(["deep","core","rem","awake"] as const).map(k=>({k,label:k==="rem"?"REM":k[0].toUpperCase()+k.slice(1),...(summary.stages?.[k]??{minutes:null,percent:null})}));
 const cx=130,cy=112,r=78,circ=2*Math.PI*r;let acc=0;const asleep=summary.metrics.asleep_s?.mean??null;
 return <section className="an-card composition" aria-labelledby="composition-heading"><h3 id="composition-heading">Average night composition</h3>
  <svg viewBox="0 0 260 230" role="img" aria-label={parts.map(p=>`${p.label} ${p.minutes===null?"no reading":`${Math.round(p.minutes)} minutes`}`).join(", ")}>
   <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--an-track)" strokeWidth="22"/>
   {parts.map(p=>{if(!p.percent)return null;const f=p.percent/100,el=<circle key={p.k} cx={cx} cy={cy} r={r} fill="none" stroke={STAGE_COLOR[p.k]} strokeWidth="22" strokeDasharray={`${Math.max(0,circ*f-3)} ${circ}`} strokeDashoffset={-circ*acc} transform={`rotate(-90 ${cx} ${cy})`}/>;acc+=f;return el;})}
   <text x={cx} y={cy-2} textAnchor="middle" className="ring-big">{asleep===null?"—":hoursText(asleep)}</text><text x={cx} y={cy+18} textAnchor="middle" className="ring-small">average asleep</text>
  </svg>
  <ul className="stage-legend">{parts.map(p=><li key={p.k}><span><i style={{background:STAGE_COLOR[p.k]}}/>{p.label}</span><span className="muted">{p.minutes===null?"no reading":`${Math.round(p.minutes)} min · ${Math.round(p.percent??0)}%`}</span></li>)}</ul>
  <p className="note">Mean per recorded night. Deep and REM are shown for description only; they are not targets.</p>
 </section>;
}

function Tiles({summary,tiles,catalog,selected,onPick}:{summary:Summary;tiles:ChartData;catalog:Record<string,Metric>;selected:string[];onPick:(id:string)=>void}){
 return <section className="tiles" aria-label="Metric tiles">{TILES.map(([id,title])=>{const m=catalog[id],s=summary.metrics[id],raw=tiles.series.find(x=>x.id===id)?.raw??[];if(!m)return null;
  const avg=s?.mean==null?"—":display(m,s.mean),range=s?.min==null||s.max==null?"no readings":`range ${display(m,s.min)} – ${display(m,s.max)}`;
  return <button type="button" key={id} className={`an-card tile${selected.includes(id)?" sel":""}`} data-tile={id} aria-pressed={selected.length===1&&selected[0]===id} aria-label={`${title}: ${avg} average. Show in the main chart`} onClick={()=>onPick(id)}>
   <h3><span><i style={{background:color(id)}}/>{title}</span><span className="dim">{s?.n??0}/{summary.days} nights</span></h3>
   <div className="tile-val">{avg} <small>avg</small></div><div className="tile-range">{range}</div>
   <Spark values={raw.map(v=>toAxis(m,v))} ink={color(id)} width={300} height={70}/></button>;})}</section>;
}

function StageBars({tiles}:{tiles:ChartData}){
 const get=(id:string)=>tiles.series.find(s=>s.id===id)?.raw??[];
 const from=Math.max(0,tiles.dates.length-BAR_DAYS),dates=tiles.dates.slice(from);
 const stack=(["deep","core","rem","awake"] as const).map(k=>({k,v:get(`${k}_s`).slice(from)}));const asleep=get("asleep_s").slice(from);
 const Wd=640,Ht=220,left=30,bottom=24,top=8,ih=Ht-top-bottom,iw=Wd-left-6,bw=iw/Math.max(1,dates.length);
 const totals=dates.map((_,i)=>stack.reduce((sum,p)=>sum+(p.v[i]??0),0)/60);const max=Math.max(8,Math.ceil(Math.max(0,...totals)/2)*2);
 return <section className="an-card stage-bars" aria-labelledby="bars-heading"><h3 id="bars-heading"><span>Sleep stages per night</span><span className="dim">hours{tiles.dates.length>BAR_DAYS?` · last ${BAR_DAYS} days of the range`:""}</span></h3>
  <svg viewBox={`0 0 ${Wd} ${Ht}`} role="img" aria-label={`Stacked nightly sleep stages for ${dates.length} days; unrecorded nights are outlined`}>
   {Array.from({length:max/2+1},(_,g)=>{const y=top+ih-g*2/max*ih;return <g key={g}><line x1={left} x2={Wd} y1={y} y2={y} className="an-grid"/><text x={left-6} y={y+3} textAnchor="end" className="tick dim-tick">{g*2}</text></g>;})}
   {dates.map((d,i)=>{const x=left+i*bw+bw*.18,w=bw*.64;if(asleep[i]===null)return <rect key={d} x={x} y={top+ih-6} width={w} height="6" rx="2" className="missing-bar"><title>{d}: no recorded sleep</title></rect>;
    let y=top+ih;return <g key={d}><title>{`${d}: ${stack.map(p=>`${p.k==="rem"?"REM":p.k[0].toUpperCase()+p.k.slice(1)} ${p.v[i]===null?"no reading":`${Math.round(p.v[i]!)} min`}`).join(", ")}`}</title>{stack.map(p=>{const h=(p.v[i]??0)/60/max*ih;y-=h;return <rect key={p.k} x={x} y={y} width={w} height={Math.max(0,h-1)} rx="1" fill={STAGE_COLOR[p.k]}/>;})}</g>;})}
   {dates.length>0&&[0,dates.length-1].map(i=><text key={i} x={left+i*bw+bw/2} y={Ht-6} textAnchor="middle" className="tick dim-tick">{shortDay(dates[i])}</text>)}
  </svg></section>;
}

function ClockStrip({summary,tiles}:{summary:Summary;tiles:ChartData}){
 const Wd=440,left=56,iw=Wd-left-10;
 const rows=([["Bedtime","onset_minute","onset",60],["Wake","wake_minute","wake",150]] as const).map(([label,id,key,y])=>{
  const stats=summary.clock?.[key],med=stats?.median??null;const raw=(tiles.series.find(s=>s.id===id)?.raw??[]).filter(finite);
  // Positions only: each time is placed within 12 hours of the typical time so midnight never splits the strip.
  const near=(v:number)=>med===null?v:med+((v-med+720)%1440+1440)%1440-720;
  const vals=raw.map(near);let lo=Math.floor(Math.min(...vals,med??0)/60)*60,hi=Math.ceil(Math.max(...vals,med??0)/60)*60;
  if(!vals.length){lo=0;hi=1440;}if(hi-lo<240){const mid=(lo+hi)/2;lo=Math.floor((mid-120)/60)*60;hi=lo+240;}
  return {label,id,y,stats,med,vals,lo,hi,near,ink:color(id)};
 });
 return <section className="an-card clock-strip" aria-labelledby="clock-heading"><h3 id="clock-heading"><span>Bedtime &amp; wake time</span><span className="dim">source-local clock</span></h3>
  <svg viewBox={`0 0 ${Wd} 220`} role="img" aria-label={rows.map(r=>`${r.label}: typical ${r.med===null?"unavailable":clockText(r.med)}`).join("; ")}>
   {rows.map(r=>{const x=(v:number)=>left+(v-r.lo)/(r.hi-r.lo)*iw;const every=r.hi-r.lo>480?120:60;return <g key={r.label} className="clock-row" data-row={r.id}>
    {r.stats?.q1!=null&&r.stats.q3!=null&&<rect x={x(r.near(r.stats.q1))} y={r.y-16} width={Math.max(2,x(r.near(r.stats.q3))-x(r.near(r.stats.q1)))} height="32" rx="8" fill={r.ink} opacity=".12"/>}
    {r.vals.map((v,i)=><circle key={i} cx={x(v)} cy={r.y+((i*37)%21-10)} r="3" fill={r.ink} opacity=".75"/>)}
    <text x="0" y={r.y+4} className="tick label-tick">{r.label}</text>
    {r.med!==null&&<><line x1={x(r.med)} x2={x(r.med)} y1={r.y-20} y2={r.y+20} className="median"/><text x={x(r.med)} y={r.y-26} textAnchor="middle" className="tick typical">typical {clockText(r.med)}</text></>}
    {Array.from({length:Math.floor((r.hi-r.lo)/every)+1},(_,k)=>r.lo+k*every).map(t=><text key={t} x={x(t)} y={r.y+36} textAnchor="middle" className="tick dim-tick">{clockText(t)}</text>)}
   </g>;})}
  </svg><p className="note">Each dot is one night. The band shows your middle 50%; typical is the median, with midnight crossings kept continuous.</p></section>;
}

export function Analytics(){
 const [catalog,setCatalog]=useState<Metric[]>([]),[presets,setPresets]=useState<Preset[]>([]);
 const [selection,setSelection]=useState<Selection>(initialSelection),[data,setData]=useState<(ChartData&{mode:Selection["mode"]})|null>(null),[win,setWin]=useState<Win|null>(null);
 const [error,setError]=useState(""),[busy,setBusy]=useState(false),[winBusy,setWinBusy]=useState(false),[ready,setReady]=useState(false),[retry,setRetry]=useState(0);
 const [name,setName]=useState(""),[current,setCurrent]=useState(""),[isDefault,setDefault]=useState(false),[saving,setSaving]=useState(false),[notice,setNotice]=useState("");
 const [confirmation,setConfirmation]=useState<"save"|"delete"|null>(null),[zoom,setZoom]=useState<[number,number]|null>(null);
 const [refused,setRefused]=useState(""),[fit,setFit]=useState(false),[table,setTable]=useState(false),[averages,setAverages]=useState(true);
 const generation=useRef(0),main=useRef<HTMLElement>(null);
 const byId=Object.fromEntries(catalog.map(m=>[m.id,m]));
 const unitFor=(mode:Selection["mode"])=>(id:string)=>byId[id]?axisUnit(byId[id],mode==="normalized"):id;
 const chips=catalog.filter(m=>!NOT_CHARTED.has(m.id));
 // Saved presets may predate the chart limits (two axes, six lines, no Core): keep what fits, in order.
 const sanitize=(s:Selection,metrics:Metric[]):Selection=>{const ids=new Map(metrics.map(m=>[m.id,m]));const allowed=new Set(metrics.filter(m=>!NOT_CHARTED.has(m.id)&&!(s.mode==="normalized"&&m.clock)).map(m=>m.id));
  const kept=fitMetrics(s.metrics,allowed,id=>ids.get(id)?axisUnit(ids.get(id)!,s.mode==="normalized"):id);return {...s,metrics:kept.length?kept:["asleep_s"]};};

 useEffect(()=>{const c=new AbortController();setReady(false);setError("");Promise.all([chartRequest<Metric[]>("metrics/catalog","GET",undefined,c.signal),chartRequest<Preset[]>("presets","GET",undefined,c.signal)]).then(([metrics,saved])=>{if(c.signal.aborted)return;setCatalog(metrics);setPresets(saved);const def=saved.find(p=>p.default);if(def){setSelection(sanitize(withDefaults(def),metrics));setCurrent(def.id);setName(def.name);setDefault(true);}setReady(true);}).catch(e=>{if(!c.signal.aborted)setError(String(e.message));});return()=>c.abort();},[retry]);

 const customInvalid=selection.range==="custom"&&(!selection.start||!selection.end||selection.start>selection.end);
 useEffect(()=>{if(!ready)return;const c=new AbortController();setError("");if(!selection.metrics.length){setData(null);setBusy(false);return;}if(customInvalid){setData(null);setError("Choose a valid start and end date.");setBusy(false);return;}setBusy(true);
  const {metrics,range,start,end,mode,rolling}=selection;
  chartRequest<ChartData>("analytics/timeseries","POST",{metrics,range,start,end,mode,rolling},c.signal).then(d=>{if(!c.signal.aborted)setData({...d,mode});}).catch(e=>{if(!c.signal.aborted){setData(null);setError(e.message);}}).finally(()=>{if(!c.signal.aborted)setBusy(false);});return()=>c.abort();},[selection,ready]);

 // Summary figures and tiles depend only on the date window, not on the chart's metric choice.
 const {range,start,end}=selection;
 useEffect(()=>{if(!ready||customInvalid)return;const c=new AbortController();setWinBusy(true);setZoom(null);
  Promise.all([chartRequest<Summary>("analytics/summary","POST",{range,start,end},c.signal),chartRequest<ChartData>("analytics/timeseries","POST",{metrics:WINDOW_METRICS,range,start,end,mode:"actual",rolling:"off"},c.signal)])
   .then(([summary,tiles])=>{if(!c.signal.aborted)setWin({summary,tiles});}).catch(e=>{if(!c.signal.aborted){setWin(null);setError(e.message);}}).finally(()=>{if(!c.signal.aborted)setWinBusy(false);});
  return()=>c.abort();},[range,start,end,ready,customInvalid]);

 function update(patch:Partial<Selection>){setSelection(s=>({...s,...patch}));setNotice("");}
 function toggle(id:string,on:boolean){
  if(!on){setRefused("");update({metrics:selection.metrics.filter(m=>m!==id)});return;}
  const why=refusal(selection.metrics,id,unitFor(selection.mode));if(why){setRefused(why);return;}
  setRefused("");update({metrics:[...selection.metrics,id]});
 }
 function setMode(mode:Selection["mode"]){
  const next=sanitize({...selection,mode,metrics:mode==="normalized"?selection.metrics.filter(id=>!byId[id]?.clock):selection.metrics},catalog);
  setRefused(next.metrics.length<selection.metrics.length&&mode==="actual"?"Some metrics were removed: actual units allow two axes and six lines.":"");update({mode,metrics:next.metrics});
 }
 async function persist(action:"new"|"save"|"delete"){
  setSaving(true);setError("");setConfirmation(null);const request=++generation.current;
  try{const existing=presets.find(p=>p.id===current);if(action!=="new"&&!existing)throw new Error("Choose an existing preset first.");
   if(action==="delete"){await chartRequest(`presets/${current}?revision=${existing!.revision}`,"DELETE");setCurrent("");setName("");setDefault(false);}
   else {const {metrics,range,start,end,mode,rolling}=selection;const saved=await chartRequest<Preset>(`presets/${action==="new"?"new":current}`,"PUT",{metrics,range,start,end,mode,rolling,name,default:isDefault,revision:action==="new"?0:existing!.revision});setCurrent(saved.id);setName(saved.name);}
   setPresets(await chartRequest<Preset[]>("presets"));setNotice(action==="delete"?"Preset deleted.":"Preset saved.");
  }catch(e){setError((e as Error).message);}finally{if(request===generation.current)setSaving(false);}
 }
 function load(id:string){const p=presets.find(v=>v.id===id);setCurrent(id);setName(p?.name??"");setDefault(p?.default??false);if(p)setSelection(sanitize(withDefaults(p),catalog));setNotice("");setRefused("");}
 function pick(id:string){setRefused("");update({metrics:[id]});const reduce=window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;main.current?.scrollIntoView({behavior:reduce?"auto":"smooth",block:"nearest"});}

 // Previous results stay visible (dimmed) while loading, so they render with the mode they were fetched in.
 const shown=data?.mode??selection.mode,normalized=shown==="normalized";
 const total=data?.dates.length??0,[za,zb]=zoom&&zoom[1]<total?zoom:[0,Math.max(0,total-1)];
 const dates=data?.dates.slice(za,zb+1)??[],sliced=(data?.series??[]).map(s=>sliceSeries(s,za,zb));
 const recorded=win?new Set(win.tiles.dates.filter((_,i)=>win.tiles.series.find(s=>s.id==="asleep_s")?.raw[i]!=null)):null;
 const hasHours=sliced.some(s=>!normalized&&axisUnit(s)==="h");
 const title=sliced.map(s=>s.label).join(" & ")||"Choose a metric";
 const loading=busy||winBusy;

 return <div className="analytics an">
  <section className="an-top" aria-label="Analytics options">
   <Segmented label="Date range" options={RANGES} value={selection.range} onChange={v=>update({range:v})}/>
   <Segmented label="Rolling average" options={ROLLING} value={selection.rolling} onChange={v=>update({rolling:v})}/>
   <Segmented label="Display" options={MODES} value={selection.mode} onChange={setMode}/>
   <details className="preset-menu"><summary>☆ Presets{current?` · ${name}`:""}</summary><div className="preset-pop">
    <label>Load preset<select value={current} onChange={e=>load(e.target.value)}><option value="">New preset</option>{presets.map(p=><option key={p.id} value={p.id}>{p.name}{p.default?" · Default":""}</option>)}</select></label>
    <label>Preset name<input maxLength={60} value={name} onChange={e=>setName(e.target.value)}/></label>
    <label className="inline"><input type="checkbox" checked={isDefault} onChange={e=>setDefault(e.target.checked)}/>Default on opening Analytics</label>
    <div className="chart-actions"><button disabled={!ready||saving||!name.trim()||!selection.metrics.length} onClick={()=>void persist("new")}>Save as new</button><button disabled={!current||saving||!name.trim()} onClick={()=>setConfirmation("save")}>Update selected</button><button disabled={!current||saving} onClick={()=>setConfirmation("delete")}>Delete selected</button><button disabled={saving} onClick={()=>{setCurrent("");setRetry(n=>n+1);}}>Reload presets</button></div>
    {confirmation&&<div className="confirm-preset" role="alert"><p>{confirmation==="delete"?"Delete this saved preset? This cannot be undone.":"Replace this preset’s name, settings and default choice?"}</p><button onClick={()=>void persist(confirmation)}>Confirm {confirmation==="delete"?"delete":"update"}</button><button onClick={()=>setConfirmation(null)}>Cancel</button></div>}
    {notice&&<p role="status">{notice}</p>}</div></details>
   {selection.range==="custom"&&<div className="custom-range"><label>From<input type="date" value={selection.start??""} onChange={e=>update({start:e.target.value})}/></label><label>To<input type="date" value={selection.end??""} onChange={e=>update({end:e.target.value})}/></label></div>}
   <span className="load-status" role="status">{loading?"Loading nightly measurements…":""}</span>
  </section>
  {(data?.synthetic||win?.summary.synthetic)&&<p className="preview-banner">Synthetic preview — generated test data, not your health records.</p>}
  {error&&<div className="panel" role="alert">{error} <button onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
  {!ready&&!error&&<section className="panel placeholder" role="status"><p>Loading analytics…</p></section>}

  {ready&&<div className="an-body" aria-busy={loading}>
   {win&&win.summary.nights>0&&<Kpis summary={win.summary} tiles={win.tiles} catalog={byId}/>}
   <div className="an-focus">
    <section className="an-card main-card" ref={main} aria-labelledby="main-heading">
     <div className="main-head"><h2 id="main-heading">{title}</h2>{dates.length>0&&<span className="dim range-label"><time dateTime={dates[0]}>{shortDay(dates[0])}</time> – <time dateTime={dates.at(-1)}>{shortDay(dates.at(-1)!)}</time> · {dates.length} days</span>}</div>
     <fieldset className="chips"><legend className="sr-only">Metrics in the main chart</legend>{chips.map(m=>{const off=selection.mode==="normalized"&&m.clock,on=selection.metrics.includes(m.id);return <label key={m.id} className={`chip${on?" on":""}${off?" disabled":""}`}><input type="checkbox" checked={on} disabled={off} onChange={e=>toggle(m.id,e.target.checked)}/><i style={{background:color(m.id)}}/>{m.label}{off?" (actual only)":""}</label>;})}</fieldset>
     <p className="chip-note" role="status">{refused}</p>
     {!selection.metrics.length&&<p role="status">Choose at least one metric.</p>}
     {data&&!data.dates.length&&<div><h2>No recorded nights yet</h2><p>Charts will appear after a successful import. Missing data is never filled in.</p></div>}
     {data&&data.dates.length>0&&<>
      <MainChart series={sliced} dates={dates} normalized={normalized} fit={fit} averages={averages} recorded={recorded} onReset={()=>setZoom(null)}/>
      <Brush series={data.series[0]} n={total} zoom={zoom} setZoom={setZoom} normalized={normalized}/>
      <div className="chart-toolbar zoom-row"><label>Zoom start<input type="range" aria-label="Zoom start" min={0} max={Math.max(0,total-1)} value={za} onChange={e=>setZoom([Math.min(Number(e.target.value),zb),zb])}/></label><label>Zoom end<input type="range" aria-label="Zoom end" min={0} max={Math.max(0,total-1)} value={zb} onChange={e=>setZoom([za,Math.max(Number(e.target.value),za)])}/></label><button onClick={()=>setZoom(null)}>Reset zoom</button>
       {hasHours&&<label className="inline"><input type="checkbox" checked={fit} onChange={e=>setFit(e.target.checked)}/>Zoom to fit hours axis</label>}
       <label className="inline"><input type="checkbox" checked={averages} onChange={e=>setAverages(e.target.checked)}/>Show averages</label>
       <button aria-expanded={table} onClick={()=>setTable(t=>!t)}>{table?"Hide table":"Show as table"}</button></div>
      <p className="hint">Hover or focus the chart and use Left/Right for exact values · drag in the strip to zoom · double-click to reset · zoom keeps the range and normalization baseline</p>
      {table&&<div className="chart-table"><table><caption className="sr-only">{title}, values shown in the chart</caption><thead><tr><th>Wake date</th>{sliced.map(s=><th key={s.id}>{s.label}</th>)}{sliced.filter(s=>s.rolling).map(s=><th key={`r-${s.id}`}>{s.label} {s.rolling!.window}-day mean</th>)}</tr></thead>
       <tbody>{dates.map((d,i)=><tr key={d}><td>{d}</td>{sliced.map(s=><td key={s.id}>{display(s,s.values[i],normalized)}</td>)}{sliced.filter(s=>s.rolling).map(s=><td key={`r-${s.id}`}>{rollingNote(s.rolling!,i,v=>display(s,v,normalized))}</td>)}</tr>)}</tbody>
       {averages&&<tfoot><tr><th scope="row">Average</th>{sliced.map(s=><td key={s.id} data-average={s.id}>{averageText(s,normalized)??"not shown for clock times"}</td>)}{sliced.filter(s=>s.rolling).map(s=><td key={`r-${s.id}`}/>)}</tr></tfoot>}</table></div>}
     </>}
     <p className="muted">{normalized?"Z-score = (value − mean) / population standard deviation over the selected range. Constant series are unavailable; clock times are excluded.":"Metrics that share a unit share an axis (all sleep durations in hours), with at most two axes and six lines. Clock times use source-local wall time; midnight crossings are not elapsed durations."}</p>
     {averages&&<p className="muted">Dotted line: {normalized?"the average, which is 0 for every normalized metric":"each metric's average over the whole selected range, not just the zoomed part; nights without a reading are left out. Clock times have no average"}.</p>}
     {selection.rolling!=="off"&&<p className="muted">Dashed line: trailing {selection.rolling}-day calendar mean, shown only when at least {selection.rolling==="7"?4:15} of those {selection.rolling} nights were recorded. Missing nights are skipped, never counted as zero; early windows may include recorded nights before the range starts. Not available for clock times.</p>}
    </section>
    {win&&win.summary.nights>0&&<Composition summary={win.summary}/>}
   </div>
   {win&&win.summary.nights>0&&<><Tiles summary={win.summary} tiles={win.tiles} catalog={byId} selected={selection.metrics} onPick={pick}/>
    <div className="an-row2"><StageBars tiles={win.tiles}/><ClockStrip summary={win.summary} tiles={win.tiles}/></div>
    <p className="muted versions">{win.summary.versions.join(" · ")} · averages exclude nights without a reading</p></>}
  </div>}
 </div>;
}
