import { ProfileCandidateReview } from "../../components/admin/profile-candidate-review";

export default function AdminPage() {
  return (
    <main className="page-shell admin-page-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">DialedIN Admin</span>
          <h1>Profile Candidate Review</h1>
          <p>Review unknown machine and grinder drafts, verify source evidence, and promote trusted profiles.</p>
        </div>
        <div className="header-stats" aria-label="Review steps">
          <span>Evidence</span>
          <span>Draft</span>
          <span>Promote</span>
        </div>
      </header>

      <ProfileCandidateReview />
    </main>
  );
}
