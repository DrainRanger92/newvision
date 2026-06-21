import { useEffect, useState } from "react";

const STORAGE_KEY = "nv-swipe-hint-shown";

export default function SwipeHint() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return;

    setVisible(true);

    let dismissed = false;

    const dismiss = () => {
      if (dismissed) return;
      dismissed = true;
      setVisible(false);
      localStorage.setItem(STORAGE_KEY, "1");
    };

    const timer = setTimeout(dismiss, 3000);
    document.addEventListener("touchstart", dismiss, { once: true });

    return () => {
      clearTimeout(timer);
      document.removeEventListener("touchstart", dismiss);
    };
  }, []);

  if (!visible) return null;

  return <div className="swipe-hint">{chr(0x1F446)} Swipe up to translate</div>;
}
