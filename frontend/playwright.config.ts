import {defineConfig} from "@playwright/test";
export default defineConfig({
 testDir:"./e2e",workers:1,outputDir:"../.cache/playwright-results",
 use:{baseURL:"http://127.0.0.1:8766",browserName:"chromium",launchOptions:{channel:"msedge"},viewport:{width:1440,height:1100}},
 webServer:{command:"..\\.venv\\Scripts\\python.exe ../scripts/preview-charts.py --fresh",url:"http://127.0.0.1:8766/api/v1/health",reuseExistingServer:false,timeout:60000},
});
