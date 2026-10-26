
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export interface Subject {
  id: number;
  name: string;
  class_level: number;
}

export interface Chapter {
  id: number;
  title: string;
  chapter_number: number;
  subject_id: number;
}

export interface Question {
  id: number;
  chapter_id: number;
  prompt: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  difficulty: string;
}

export interface AnswerSubmission {
  question_id: number;
  selected_option: string;
}


export interface AssessmentResult {
  question_id: number;
  question?: string;
  question_type?: "mcq" | "written";
  student_answer?: string | null;
  selected_option?: string | null;
  correct_option?: string | null;
  correct_answer?: string | null;
  expected_answer?: string | null;
  is_correct: boolean;
  score_awarded?: number;
  max_score?: number;
  feedback?: string;
  strengths?: string[];
  improvements?: string[];
  explanation?: string | null;
}



export interface AssessmentResponse {
  chapter_id: number;
  score: number;
  total_questions: number;
  percentage: number;
  total_score?: number;
  attempt_id?: number;
  overall_feedback?: string;
  results: AssessmentResult[];
}


export interface AttemptHistory {
  attempt_id: number;
  assessment_id: number;
  chapter_id: number;
  title: string;
  score: number;
  total_questions: number;
  percentage: number;
  submitted_at: string | null;
  has_detailed_feedback?: boolean;
}


export interface MLPerformanceResponse {
  student_id: number;
  chapter_id: number;
  performance_level: "Needs Revision" | "Developing" | "Proficient";
  confidence: number;
  current_percentage: number;
  previous_percentage: number;
  improvement: number;
  attempt_count: number;
  data_type: string;
  is_educationally_validated: boolean;
}




async function fetchData<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep the default error if the response is not JSON.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function getSubjects(
  classLevel: 11 | 12
): Promise<Subject[]> {
  return fetchData(
    `/api/subjects?class_level=${classLevel}`
  );
}

export function getChapters(
  subjectId: number
): Promise<Chapter[]> {
  return fetchData(
    `/api/chapters?subject_id=${subjectId}`
  );
}

export function getQuestions(
  chapterId: number
): Promise<Question[]> {
  return fetchData(
    `/api/chapters/${chapterId}/questions`
  );
}



export function submitAssessment(
  chapterId: number,
  answers: AnswerSubmission[],
  accessToken: string,
): Promise<AssessmentResponse> {
  return fetchData("/api/assessments/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      chapter_id: chapterId,
      answers,
    }),
  });
}


export function getMyAttempts(
  accessToken: string
): Promise<AttemptHistory[]> {
  return fetchData<AttemptHistory[]>("/api/attempts/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}


export function getMLPerformance(
  chapterId: number,
  accessToken: string
): Promise<MLPerformanceResponse> {
  return fetchData<MLPerformanceResponse>(
    `/api/ml/performance?chapter_id=${chapterId}`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }
  );
}


export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: number;
    full_name: string;
    email: string;
    class_level: number;
  };
}

export function loginStudent(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return fetchData("/api/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });
}


export function loginWithGoogle(
  idToken: string,
  classLevel?: 11 | 12,
): Promise<LoginResponse> {
  const body: { id_token: string; class_level?: 11 | 12 } = {
    id_token: idToken,
  };

  // Send a class only during Google sign-up. Existing users use the class
  // already stored in the database.
  if (classLevel !== undefined) {
    body.class_level = classLevel;
  }

  return fetchData("/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}


export interface GeneratedQuestion {
  id: number;
  temporary_id: number;
  question_type: "mcq" | "written";
  question: string;
  topic: string;
  bloom_level: string;
  difficulty: string;
  options: string[];
}

export interface GenerateQuestionsResponse {
  assessment_id: number;
  chapter_id: number;
  chapter: string;
  topic: string;
  subject: string;
  class_level: number;
  count: number;
  questions: GeneratedQuestion[];
}

export function generateChapterQuestions(
  chapterId: number, accessToken: string, topic: string, count = 5,
): Promise<GenerateQuestionsResponse> {
  return fetchData(`/api/chapters/${chapterId}/generate-questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ count, topic: topic.trim() || undefined, bloom_levels: ["Remember", "Understand", "Apply", "Analyze"], include_written: true }),
  });
}


export interface GeneratedAnswerSubmission {
  question_id: number;
  answer: string;
}

export function submitGeneratedAssessment(
  assessmentId: number,
  answers: GeneratedAnswerSubmission[],
  accessToken: string,
): Promise<AssessmentResponse> {
  return fetchData("/api/assessments/submit-generated", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ assessment_id: assessmentId, answers }),
  });
}

export function getAttemptReview(
  attemptId: number,
  accessToken: string,
): Promise<AssessmentResponse & { title: string; submitted_at: string | null }> {
  return fetchData(`/api/attempts/${attemptId}/review`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}


export interface BloomProfileLevel {
  level: string;
  score: number | null;
  earned_marks: number;
  possible_marks: number;
  question_count: number;
}

export interface BloomProfileResponse {
  levels: BloomProfileLevel[];
  recommendations: string[];
  data_points: number;
}

export function getBloomProfile(accessToken: string): Promise<BloomProfileResponse> {
  return fetchData("/api/ml/bloom-profile", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
