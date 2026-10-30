import {useEffect,useLayoutEffect,useRef,useState} from "react";
import type {KeyboardEvent,PointerEvent} from "react";
import {SHORT_LABEL,ageColour,chartRequest,curveRuns,groupMetrics,nearestPoint,niceAxis,pairText,rText,runPath,scatterHeight} from "./charts";
import type {ChartData,Correlation,CorrelationGrid,Metric,Pt,Range} from "./charts";
import {fullDay,shortDay} from "./dashboardModel";

// U17 (P29): Afterburn Holo redesign. Python pairs nights and computes r, n, exclusions and the best-fit line;
// this view positions, animates and labels the results. Charts are drawn at their real pixel size.
const RANGES:[Range,string][]=[["30","30 days"],["90","90 days"],["365","1 year"],["all","All"],["custom","Custom"]];
type Brush=[string,string]|null;
type Win={range:Range;start:string|null;end:string|null};
const reduced=()=>typeof window!=="undefined"&&!!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function useWidth<T extends HTMLElement>(){
 const ref=useRef<T>(null),[width,setWidth]=useState(0);
 useLayoutEffect(()=>{const el=ref.current;if(!el)return;setWidth(el.clientWidth);
  if(typeof ResizeObserver==="undefined")return;const ro=new ResizeObserver(([e])=>setWidth(Math.round(e.contentRect.width)));ro.observe(el);return()=>ro.disconnect();},[]);
 return [ref,width] as const;
}
function useHeight<T extends HTMLElement>(){
 const ref=useRef<T>(null),[height,setHeight]=useState(0);
 useLayoutEffect(()=>{const el=ref.current;if(!el||typeof ResizeObserver==="undefined")return;const ro=new ResizeObserver(([e])=>setHeight(Math.round(e.borderBoxSize?.[0]?.blockSize??e.contentRect.height)));ro.observe(el);return()=>ro.disconnect();},[]);
 return [ref,height] as const;
}
function useViewportHeight(){
 const [h,setH]=useState(()=>typeof window==="undefined"?900:window.innerHeight);
 useEffect(()=>{const on=()=>setH(window.innerHeight);window.addEventListener("resize",on);return()=>window.removeEventListener("resize",on);},[]);
 return h;
}
/** Counts the readout to its new value (off under reduced motion). */
function useTween(target:number|null){
 const [value,setValue]=useState(target??0),current=useRef(target??0);
 useEffect(()=>{if(target===null)return;const from=current.current,t0=performance.now();let frame=0;
  const step=(t:number)=>{const k=reduced()?1:Math.min(1,(t-t0)/650),v=from+(target-from)*(1-(1-k)**3);current.current=v;setValue(v);if(k<1)frame=requestAnimationFrame(step);};
  frame=requestAnimationFrame(step);return()=>cancelAnimationFrame(frame);},[target]);
 return value;
}
/** One request per window/pair; the previous result stays on screen (dimmed) until the new one arrives. */
function useRequest<T>(path:string,body:unknown,enabled:boolean,retry:number,onError:(m:string)=>void){
 const [data,setData]=useState<T|null>(null),[busy,setBusy]=useState(false),key=JSON.stringify(body);
 useEffect(()=>{if(!enabled)return;const c=new AbortController();setBusy(true);
  chartRequest<T>(path,"POST",body,c.signal).then(d=>{if(!c.signal.aborted)setData(d);}).catch(e=>{if(!c.signal.aborted){setData(null);onError(e.message);}}).finally(()=>{if(!c.signal.aborted)setBusy(false);});
  return()=>c.abort();
 },[path,key,enabled,retry]);
 return [data,busy] as const;
}

function Segmented({value,onChange}:{value:Range;onChange:(r:Range)=>void}){
 const box=useRef<HTMLDivElement>(null),[thumb,setThumb]=useState<{left:number;width:number}|null>(null);
 useLayoutEffect(()=>{const b=box.current?.querySelector<HTMLButtonElement>("button[aria-pressed=true]");if(b)setThumb({left:b.offsetLeft,width:b.offsetWidth});},[value]);
 return <div className="cx-seg" role="group" aria-label="Date range" ref={box}>{thumb&&<span className="cx-thumb" style={thumb}/>}
  {RANGES.map(([r,label])=><button key={r} type="button" aria-pressed={value===r} onClick={()=>onChange(r)}>{label}</button>)}</div>;
}

