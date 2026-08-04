import { ChatCoach } from "../components/chat-coach";

export default function Home() {
  return (
    <main className="page-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">DialedIN</span>
          <h1>AI Shot Analysis</h1>
          <p>A guided chat that collects shot context, analyzes timing, and recommends the next grind setting.</p>
        </div>
      </header>

      <ChatCoach />
    </main>
  );
}
