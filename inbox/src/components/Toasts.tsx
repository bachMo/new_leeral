import { createContext, type ReactNode, useCallback, useContext, useState } from "react";

interface Toast {
  id: number;
  text: string;
  error: boolean;
}

type Show = (text: string, options?: { error?: boolean }) => void;

const ToastContext = createContext<Show>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const show = useCallback<Show>((text, options) => {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, text, error: Boolean(options?.error) }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast${toast.error ? " is-error" : ""}`} role="status">
            {toast.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Show {
  return useContext(ToastContext);
}