function ChipRow({axis,catalog,value,other,onPick}:{axis:"x"|"y";catalog:Metric[];value:string;other:string;onPick:(id:string)=>void}){
 const name=axis==="x"?"X axis":"Y axis";
 return <div className={`cx-row cx-${axis}`} role="group" aria-label={name}><span className="cx-axis"><i/>{name.toUpperCase()}</span>
  <div className="cx-chips">{groupMetrics(catalog).map(([group,ms])=><span className="cx-grp" key={group}><span className="cx-group" aria-hidden="true">{group}</span>
   {ms.map(m=><button key={m.id} type="button" className="cx-chip" data-metric={m.id} aria-pressed={value===m.id} disabled={other===m.id} title={other===m.id?`Already on the ${axis==="x"?"Y":"X"} axis`:undefined} onClick={()=>onPick(m.id)}><i/>{m.label}</button>)}</span>)}</div></div>;
}

const M={l:52,r:16,t:12,b:46};
function Scatter({data,width,height,colourFrom,colourTo,fit,focus,setFocus}:{data:Correlation;width:number;height:number;colourFrom:string;colourTo:string;fit:boolean;focus:string|null;setFocus:(d:string|null)=>void}){
 const iw=Math.max(1,width-M.l-M.r),ih=Math.max(1,height-M.t-M.b);
 const ax=niceAxis(data.pairs.map(p=>p.x)),ay=niceAxis(data.pairs.map(p=>p.y));
 const sx=(v:number)=>M.l+(v-ax.lo)/(ax.hi-ax.lo)*iw,sy=(v:number)=>M.t+ih-(v-ay.lo)/(ay.hi-ay.lo)*ih;
 const points=data.pairs.map(p=>({...p,cx:sx(p.x),cy:sy(p.y)})),hot=points.find(p=>p.date===focus);
 const line=data.fit&&`path("M ${sx(ax.lo).toFixed(1)} ${sy(data.fit.intercept+data.fit.slope*ax.lo).toFixed(1)} L ${sx(ax.hi).toFixed(1)} ${sy(data.fit.intercept+data.fit.slope*ax.hi).toFixed(1)}")`;
 const svg=useRef<SVGSVGElement>(null);
 const move=(e:PointerEvent<SVGSVGElement>)=>{const b=svg.current?.getBoundingClientRect();if(!b||!points.length)return;const k=width/b.width;
  const next=nearestPoint(points,(e.clientX-b.left)*k,(e.clientY-b.top)*k,focus);if(next!==focus)setFocus(next);};
 const key=(e:KeyboardEvent<SVGSVGElement>)=>{if(!points.length)return;const i=points.findIndex(p=>p.date===focus);
  const to:Record<string,number>={ArrowRight:i+1,ArrowLeft:i<0?points.length-1:i-1,Home:0,End:points.length-1};
  if(e.key in to){e.preventDefault();setFocus(points[Math.max(0,Math.min(points.length-1,to[e.key]))].date);}};
 const tipLeft=hot?(hot.cx+16+214>width?hot.cx-16-214:hot.cx+16):0,tipTop=hot?Math.max(0,Math.min(height-78,hot.cy-36)):0;
 return <div className="cx-plot">
  <svg ref={svg} width="100%" height={height} viewBox={`0 0 ${width} ${height}`} tabIndex={0} role="group" className="cx-scatter"
   aria-label={`Scatter plot of ${data.y.label} against ${data.x.label}. Left and Right step through nights in date order.`}
   onPointerMove={move} onPointerLeave={()=>setFocus(null)} onFocus={()=>{if(!focus&&points.length)setFocus(points[points.length-1].date);}} onBlur={()=>setFocus(null)} onKeyDown={key}>
   <defs><linearGradient id="cx-fit" x1="0" x2="1"><stop offset="0" stopColor="#7fd3ff"/><stop offset="1" stopColor="#ffc45a"/></linearGradient>
    <clipPath id="cx-clip"><rect x={M.l} y={M.t} width={iw} height={ih}/></clipPath></defs>
   {ay.ticks.map(v=><g key={`y${v}`}><line className="cx-grid" x1={M.l} x2={width-M.r} y1={sy(v)} y2={sy(v)}/><text className="cx-tick" x={M.l-10} y={sy(v)+3.5} textAnchor="end">{v.toFixed(ay.decimals)}</text></g>)}
   {ax.ticks.map(v=><g key={`x${v}`}><line className="cx-grid cx-grid-v" x1={sx(v)} x2={sx(v)} y1={M.t} y2={M.t+ih}/><text className="cx-tick" x={sx(v)} y={M.t+ih+18} textAnchor="middle">{v.toFixed(ax.decimals)}</text></g>)}
   <g clipPath="url(#cx-clip)"><path className="cx-fit-glow" style={{d:line||undefined,opacity:fit&&line?.1:0}}/><path className="cx-fit" data-fit={fit&&line?"on":"off"} style={{d:line||undefined,opacity:fit&&line?1:0}}/></g>
   {hot&&<g className="cx-cross"><line x1={M.l} x2={hot.cx} y1={hot.cy} y2={hot.cy}/><line x1={hot.cx} x2={hot.cx} y1={hot.cy} y2={M.t+ih}/></g>}
   <g>{points.map(p=><circle key={p.date} className="cx-pt" data-date={p.date} style={{cx:`${p.cx}px`,cy:`${p.cy}px`,fill:ageColour(p.date,colourFrom,colourTo)}}/>)}</g>
   {hot&&<circle className="cx-ring" r="8" style={{transform:`translate(${hot.cx}px,${hot.cy}px)`}}/>}
   <text className="cx-axis-title cx-x-title" x={M.l+iw/2} y={height-6} textAnchor="middle">{data.x.label} ({data.x.unit})</text>
   <text className="cx-axis-title cx-y-title" transform={`translate(12 ${M.t+ih/2}) rotate(-90)`} textAnchor="middle">{data.y.label} ({data.y.unit})</text>
  </svg>
  <div className={`cx-tip${hot?" on":""}`} role="status" aria-live="polite" style={{transform:`translate(${tipLeft}px,${tipTop}px)`}}>
   {hot&&<><b><time dateTime={hot.date}>{fullDay(hot.date)}</time></b><div><span><i className="cx-dot cx-dot-x"/>{data.x.label}</span><span>{pairText(data.x,hot.x)}</span></div><div><span><i className="cx-dot cx-dot-y"/>{data.y.label}</span><span>{pairText(data.y,hot.y)}</span></div></>}
  </div>
  {!points.length&&<p className="cx-empty" role="status">No nights in this range have both readings.</p>}
 </div>;
}

