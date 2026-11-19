import {
  FileText,
  Film,
  Image as ImageIcon,
  Mic,
  Music,
  Paperclip,
  Send,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import {
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
} from "react";
import type { OutgoingPayload } from "../lib/api";
import { formatBytes, formatDuration, senderLabel } from "../lib/format";
import type { Message, OutgoingKind } from "../lib/types";

const MB = 1024 * 1024;
const MAX_UPLOAD = 25 * MB;
const MAX_VIDEO = 16 * MB;
const MAX_AUDIO = 16 * MB;
const MAX_RECORDING_SECONDS = 300;

type FileKind = Extract<OutgoingKind, "image" | "video" | "audio" | "document">;

const ACCEPT: Record<FileKind, string> = {
  image: "image/*",
  video: "video/mp4,video/3gpp",
  audio: "audio/*",
  document: ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt",
};

const KIND_LABELS: Record<FileKind, string> = {
  image: "Photo",
  video: "Vidéo",
  audio: "Audio",
  document: "Document",
};

interface StagedFile {
  kind: FileKind;
  file: File;
  preview: string | null;
}

export interface ComposerHandle {
  stageFile: (file: File) => void;
  focus: () => void;
}

interface ComposerProps {
  windowOpen: boolean;
  replyTo: Message | null;
  onCancelReply: () => void;
  onSend: (payload: OutgoingPayload) => void;
  onError: (text: string) => void;
}

export function kindForFile(file: File): FileKind {
  if (file.type.startsWith("image/")) return "image";
  if (file.type === "video/mp4" || file.type === "video/3gpp") return "video";
  if (file.type.startsWith("audio/")) return "audio";
  return "document";
}

function sizeProblem(kind: FileKind, file: File): string | null {
  const limit = kind === "video" ? MAX_VIDEO : kind === "audio" ? MAX_AUDIO : MAX_UPLOAD;
  if (file.size > limit) {
    return `Ce fichier fait ${formatBytes(file.size)}. La limite est de ${formatBytes(limit)}.`;
  }
  if (file.size === 0) return "Ce fichier est vide.";
  return null;
}

function pickRecorderType(): string | undefined {
  const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type));
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(props, ref) {
  const [text, setText] = useState("");
  const [staged, setStaged] = useState<StagedFile | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [recording, setRecording] = useState<{ startedAt: number; elapsed: number } | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pendingKind = useRef<FileKind>("image");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const keepRecording = useRef(false);

  const { onError, onSend } = props;

  function stage(kind: FileKind, file: File) {
    const problem = sizeProblem(kind, file);
    if (problem) {
      onError(problem);
      return;
    }
    setStaged((previous) => {
      if (previous?.preview) URL.revokeObjectURL(previous.preview);
      return { kind, file, preview: kind === "image" ? URL.createObjectURL(file) : null };
    });
    textarea.current?.focus();
  }

  useImperativeHandle(ref, () => ({
    stageFile: (file: File) => stage(kindForFile(file), file),
    focus: () => textarea.current?.focus(),
  }));

  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }, [text]);

  useEffect(() => {
    if (props.replyTo) textarea.current?.focus();
  }, [props.replyTo]);

  useEffect(
    () => () => {
      keepRecording.current = false;
      recorder.current?.stream.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => {
      const elapsed = (Date.now() - recording.startedAt) / 1000;
      setRecording((current) => (current ? { ...current, elapsed } : current));
      if (elapsed >= MAX_RECORDING_SECONDS) stopRecording(true);
    }, 250);
    return () => window.clearInterval(id);
  }, [recording?.startedAt]);

  function clearStaged() {
    if (staged?.preview) URL.revokeObjectURL(staged.preview);
    setStaged(null);
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const trimmed = text.trim();
    const replyTo = props.replyTo?.id;
    if (staged) {
      onSend({
        kind: staged.kind,
        file: staged.file,
        fileName: staged.file.name,
        text: staged.kind === "audio" ? undefined : trimmed || undefined,
        replyTo,
      });
      clearStaged();
      if (staged.kind !== "audio") setText("");
    } else if (trimmed) {
      onSend({ kind: "text", text: trimmed, replyTo });
      setText("");
    } else {
      return;
    }
    props.onCancelReply();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
    if (event.key === "Escape") {
      if (staged) clearStaged();
      else if (props.replyTo) props.onCancelReply();
    }
  }

  function onPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const file = Array.from(event.clipboardData.files)[0];
    if (file) {
      event.preventDefault();
      stage(kindForFile(file), file);
    }
  }

  function openPicker(kind: FileKind) {
    pendingKind.current = kind;
    setMenuOpen(false);
    if (fileInput.current) {
      fileInput.current.accept = ACCEPT[kind];
      fileInput.current.value = "";
      fileInput.current.click();
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      onError("Ce navigateur ne permet pas d'enregistrer un message vocal.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = pickRecorderType();
      const media = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks.current = [];
      keepRecording.current = true;
      media.ondataavailable = (event) => event.data.size && chunks.current.push(event.data);
      media.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        if (!keepRecording.current) return;
        const blob = new Blob(chunks.current, { type: media.mimeType || "audio/webm" });
        if (blob.size === 0) return;
        onSend({ kind: "voice", file: blob, fileName: "note-vocale", replyTo: props.replyTo?.id });
        props.onCancelReply();
      };
      recorder.current = media;
      media.start(250);
      setRecording({ startedAt: Date.now(), elapsed: 0 });
    } catch {
      onError("Accès au micro refusé. Autorise le micro dans le navigateur pour enregistrer.");
    }
  }

  function stopRecording(send: boolean) {
    keepRecording.current = send;
    recorder.current?.stop();
    recorder.current = null;
    setRecording(null);
  }

  if (!props.windowOpen) {
    return null;
  }

  return (
    <form className="composer" onSubmit={submit} style={{ position: "relative" }}>
      <input
        ref={fileInput}
        type="file"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) stage(pendingKind.current, file);
        }}
      />
      {props.replyTo && (
        <div className="composer-strip">
          <div className="strip-text">
            <strong>Réponse à {senderLabel(props.replyTo).toLowerCase()}</strong>
            <span>{props.replyTo.body ?? props.replyTo.filename ?? "Message"}</span>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={props.onCancelReply}
            aria-label="Annuler la réponse"
          >
            <X size={18} />
          </button>
        </div>
      )}
      {staged && (
        <div className="composer-strip">
          {staged.preview ? (
            <img src={staged.preview} alt="" />
          ) : staged.kind === "video" ? (
            <Film size={28} aria-hidden="true" />
          ) : staged.kind === "audio" ? (
            <Music size={28} aria-hidden="true" />
          ) : (
            <FileText size={28} aria-hidden="true" />
          )}
          <div className="strip-text">
            <strong>{KIND_LABELS[staged.kind]}</strong>
            <span>
              {staged.file.name} ({formatBytes(staged.file.size)})
            </span>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={clearStaged}
            aria-label="Retirer le fichier"
          >
            <X size={18} />
          </button>
        </div>
      )}
      {menuOpen && (
        <div className="attach-menu" role="menu" onMouseLeave={() => setMenuOpen(false)}>
          <button type="button" role="menuitem" onClick={() => openPicker("image")}>
            <ImageIcon size={18} /> Photo
          </button>
          <button type="button" role="menuitem" onClick={() => openPicker("video")}>
            <Film size={18} /> Vidéo
          </button>
          <button type="button" role="menuitem" onClick={() => openPicker("document")}>
            <FileText size={18} /> Document
          </button>
          <button type="button" role="menuitem" onClick={() => openPicker("audio")}>
            <Music size={18} /> Fichier audio
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              setContactOpen(true);
            }}
          >
            <UserRound size={18} /> Contact
          </button>
        </div>
      )}
      <div className="composer-row">
        {recording ? (
          <>
            <button
              type="button"
              className="icon-button"
              onClick={() => stopRecording(false)}
              aria-label="Annuler l'enregistrement"
            >
              <Trash2 size={20} />
            </button>
            <div className="recording" role="status">
              <span className="recording-dot" aria-hidden="true" />
              Enregistrement {formatDuration(recording.elapsed)}
            </div>
            <button
              type="button"
              className="icon-button send-button"
              onClick={() => stopRecording(true)}
              aria-label="Envoyer le message vocal"
            >
              <Send size={18} />
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="icon-button"
              aria-label="Joindre un fichier"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <Paperclip size={20} />
            </button>
            <label className="sr-only" htmlFor="composer-text">
              Message
            </label>
            <textarea
              id="composer-text"
              ref={textarea}
              rows={1}
              value={text}
              maxLength={staged ? 1024 : 4096}
              placeholder={
                staged && staged.kind !== "audio" ? "Ajouter une légende" : "Écrire un message"
              }
              onChange={(event) => setText(event.target.value)}
              onKeyDown={onKeyDown}
              onPaste={onPaste}
            />
            {text.trim() || staged ? (
              <button type="submit" className="icon-button send-button" aria-label="Envoyer">
                <Send size={18} />
              </button>
            ) : (
              <button
                type="button"
                className="icon-button send-button"
                onClick={() => void startRecording()}
                aria-label="Enregistrer un message vocal"
              >
                <Mic size={19} />
              </button>
            )}
          </>
        )}
      </div>
      {contactOpen && (
        <ContactForm
          onCancel={() => setContactOpen(false)}
          onSubmit={(name, phone) => {
            setContactOpen(false);
            onSend({
              kind: "contact",
              contactName: name,
              contactPhone: phone,
              replyTo: props.replyTo?.id,
            });
            props.onCancelReply();
          }}
        />
      )}
    </form>
  );
});

function ContactForm({
  onCancel,
  onSubmit,
}: {
  onCancel: () => void;
  onSubmit: (name: string, phone: string) => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="contact-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="contact-title">Envoyer un contact</h2>
        <label className="field">
          Nom
          <input
            value={name}
            maxLength={100}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </label>
        <label className="field">
          Numéro
          <input
            value={phone}
            inputMode="tel"
            placeholder="77 123 45 67"
            maxLength={32}
            onChange={(event) => setPhone(event.target.value)}
          />
        </label>
        <div className="modal-actions">
          <button type="button" className="ghost-button" onClick={onCancel}>
            Annuler
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!name.trim() || phone.replace(/\D/g, "").length < 7}
            onClick={() => onSubmit(name.trim(), phone.trim())}
          >
            Envoyer le contact
          </button>
        </div>
      </div>
    </div>
  );
}
