import React from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

function App() {
  return (
    <div className="card">
      <h1>Hello World from Docker multi-stage build</h1>
      <p>React production bundle served by Nginx</p>
      <p className="meta">Vibhuti Bhatnagar &middot; 24BCS10288 &middot; Batch B</p>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