const S={l:12,r:12,t:10,b:142,h:170};
function Strip({series,x,y,width,paired,focus,setFocus,brush,onBrush}:{series:ChartData;x:string;y:string;width:number;paired:Set<string>;focus:string|null;setFocus:(d:string|null)=>void;brush:Brush;onBrush:(b:Brush)=>void}){
 const dates=series.dates,n=dates.length,svg=useRef<SVGSVGElement>(null);
 const [drag,setDrag]=useState<[number,number]|null>(null),[hover,setHover]=useState<number|null>(null);
 const xs=(i:number)=>S.l+i/Math.max(1,n-1)*(width-S.l-S.r);
 const lines=[x,y].map(id=>{const raw=series.series.find(s=>s.id===id)?.raw??[],vals=raw.filter((v):v is number=>v!==null),lo=Math.min(...vals),hi=Math.max(...vals);
  const yAt=(v:number)=>S.b-6-(v-lo)/((hi-lo)||1)*(S.b-S.t-12);
  return {id,yAt:(i:number)=>raw[i]==null?null:yAt(raw[i]!),d:curveRuns(raw.map((v,i):Pt|null=>v===null?null:[xs(i),yAt(v)])).map(r=>r.points.length===1?`M${(r.points[0][0]-2).toFixed(1)},${r.points[0][1].toFixed(1)}L${(r.points[0][0]+2).toFixed(1)},${r.points[0][1].toFixed(1)}`:runPath(r)).join("")};});
 const index=(clientX:number)=>{const b=svg.current?.getBoundingClientRect();if(!b||!n)return 0;return Math.max(0,Math.min(n-1,Math.round(((clientX-b.left)/b.width*width-S.l)/(width-S.l-S.r)*(n-1))));};
 const shown=drag?[Math.min(...drag),Math.max(...drag)]:brush?[dates.indexOf(brush[0]),dates.indexOf(brush[1])]:null;
 const at=focus&&dates.includes(focus)?dates.indexOf(focus):hover;
 return <div className="cx-strip-wrap">
  <svg ref={svg} className="cx-strip" width="100%" height={S.h} viewBox={`0 0 ${width} ${S.h}`} role="img" aria-label={`${series.series.map(s=>s.label).join(" and ")} over ${n} days; drag to narrow the nights used`}
   onPointerDown={e=>{svg.current?.setPointerCapture?.(e.pointerId);const i=index(e.clientX);setDrag([i,i]);}}
   onPointerMove={e=>{const i=index(e.clientX);if(drag){setDrag([drag[0],i]);return;}setHover(i);setFocus(paired.has(dates[i])?dates[i]:null);}}
   onPointerUp={()=>{if(!drag)return;const a=Math.min(...drag),b=Math.max(...drag);setDrag(null);if(b-a>=5)onBrush([dates[a],dates[b]]);}}
   onPointerLeave={()=>{if(!drag){setHover(null);setFocus(null);}}} onDoubleClick={()=>onBrush(null)}>
   {[S.t+4,(S.t+S.b)/2,S.b].map(v=><line key={v} className="cx-grid" x1={S.l} x2={width-S.r} y1={v} y2={v}/>)}
   {lines.map((l,k)=><path key={l.id} className={`cx-series cx-series-${k?"y":"x"}`} data-metric={l.id} d={l.d}/>)}
   {shown&&shown[0]>=0&&<rect className="cx-brush" x={xs(shown[0])} y="6" width={Math.max(2,xs(shown[1])-xs(shown[0]))} height="136" rx="6"/>}
   {at!==null&&<><line className="cx-hover" x1={xs(at)} x2={xs(at)} y1="6" y2="142"/>{lines.map((l,k)=>{const v=l.yAt(at);return v===null?null:<circle key={l.id} className={`cx-hover-dot cx-dot-${k?"y":"x"}`} cx={xs(at)} cy={v} r="4"/>;})}</>}
   {n>0&&([[0,"start"],[Math.floor((n-1)/2),"middle"],[n-1,"end"]] as [number,"start"|"middle"|"end"][]).map(([i,a])=><text key={a} className="cx-tick" x={a==="start"?S.l:a==="end"?width-S.r:xs(i)} y="164" textAnchor={a}>{fullDay(dates[i])}</text>)}
  </svg>
  {drag&&<div className="cx-drag-label" style={{left:xs((drag[0]+drag[1])/2)}}>{shortDay(dates[Math.min(...drag)])} – {shortDay(dates[Math.max(...drag)])} · {Math.abs(drag[1]-drag[0])+1} days</div>}
 </div>;
}

