import {useEffect,useState} from "react";
import {chartRequest,exportRequest,fileNameFrom} from "./charts";
import type {Metric,Range} from "./charts";

// Python builds the CSV; this panel only collects the selection and hands the file to the browser.
export function DataExport(){
 const [catalog,setCatalog]=useState<Metric[]>([]),[picked,setPicked]=useState<string[]>([]),[range,setRange]=useState<Range>("all");
 const [start,setStart]=useState(""),[end,setEnd]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[retry,setRetry]=useState(0);
 useEffect(()=>{const c=new AbortController();setError("");chartRequest<Metric[]>("metrics/catalog","GET",undefined,c.signal).then(m=>{if(c.signal.aborted)return;setCatalog(m);setPicked(m.map(v=>v.id));}).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[retry]);
 const invalid=picked.length===0?"Choose at least one metric.":range==="custom"&&(!start||!end||start>end)?"Choose a valid start and end date.":"";
 async function download(){
  setBusy(true);setError("");setMessage("");
  try{
   const {blob,name,rows}=await exportRequest({metrics:catalog.filter(m=>picked.includes(m.id)).map(m=>m.id),range,start:range==="custom"?start:null,end:range==="custom"?end:null});
   const url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=fileNameFrom(name);document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
   setMessage(`Downloaded ${rows} night${rows===1?"":"s"} as ${fileNameFrom(name)}.`);
  }catch(e){setError(e instanceof Error?e.message:"Export failed.");}finally{setBusy(false);}
 }
 return <section className="panel export-panel" aria-labelledby="export-heading"><div className="panel-title"><h2 id="export-heading">Export nightly metrics</h2><span className="pill">CSV</span></div>
  {error&&<div role="alert" className="export-error">{error} {catalog.length===0&&<button onClick={()=>setRetry(n=>n+1)}>Retry</button>}</div>}
  {catalog.length>0&&<><fieldset className="export-metrics"><legend>Metrics</legend><div className="chart-toolbar"><button type="button" onClick={()=>setPicked(catalog.map(m=>m.id))}>Select all</button><button type="button" onClick={()=>setPicked([])}>Clear</button></div>
   {catalog.map(m=><label key={m.id}><input type="checkbox" checked={picked.includes(m.id)} onChange={e=>setPicked(e.target.checked?[...picked,m.id]:picked.filter(id=>id!==m.id))}/>{m.label} ({m.clock?"HH:MM":m.unit})</label>)}</fieldset>
   <div className="chart-toolbar"><label>Range<select aria-label="Export range" value={range} onChange={e=>setRange(e.target.value as Range)}>{(["7","30","90","all","custom"] as Range[]).map(r=><option key={r} value={r}>{r==="all"?"All history":r==="custom"?"Custom":`Latest ${r} days`}</option>)}</select></label>
    {range==="custom"&&<><label>From<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>To<input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label></>}
    <button type="button" className="text-button" disabled={busy||invalid!==""} onClick={download}>{busy?"Preparing…":"Download CSV"}</button></div>
   {invalid&&<p role="status" className="muted">{invalid}</p>}</>}
  <p role="status" aria-live="polite" className="muted">{message}</p></section>;
}
