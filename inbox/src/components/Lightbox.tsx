import { Download, X } from "lucide-react";
import { useEffect } from "react";

export function Lightbox({ url, onClose }: { url: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="Photo" onClick={onClose}>
      <div className="lightbox-tools" onClick={(event) => event.stopPropagation()}>
        <a href={url} target="_blank" rel="noopener noreferrer" aria-label="Ouvrir l'original">
          <Download size={20} />
        </a>
        <button className="icon-button" onClick={onClose} aria-label="Fermer" autoFocus>
          <X size={22} />
        </button>
      </div>
      <img src={url} alt="" onClick={(event) => event.stopPropagation()} />
    </div>
  );
}
