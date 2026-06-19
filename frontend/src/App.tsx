import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { isInsideTelegram } from "./lib/telegram";
import Reader from "./pages/Reader";

function Home() {
  return (
    <div className="app">
      <h1>NewVision</h1>
      <p>
        {isInsideTelegram()
          ? "Send a URL to the bot to read articles here."
          : "Running in browser (development mode)"}
      </p>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/reader/:id" element={<Reader />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}
