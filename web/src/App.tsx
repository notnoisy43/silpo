import { useEffect } from "react";

import { getHealth } from "./api";
import { useAppStore } from "./store";

const statusLabel = {
  unknown: "Перевіряємо з'єднання",
  ok: "Сервер на зв'язку",
  down: "Сервер недоступний",
} as const;

export default function App() {
  const { apiStatus, setApiStatus } = useAppStore();

  useEffect(() => {
    getHealth()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("down"));
  }, [setApiStatus]);

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Передчуття</h1>
        <span className="flex items-center gap-2 text-sm text-muted">
          <span
            className={`h-2 w-2 rounded-pill ${
              apiStatus === "ok" ? "bg-ok" : apiStatus === "down" ? "bg-storm" : "bg-muted"
            }`}
          />
          {statusLabel[apiStatus]}
        </span>
      </header>

      <main className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-card bg-paper p-6">
          <h2 className="font-semibold">Кошик</h2>
          <p className="mt-2 text-sm text-muted">Тут з'явиться ваш кошик Сільпо.</p>
        </section>

        <section className="rounded-card bg-ink p-6 text-paper">
          <h2 className="font-semibold">Хід агента</h2>
          <p className="mt-2 text-sm opacity-70">Трейс викликів MCP з'явиться тут.</p>
        </section>
      </main>
    </div>
  );
}
