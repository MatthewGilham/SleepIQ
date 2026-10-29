import {useEffect,useRef,useState} from "react";

import {chartRequest,chartSegments,formatValue,initialSelection,rollingNote,sliceSeries,withDefaults} from "./charts";

import {Investigator} from "./Investigator";
import type {ChartData,Metric,Preset,Selection,Series} from "./charts";

const inks=["#ff8c80","#8bd7ee","#edcb72","#b2d591","#c1aff0","#e7b5a6"];

function Plot({items,dates,normalized,label}:{items:Series[];dates:string[];normalized:boolean;label:string}){

 const [focus,setFocus]=useState<string>("");

 const observed=items.flatMap(s=>s.values.filter((v):v is number=>v!==null));

 // Rolling windows can reach before the range, so their means share the axis with the points.
 const all=[...observed,...items.flatMap(s=>(s.rolling?.values??[]).filter((v):v is number=>v!==null))];

 const show=(s:Series,v:number)=>normalized?`${v.toFixed(3)} z`:formatValue(v,s);

 const clock=items.some(s=>s.clock);const min=clock?0:Math.min(...all);const max=clock?1440:Math.max(...all);

 const low=all.length?(min===max?min-1:min):0,high=all.length?(min===max?max+1:max):1;

 return <div className="chart-plot"><svg viewBox="0 0 930 215" role="group" aria-label={label}>

 {[0,.5,1].map(f=><g key={f}><line x1="48" x2="888" y1={170-f*140} y2={170-f*140} className="gridline"/><text x="2" y={174-f*140}>{clock?`${Math.round((low+(high-low)*f)/60)}h`:(low+(high-low)*f).toFixed(1)}</text></g>)}

 {items.map((s,j)=><g key={s.id}>{chartSegments(s.values,low,high).map((d,i)=><path key={i} d={d} fill="none" stroke={inks[j%inks.length]} strokeWidth="2"/>)}{s.rolling?.values&&chartSegments(s.rolling.values,low,high).map((d,i)=><path key={`rolling-${i}`} d={d} fill="none" stroke={inks[j%inks.length]} strokeWidth="2.5" strokeDasharray="7 5" opacity="0.75" className="rolling-line"/>)}{s.values.map((v,i)=>{if(v===null)return null;const detail=`${dates[i]} · ${s.label}: ${normalized?`${v.toFixed(3)} z; original ${formatValue(s.raw[i],s)}`:formatValue(v,s)} · ${s.method}${s.details[i].n!==null?`; n=${s.details[i].n}`:""}${s.clock?`; UTC offset ${s.details[i].offset_minutes} minutes`:""}${s.details[i].flags.length?`; flags: ${s.details[i].flags.join(", ")}`:""}${s.rolling?`; ${rollingNote(s.rolling,i,r=>show(s,r))}`:""}`;return <circle key={i} tabIndex={0} role="img" aria-label={detail} cx={48+i/Math.max(1,dates.length-1)*840} cy={170-(v-low)/(high-low||1)*140} r="4" fill={inks[j%inks.length]} onFocus={()=>setFocus(detail)} onMouseEnter={()=>setFocus(detail)}><title>{detail}</title></circle>;})}</g>)}

 <text x="48" y="205">{dates[0]}</text><text x="888" y="205" textAnchor="end">{dates.at(-1)}</text></svg>

 <p className="chart-detail" aria-live="polite">{focus||"Hover or focus a point for its date, value and method. Missing nights break the line."}</p>

 {!observed.length&&<p role="status">{normalized?"Normalization unavailable: no variation or no observations.":"No readings in this range."}</p>}

 </div>;

}

