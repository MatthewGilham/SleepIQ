import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./style.css";
const theme = new URLSearchParams(window.location.search).get("theme");
document.documentElement.dataset.theme = theme && ["iris", "ember", "bloom", "tide", "velvet", "blackout", "terminal", "afterburn", "reactor", "overdrive", "terminal-ghost", "terminal-venom", "terminal-glacier", "terminal-hazard", "terminal-mainframe", "afterburn-inferno", "afterburn-bloodline", "afterburn-arctic", "afterburn-ignition", "afterburn-obsidian"].includes(theme) ? theme : "afterburn";
createRoot(document.getElementById("root")!).render(<App />);

