import { isInsideTelegram } from "./lib/telegram";

export default function App() {
  return (
    <div className="app">
      <h1>Curtain Reader</h1>
      <p>
        {isInsideTelegram()
          ? "Running inside Telegram Mini App"
          : "Running in browser (development mode)"}
      </p>
    </div>
  );
}