export function Analytics(){

 const [catalog,setCatalog]=useState<Metric[]>([]),[presets,setPresets]=useState<Preset[]>([]);

 const [selection,setSelection]=useState<Selection>(initialSelection),[data,setData]=useState<(ChartData&{mode:Selection["mode"]})|null>(null);

 const [error,setError]=useState(""),[busy,setBusy]=useState(false),[ready,setReady]=useState(false),[retry,setRetry]=useState(0);

 const [name,setName]=useState(""),[current,setCurrent]=useState(""),[isDefault,setDefault]=useState(false),[saving,setSaving]=useState(false),[notice,setNotice]=useState("");

 const [confirmation,setConfirmation]=useState<"save"|"delete"|null>(null),[hidden,setHidden]=useState<string[]>([]),[zoom,setZoom]=useState<[number,number]|null>(null);

 const generation=useRef(0);

 useEffect(()=>{const c=new AbortController();setReady(false);setError("");Promise.all([chartRequest<Metric[]>("metrics/catalog","GET",undefined,c.signal),chartRequest<Preset[]>("presets","GET",undefined,c.signal)]).then(([metrics,saved])=>{if(c.signal.aborted)return;setCatalog(metrics);setPresets(saved);const def=saved.find(p=>p.default);if(def){setSelection(withDefaults(def));setCurrent(def.id);setName(def.name);setDefault(true);}setReady(true);}).catch(e=>{if(!c.signal.aborted)setError(String(e.message));});return()=>c.abort();},[retry]);

 useEffect(()=>{if(!ready)return;const c=new AbortController();setZoom(null);setHidden([]);setError("");if(!selection.metrics.length){setData(null);setBusy(false);return;}if(selection.range==="custom"&&(!selection.start||!selection.end||selection.start>selection.end)){setData(null);setError("Choose a valid start and end date.");setBusy(false);return;}setBusy(true);

 const {metrics,range,start,end,mode,rolling}=selection;

 chartRequest<ChartData>("analytics/timeseries","POST",{metrics,range,start,end,mode,rolling},c.signal).then(d=>{if(!c.signal.aborted)setData({...d,mode});}).catch(e=>{if(!c.signal.aborted){setData(null);setError(e.message);}}).finally(()=>{if(!c.signal.aborted)setBusy(false);});return()=>c.abort();},[selection,ready]);

 function update(patch:Partial<Selection>){setSelection(s=>({...s,...patch}));setNotice("");}

 async function persist(action:"new"|"save"|"delete"){

  setSaving(true);setError("");setConfirmation(null);const request=++generation.current;

  try{const existing=presets.find(p=>p.id===current);if(action!=="new"&&!existing)throw new Error("Choose an existing preset first.");

   if(action==="delete"){await chartRequest(`presets/${current}?revision=${existing!.revision}`,"DELETE");setCurrent("");setName("");setDefault(false);}

   else {const {metrics,range,start,end,mode,rolling}=selection;const saved=await chartRequest<Preset>(`presets/${action==="new"?"new":current}`,"PUT",{metrics,range,start,end,mode,rolling,name,default:isDefault,revision:action==="new"?0:existing!.revision});setCurrent(saved.id);setName(saved.name);}

   setPresets(await chartRequest<Preset[]>("presets"));setNotice(action==="delete"?"Preset deleted.":"Preset saved.");

  }catch(e){setError((e as Error).message);}finally{if(request===generation.current)setSaving(false);}

 }

 function load(id:string){const p=presets.find(v=>v.id===id);setCurrent(id);setName(p?.name??"");setDefault(p?.default??false);if(p)setSelection(withDefaults(p));setNotice("");}

 const visible=data?.series.filter(s=>!hidden.includes(s.id))??[];

 const dates=data?.dates.slice(zoom?.[0]??0,(zoom?.[1]??((data?.dates.length??1)-1))+1)??[];

 const sliced=visible.map(s=>sliceSeries(s,zoom?.[0]??0,zoom?.[1]??(data!.dates.length-1)));

 // Previous charts stay visible (dimmed) while loading, so they render with the mode they were fetched in.

 const shown=data?.mode??selection.mode;

 // Actual-unit overlays are grouped by unit: different dimensions never share an axis.

 const groups:Series[][]=shown==="normalized"?[sliced]:Object.values(sliced.reduce<Record<string,Series[]>>((out,s)=>{(out[s.unit]??=[]).push(s);return out;},{}));

 return <div className="analytics"><section className="panel chart-controls"><div className="panel-title"><h2>Explore your nights</h2><span className="pill">LOCAL ANALYTICS</span></div>{data?.synthetic&&<p className="preview-banner">Synthetic preview — generated test data, not your health records.</p>}<p className="muted">Stored nightly measurements. Relative ranges end on the latest recorded wake date. Explore measurements and save your chart selections.</p>

 <div className="chart-toolbar"><label>Range<select aria-label="Date range" value={selection.range} onChange={e=>update({range:e.target.value as Selection["range"]})}>{["7","30","90","all","custom"].map(r=><option key={r} value={r}>{r==="all"?"All history":r==="custom"?"Custom":`${r} days`}</option>)}</select></label><label>Display<select aria-label="Display" value={selection.mode} onChange={e=>update({mode:e.target.value as Selection["mode"],metrics:e.target.value==="normalized"?selection.metrics.filter(id=>!catalog.find(m=>m.id===id)?.clock):selection.metrics})}><option value="actual">Actual units</option><option value="normalized">Normalized trend</option></select></label><label>Rolling average<select aria-label="Rolling average" value={selection.rolling} onChange={e=>update({rolling:e.target.value as Selection["rolling"]})}><option value="off">Off</option><option value="7">7-day</option><option value="30">30-day</option></select></label>

 {selection.range==="custom"&&<><label>From<input type="date" value={selection.start??""} onChange={e=>update({start:e.target.value})}/></label><label>To<input type="date" value={selection.end??""} onChange={e=>update({end:e.target.value})}/></label></>}<span className="load-status" role="status">{busy?"Loading nightly measurements…":""}</span></div>

 <fieldset className="metric-picker"><legend>Metrics</legend>{catalog.map(m=><label key={m.id}><input type="checkbox" checked={selection.metrics.includes(m.id)} disabled={selection.mode==="normalized"&&m.clock} onChange={e=>update({metrics:e.target.checked?[...selection.metrics,m.id]:selection.metrics.filter(id=>id!==m.id)})}/>{m.label}{m.clock&&selection.mode==="normalized"?" (actual only)":""}</label>)}</fieldset>

 <p className="muted">{selection.mode==="normalized"?"Z-score = (value − mean) / population standard deviation over the selected range. Constant series are unavailable; clock times are excluded.":"Different units use separate aligned chart panels. Clock times use source-local wall time; midnight crossings are not elapsed durations."}</p>{selection.rolling!=="off"&&<p className="muted">Dashed line: trailing {selection.rolling}-day calendar mean, shown only when at least {selection.rolling==="7"?4:15} of those {selection.rolling} nights were recorded. Missing nights are skipped, never counted as zero; early windows may include recorded nights before the range starts. Not available for clock times.</p>}</section>

 <section className="panel preset-panel"><h2>Saved chart presets</h2><div className="chart-toolbar"><label>Load preset<select value={current} onChange={e=>load(e.target.value)}><option value="">New preset</option>{presets.map(p=><option key={p.id} value={p.id}>{p.name}{p.default?" · Default":""}</option>)}</select></label><label>Preset name<input maxLength={60} value={name} onChange={e=>setName(e.target.value)}/></label><label><input type="checkbox" checked={isDefault} onChange={e=>setDefault(e.target.checked)}/>Default on opening Analytics</label></div><div className="chart-actions"><button disabled={!ready||saving||!name.trim()||!selection.metrics.length} onClick={()=>void persist("new")}>Save as new</button><button disabled={!current||saving||!name.trim()} onClick={()=>setConfirmation("save")}>Update selected</button><button disabled={!current||saving} onClick={()=>setConfirmation("delete")}>Delete selected</button><button disabled={saving} onClick={()=>{setCurrent("");setRetry(n=>n+1);}}>Reload presets</button></div>

 {confirmation&&<div className="confirm-preset" role="alert"><p>{confirmation==="delete"?"Delete this saved preset? This cannot be undone.":"Replace this preset’s name, settings and default choice?"}</p><button onClick={()=>void persist(confirmation)}>Confirm {confirmation==="delete"?"delete":"update"}</button><button onClick={()=>setConfirmation(null)}>Cancel</button></div>}

 {notice&&<p role="status">{notice}</p>}</section>

 {error&&<div className="panel" role="alert">{error} <button onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}

 {ready&&!selection.metrics.length&&<p role="status">Choose at least one metric.</p>}

 {data&&!data.dates.length&&<section className="panel"><h2>No recorded nights yet</h2><p>Charts will appear after a successful import. Missing data is never filled in.</p></section>}

 {data&&data.dates.length>0&&<div className="chart-results" aria-busy={busy}><section className="panel"><div className="panel-title"><h2>Multi-metric exploration</h2><span className="muted">{data.start} — {data.end}</span></div><div className="chart-actions">{data.series.map(s=><button key={s.id} aria-pressed={!hidden.includes(s.id)} onClick={()=>setHidden(h=>h.includes(s.id)?h.filter(v=>v!==s.id):[...h,s.id])}>{s.label}</button>)}</div>

 <div className="chart-toolbar"><label>Zoom start<input type="range" aria-label="Zoom start" min={0} max={Math.max(0,data.dates.length-1)} value={zoom?.[0]??0} onChange={e=>setZoom([Math.min(Number(e.target.value),zoom?.[1]??data.dates.length-1),zoom?.[1]??data.dates.length-1])}/></label><label>Zoom end<input type="range" aria-label="Zoom end" min={0} max={Math.max(0,data.dates.length-1)} value={zoom?.[1]??data.dates.length-1} onChange={e=>setZoom([zoom?.[0]??0,Math.max(Number(e.target.value),zoom?.[0]??0)])}/></label><button onClick={()=>setZoom(null)}>Reset zoom</button><span className="muted">Zoom preserves the selected range and normalization baseline.</span></div>

 {!visible.length&&<p>All series hidden. Use the legend buttons to show them.</p>}{groups.filter(g=>g.length).map((g,i)=><div key={i}><h3>{shown==="normalized"?"Standard deviations (z)":g[0].unit}</h3><div className="chart-legend">{g.map((s,j)=><span key={s.id} style={{color:inks[j%inks.length]}}>{s.label}</span>)}</div><Plot items={g} dates={dates} normalized={shown==="normalized"} label="Metric overlay"/></div>)}</section>

 <div className="section-heading"><h2>Individual metric charts</h2><span>{data.versions.join(" · ")}</span></div>{data.series.map(s=><section className="panel" key={s.id}><h2>{s.label}</h2><p className="muted">{s.method} · {shown==="normalized"?`n=${s.normalization.n}; mean=${s.normalization.mean?.toFixed(2)??"—"}; SD=${s.normalization.sd?.toFixed(2)??"—"}`:s.unit}</p><Plot items={[s]} dates={data.dates} normalized={shown==="normalized"} label={`${s.label} chart`}/><details><summary>Accessible data table</summary><div className="chart-table"><table><thead><tr><th>Wake date</th><th>Value</th><th>Sample count</th>{s.rolling&&<th>{s.rolling.window}-day mean</th>}</tr></thead><tbody>{data.dates.map((d,i)=><tr key={d}><td>{d}</td><td>{shown==="normalized"?(s.values[i]===null?"Normalization unavailable / missing":`${s.values[i]!.toFixed(3)} z`):formatValue(s.values[i],s)}</td><td>{s.details[i].n??"—"}</td>{s.rolling&&<td>{rollingNote(s.rolling,i,r=>shown==="normalized"?`${r.toFixed(3)} z`:formatValue(r,s))}</td>}</tr>)}</tbody></table></div></details></section>)}</div>}

 <Investigator selection={selection}/>
 </div>;

}

