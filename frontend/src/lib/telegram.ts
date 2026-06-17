import WebApp from "@twa-dev/sdk";

let isTelegramAvailable = false;

export function initTelegram(): boolean {
  try {
    if (WebApp.platform !== "unknown") {
      isTelegramAvailable = true;
      WebApp.ready();
      WebApp.expand();
      return true;
    }
  } catch {
    isTelegramAvailable = false;
  }
  return false;
}

export function isInsideTelegram(): boolean {
  return isTelegramAvailable;
}
