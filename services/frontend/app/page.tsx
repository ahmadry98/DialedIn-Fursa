import { ChatCoach } from "../components/chat-coach";

export default function Home() {
  return (
    <main className="page-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">DialedIN</span>
          <h1>Espresso Shot Review</h1>
          <p>A guided chat that collects shot context, analyzes timing, and recommends the next grind setting.</p>
        </div>
        <div className="header-stats" aria-label="Pipeline">
          <span>Chat</span>
          <span>Audio</span>
          <span>Recommendation</span>
        </div>
      </header>

      <ChatCoach />
    </main>
  );
}
