export type Language = 'wo' | 'ff' | 'sr';
export type TextLanguage = Language | 'fr';
export type Category = 'health' | 'money' | 'school' | 'admin' | 'other';
export type Urgency = 'urgent' | 'soon' | 'none';
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'unreadable' | 'failed';
export type MessageStatus = 'pending' | 'ready' | 'failed';
export type WritingType = 'cv_cover_letter' | 'request_letter' | 'bank_letter' | 'other';
export type WritingStatus = 'collecting' | 'generating' | 'ready' | 'failed';
export type PlanCode = 'free' | 'leeral_plus';

export interface User {
  id: string;
  first_name: string | null;
  phone_number: string | null;
  language: Language;
  is_guest: boolean;
  has_completed_profile: boolean;
  registered_at: string | null;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  is_new_account: boolean;
  user: User;
}

export interface OtpChallenge {
  phone_number: string;
  expires_in: number;
  resend_in: number;
  code_length: number;
}

export interface Usage {
  writings_used: number;
  writings_limit: number;
  practice_used: number;
  practice_limit: number | null;
}

export interface Me {
  user: User;
  plan: { code: PlanCode; expires_at: string | null; document_words: boolean };
  usage: Usage;
}

export interface Prompt {
  key: string;
  text_fr: string;
  audio_url: string | null;
}

export interface Explanation {
  id: string;
  language: Language;
  variant: 'standard' | 'simple';
  text: string;
  text_fr: string;
  audio_url: string;
  audio_duration_s: number;
}

export interface KeyPoint {
  position: number;
  kind: 'action' | 'date' | 'amount' | 'info';
  tag: string;
  title_fr: string;
  detail_fr: string | null;
  due_date: string | null;
  amount_xof: number | null;
  audio_url: string;
}

export interface SuggestedQuestion {
  id: string;
  position: number;
  text_fr: string;
  audio_url: string;
}

export interface DocumentSummary {
  id: string;
  source: 'app' | 'whatsapp';
  status: DocumentStatus;
  failure_reason: string | null;
  title: string | null;
  doc_type: string | null;
  category: Category;
  urgency: Urgency;
  urgency_label: string | null;
  main_due_date: string | null;
  main_amount_xof: number | null;
  page_count: number;
  created_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  issuer: string | null;
  document_date: string | null;
  explanation: Explanation | null;
  simple_explanation: Explanation | null;
  key_points: KeyPoint[];
  suggested_questions: SuggestedQuestion[];
}

export interface DocumentPage {
  items: DocumentSummary[];
  next_before: string | null;
}

export interface Conversation {
  id: string;
  kind: 'document' | 'writing' | 'free';
  document_id: string | null;
  language: Language;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content_type: 'text' | 'audio' | 'image' | 'file';
  language: TextLanguage;
  status: MessageStatus;
  text: string | null;
  text_fr: string | null;
  audio_url: string | null;
  audio_duration_s: number | null;
  source_quote: string | null;
  suggested_question_id: string | null;
  created_at: string;
}

export interface Exchange {
  question: Message;
  answer: Message;
}

export interface WritingStep {
  position: number;
  field_key: string;
  question_fr: string;
  required: boolean;
  question_message_id: string;
  understood_value: string | null;
  confirmed: boolean;
}

export interface WritingOutput {
  id: string;
  version: number;
  kind: 'cv' | 'cover_letter' | 'letter';
  content: string;
  pdf_url: string;
  readback_audio_url: string | null;
  created_at: string;
}

export interface Writing {
  id: string;
  type: WritingType;
  title_fr: string;
  status: WritingStatus;
  conversation_id: string;
  current_step: number;
  total_steps: number;
  steps: WritingStep[];
  outputs: WritingOutput[];
  created_at: string;
}

export interface LearningOverview {
  total_words: number;
  mastered_words: number;
  due_words: number;
  usage: Usage;
}

export interface Choice {
  word_id: string;
  word_fr: string;
  meaning: string | null;
  meaning_audio_url: string | null;
}

export interface Exercise {
  word_id: string;
  word_fr: string;
  example_fr: string | null;
  meaning: string;
  meaning_audio_url: string;
  choices: Choice[];
}

export interface PracticeRound {
  session_id: string;
  exercises: Exercise[];
}

export interface PracticeAnswer {
  is_correct: boolean;
  correct_word_id: string;
  correct_word_fr: string;
  box: number;
  mastered: boolean;
  correct_count: number;
  total_count: number;
}

export interface Word {
  word_id: string;
  word_fr: string;
  category: string;
  example_fr: string | null;
  meaning: string | null;
  meaning_audio_url: string | null;
  box: number;
  mastered: boolean;
}

export interface Plan {
  code: PlanCode;
  price_xof: number;
  duration_days: number | null;
  writings_per_month: number;
  practice_per_day: number | null;
  document_words: boolean;
}

export interface Payment {
  public_token: string;
  status: 'pending' | 'succeeded' | 'failed' | 'cancelled';
  amount_xof: number;
}

export interface Transcription {
  text: string;
  text_fr: string;
}

export interface LocalFile {
  uri: string;
  name: string;
  type: string;
}
