import {expect,test,vi,afterEach} from "vitest";
import {analysisAvailability,analyzeRequest,loadAnalysisStatus} from "./ai";
import type {AnalysisStatus} from "./ai";
import {initialSelection} from "./charts";

afterEach(()=>vi.unstubAllGlobals());
const status:AnalysisStatus={state:"ready",model:"gpt-6-luna",limits:{input_tokens:15000,output_tokens:2000,per_day:20,per_month:300,max_metrics:6,max_nights:90},usage:{today:0,month:0,tokens_today:{input:0,output:0}},disclosure:["x"]};
const sel=initialSelection;

test("Analyze is offered only when every precondition holds",()=>{
 expect(analysisAvailability(null,sel,"hello there").canAsk).toBe(false);
 expect(analysisAvailability({...status,state:"disabled"},sel,"hello there").canAsk).toBe(false);
 expect(analysisAvailability({...status,state:"not_configured"},sel,"hello there").canAsk).toBe(false);
 expect(analysisAvailability(status,sel,"hello there")).toEqual({canAsk:true,reason:""});
 expect(analysisAvailability(status,sel,"  hi").reason).toContain("Type a question");
 expect(analysisAvailability(status,{...sel,metrics:[]},"hello there").reason).toContain("at least one");
 expect(analysisAvailability(status,{...sel,metrics:["a","b","c","d","e","f","g"]},"hello there").reason).toContain("at most 6");
 expect(analysisAvailability(status,{...sel,range:"custom",start:"2026-02-01",end:"2026-01-01"},"hello there").reason).toContain("valid start");
 expect(analysisAvailability({...status,usage:{...status.usage,today:20}},sel,"hello there").reason).toContain("Daily limit of 20");
 expect(analysisAvailability({...status,usage:{...status.usage,month:300}},sel,"hello there").reason).toContain("Monthly limit of 300");
});
test("loading status makes one read-only GET and never a POST",async()=>{
 const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify(status)));vi.stubGlobal("fetch",fetchMock);
 await loadAnalysisStatus(new AbortController().signal);
 expect(fetchMock).toHaveBeenCalledTimes(1);expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/analysis/status");expect(fetchMock.mock.calls[0][1]?.method).toBeUndefined();
});
test("analysis posts the confirmation header and surfaces the server's safe message",async()=>{
 const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"Daily limit of 20 analyses reached."}),{status:429}));vi.stubGlobal("fetch",fetchMock);
 await expect(analyzeRequest({question:"q?",metrics:["asleep_s"],range:"30",start:null,end:null,confirm:true})).rejects.toThrow("Daily limit of 20 analyses reached.");
 const init=fetchMock.mock.calls[0][1] as RequestInit;expect(init.method).toBe("POST");expect((init.headers as Record<string,string>)["X-SleepIQ-Request"]).toBe("charts");
 vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response("<html>",{status:500})));
 await expect(analyzeRequest({question:"q?",metrics:["asleep_s"],range:"30",start:null,end:null,confirm:true})).rejects.toThrow("Analysis failed (500)");
});