function PairGrid({grid,x,y,onPick}:{grid:CorrelationGrid;x:string;y:string;onPick:(a:string,b:string)=>void}){
 const ms=grid.metrics,cells=new Map(grid.cells.map(c=>[`${c.x}|${c.y}`,c])),[hot,setHot]=useState<[number,number]|null>(null);
 const label=(id:string)=>SHORT_LABEL[id]??ms.find(m=>m.id===id)?.label??id;
 const info=hot&&(()=>{const [r,c]=hot,a=ms[c],b=ms[r],cell=cells.get(`${a.id}|${b.id}`);return cell?`${b.label} and ${a.label} · ${cell.r===null?`not calculated (${cell.reason?.replace(/^Unavailable: /,"")})`:`r ${rText(cell.r)}`} · ${cell.n} paired nights`:"";})();
 return <><div className="cx-grid-scroll"><div className="cx-matrix" style={{gridTemplateColumns:`104px repeat(${ms.length-1},minmax(52px,1fr))`}} onMouseLeave={()=>setHot(null)}>
  <div/>{ms.slice(0,-1).map((m,c)=><div key={m.id} className={`cx-ml cx-col${hot?.[1]===c?" hl":""}`}>{label(m.id)}</div>)}
  {ms.slice(1).map((row,ri)=>{const r=ri+1;return [<div key={`l${row.id}`} className={`cx-ml${hot?.[0]===r?" hl":""}`}>{label(row.id)}</div>,
   ...ms.slice(0,-1).map((col,c)=>{if(c>=r)return <div key={`${row.id}-${col.id}`}/>;const cell=cells.get(`${col.id}|${row.id}`);
    const name=`${row.label} and ${col.label}`;
    if(!cell||cell.r===null)return <button key={col.id} type="button" className="cx-cell na" disabled aria-label={`${name}: not calculated`} onMouseEnter={()=>setHot([r,c])}>—</button>;
    const k=Math.abs(cell.r),rgb=cell.r<0?"127,211,255":"255,196,90",sel=(x===col.id&&y===row.id)||(x===row.id&&y===col.id);
    return <button key={col.id} type="button" className={`cx-cell${sel?" sel":""}${k<.3?" weak":""}`} data-x={col.id} data-y={row.id} style={{background:`rgba(${rgb},${(.05+k*.5).toFixed(3)})`}}
     aria-label={`${name}, r ${rText(cell.r)}, ${cell.n} paired nights`} aria-pressed={sel} onMouseEnter={()=>setHot([r,c])} onFocus={()=>setHot([r,c])} onClick={()=>onPick(col.id,row.id)}>{rText(cell.r)}</button>;})];})}
 </div></div>
 <div className="cx-grid-foot"><span className="cx-cell-info" aria-live="polite">{info||"Hover a cell for its pair and paired nights."}</span><span className="cx-ramp">moves opposite <i/> moves together</span></div></>;
}

