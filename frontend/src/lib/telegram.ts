import WebApp from "@twa-dev/sdk";

let isTelegramAvailable = false;

export function initTelegram(): boolean {
  try {
    if (WebApp.platform !== "unknown") {
      isTelegramAvailable = true;
      WebApp.ready();
      WebApp.expand();
      applyTheme();
      WebApp.onEvent("themeChanged", applyTheme);
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

export function applyTheme(): void {
  const root = document.documentElement;
  const theme = WebApp.themeParams;

  root.style.setProperty("--tg-bg-color", theme.bg_color || "#ffffff");
  root.style.setProperty("--tg-text-color", theme.text_color || "#1a1a1a");
  root.style.setProperty("--tg-hint-color", theme.hint_color || "#999999");
  root.style.setProperty("--tg-link-color", theme.link_color || "#2481cc");
  root.style.setProperty("--tg-secondary-bg-color", theme.secondary_bg_color || "#f0f0f0");
  root.style.setProperty("--tg-button-color", theme.button_color || "#2481cc");
  root.style.setProperty("--tg-button-text-color", theme.button_text_color || "#ffffff");
  root.style.setProperty("--tg-error-color", "#e74c3c");
}
