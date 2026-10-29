import type {Range,Selection} from "./charts";

export type AnalysisStatus = {state:"ready"|"disabled"|"not_configured";model:string;limits:{input_tokens:number;output_tokens:number;per_day:number;per_month:number;max_metrics:number;max_nights:number};usage:{today:number;month:number;tokens_today:{input:number;output:number}};disclosure:string[]};
export type EvidenceMetric = {metric:string;unit:string;nights_recorded:number;nights_missing:number;mean?:number|null;sd?:number|null;change_per_week?:number|null};
export type Evidence = {date_range:[string|null,string|null];calendar_days:number;metrics:EvidenceMetric[];correlations:{x:string;y:string;paired_nights:number;pearson_r:number|null;unavailable_reason:string|null}[]};
export type AnalysisResult = {answer:string;model:string;evidence:Evidence;usage:AnalysisStatus["usage"]};
export type AnalysisBody = {question:string;metrics:string[];range:Range;start:string|null;end:string|null;confirm:true};

export async function loadAnalysisStatus(signal:AbortSignal):Promise<AnalysisStatus>{
 const response=await fetch("/api/v1/analysis/status",{signal});
 if(!response.ok)throw new Error(response.status===503?"No chart store is configured.":`Status request failed (${response.status}).`);
 return await response.json() as AnalysisStatus;
}
// The only function that can cause a provider request; it is called from the Analyze button handler alone.
export async function analyzeRequest(body:AnalysisBody):Promise<AnalysisResult>{
 const response=await fetch("/api/v1/analysis",{method:"POST",headers:{"Content-Type":"application/json","X-SleepIQ-Request":"charts"},body:JSON.stringify(body)});
 if(!response.ok){
  let detail="";
  try{const payload=await response.json() as {detail?:unknown};if(typeof payload.detail==="string")detail=payload.detail;}catch{/* keep the generic message */}
  throw new Error(detail||`Analysis failed (${response.status}). Your charts are unaffected.`);
 }
 return await response.json() as AnalysisResult;
}
// Mirrors server checks only to explain a disabled button; the server enforces every limit again.
export function analysisAvailability(status:AnalysisStatus|null,selection:Selection,question:string):{canAsk:boolean;reason:string}{
 if(!status)return {canAsk:false,reason:""};
 if(status.state!=="ready")return {canAsk:false,reason:""};
 if(selection.metrics.length===0)return {canAsk:false,reason:"Select at least one metric above."};
 if(selection.metrics.length>status.limits.max_metrics)return {canAsk:false,reason:`Select at most ${status.limits.max_metrics} metrics to analyze.`};
 if(selection.range==="custom"&&(!selection.start||!selection.end||selection.start>selection.end))return {canAsk:false,reason:"Choose a valid start and end date above."};
 if(status.usage.today>=status.limits.per_day)return {canAsk:false,reason:`Daily limit of ${status.limits.per_day} analyses reached. It resets tomorrow.`};
 if(status.usage.month>=status.limits.per_month)return {canAsk:false,reason:`Monthly limit of ${status.limits.per_month} analyses reached.`};
 if(question.trim().length<3)return {canAsk:false,reason:"Type a question (at least 3 characters)."};
 return {canAsk:true,reason:""};
}
