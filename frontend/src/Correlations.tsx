import {useEffect,useState} from "react";
import {chartRequest,formatValue,scatterLayout} from "./charts";
import type {Correlation,Metric,Range} from "./charts";

// Python pairs nights and computes Pearson r; this view only positions and labels the results.
export function Correlations(){
 const [catalog,setCatalog]=useState<Metric[]>([]),[x,setX]=useState("hr_mean"),[y,setY]=useState("hrv_mean");
 const [range,setRange]=useState<Range>("90"),[start,setStart]=useState(""),[end,setEnd]=useState("");
 const [data,setData]=useState<Correlation|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[focus,setFocus]=useState(""),[retry,setRetry]=useState(0);
 useEffect(()=>{const c=new AbortController();setError("");chartRequest<Metric[]>("metrics/catalog","GET",undefined,c.signal).then(m=>{if(!c.signal.aborted)setCatalog(m.filter(v=>!v.clock));}).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[retry]);
 useEffect(()=>{if(!catalog.length)return;const c=new AbortController();setError("");setFocus("");setBusy(false);
  // The previous result stays mounted (dimmed) while loading so the page height, and scroll position, hold steady.
  if(x===y){setData(null);setError("Choose two different metrics.");return;}
  if(range==="custom"&&(!start||!end||start>end)){setData(null);setError("Choose a valid start and end date.");return;}
  setBusy(true);
  chartRequest<Correlation>("analytics/correlation","POST",{x,y,range,start:range==="custom"?start:null,end:range==="custom"?end:null},c.signal).then(d=>{if(!c.signal.aborted)setData(d);}).catch(e=>{if(!c.signal.aborted){setData(null);setError(e.message);}}).finally(()=>{if(!c.signal.aborted)setBusy(false);});
  return()=>c.abort();},[catalog,x,y,range,start,end]);
 const layout=data?scatterLayout(data.pairs):null;
 const picker=(label:string,value:string,set:(v:string)=>void)=><label>{label}<select aria-label={`${label} metric`} value={value} onChange={e=>set(e.target.value)}>{catalog.map(m=><option key={m.id} value={m.id}>{m.label} ({m.unit})</option>)}</select></label>;
 return <div className="analytics correlations">
  <section className="panel"><div className="panel-title"><h2>Correlation explorer</h2><span className="pill">PAIRED NIGHTS</span></div>
   {data?.synthetic&&<p className="preview-banner">Synthetic preview — generated test data, not your health records.</p>}
   <p className="muted">Compare two nightly metrics across nights where both were recorded. Calculated locally; no AI involved.</p>
   <div className="chart-toolbar">{picker("X axis",x,setX)}{picker("Y axis",y,setY)}
    <label>Range<select aria-label="Date range" value={range} onChange={e=>setRange(e.target.value as Range)}>{(["7","30","90","all","custom"] as Range[]).map(r=><option key={r} value={r}>{r==="all"?"All history":r==="custom"?"Custom":`${r} days`}</option>)}</select></label>
    {range==="custom"&&<><label>From<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>To<input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label></>}<span className="load-status" role="status">{busy?"Calculating paired correlation…":""}</span></div>
   <p className="muted">Sleep onset and wake time are excluded: clock times wrap around midnight, so a straight-line correlation would mislead.</p></section>
  {error&&<div className="panel" role="alert">{error} <button onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
  {data&&layout&&<section className="panel" aria-busy={busy}>
   <div className="correlation-summary"><div><p className="eyebrow">PEARSON r</p><strong className="correlation-r">{data.r===null?"Unavailable":data.r.toFixed(2)}</strong>{data.reason&&<p role="status" className="muted">{data.reason}</p>}</div>
    <dl><div><dt>Paired nights (n)</dt><dd>{data.n}</dd></div><div><dt>Missing {data.x.label}</dt><dd>{data.excluded.missing_x}</dd></div><div><dt>Missing {data.y.label}</dt><dd>{data.excluded.missing_y}</dd></div><div><dt>Neither recorded</dt><dd>{data.excluded.neither}</dd></div></dl></div>
   <p className="muted">{data.start??"—"} — {data.end??"—"} · {data.days} calendar days. {data.method}. Nights missing either reading are excluded, never filled in. With few paired nights r is unstable; treat it as a prompt to look closer, not a finding.</p>
   {data.pairs.length?<><div className="chart-plot"><svg viewBox="0 0 640 340" role="group" aria-label={`Scatter plot of ${data.y.label} against ${data.x.label}`}>
    {[0,.5,1].map(f=><g key={f}><line x1="60" x2="620" y1={290-f*260} y2={290-f*260} className="gridline"/><text x="54" y={294-f*260} textAnchor="end">{(layout.y[0]+(layout.y[1]-layout.y[0])*f).toFixed(1)}</text><text x={60+f*560} y="308" textAnchor="middle">{(layout.x[0]+(layout.x[1]-layout.x[0])*f).toFixed(1)}</text></g>)}
    <text x="340" y="334" textAnchor="middle">{data.x.label} ({data.x.unit})</text><text x="12" y="160" textAnchor="middle" transform="rotate(-90 12 160)">{data.y.label} ({data.y.unit})</text>
    {layout.points.map(p=>{const detail=`${p.date} · ${data.x.label} ${formatValue(p.x,data.x)} · ${data.y.label} ${formatValue(p.y,data.y)}`;return <circle key={p.date} className="scatter-point" tabIndex={0} role="img" aria-label={detail} cx={p.cx} cy={p.cy} r="5" onFocus={()=>setFocus(detail)} onMouseEnter={()=>setFocus(detail)}><title>{detail}</title></circle>;})}
   </svg></div>
   <p className="chart-detail" aria-live="polite">{focus||"Hover or focus a point for its wake date and both values."}</p>
   <details><summary>Accessible paired data table</summary><div className="chart-table"><table><thead><tr><th>Wake date</th><th>{data.x.label}</th><th>{data.y.label}</th></tr></thead><tbody>{data.pairs.map(p=><tr key={p.date}><td>{p.date}</td><td>{formatValue(p.x,data.x)}</td><td>{formatValue(p.y,data.y)}</td></tr>)}</tbody></table></div></details></>
   :<p role="status">No nights in this range have both readings.</p>}
  </section>}
 </div>;
}
