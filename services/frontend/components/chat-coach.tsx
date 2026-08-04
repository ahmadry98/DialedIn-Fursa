"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { analyzeShot, AnalyzeShotResponse, chatWithCoach, ChatMessage, ShotFormValues } from "../lib/api";
import { ShotResult } from "./shot-result";

type UiMessage = ChatMessage & { id: string };

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
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, result]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setInput("");
    await sendMessage(trimmed);
  }

  async function sendMessage(content: string, image?: Pick<ChatMessage, "image_base64" | "image_media_type" | "image_kind">) {
    const userMessage: UiMessage = { id: makeId("user"), role: "user", content, ...image };
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
      await sendMessage(`data/raw-videos/${file.name}`);
      return;
    }

    if (!file.type.startsWith("image/") && !isImageFile(file.name)) {
      setError("Attach an image of the machine/grinder or a shot video.");
      return;
    }

    const kind = inferImageKind(shotContext);
    setIsLoading(true);
    setError("");
    try {
      const imageBase64 = await readFileAsBase64(file);
      await sendMessage("I uploaded a photo.", {
        image_base64: imageBase64,
        image_media_type: file.type || "image/jpeg",
        image_kind: kind,
      });
    } catch (requestError) {
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
              <p>{message.content}</p>
              {message.image_base64 ? <span className="chat-image-note">Photo attached</span> : null}
            </div>
          ))}
          {isLoading ? (
            <div className="chat-message assistant pending">
              <p>Thinking through the shot...</p>
            </div>
          ) : null}
          <div ref={messageEndRef} />
        </div>

        <div className="context-strip" aria-label="Collected shot context">
          {contextItems(shotContext).map((item) => (
            <span className={item.ready ? "context-chip ready" : "context-chip"} key={item.label}>
              {item.label}: {item.value || "needed"}
            </span>
          ))}
        </div>

        {error ? <div className="alert" role="alert">{error}</div> : null}

        <div className="chat-input-dock">
          <div className="attachment-toolbar" aria-label="Attachments">
            <label className="attachment-button" title="Attach a setup photo or shot video">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/heic,image/heif,image/*,video/mp4,video/quicktime,video/x-m4v,video/*"
                onChange={(event) => {
                  handleAttachmentSelected(event.target.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
              <span>Attach photo/video</span>
            </label>
            <span className="attachment-hint">Use a machine/grinder photo or a shot video.</span>
          </div>

          <form className="chat-composer" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Type a reply, a full shot description, or 27 seconds"
              aria-label="Message"
            />
            <button className="primary-button" type="submit" disabled={isLoading || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      </section>

      <aside className="chat-result-column" aria-label="Shot result">
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

function contextItems(context: ShotFormValues) {
  return [
    { label: "Machine", value: context.machine, ready: Boolean(context.machine) },
    {
      label: "Grinder",
      value: context.uses_built_in_grinder ? "Built-in" : context.grinder,
      ready: Boolean(context.uses_built_in_grinder || context.grinder),
    },
    {
      label: "Dose",
      value: hasNumber(context.dose_g) ? `${context.dose_g}g` : "",
      ready: hasNumber(context.dose_g),
    },
    { label: "Grind", value: context.grind_setting, ready: Boolean(context.grind_setting) },
    { label: "Roast", value: context.roast_level, ready: Boolean(context.roast_level) },
    { label: "Taste", value: context.taste, ready: Boolean(context.taste) },
    {
      label: "Timing",
      value: context.video_s3_key || (hasNumber(context.total_shot_seconds) ? `${context.total_shot_seconds}s` : ""),
      ready: Boolean(context.video_s3_key || hasNumber(context.total_shot_seconds)),
    },
  ];
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
