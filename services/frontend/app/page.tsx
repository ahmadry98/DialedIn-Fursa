import { ShotUpload } from "../components/shot-upload";

export default function Home() {
  return (
    <main className="page-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">DialedIN</span>
          <h1>Espresso Shot Review</h1>
          <p>Audio timing, machine context, and grind adjustment in one pass.</p>
        </div>
        <div className="header-stats" aria-label="Pipeline">
          <span>Audio</span>
          <span>Machine profile</span>
          <span>Recommendation</span>
        </div>
      </header>

      <ShotUpload />
    </main>
  );
}
