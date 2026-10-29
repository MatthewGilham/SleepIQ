import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { checkHealth } from "./health";
import { loadBackupStatus } from "./backup";
import "./style.css";

function App() {
  const [status, setStatus] = useState("Connecting to local service...");
  const [backup, setBackup] = useState("Checking backup status...");
  useEffect(() => {
    const controller = new AbortController();
    loadBackupStatus(controller.signal)
      .then(message => { if (!controller.signal.aborted) setBackup(message); })
      .catch(() => { if (!controller.signal.aborted) setBackup("Backup status unavailable."); });
    checkHealth(controller.signal)
      .then(() => { if (!controller.signal.aborted) setStatus("Local service connected"); })
      .catch(() => { if (!controller.signal.aborted) setStatus("Local service unavailable. Try again shortly."); });
    return () => controller.abort();
  }, []);
  return <main><p>LOCAL SLEEP ANALYTICS</p><h1>SleepIQ</h1><p role="status">{status}</p><p role="status">{backup}</p><p>Setup in progress. Sleep data is not connected yet.</p></main>;
}
createRoot(document.getElementById("root")!).render(<App />);
