import React from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const STUDENT = "Vibhuti Bhatnagar";
const ROLL_NO = "24BCS10288";
const BATCH = "B";

function App() {
  return (
    <div className="card">
      <h1>Hello World</h1>
      <p>React production build served by Nginx</p>
      <p className="meta">
        {STUDENT} &middot; {ROLL_NO} &middot; Batch {BATCH}
      </p>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
