import {describe,expect,it} from "vitest";
import {hrQualityText} from "./HRInfo";
const base={method:"time_weighted_linear",n:18,covered_s:22320,window_s:28800,coverage:0.775,fallback_reason:null};
describe("HR calculation information",()=>{
 it("labels estimated support and formats real elapsed minutes",()=>expect(hrQualityText(base)).toBe("Time-weighted estimate · 18 samples. Estimated coverage: 6h 12m of 8h 00m (78%)."));
 it("explains sparse fallback without claiming full coverage",()=>expect(hrQualityText({...base,method:"simple_mean_fallback",n:1,covered_s:0,coverage:0,fallback_reason:"insufficient_points"})).toContain("Simple average · 1 sample. Too few readings to connect."));
 it("keeps unknown coverage unknown",()=>expect(hrQualityText({...base,method:"simple_mean_fallback",coverage:null,covered_s:null,window_s:null})).toContain("Duration coverage unknown."));
 it("does not turn absent HR into a reading",()=>expect(hrQualityText({...base,n:0,method:null})).toBe("No overnight heart-rate readings."));
});
