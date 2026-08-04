"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { analyzeShot, AnalyzeShotResponse, chatWithCoach, ChatMessage, ShotFormValues } from "../lib/api";
import { ShotResult } from "./shot-result";

type UiMessage = ChatMessage & { id: string; preview_url?: string; preview_kind?: "image" | "video"; preview_name?: string };

const initialAssistant: UiMessage = {
  id: "assistant-start",
  role: "assistant",
  content: "Hey, I can help dial in your espresso shot. What machine are you using?",
};

export function ChatCoach() {
  const [messages, setMessages] = useState<UiMessage[]>([initialAssistant]);
  const [input, setInput] = useState("");
  const [shotContext, setShotContext] = useState<ShotFormValues>({ user_id: "demo-user" });
  const [result, setResult] = useState<AnalyzeShotResponse | null>(null);
  const [manualStart, setManualStart] = useState("");
  const [manualStop, setManualStop] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [showMobileResults, setShowMobileResults] = useState(false);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const mediaObjectUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, result]);

  useEffect(() => {
    return () => {
      mediaObjectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setInput("");
    await sendMessage(trimmed);
  }

  async function sendMessage(
    content: string,
    image?: Pick<ChatMessage, "image_base64" | "image_media_type" | "image_kind">,
    preview?: Pick<UiMessage, "preview_url" | "preview_kind" | "preview_name">,
  ) {
    const userMessage: UiMessage = { id: makeId("user"), role: "user", content, ...image, ...preview };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setIsLoading(true);
    setError("");

    try {
      const response = await chatWithCoach({
        messages: nextMessages.map(({ id, role, content, image_base64, image_media_type, image_kind }) => ({
          role,
          content,
          image_base64: id === userMessage.id ? image_base64 : undefined,
          image_media_type: id === userMessage.id ? image_media_type : undefined,
          image_kind: id === userMessage.id ? image_kind : undefined,
        })),
        shot_context: shotContext,
      });
      if (response.shot_context) {
        setShotContext({ ...response.shot_context, user_id: response.shot_context.user_id || "demo-user" });
      }
      if (response.analysis_result) {
        setResult(response.analysis_result);
        setShowMobileResults(true);
        setManualStart(formatInputTime(response.analysis_result.timing.machine_start_time));
        setManualStop(formatInputTime(response.analysis_result.timing.machine_stop_time));
      }
      setMessages((current) => [
        ...current,
        { id: makeId("assistant"), role: "assistant", content: response.response },
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Coach request failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleApplyTiming() {
    const start = parseOptionalNumber(manualStart);
    const stop = parseOptionalNumber(manualStop);

    if (start === undefined || stop === undefined || stop <= start) {
      setError("Enter a valid start and stop time.");
      return;
    }

    setIsLoading(true);
    setError("");
    try {
      const payload: ShotFormValues = {
        ...shotContext,
        video_s3_key: undefined,
        total_shot_seconds: round(stop - start),
        timing_confidence: 1,
        requires_manual_confirmation: false,
      };
      const response = await analyzeShot(payload);
      setShotContext(payload);
      setResult(response);
      setShowMobileResults(true);
      setMessages((current) => [
        ...current,
        {
          id: makeId("assistant"),
          role: "assistant",
          content: `Got it. With your corrected timing, the shot ran ${response.timing.total_shot_seconds}s. ${response.message}`,
        },
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to apply timing correction.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAttachmentSelected(file: File | null) {
    if (!file || isLoading) {
      return;
    }

    if (file.type.startsWith("video/") || isVideoFile(file.name)) {
      const previewUrl = createMediaPreviewUrl(file, mediaObjectUrlsRef.current);
      await sendMessage(`data/raw-videos/${file.name}`, undefined, {
        preview_url: previewUrl,
        preview_kind: "video",
        preview_name: file.name,
      });
      return;
    }

    if (!file.type.startsWith("image/") && !isImageFile(file.name)) {
      setError("Attach an image of the machine/grinder or a shot video.");
      return;
    }

    const kind = inferImageKind(shotContext);
    const previewUrl = createMediaPreviewUrl(file, mediaObjectUrlsRef.current);
    setIsLoading(true);
    setError("");
    try {
      const imageBase64 = await readFileAsBase64(file);
      await sendMessage("I uploaded a photo.", {
        image_base64: imageBase64,
        image_media_type: file.type || "image/jpeg",
        image_kind: kind,
      }, {
        preview_url: previewUrl,
        preview_kind: "image",
        preview_name: file.name,
      });
    } catch (requestError) {
      URL.revokeObjectURL(previewUrl);
      mediaObjectUrlsRef.current = mediaObjectUrlsRef.current.filter((url) => url !== previewUrl);
      setError(requestError instanceof Error ? requestError.message : "Unable to read attached file.");
      setIsLoading(false);
    }
  }

  return (
    <div className="chat-workspace">
      <section className="chat-panel" aria-label="DialedIN chat coach">
        <div className="chat-thread">
          {messages.map((message) => (
            <div className={`chat-message ${message.role}`} key={message.id}>
              {message.preview_url ? <MediaPreview message={message} /> : null}
              {shouldShowMessageText(message) ? <p>{message.content}</p> : null}
              {message.image_base64 && !message.preview_url ? <span className="chat-image-note">Photo attached</span> : null}
            </div>
          ))}
          {isLoading ? (
            <div className="chat-message assistant pending">
              <p>Thinking through the shot...</p>
            </div>
          ) : null}
          <div ref={messageEndRef} />
        </div>

        {error ? <div className="alert" role="alert">{error}</div> : null}

        <div className="chat-input-dock">
          {result ? (
            <button className="mobile-results-button" type="button" onClick={() => setShowMobileResults(true)}>
              View shot analysis
            </button>
          ) : null}
          <form className="chat-composer" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Message DialedIN..."
              aria-label="Message"
            />
            <label className="composer-icon-button attachment-icon-button" title="Attach photo or video" aria-label="Attach photo or video">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/heic,image/heif,image/*,video/mp4,video/quicktime,video/x-m4v,video/*"
                onChange={(event) => {
                  handleAttachmentSelected(event.target.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
              <PaperclipIcon />
            </label>
            <button
              className="composer-icon-button send-icon-button"
              type="submit"
              disabled={isLoading || !input.trim()}
              title="Send message"
              aria-label="Send message"
            >
              <SendIcon />
            </button>
          </form>
        </div>
      </section>

      <aside className={showMobileResults ? "chat-result-column open" : "chat-result-column"} aria-label="Shot result">
        <div className="mobile-results-header">
          <strong>Shot Analysis</strong>
          <button type="button" onClick={() => setShowMobileResults(false)} aria-label="Close shot analysis">
            Close
          </button>
        </div>
        {result ? (
          <ShotResult
            result={result}
            manualStart={manualStart}
            manualStop={manualStop}
            onManualStartChange={setManualStart}
            onManualStopChange={setManualStop}
            onApplyTiming={handleApplyTiming}
          />
        ) : (
          <section className="panel empty-state">
            <p>The coach will show timing and grind guidance here after it has enough shot details.</p>
          </section>
        )}
      </aside>
    </div>
  );
}




function shouldShowMessageText(message: UiMessage) {
  if (!message.content.trim()) {
    return false;
  }
  if (message.preview_kind === "image" && message.content === "I uploaded a photo.") {
    return false;
  }
  if (message.preview_kind === "video" && isVideoPathMessage(message.content)) {
    return false;
  }
  return true;
}

function isVideoPathMessage(content: string) {
  return /(?:^data\/|\.(?:mp4|mov|m4v)(?:$|[\s.,]))/i.test(content.trim());
}

function MediaPreview({ message }: { message: UiMessage }) {
  if (!message.preview_url) {
    return null;
  }

  if (message.preview_kind === "video") {
    return (
      <video className="chat-media-preview" src={message.preview_url} controls preload="metadata">
        Your browser does not support video preview.
      </video>
    );
  }

  return <img className="chat-media-preview" src={message.preview_url} alt={message.preview_name || "Attached preview"} />;
}

function createMediaPreviewUrl(file: File, objectUrls: string[]) {
  const previewUrl = URL.createObjectURL(file);
  objectUrls.push(previewUrl);
  return previewUrl;
}

function PaperclipIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path d="M8.5 12.5L14.7 6.3a3.2 3.2 0 0 1 4.5 4.5l-7.6 7.6a5 5 0 0 1-7.1-7.1l7.7-7.7" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path d="M4 12L20 4l-4.5 16-3.2-6.6L4 12z" />
      <path d="M12.3 13.4L20 4" />
    </svg>
  );
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatInputTime(value: number | null | undefined) {
  return typeof value === "number" ? String(round(value)) : "";
}

function hasNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value);
}

function round(value: number) {
  return Math.round(value * 100) / 100;
}

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}


function inferImageKind(context: ShotFormValues): "machine" | "grinder" {
  if (context.pending_gear_type === "grinder") {
    return "grinder";
  }
  if (context.pending_gear_type === "machine") {
    return "machine";
  }
  if (!context.machine) {
    return "machine";
  }
  if (!context.uses_built_in_grinder && !context.grinder) {
    return "grinder";
  }
  return "machine";
}

function isVideoFile(fileName: string) {
  return /\.(mp4|mov|m4v)$/i.test(fileName);
}

function isImageFile(fileName: string) {
  return /\.(png|jpe?g|webp|heic)$/i.test(fileName);
}
