import {useEffect,useState} from "react";
import {analysisAvailability,analyzeRequest,loadAnalysisStatus} from "./ai";
import type {AnalysisResult,AnalysisStatus} from "./ai";
import type {Selection} from "./charts";

// Nothing here runs on load except a read-only status request. A provider call happens only inside analyze(), from the button.
export function Investigator({selection}:{selection:Selection}){
 const [status,setStatus]=useState<AnalysisStatus|null>(null),[question,setQuestion]=useState(""),[busy,setBusy]=useState(false);
 const [result,setResult]=useState<AnalysisResult|null>(null),[error,setError]=useState(""),[loadError,setLoadError]=useState("");
 useEffect(()=>{const c=new AbortController();loadAnalysisStatus(c.signal).then(s=>{if(!c.signal.aborted)setStatus(s);}).catch(e=>{if(!c.signal.aborted)setLoadError(e instanceof Error?e.message:"AI status unavailable.");});return()=>c.abort();},[]);
 const availability=analysisAvailability(status,selection,question);
 async function analyze(){
  if(!availability.canAsk||busy)return;
  setBusy(true);setError("");
  try{
   const answer=await analyzeRequest({question:question.trim(),metrics:selection.metrics,range:selection.range,start:selection.range==="custom"?selection.start:null,end:selection.range==="custom"?selection.end:null,confirm:true});
   setResult(answer);setStatus(s=>s&&{...s,usage:answer.usage});
  }catch(e){setResult(null);setError(e instanceof Error?e.message:"Analysis failed.");loadAnalysisStatus(new AbortController().signal).then(setStatus).catch(()=>undefined);}
  finally{setBusy(false);}
 }
 return <section className="panel investigator" aria-labelledby="ai-heading"><div className="panel-title"><h2 id="ai-heading">Ask about these nights</h2><span className="pill">ON REQUEST ONLY</span></div>
  {loadError&&<p role="status" className="muted">AI status unavailable: {loadError} Charts and statistics are unaffected.</p>}
  {status&&<>
   {status.state!=="ready"&&<p role="status" className="muted">{status.state==="disabled"?"AI analysis is turned off. Everything else works without it. To turn it on, the owner sets SLEEPIQ_AI_ENABLED=1 and an API key before launching the app.":"AI analysis is switched on but has no API key configured. Everything else works without it."}</p>}
   <details className="disclosure" open={status.state==="ready"}><summary>What is sent, and what it costs</summary><ul>{status.disclosure.map(line=><li key={line}>{line}</li>)}</ul>
    <p className="muted">Model {status.model} · used today {status.usage.today}/{status.limits.per_day} · this month {status.usage.month}/{status.limits.per_month}</p></details>
   <label className="ai-question">Your question about the selected metrics and range
    <textarea value={question} maxLength={500} rows={3} onChange={e=>setQuestion(e.target.value)} placeholder="For example: is my sleeping heart rate related to deep sleep?"/></label>
   <div className="chart-toolbar"><button type="button" className="text-button" disabled={!availability.canAsk||busy} onClick={analyze}>{busy?"Analyzing…":"Analyze"}</button>
    <span className="muted">{question.trim().length}/500 · {selection.metrics.length} metric{selection.metrics.length===1?"":"s"} selected</span></div>
   {availability.reason&&<p role="status" className="muted">{availability.reason}</p>}
  </>}
  {error&&<div role="alert" className="export-error">{error}</div>}
  {result&&<div className="ai-answer" aria-live="polite"><p className="eyebrow">ANSWER · {result.model}</p><p className="ai-text">{result.answer}</p>
   <p className="muted">Explains statistics computed on this PC; not medical advice. Used today {result.usage.today}/{status?.limits.per_day}.</p>
   <details><summary>Evidence sent for this answer</summary><p className="muted">{result.evidence.date_range[0]} to {result.evidence.date_range[1]} · {result.evidence.calendar_days} calendar days</p>
    <div className="chart-table"><table><thead><tr><th>Metric</th><th>Nights</th><th>Missing</th><th>Mean</th><th>SD</th><th>Change/week</th></tr></thead><tbody>{result.evidence.metrics.map(m=><tr key={m.metric}><td>{m.metric} ({m.unit})</td><td>{m.nights_recorded}</td><td>{m.nights_missing}</td><td>{m.mean??"—"}</td><td>{m.sd??"—"}</td><td>{m.change_per_week??"—"}</td></tr>)}</tbody></table></div>
    {result.evidence.correlations.length>0&&<div className="chart-table"><table><thead><tr><th>Pair</th><th>Paired nights</th><th>Pearson r</th></tr></thead><tbody>{result.evidence.correlations.map(c=><tr key={c.x+c.y}><td>{c.x} / {c.y}</td><td>{c.paired_nights}</td><td>{c.pearson_r??`Unavailable (${c.unavailable_reason??"no reason"})`}</td></tr>)}</tbody></table></div>}
    <p className="muted">Nightly values for these metrics were also sent (latest {status?.limits.max_nights} nights each).</p></details></div>}
 </section>;
}
