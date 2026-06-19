import { isInsideTelegram } from "./lib/telegram";

export default function App() {
  return (
    <div className="app">
      <h1>NewVision</h1>
      <p>
        {isInsideTelegram()
          ? "Send a URL to the bot to start reading."
          : "Send a URL to the NewVision bot in Telegram to start reading."}
      </p>
    </div>
  );
}