export function Correlations(){
 const [catalog,setCatalog]=useState<Metric[]>([]),[x,setX]=useState("hr_mean"),[y,setY]=useState("hrv_mean");
 const [range,setRange]=useState<Range>("90"),[start,setStart]=useState(""),[end,setEnd]=useState(""),[brush,setBrush]=useState<Brush>(null);
 const [error,setError]=useState(""),[retry,setRetry]=useState(0),[focus,setFocus]=useState<string|null>(null),[fit,setFit]=useState(true),[turn,setTurn]=useState(0);
 const [plotRef,plotWidth]=useWidth<HTMLDivElement>(),[stripRef,stripWidth]=useWidth<HTMLDivElement>(),viewport=useViewportHeight();
 const [sideRef,sideHeight]=useHeight<HTMLDivElement>(),[headRef,headHeight]=useHeight<HTMLDivElement>(),[footRef,footHeight]=useHeight<HTMLDivElement>();
 useEffect(()=>{const c=new AbortController();setError("");chartRequest<Metric[]>("metrics/catalog","GET",undefined,c.signal).then(m=>{if(!c.signal.aborted)setCatalog(m.filter(v=>!v.clock));}).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[retry]);
 const invalid=range==="custom"&&(!start||!end||start>end),ready=catalog.length>0&&!invalid;
 const base:Win={range,start:range==="custom"?start:null,end:range==="custom"?end:null};
 const narrowed:Win=brush?{range:"custom",start:brush[0],end:brush[1]}:base;
 const fail=(m:string)=>setError(m);
 const [pair,pairBusy]=useRequest<Correlation>("analytics/correlation",{x,y,...narrowed},ready,retry,fail);
 const [grid,gridBusy]=useRequest<CorrelationGrid>("analytics/correlation/matrix",narrowed,ready,retry,fail);
 const [strip,stripBusy]=useRequest<ChartData>("analytics/timeseries",{metrics:[x,y],...base,mode:"actual",rolling:"off"},ready,retry,fail);
 useEffect(()=>{setError("");},[x,y,range,start,end,brush]);
 const r=useTween(pair?.r??null),busy=pairBusy||gridBusy||stripBusy;
 const pick=(axis:"x"|"y",id:string)=>{(axis==="x"?setX:setY)(id);setFocus(null);};
 const choose=(next:Range)=>{setRange(next);setBrush(null);};
 const paired=new Set(pair?.pairs.map(p=>p.date));
 const colourFrom=strip?.start??pair?.start??"",colourTo=strip?.end??pair?.end??"";
 const pos=pair?.r==null?50:(pair.r+1)/2*100;
 // Side by side (wide screens), the plot also fills the height of the readout column so the card has no dead space;
 // 62 px = card padding (40) + plot margin (10) + foot padding (10) + borders. Never taller than one screen allows.
 const sideBySide=typeof window!=="undefined"&&window.innerWidth>1180;
 const height=Math.round(Math.min(Math.max(scatterHeight(plotWidth,viewport),sideBySide&&sideHeight?sideHeight-headHeight-footHeight-62:0),Math.max(scatterHeight(plotWidth,viewport),viewport-260)));
 return <div className="cx">
  <div className="cx-top"><Segmented value={range} onChange={choose}/>
   {range==="custom"&&<div className="cx-custom"><label>From<input type="date" value={start} onChange={e=>{setStart(e.target.value);setBrush(null);}}/></label><label>To<input type="date" value={end} onChange={e=>{setEnd(e.target.value);setBrush(null);}}/></label></div>}
   <span className={`cx-narrow${brush?" on":""}`} aria-hidden={!brush}>{brush&&<>Narrowed to {shortDay(brush[0])} – {shortDay(brush[1])}<button type="button" aria-label="Use the whole range again" onClick={()=>setBrush(null)}>×</button></>}</span>
   <span className="cx-status" role="status">{busy?"Calculating paired correlation…":""}</span></div>
  {(pair?.synthetic||strip?.synthetic)&&<p className="preview-banner">Synthetic preview — generated test data, not your health records.</p>}
  {invalid&&<div className="cx-card" role="alert">Choose a valid start and end date.</div>}
  {error&&<div className="cx-card" role="alert">{error} <button type="button" className="cx-btn" onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
  {catalog.length>0&&<section className="cx-card cx-pair" aria-label="Choose the pair">
   <div className="cx-rows"><ChipRow axis="y" catalog={catalog} value={y} other={x} onPick={id=>pick("y",id)}/><ChipRow axis="x" catalog={catalog} value={x} other={y} onPick={id=>pick("x",id)}/></div>
   <button type="button" className="cx-swap" aria-label="Swap the X and Y measurements" title="Swap axes" onClick={()=>{setX(y);setY(x);setTurn(t=>t+180);setFocus(null);}}>
    <svg viewBox="0 0 20 20" style={{transform:`rotate(${turn}deg)`}} aria-hidden="true"><path d="M6 3v13M6 3 3 6M6 3l3 3M14 17V4M14 17l-3-3M14 17l3-3"/></svg></button>
  </section>}
  <div className="cx-main" aria-busy={busy}>
   <section className="cx-card cx-scatter-card" aria-labelledby="cx-title">
    <div ref={headRef}><div className="cx-label">Paired nights</div><h2 id="cx-title">{pair?`${pair.y.label} against ${pair.x.label}`:"Loading…"}</h2>
    <div className="cx-sub">{pair?.start&&pair.end?<><time dateTime={pair.start}>{fullDay(pair.start)}</time> – <time dateTime={pair.end}>{fullDay(pair.end)}</time> · {pair.days} days</>:" "}</div></div>
    <div ref={plotRef} className="cx-plot-box">{pair&&plotWidth>0&&<Scatter data={pair} width={plotWidth} height={height} colourFrom={colourFrom} colourTo={colourTo} fit={fit} focus={focus} setFocus={setFocus}/>}</div>
    <div className="cx-foot" ref={footRef}><label className="cx-switch"><input type="checkbox" checked={fit} onChange={e=>setFit(e.target.checked)}/><span aria-hidden="true"/>Best-fit line</label>
     <span className="cx-age">older <i/> newer</span><span>Hover, or focus the plot and use ← →</span></div>
   </section>
   <div className="cx-side" ref={sideRef}>
    <section className="cx-card" aria-labelledby="cx-r-label">
     <div className="cx-label" id="cx-r-label">Pearson r</div>
     <div className={`cx-r${pair?.r==null?" na":""}`} data-r={pair?.r??""}>{pair?pair.r===null?"Unavailable":rText(r):"—"}</div>
     <p className="cx-r-caption">{pair?(pair.r===null?pair.reason:`From ${pair.n} paired night${pair.n===1?"":"s"}`):" "}</p>
     <div className="cx-meter" aria-hidden="true"><div className="cx-track"/><div className="cx-fill" style={{left:`${Math.min(50,pos)}%`,width:`${Math.abs(pos-50)}%`,background:(pair?.r??0)<0?"var(--cx-ice)":"var(--cx-gold)"}}/>
      <div className="cx-knob" style={{left:`${pos}%`,opacity:pair?.r==null?.25:1}}/>
      <div className="cx-scale"><span>−1</span><span>−0.5</span><span>0</span><span>+0.5</span><span>+1</span></div></div>
    </section>
    <section className="cx-card" aria-labelledby="cx-counts">
     <div className="cx-label" id="cx-counts">Nights used</div>
     <dl className="cx-counts"><div><dt>Paired nights</dt><dd>{pair?.n??0}</dd></div><div><dt>{pair?.x.label??"X"} missing</dt><dd>{pair?.excluded.missing_x??0}</dd></div>
      <div><dt>{pair?.y.label??"Y"} missing</dt><dd>{pair?.excluded.missing_y??0}</dd></div><div><dt>Both missing</dt><dd>{pair?.excluded.neither??0}</dd></div></dl>
     <p className="cx-caveat"><b>Exploratory only.</b> r shows how closely two measurements move together in a straight line. It is not a significance test or evidence of cause, and it is unstable with few nights. Nights missing either reading are left out, never filled in.</p>
     {pair&&pair.pairs.length>0&&<details className="cx-table"><summary>Paired nights as a table</summary><div className="chart-table"><table><thead><tr><th>Wake date</th><th>{pair.x.label}</th><th>{pair.y.label}</th></tr></thead>
      <tbody>{pair.pairs.map(p=><tr key={p.date}><td>{p.date}</td><td>{pairText(pair.x,p.x)}</td><td>{pairText(pair.y,p.y)}</td></tr>)}</tbody></table></div></details>}
    </section>
   </div>
  </div>
  <section className="cx-card" aria-labelledby="cx-time">
   <div className="cx-head"><div><div className="cx-label">Over time</div><h2 id="cx-time">Both measurements, night by night</h2><div className="cx-sub">Each line is scaled to its own range so their shapes can be compared</div></div>
    <div className="cx-legend"><span><i className="cx-key-x"/>{catalog.find(m=>m.id===x)?.label}</span><span><i className="cx-key-y"/>{catalog.find(m=>m.id===y)?.label}</span><span className="cx-dim">Drag to focus on a stretch · double-click to reset</span></div></div>
   <div ref={stripRef} className="cx-strip-box">{strip&&stripWidth>0&&strip.dates.length>0&&<Strip series={strip} x={x} y={y} width={stripWidth} paired={paired} focus={focus} setFocus={setFocus} brush={brush} onBrush={b=>{setBrush(b);setFocus(null);}}/>}</div>
  </section>
  <section className="cx-card" aria-labelledby="cx-every">
   <div className="cx-label">Every pair</div><h2 id="cx-every">All measurements at a glance</h2><div className="cx-sub">r for each pair over the same nights · select a cell to explore it</div>
   {grid&&<PairGrid grid={grid} x={x} y={y} onPick={(a,b)=>{setX(a);setY(b);setFocus(null);}}/>}
  </section>
  <p className="cx-note">Sleep onset and wake time are not offered: clock times wrap around midnight, so a straight-line correlation would mislead. {pair?.method}.</p>
 </div>;
}
