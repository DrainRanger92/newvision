import { Routes, Route } from "react-router-dom";
import App from "./App";
import Reader from "./pages/Reader";

export default function Router() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/reader/:id" element={<Reader />} />
    </Routes>
  );
}
