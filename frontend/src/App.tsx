import { useEffect, useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import type { FormEvent } from "react";
import {
  loginStudent,
  loginWithGoogle,
  getSubjects,
  getChapters,
  generateChapterQuestions,
  submitAssessment,
  submitGeneratedAssessment,
  getAttemptReview,
  getMyAttempts,
  getMLPerformance,
  getBloomProfile,
  type Subject,
  type Chapter,
  type Question,
  type GeneratedQuestion,
  type AssessmentResponse,
  type AttemptHistory,
  type MLPerformanceResponse,
  type BloomProfileResponse,
} from "./api";
import "./App.css";
import Home from "./pages/Home";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type Page = "login" | "register" | "home" | "dashboard" | "subjects" | "chapters" | "assessment" | "results";


function BloomRadarChart({ profile }: { profile: import("./api").BloomProfileResponse }) {
  const levels = profile.levels;
  const center = 150;
  const radius = 105;
  const angleFor = (index: number) => (-Math.PI / 2) + (index * 2 * Math.PI / 6);
  const point = (index: number, value: number) => ({
    x: center + Math.cos(angleFor(index)) * radius * (value / 100),
    y: center + Math.sin(angleFor(index)) * radius * (value / 100),
  });
  const gridPolygons = [20, 40, 60, 80, 100].map((value) =>
    levels.map((_, index) => {
      const p = point(index, value);
      return `${p.x},${p.y}`;
    }).join(" ")
  );
  const knownPoints = levels
    .map((item, index) => item.score === null ? null : point(index, item.score))
    .filter((item): item is { x: number; y: number } => item !== null);
  // Draw the filled radar area whenever at least three Bloom levels have data.
  // Levels without scores remain unavailable rather than being treated as zero.
  const polygon = knownPoints.length >= 3
    ? knownPoints.map((p) => `${p.x},${p.y}`).join(" ")
    : "";
  return (
    <div className="bloom-chart-layout">
      <svg className="bloom-radar-chart" viewBox="0 0 300 300" role="img" aria-label="Bloom's Taxonomy performance radar chart">
        {gridPolygons.map((points, index) => <polygon key={index} points={points} className="bloom-grid" />)}
        {levels.map((item, index) => {
          const outer = point(index, 100);
          const label = {
            x: center + Math.cos(angleFor(index)) * 128,
            y: center + Math.sin(angleFor(index)) * 128,
          };
          const anchor = label.x < center - 10 ? "end" : label.x > center + 10 ? "start" : "middle";
          return <g key={item.level}>
            <line x1={center} y1={center} x2={outer.x} y2={outer.y} className="bloom-axis" />
            <text x={label.x} y={label.y} textAnchor={anchor} dominantBaseline="middle" className="bloom-axis-label">{item.level}</text>
          </g>;
        })}
        {polygon && <polygon points={polygon} className="bloom-data-area" />}
        {levels.map((item, index) => item.score === null ? null : (() => {
          const p = point(index, item.score as number);
          return <circle key={item.level} cx={p.x} cy={p.y} r="4" className="bloom-data-point" />;
        })())}
      </svg>
      <div className="bloom-score-list">
        {levels.map((item) => <div className="bloom-score-row" key={item.level}>
          <span>{item.level}</span>
          <strong>{item.score === null ? "Not enough data" : `${item.score}%`}</strong>
          <small>{item.question_count} question{item.question_count === 1 ? "" : "s"}</small>
        </div>)}
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>(() => {
    const savedPage = window.history.state?.discipulusPage as Page | undefined;
    return savedPage ?? "home";
  });

  // Keep React's current screen synchronized with the browser Back/Forward buttons.
  useEffect(() => {
    if (!window.history.state?.discipulusPage) {
      window.history.replaceState({ ...window.history.state, discipulusPage: page }, "", window.location.href);
    }

    function handlePopState(event: PopStateEvent) {
      const restoredPage = event.state?.discipulusPage as Page | undefined;
      setPage(restoredPage ?? "home");
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigateTo(nextPage: Page) {
    if (nextPage === page) return;
    window.history.pushState({ ...window.history.state, discipulusPage: nextPage }, "", window.location.href);
    setPage(nextPage);
  }

  // Authentication transitions replace the current history entry so Back does not
  // immediately reopen the login/register screen from the same transition.
  function replacePage(nextPage: Page) {
    window.history.replaceState({ ...window.history.state, discipulusPage: nextPage }, "", window.location.href);
    setPage(nextPage);
  }
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [registering, setRegistering] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState("");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loggedInUser, setLoggedInUser] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [classLevel, setClassLevel] = useState<11 | 12>(11);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [generatedQuestions, setGeneratedQuestions] = useState<GeneratedQuestion[]>([]);
  const [generatedAssessmentId, setGeneratedAssessmentId] = useState<number | null>(null);
  const [selectedReview, setSelectedReview] = useState<(AssessmentResponse & { title?: string }) | null>(null);
  const [loadingReviewId, setLoadingReviewId] = useState<number | null>(null);
  const [topic, setTopic] = useState("");
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState("");
  const [selectedChapter, setSelectedChapter] = useState("");
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState<AttemptHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [mlPerformance, setMLPerformance] = useState<MLPerformanceResponse | null>(null);
  const [loadingML, setLoadingML] = useState(false);
  const [mlError, setMLError] = useState("");
  const [bloomProfile, setBloomProfile] = useState<BloomProfileResponse | null>(null);
  const [loadingBloomProfile, setLoadingBloomProfile] = useState(false);
  const [bloomProfileError, setBloomProfileError] = useState("");

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoggingIn(true);
    setError("");
    try {
      const response = await loginStudent(email, password);
      setAccessToken(response.access_token);
      setLoggedInUser(response.user.full_name || response.user.email);
      setClassLevel(response.user.class_level as 11 | 12);
      setPassword("");
      replacePage("home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoggingIn(false);
    }
  }


  async function handleGoogleSuccess(credentialResponse: { credential?: string }) {
    if (!credentialResponse.credential) {
      setError("Google sign-in did not return a credential. Please try again.");
      return;
    }

    setLoggingIn(true);
    setError("");
    setRegistrationMessage("");
    try {
      // Existing Google users sign in with their saved class. Only the
      // registration screen sends a class selection for a new account.
      const response = await loginWithGoogle(
        credentialResponse.credential,
        page === "register" ? classLevel : undefined,
      );
      setAccessToken(response.access_token);
      setLoggedInUser(response.user.full_name || response.user.email);
      setClassLevel(response.user.class_level as 11 | 12);
      setPassword("");
      setConfirmPassword("");
      replacePage("home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed.");
    } finally {
      setLoggingIn(false);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setRegistrationMessage("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }
    setRegistering(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName.trim(), email: email.trim(), password, class_level: classLevel }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || "Could not create your account.");
      }
      setRegistrationMessage("Account created successfully. You can now log in.");
      setPassword("");
      setConfirmPassword("");
      replacePage("login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setRegistering(false);
    }
  }

  function handleLogout() {
    setAccessToken(null);
    setLoggedInUser("");
    setPassword("");
    setAttempts([]);
    setHistoryError("");
    setMLPerformance(null);
    setMLError("");
    setBloomProfile(null);
    setBloomProfileError("");
    setResult(null);
    setAnswers({});
    setSelectedSubject("");
    setSelectedChapter("");
    setQuestions([]);
    setGeneratedQuestions([]);
    setTopic("");
    setChapters([]);
    setError("");
    setMLError("");
    setLoadingML(false);
    replacePage("login");
  }

  useEffect(() => {
    let cancelled = false;
    async function loadSubjects() {
      setLoadingSubjects(true);
      try {
        const data = await getSubjects(classLevel);
        if (!cancelled) setSubjects(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load subjects.");
      } finally {
        if (!cancelled) setLoadingSubjects(false);
      }
    }
    void loadSubjects();
    return () => { cancelled = true; };
  }, [classLevel]);

  useEffect(() => {
    let cancelled = false;
    async function loadChapters() {
      setChapters([]);
      setSelectedChapter("");
      setQuestions([]);
      setGeneratedQuestions([]);
      setAnswers({});
      setResult(null);
      if (!selectedSubject) { setLoadingChapters(false); return; }
      setLoadingChapters(true);
      try {
        const data = await getChapters(Number(selectedSubject));
        if (!cancelled) setChapters(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load chapters.");
      } finally {
        if (!cancelled) setLoadingChapters(false);
      }
    }
    void loadChapters();
    return () => { cancelled = true; };
  }, [selectedSubject]);

  useEffect(() => {
    // AI questions are generated on demand rather than loaded automatically from PostgreSQL.
    setQuestions([]);
    setGeneratedQuestions([]);
    setAnswers({});
    setResult(null);
    setTopic("");
  }, [selectedChapter]);

  useEffect(() => {
    let cancelled = false;
    async function loadHistory() {
      if (!accessToken) { setAttempts([]); setLoadingHistory(false); return; }
      setLoadingHistory(true);
      setHistoryError("");
      try {
        const data = await getMyAttempts(accessToken);
        if (!cancelled) setAttempts(data);
      } catch (err) {
        if (!cancelled) setHistoryError(err instanceof Error ? err.message : "Could not load assessment history.");
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    }
    void loadHistory();
    return () => { cancelled = true; };
  }, [accessToken, historyRefresh]);

  const chapterAttemptCounts = attempts.reduce<Record<number, number>>((counts, attempt) => {
    counts[attempt.chapter_id] = (counts[attempt.chapter_id] || 0) + 1;
    return counts;
  }, {});
  const eligibleChapterId = selectedChapter && (chapterAttemptCounts[Number(selectedChapter)] || 0) >= 2
    ? Number(selectedChapter)
    : (attempts.find((attempt) => (chapterAttemptCounts[attempt.chapter_id] || 0) >= 2)?.chapter_id ?? null);

  useEffect(() => {
    let cancelled = false;
    async function loadML() {
      if (!accessToken || loadingHistory || eligibleChapterId === null) {
        setMLPerformance(null); setMLError(""); setLoadingML(false); return;
      }
      setLoadingML(true); setMLError(""); setMLPerformance(null);
      try {
        const data = await getMLPerformance(eligibleChapterId, accessToken);
        if (!cancelled) setMLPerformance(data);
      } catch (err) {
        if (!cancelled) { setMLPerformance(null); setMLError(err instanceof Error ? err.message : "Could not load ML performance."); }
      } finally { if (!cancelled) setLoadingML(false); }
    }
    void loadML();
    return () => { cancelled = true; };
  }, [accessToken, eligibleChapterId, historyRefresh, loadingHistory]);

  useEffect(() => {
    let cancelled = false;
    async function loadBloomProfile() {
      if (!accessToken || page !== "dashboard") return;
      setLoadingBloomProfile(true);
      setBloomProfileError("");
      try {
        const profile = await getBloomProfile(accessToken);
        if (!cancelled) setBloomProfile(profile);
      } catch (err) {
        if (!cancelled) setBloomProfileError(
          err instanceof Error ? err.message : "Could not load Bloom's Taxonomy analytics."
        );
      } finally {
        if (!cancelled) setLoadingBloomProfile(false);
      }
    }
    void loadBloomProfile();
    return () => { cancelled = true; };
  }, [accessToken, page, historyRefresh]);

  const averagePercentage = attempts.length
    ? Math.round((attempts.reduce((sum, attempt) => sum + attempt.percentage, 0) / attempts.length) * 100) / 100
    : 0;
  function getOptionText(question: Question, option: string) {
    return ({ A: question.option_a, B: question.option_b, C: question.option_c, D: question.option_d } as Record<string, string>)[option];
  }

  async function handleGenerateQuestions() {
    if (!accessToken) { setError("Please log in before generating an assessment."); return; }
    if (!selectedChapter) { setError("Please select a chapter first."); return; }
    setGeneratingQuestions(true); setError(""); setGeneratedQuestions([]); setGeneratedAssessmentId(null); setQuestions([]); setAnswers({}); setResult(null);
    try {
      const response = await generateChapterQuestions(Number(selectedChapter), accessToken, topic, 5);
      setGeneratedAssessmentId(response.assessment_id);
      setGeneratedQuestions(response.questions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate questions.");
    } finally { setGeneratingQuestions(false); }
  }

  async function handleSubmit() {
    if (!accessToken) { setError("Please log in before submitting an assessment."); return; }
    if (!selectedChapter) return;
    setSubmitting(true); setError("");
    try {
      if (generatedQuestions.length > 0 && generatedAssessmentId !== null) {
        const unanswered = generatedQuestions.filter((question) => !(answers[question.id] || "").trim());
        if (unanswered.length > 0) {
          setError("Please answer every question before submitting.");
          return;
        }
        const response = await submitGeneratedAssessment(
          generatedAssessmentId,
          generatedQuestions.map((question) => ({ question_id: question.id, answer: answers[question.id] || "" })),
          accessToken,
        );
        setResult(response);
      } else {
        if (questions.length === 0) { setError("Generate an AI assessment first."); return; }
        if (Object.keys(answers).length !== questions.length) { setError("Please answer every question before submitting."); return; }
        const response = await submitAssessment(
          Number(selectedChapter),
          questions.map((question) => ({ question_id: question.id, selected_option: answers[question.id] })),
          accessToken,
        );
        setResult(response);
      }
      setHistoryRefresh((previous) => previous + 1);
      navigateTo("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit assessment.");
    } finally { setSubmitting(false); }
  }

  async function handleOpenReview(attemptId: number) {
    if (!accessToken) return;
    setLoadingReviewId(attemptId);
    setHistoryError("");
    try {
      const review = await getAttemptReview(attemptId, accessToken);
      setSelectedReview(review);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Could not load this review.");
    } finally { setLoadingReviewId(null); }
  }

  function pageTitle() {
    const titles: Record<Page, string> = { login: "Student Login", register: "Create Account", home: "Home", dashboard: "Your Learning Dashboard", subjects: "Choose a Subject", chapters: "Choose a Chapter", assessment: "Chapter Assessment", results: "Assessment Results" };
    return titles[page];
  }

  return (
    <main>
      {page !== "login" && page !== "register" && (
        <header className="app-header">
          <h1>Discipulus-AI</h1>
          <p>Personalized learning for Class XI and XII PCMB students.</p>
        </header>
      )}

      {page === "home" && (
        <nav className="top-nav" aria-label="Main navigation">
          <span className="nav-welcome">Hi, {accessToken ? (loggedInUser || "Student") : "Guest"}</span>
          <div className="nav-actions">
            {!accessToken && (
              <>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => { setError(""); setRegistrationMessage(""); navigateTo("login"); }}
                >
                  Log in
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => { setError(""); setRegistrationMessage(""); navigateTo("register"); }}
                >
                  Sign up
                </button>
              </>
            )}
            {accessToken && (
              <>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => navigateTo("subjects")}
                >
                  Take Assessment
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => navigateTo("dashboard")}
                >
                  My Dashboard
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={handleLogout}
                >
                  Log out
                </button>
              </>
            )}
            <button className="secondary-button" type="button" onClick={() => navigateTo("home")}>Home</button>
          </div>
        </nav>
      )}

      {accessToken && page !== "home" && (
        <nav className="top-nav" aria-label="Student navigation">
          <span className="nav-welcome">Hi, {loggedInUser || "Student"}</span>
          <button className="secondary-button" type="button" onClick={() => navigateTo("home")}>Home</button>
          <button className="secondary-button" type="button" onClick={() => navigateTo("dashboard")}>Dashboard</button>
          <button className="secondary-button" type="button" onClick={() => navigateTo("subjects")}>Subjects</button>
          <button className="secondary-button" type="button" onClick={handleLogout}>Log out</button>
        </nav>
      )}

      {page !== "login" && page !== "register" && page !== "home" && <div className="page-heading">
        <h2>{pageTitle()}</h2>
      </div>}

      {error && <p role="alert">{error}</p>}

      {page === "login" && (
        <section className="login-page" aria-labelledby="login-welcome-title">
          <div className="login-brand-mark" aria-hidden="true"><span>↪</span></div>
          <div className="login-welcome">
            <p className="login-eyebrow">DISCIPULUS-AI</p>
            <h1 id="login-welcome-title">Welcome back</h1>
            <p>Log in to your account</p>
          </div>
          <section className="page-card login-card">
            <form onSubmit={(event) => void handleLogin(event)}>
              <div className="form-field login-input-field">
                <label htmlFor="login-email"><span className="field-icon" aria-hidden="true">✉</span>Email</label>
                <input id="login-email" type="email" autoComplete="username" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </div>
              <div className="form-field login-input-field">
                <label htmlFor="login-password"><span className="field-icon" aria-hidden="true">▣</span>Password</label>
                <input id="login-password" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} required />
              </div>
              <button className="login-submit" type="submit" disabled={loggingIn}>{loggingIn ? "Logging in…" : "Log in"}</button>
            </form>
            <div className="google-auth-divider" aria-hidden="true"><span>OR</span></div>
            <div className="google-auth-control">
              <GoogleLogin
                onSuccess={(credentialResponse) => void handleGoogleSuccess(credentialResponse)}
                onError={() => setError("Google sign-in failed. Please try again.")}
                text="continue_with"
                shape="pill"
                theme="outline"
                size="large"
                width="320"
              />
            </div>
          </section>
          {registrationMessage && <p className="registration-success" role="status">{registrationMessage}</p>}
          <p className="login-footer-note">Don’t have an account? <button className="inline-link" type="button" onClick={() => { setError(""); setRegistrationMessage(""); navigateTo("register"); }}>Create one</button></p>
          <p className="login-footer-note login-tagline">Personalized learning for Class XI and XII PCMB students.</p>
        </section>
      )}

      {page === "register" && (
        <section className="login-page register-page" aria-labelledby="register-title">
          <div className="login-brand-mark" aria-hidden="true"><span>♙+</span></div>
          <div className="login-welcome">
            <h1 id="register-title">Create your account</h1>
            <p>Sign up to start your personalized learning journey</p>
          </div>
          <section className="page-card login-card register-card">
            <div className="register-role-label">I am a...</div>
            <div className="register-role-choice" aria-label="Account type">
              <div className="register-role-option selected"><span aria-hidden="true">♧</span><strong>Student</strong></div>
            </div>
            <form onSubmit={(event) => void handleRegister(event)}>
              <div className="form-field login-input-field">
                <label htmlFor="register-name"><span className="field-icon" aria-hidden="true">♙</span>Full name</label>
                <input id="register-name" type="text" autoComplete="name" placeholder="Your full name" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
              </div>
              <div className="form-field login-input-field">
                <label htmlFor="register-email"><span className="field-icon" aria-hidden="true">✉</span>Email</label>
                <input id="register-email" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </div>
              <div className="form-field login-input-field">
                <label htmlFor="register-class"><span className="field-icon" aria-hidden="true">▤</span>Class</label>
                <select id="register-class" value={classLevel} onChange={(event) => setClassLevel(Number(event.target.value) as 11 | 12)}><option value={11}>Class XI</option><option value={12}>Class XII</option></select>
              </div>
              <div className="form-field login-input-field">
                <label htmlFor="register-password"><span className="field-icon" aria-hidden="true">▣</span>Password</label>
                <input id="register-password" type="password" autoComplete="new-password" placeholder="At least 8 characters" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required />
              </div>
              <div className="form-field login-input-field">
                <label htmlFor="register-confirm"><span className="field-icon" aria-hidden="true">▣</span>Confirm password</label>
                <input id="register-confirm" type="password" autoComplete="new-password" placeholder="Re-enter your password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={8} required />
              </div>
              <button className="login-submit" type="submit" disabled={registering}>{registering ? "Creating account…" : "Create account"}</button>
            </form>
            <div className="google-auth-divider" aria-hidden="true"><span>OR</span></div>
            <div className="google-auth-control">
              <GoogleLogin
                onSuccess={(credentialResponse) => void handleGoogleSuccess(credentialResponse)}
                onError={() => setError("Google sign-in failed. Please try again.")}
                text="continue_with"
                shape="pill"
                theme="outline"
                size="large"
                width="320"
              />
            </div>
          </section>
          {registrationMessage && <p className="registration-success" role="status">{registrationMessage}</p>}
          <p className="login-footer-note">Already have an account? <button className="inline-link" type="button" onClick={() => { setError(""); setRegistrationMessage(""); navigateTo("login"); }}>Log in</button></p>
        </section>
      )}

      {page === "home" && (
        <Home studentName={loggedInUser || "Guest"} onStartAssessment={() => navigateTo(accessToken ? "subjects" : "login")} onViewDashboard={() => navigateTo(accessToken ? "dashboard" : "login")} />
      )}

      {page === "dashboard" && accessToken && (
        <>
          <section className="page-card welcome-card">
            <p>Welcome back, <strong>{loggedInUser || "Student"}</strong>.</p>
            <p>Choose a class to explore your PCMB subjects and continue learning.</p>
            <div className="form-field class-picker"><label htmlFor="class-level">Your class</label><select id="class-level" value={classLevel} onChange={(event) => { setClassLevel(Number(event.target.value) as 11 | 12); setSelectedSubject(""); setSelectedChapter(""); }}><option value={11}>Class XI</option><option value={12}>Class XII</option></select></div>
            <button type="button" onClick={() => navigateTo("subjects")}>Explore subjects →</button>
          </section>
          <section className="page-card">
            <h3>My Learning History</h3>
            {loadingHistory ? <p>Loading your assessment history…</p> : historyError ? <p role="alert">{historyError}</p> : attempts.length === 0 ? <p>No assessments yet. Start with a subject and complete your first chapter assessment.</p> : <>
              <div className="summary-grid"><article className="summary-tile"><span>Total attempts</span><strong>{attempts.length}</strong></article><article className="summary-tile"><span>Average score</span><strong>{averagePercentage}%</strong></article></div>
              <section className="bloom-analytics-card">
                <div className="bloom-section-heading">
                  <div><span className="bloom-kicker">PERSONALIZED LEARNING</span><h3>Bloom's Taxonomy Distribution</h3></div>
                  <span className="bloom-ml-tag">Learning analytics</span>
                </div>
                {loadingBloomProfile ? <p>Calculating your cognitive-skill profile…</p> :
                  bloomProfileError ? <p className="muted-text" role="status">{bloomProfileError}</p> :
                  bloomProfile ? <>
                    {bloomProfile.data_points > 0
                      ? <BloomRadarChart profile={bloomProfile} />
                      : <p className="muted-text">Complete an AI-generated assessment with saved question-level marks to populate this chart.</p>}
                    <div className="bloom-recommendations">
                      <h4>Recommended next steps</h4>
                      {bloomProfile.recommendations.map((recommendation, index) => <p key={index}>{recommendation}</p>)}
                    </div>
                    <p className="bloom-data-note">Scores are calculated from saved assessment marks. Levels without assessed questions are shown as unavailable, not zero.</p>
                  </> : <p className="muted-text">Bloom analytics are not available yet.</p>}
              </section>
              <h3>Recent assessments</h3>
              {attempts.slice(0, 10).map((attempt) => (
                <article className="history-item" key={attempt.attempt_id}>
                  <h4>{attempt.title}</h4>
                  <p>Score: <strong>{attempt.score}/{attempt.total_questions}</strong> · {attempt.percentage}%</p>
                  <p className="muted-text">{attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : "Date unavailable"}</p>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => void handleOpenReview(attempt.attempt_id)}
                    disabled={loadingReviewId === attempt.attempt_id}
                  >
                    {loadingReviewId === attempt.attempt_id ? "Loading feedback…" : "View feedback"}
                  </button>
                </article>
              ))}
              {selectedReview && <section className="dashboard-review"><h3>{selectedReview.title || "Assessment feedback"}</h3><div className="result-score"><span>Your score</span><strong>{selectedReview.percentage}%</strong><p>{selectedReview.score}/{selectedReview.total_score ?? selectedReview.total_questions} marks</p></div>{selectedReview.overall_feedback && <p>{selectedReview.overall_feedback}</p>}{selectedReview.results.map((item, index) => <article className="review-item" key={item.question_id}><h4>Question {index + 1}: {item.question}</h4><p><strong>Your answer:</strong> {item.student_answer || "Not answered"}</p><p><strong>Marks:</strong> {item.score_awarded ?? (item.is_correct ? 1 : 0)}/{item.max_score ?? 1}</p>{!item.is_correct && <p><strong>Correct answer:</strong> {item.correct_answer || item.expected_answer || item.correct_option || "Review the explanation below."}</p>}{item.feedback && <p><strong>Feedback:</strong> {item.feedback}</p>}{item.strengths?.length ? <p><strong>What you did well:</strong> {item.strengths.join("; ")}</p> : null}{item.improvements?.length ? <p><strong>How to improve:</strong> {item.improvements.join("; ")}</p> : null}{item.explanation && <p><strong>Explanation:</strong> {item.explanation}</p>}</article>)}<button type="button" className="secondary-button" onClick={() => setSelectedReview(null)}>Close feedback</button></section>}
            </>}
          </section>
          <section className="page-card">
            <h3>My Learning Performance</h3>
            {loadingHistory || loadingML ? <p>Analyzing your learning performance…</p> : historyError ? <p>Performance analysis is unavailable until history loads successfully.</p> : mlError ? <p role="alert">{mlError}</p> : !mlPerformance ? <p>Complete at least two assessments in the same chapter to view your performance analysis.</p> : <>
              <div className="performance-highlight"><span>Performance level</span><strong>{mlPerformance.performance_level}</strong></div>
              <div className="summary-grid"><article className="summary-tile"><span>Latest score</span><strong>{mlPerformance.current_percentage}%</strong></article><article className="summary-tile"><span>Previous score</span><strong>{mlPerformance.previous_percentage}%</strong></article><article className="summary-tile"><span>Score change</span><strong>{mlPerformance.improvement > 0 ? "+" : ""}{mlPerformance.improvement} pts</strong></article></div>
              <p className="muted-text">Model confidence: {(mlPerformance.confidence * 100).toFixed(2)}%. Demonstration model trained on synthetic data; educational validity has not been established.</p>
            </>}
          </section>
        </>
      )}

      {page === "subjects" && accessToken && (
        <section className="page-card">
          <div className="selection-summary"><span>Selected class</span><strong>Class {classLevel === 11 ? "XI" : "XII"}</strong><button className="text-button" type="button" onClick={() => navigateTo("dashboard")}>Change class</button></div>
          {loadingSubjects ? <p>Loading subjects…</p> : <div className="subject-grid">{subjects.map((subject) => <button className={`subject-card ${selectedSubject === String(subject.id) ? "selected" : ""}`} type="button" key={subject.id} onClick={() => { setSelectedSubject(String(subject.id)); navigateTo("chapters"); setError(""); }}><span className="subject-symbol">{subject.name.toLowerCase().startsWith("physics") ? "⚛" : subject.name.toLowerCase().startsWith("chemistry") ? "⚗" : subject.name.toLowerCase().startsWith("biology") ? "⌬" : "∑"}</span><strong>{subject.name}</strong><span>Explore chapters →</span></button>)}</div>}
          {!loadingSubjects && subjects.length === 0 && <p>No subjects are available for this class yet.</p>}
        </section>
      )}

      {page === "chapters" && accessToken && (
        <section className="page-card">
          <div className="selection-summary"><span>Subject</span><strong>{subjects.find((subject) => String(subject.id) === selectedSubject)?.name || "Selected subject"}</strong></div>
          {loadingChapters ? <p>Loading chapters…</p> : chapters.length === 0 ? <p>No chapters are available for this subject yet.</p> : <div className="chapter-list">{chapters.map((chapter) => <button className="chapter-card" type="button" key={chapter.id} onClick={() => { setSelectedChapter(String(chapter.id)); navigateTo("assessment"); setError(""); }}><span className="chapter-number">{String(chapter.chapter_number).padStart(2, "0")}</span><span className="chapter-copy"><strong>{chapter.title}</strong><small>Chapter {chapter.chapter_number}</small></span><span className="chapter-arrow">→</span></button>)}</div>}
        </section>
      )}

      {page === "assessment" && accessToken && (
        <section className="page-card">
          <div className="selection-summary"><span>{subjects.find((subject) => String(subject.id) === selectedSubject)?.name || "Subject"}</span><strong>{chapters.find((chapter) => String(chapter.id) === selectedChapter)?.title || "Selected chapter"}</strong></div>
          <div className="form-field"><label htmlFor="assessment-topic">Topic (optional)</label><input id="assessment-topic" type="text" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="e.g. Acceleration" maxLength={200} /></div>
          <p className="section-intro">Generate a fresh, chapter-specific assessment using AI. Questions are generated when you click the button.</p>
          <div className="assessment-footer"><span>{generatedQuestions.length ? `${generatedQuestions.length} questions generated` : "Ready to generate"}</span><button type="button" disabled={generatingQuestions || !selectedChapter} onClick={() => void handleGenerateQuestions()}>Generate AI Assessment</button></div>

          {generatedQuestions.length > 0 && <>
            <h3>Your AI-Generated Assessment</h3>
            {generatedQuestions.map((question, index) => <fieldset key={question.id} className="generated-question">
              <legend>Question {index + 1} of {generatedQuestions.length}</legend><p className="question-prompt">{question.question}</p>
              <p className="muted-text">{question.topic} · {question.bloom_level} · {question.difficulty} · {question.question_type === "mcq" ? "Multiple choice" : "Written response"}</p>
              {question.question_type === "mcq" ? <div className="generated-options">{question.options.map((option, optionIndex) => {
                const optionLetter = ["A", "B", "C", "D"][optionIndex];
                return <label className={`answer-option ${answers[question.id] === optionLetter ? "chosen" : ""}`} key={`${question.id}-${optionIndex}`}>
                  <input type="radio" name={`generated-question-${question.id}`} value={optionLetter} checked={answers[question.id] === optionLetter} onChange={() => setAnswers((previous) => ({ ...previous, [question.id]: optionLetter }))} />
                  <span><strong>{optionLetter}.</strong> {option.replace(/^[A-D][).:]\s*/, "")}</span>
                </label>;
              })}</div> : (
                <div className="written-answer-panel">
                  <label className="written-answer-label" htmlFor={`written-answer-${question.id}`}>
                    Your answer
                  </label>
                  <textarea
                    id={`written-answer-${question.id}`}
                    className="generated-written-answer"
                    rows={6}
                    value={answers[question.id] || ""}
                    onChange={(event) => setAnswers((previous) => ({ ...previous, [question.id]: event.target.value }))}
                    placeholder="Explain your reasoning step by step…"
                    aria-label={`Answer to question ${index + 1}`}
                  />
                  <div className="written-answer-footer">
                    <span>Show your working and include relevant formulas where needed.</span>
                    <span>{(answers[question.id] || "").length} characters</span>
                  </div>
                </div>
              )}
            </fieldset>)}
            <div className="assessment-submit-row">
              <p className="muted-text">Review your answers before submitting. AI will evaluate written responses and your results will be saved to your dashboard.</p>
              <button type="button" onClick={() => void handleSubmit()} disabled={submitting || generatingQuestions}>
                {submitting ? "Evaluating answers…" : "Submit Answers"}
              </button>
            </div>
          </>}
          {!generatingQuestions && generatedQuestions.length === 0 && <p className="muted-text">No AI questions generated yet. Select Generate AI Assessment to begin.</p>}
        </section>
      )}

      {page === "results" && accessToken && result && (
        <section className="page-card">
          <div className="result-score"><span>Your score</span><strong>{result.percentage}%</strong><p>{result.score} / {result.total_score ?? result.total_questions} marks</p></div>
          {result.overall_feedback && <p className="assessment-overall-feedback">{result.overall_feedback}</p>}
          <h3>Answer review</h3>
          {result.results.map((item, index) => {
            const staticQuestion = questions.find((candidate) => candidate.id === item.question_id);
            return <article className="review-item" key={item.question_id}>
              <h4>Question {index + 1}: {item.question || staticQuestion?.prompt || "Question"}</h4>
              <p><strong>Your answer:</strong> {item.student_answer || item.selected_option || "Not answered"}</p>
              <p><strong>Marks:</strong> {item.score_awarded ?? (item.is_correct ? 1 : 0)}/{item.max_score ?? 1}</p>
              <span className={item.is_correct ? "result-correct" : "result-incorrect"}>{item.is_correct ? "✓ Correct" : "✕ Needs review"}</span>
              {!item.is_correct && <p><strong>Correct answer:</strong> {item.correct_answer || item.expected_answer || (item.correct_option && staticQuestion ? getOptionText(staticQuestion, item.correct_option) : item.correct_option) || "See explanation below."}</p>}
              {item.feedback && <p><strong>Feedback:</strong> {item.feedback}</p>}
              {item.strengths?.length ? <p><strong>What you did well:</strong> {item.strengths.join("; ")}</p> : null}
              {item.improvements?.length ? <p><strong>How to improve:</strong> {item.improvements.join("; ")}</p> : null}
              {item.explanation && <p><strong>Explanation:</strong> {item.explanation}</p>}
            </article>;
          })}
          <div className="button-row"><button type="button" onClick={() => { setAnswers({}); setResult(null); setGeneratedQuestions([]); setGeneratedAssessmentId(null); navigateTo("assessment"); }}>Try another assessment</button><button className="secondary-button" type="button" onClick={() => navigateTo("dashboard")}>View dashboard</button></div>
        </section>
      )}

      <footer className="app-footer">Discipulus-AI · Personalized learning for PCMB students</footer>
    </main>
  );
}

export default App;
