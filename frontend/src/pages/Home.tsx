import "./home.css";

type HomeProps = {
  studentName: string;
  onStartAssessment: () => void;
  onViewDashboard: () => void;
};

const features = [
  { number: "01", title: "Bloom’s Taxonomy Classification", description: "Explore questions designed around different levels of thinking and understanding." },
  { number: "02", title: "Misconception Detection", description: "Identify concepts that may need another explanation or more practice." },
  { number: "03", title: "Adaptive Question Engine", description: "Use assessment performance to guide what you practise next." },
  { number: "04", title: "Personalized Study Plan", description: "Focus your learning time on the topics that need the most attention." },
  { number: "05", title: "Cognitive Profile Dashboard", description: "Review your learning progress and performance patterns in one place." },
  { number: "06", title: "AI Feedback on Every Answer", description: "Review your answers and use feedback to guide your next attempt." },
];

const steps = [
  { number: "01", title: "Take an assessment", description: "Answer chapter-based questions in your PCMB subjects." },
  { number: "02", title: "Analyse your thinking", description: "Review your responses and identify areas that need attention." },
  { number: "03", title: "Discover learning gaps", description: "See which concepts may benefit from further practice." },
  { number: "04", title: "Get a personal plan", description: "Use your results to decide what to revise next." },
  { number: "05", title: "Improve and reassess", description: "Practise again and compare your progress over time." },
];

export default function Home({ studentName, onStartAssessment, onViewDashboard }: HomeProps) {
  return <div className="discipulus-home">
    <section className="home-hero">
      <div className="home-hero-copy">
        <span className="home-eyebrow">PERSONALIZED LEARNING · CLASS XI & XII PCMB</span>
        <h1>Understand how you think, <em>not just what you know.</em></h1>
        <p className="home-lead">Welcome{studentName ? `, ${studentName}` : ""}. Build a clearer picture of your understanding with assessments, focused feedback, and a learning path shaped around your progress.</p>
        <div className="home-actions"><button type="button" onClick={onStartAssessment}>Start Assessment <span aria-hidden="true">→</span></button><button type="button" className="home-secondary" onClick={onViewDashboard}>View My Dashboard</button></div>
        <div className="home-proof"><span><b>01</b> Remember</span><span><b>02</b> Understand</span><span><b>03</b> Apply</span><span><b>04</b> Analyze</span><span><b>05</b> Evaluate</span><span><b>06</b> Create</span></div>
      </div>
      <div className="home-hero-visual" aria-hidden="true"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="home-core"><span>DA</span><small>LEARNER<br/>PROFILE</small></div><div className="orbit-node node-a">↗<small>Growth</small></div><div className="orbit-node node-b">◈<small>Concepts</small></div><div className="orbit-node node-c">◎<small>Insight</small></div></div>
    </section>
    <section className="home-section home-features"><div className="home-section-heading"><span className="home-eyebrow">BUILT AROUND YOUR LEARNING</span><h2>More than a score.<br/><em>A clearer way forward.</em></h2><p>Tools that help you understand where you are and what to work on next.</p></div><div className="home-feature-grid">{features.map((feature) => <article className="home-feature-card" key={feature.number}><span className="home-card-number">{feature.number}</span><div className="home-card-mark" aria-hidden="true">✳</div><h3>{feature.title}</h3><p>{feature.description}</p><span className="home-card-arrow" aria-hidden="true">↗</span></article>)}</div></section>
    <section className="home-section home-how"><div className="home-section-heading"><span className="home-eyebrow">A SIMPLE LEARNING LOOP</span><h2>How it <em>works.</em></h2><p>Turn assessment results into practical next steps.</p></div><div className="home-steps">{steps.map((step) => <article className="home-step" key={step.number}><span className="home-step-number">{step.number}</span><div><h3>{step.title}</h3><p>{step.description}</p></div></article>)}</div><div className="home-bottom-cta"><div><span className="home-eyebrow">YOUR NEXT STEP STARTS HERE</span><h2>Ready to understand your learning better?</h2></div><button type="button" onClick={onStartAssessment}>Start an assessment <span aria-hidden="true">→</span></button></div></section>
  </div>;
}
