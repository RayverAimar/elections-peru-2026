"""Adaptive quiz engine using Bayesian inference and information gain.

The engine maintains a probability distribution over political parties and
selects questions that maximally reduce uncertainty about which party best
matches the user's positions.

Algorithm:
    1. Start with uniform prior P(party) = 1/N for all N parties.
    2. For each user answer, update P using Gaussian likelihood:
       P(party) *= exp(-(answer - party_score)^2 / 2σ²)
    3. Select next question by maximizing expected information gain:
       IG(q) = H(P) - E[H(P|answer)]
    4. After enough questions, rank parties by posterior probability.

Key design decisions:
    - SIGMA=1.0: A 2-point mismatch gives ~13.5% likelihood (strict).
    - Confidence blending: Low-confidence scores are blended toward the mean
      likelihood, making them less informative (appropriately).
    - No-data treatment: score=0 with low confidence is treated as truly
      unknown (likelihood = mean), preventing "ghost" parties from floating up.
    - Contender refinement: After 6 questions, boost questions where the top
      contending parties differ most, breaking ties between similar parties.
"""

import json
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Gaussian likelihood width. Controls how strictly mismatches are penalized.
# At SIGMA=1.0: diff=0 → 1.0, diff=1 → 0.61, diff=2 → 0.14, diff=4 → 0.0003
SIGMA = 1.0

# Confidence multipliers: how much we trust each confidence level.
# High = fully trust the score, Low = mostly ignore it (blend toward mean).
CONFIDENCE_MAP = {"high": 1.0, "medium": 0.75, "low": 0.25}

# Session and quiz parameters
MIN_QUESTIONS = 12       # Minimum before allowing early stop
MAX_QUESTIONS = 20       # Hard cap
CONFIDENCE_RATIO = 3.0   # Stop early if top party is 3x the second
SESSION_TTL = 3600       # 1 hour session expiry
MIN_RELIABLE_SCORES = 30 # Exclude parties with fewer reliable scores
CONTENDER_THRESHOLD = 0.05  # Posterior probability to be a "contender"
CONTENDER_MIN_QUESTIONS = 6  # Questions before activating refinement
TOPIC_DIVERSITY_PENALTY = 0.7  # Penalize repeating the same topic


@dataclass
class QuizSession:
    """State for an in-progress quiz session."""

    id: str
    posterior: np.ndarray          # P(party) for each party, sums to 1
    answered: list[tuple[str, int]] = field(default_factory=list)  # (question_id, value)
    topic_prefs: list[str] | None = None
    created_at: float = field(default_factory=time.time)


class AdaptiveQuizEngine:
    """Bayesian adaptive quiz engine for electoral matching."""

    def __init__(self, data_dir: Path):
        self._questions: list[dict] = []
        self._question_index: dict[str, int] = {}  # question_id → index
        self._party_keys: list[str] = []
        self._party_info: dict[str, dict] = {}
        self._score_matrix: np.ndarray | None = None   # (n_questions, n_parties)
        self._confidence_matrix: np.ndarray | None = None
        self._sessions: dict[str, QuizSession] = {}
        self._excluded_parties: set[str] = set()

        self._load(data_dir)

    @property
    def available(self) -> bool:
        return self._score_matrix is not None and len(self._questions) > 0

    # ── Data Loading ──────────────────────────────────────────────

    def _load(self, data_dir: Path):
        qb_path = data_dir / "question_bank.json"
        if not qb_path.exists():
            return

        with open(qb_path, encoding="utf-8") as f:
            data = json.load(f)

        self._questions = data.get("questions", [])
        if not self._questions:
            return

        # Index questions by ID for O(1) lookup
        self._question_index = {q["id"]: i for i, q in enumerate(self._questions)}

        # Filter parties by data quality
        all_party_keys = sorted(self._questions[0].get("party_scores", {}).keys())
        self._excluded_parties = self._find_excluded_parties(all_party_keys)
        self._party_keys = [pk for pk in all_party_keys if pk not in self._excluded_parties]

        # Build matrices for fast numpy operations
        n_questions = len(self._questions)
        n_parties = len(self._party_keys)
        self._score_matrix = np.zeros((n_questions, n_parties))
        self._confidence_matrix = np.ones((n_questions, n_parties))

        for qi, q in enumerate(self._questions):
            scores = q.get("party_scores", {})
            for pi, pk in enumerate(self._party_keys):
                ps = scores.get(pk, {})
                self._score_matrix[qi, pi] = ps.get("score", 0)
                self._confidence_matrix[qi, pi] = CONFIDENCE_MAP.get(
                    ps.get("confidence", "medium"), 0.5
                )

        # Load party display info (names, photos)
        self._load_party_info(data_dir)

    def _find_excluded_parties(self, all_keys: list[str]) -> set[str]:
        """Exclude parties with too few reliable (high/medium confidence) scores."""
        excluded = set()
        for pk in all_keys:
            reliable = sum(
                1
                for q in self._questions
                if q.get("party_scores", {}).get(pk, {}).get("confidence", "low")
                in ("high", "medium")
            )
            if reliable < MIN_RELIABLE_SCORES:
                excluded.add(pk)
        return excluded

    def _load_party_info(self, data_dir: Path):
        candidates_path = data_dir / "candidatos_2026.json"
        if not candidates_path.exists():
            return
        with open(candidates_path, encoding="utf-8") as f:
            cdata = json.load(f)
        for p in cdata.get("parties", []):
            pres = p.get("presidential_formula", {}).get("president") or {}
            name = p.get("party_name", "")
            self._party_info[name] = {
                "candidate": pres.get("full_name", ""),
                "photo_url": pres.get("photo_url"),
                "party": name,
            }

    # ── Session Management ────────────────────────────────────────

    def start_session(
        self, topic_prefs: list[str] | None = None
    ) -> tuple[str, dict, dict]:
        """Start a new quiz session with uniform prior."""
        self._cleanup_expired_sessions()

        n_parties = len(self._party_keys)
        session = QuizSession(
            id=str(uuid.uuid4()),
            posterior=np.ones(n_parties) / n_parties,
            topic_prefs=topic_prefs,
        )
        self._sessions[session.id] = session

        question = self._select_next_question(session)
        return session.id, question, self._get_progress(session)

    def get_session(self, session_id: str) -> QuizSession | None:
        return self._sessions.get(session_id)

    def _cleanup_expired_sessions(self):
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.created_at > SESSION_TTL
        ]
        for sid in expired:
            del self._sessions[sid]

    # ── Core: Answer Processing ───────────────────────────────────

    def answer(
        self, session_id: str, question_id: str, value: int
    ) -> tuple[dict | None, dict, bool]:
        """Process an answer and return (next_question, progress, finished)."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        q_idx = self._question_index.get(question_id)
        if q_idx is None:
            raise ValueError("Question not found")

        session.answered.append((question_id, value))
        self._update_posterior(session, q_idx, value)

        if self._should_stop(session):
            return None, self._get_progress(session), True

        next_q = self._select_next_question(session)
        if next_q is None:
            return None, self._get_progress(session), True

        return next_q, self._get_progress(session), False

    def _update_posterior(self, session: QuizSession, q_idx: int, value: int):
        """Bayesian update: multiply posterior by Gaussian likelihood."""
        party_scores = self._score_matrix[q_idx]
        confidences = self._confidence_matrix[q_idx]

        # Gaussian likelihood: how well does each party's score match the answer?
        raw_likelihood = np.exp(-((value - party_scores) ** 2) / (2 * SIGMA**2))

        # Blend by confidence: low-confidence scores → blend toward mean
        mean_lk = np.mean(raw_likelihood)
        likelihood = raw_likelihood * confidences + (1 - confidences) * mean_lk

        # No-data treatment: score=0 with low confidence → uninformative
        no_data = (party_scores == 0) & (confidences <= CONFIDENCE_MAP["low"])
        likelihood[no_data] = mean_lk

        # Update and normalize
        session.posterior *= likelihood
        total = session.posterior.sum()
        if total > 0:
            session.posterior /= total
        else:
            # Numerical underflow: reset to uniform
            session.posterior = np.ones_like(session.posterior) / len(session.posterior)

    # ── Core: Question Selection ──────────────────────────────────

    def _select_next_question(self, session: QuizSession) -> dict | None:
        """Select the question that maximizes expected information gain.

        Two phases:
        - Early (< 6 answers): pure information gain across all parties
        - Late (≥ 6 answers): boost questions that differentiate top contenders
        """
        answered_ids = {qid for qid, _ in session.answered}
        unanswered = [
            (i, q) for i, q in enumerate(self._questions)
            if q["id"] not in answered_ids
        ]
        if not unanswered:
            return None

        h_current = _entropy(session.posterior)
        recent_topics = self._get_recent_topics(session, n=2)
        contender_indices = self._get_contender_indices(session)
        possible_answers = np.array([-2, -1, 0, 1, 2])

        best_score = -1.0
        best_question = None

        for qi, q in unanswered:
            ig = self._compute_information_gain(
                session, qi, h_current, possible_answers
            )

            # Modifiers
            if q.get("topic", "") in recent_topics:
                ig *= TOPIC_DIVERSITY_PENALTY

            if session.topic_prefs and q.get("topic", "") in session.topic_prefs:
                ig *= 1.3

            if len(session.answered) < 2:
                ig *= random.uniform(0.8, 1.2)  # Vary first questions

            if contender_indices is not None:
                ig *= self._contender_boost(qi, contender_indices)

            if ig > best_score:
                best_score = ig
                best_question = q

        return best_question

    def _compute_information_gain(
        self,
        session: QuizSession,
        q_idx: int,
        h_current: float,
        possible_answers: np.ndarray,
    ) -> float:
        """Expected reduction in entropy if we ask this question."""
        party_scores = self._score_matrix[q_idx]
        confidences = self._confidence_matrix[q_idx]
        no_data = (party_scores == 0) & (confidences <= CONFIDENCE_MAP["low"])

        # Compute likelihood for each possible answer
        likelihoods = []
        for a in possible_answers:
            lk = np.exp(-((a - party_scores) ** 2) / (2 * SIGMA**2))
            mean_lk = np.mean(lk)
            lk = lk * confidences + (1 - confidences) * mean_lk
            lk[no_data] = mean_lk
            likelihoods.append(lk)

        # P(answer=a) = weighted sum under current posterior
        p_answers = np.array(
            [np.dot(session.posterior, lk) for lk in likelihoods]
        )
        p_total = p_answers.sum()
        if p_total <= 0:
            return 0.0
        p_answers /= p_total

        # Expected entropy after observing each possible answer
        expected_h = 0.0
        for ai, lk in enumerate(likelihoods):
            if p_answers[ai] <= 0:
                continue
            posterior_given_a = session.posterior * lk
            total = posterior_given_a.sum()
            if total > 0:
                posterior_given_a /= total
            expected_h += p_answers[ai] * _entropy(posterior_given_a)

        return h_current - expected_h

    def _contender_boost(self, q_idx: int, contender_indices: np.ndarray) -> float:
        """Boost factor for questions where top contenders disagree."""
        contender_scores = self._score_matrix[q_idx][contender_indices]
        spread = float(contender_scores.max() - contender_scores.min())
        # 0 spread → 1.0x (no boost), 4 spread → 2.0x (max boost)
        return 1.0 + spread * 0.25

    def _get_contender_indices(self, session: QuizSession) -> np.ndarray | None:
        """Indices of parties with >5% posterior (the "shortlist").

        Returns None if too early or posterior is still too spread out.
        """
        if len(session.answered) < CONTENDER_MIN_QUESTIONS:
            return None

        contender_mask = session.posterior > CONTENDER_THRESHOLD
        n = contender_mask.sum()
        if n < 2 or n > 8:
            return None

        return np.where(contender_mask)[0]

    def _get_recent_topics(self, session: QuizSession, n: int = 2) -> list[str]:
        """Topics of the last N answered questions (for diversity penalty)."""
        return [
            self._questions[self._question_index[qid]].get("topic", "")
            for qid, _ in session.answered[-n:]
            if qid in self._question_index
        ]

    # ── Stopping Logic ────────────────────────────────────────────

    def _should_stop(self, session: QuizSession) -> bool:
        n = len(session.answered)
        if n >= MAX_QUESTIONS:
            return True
        if n < MIN_QUESTIONS:
            return False

        # Stop early if the leader is clearly ahead
        sorted_probs = np.sort(session.posterior)[::-1]
        return (
            len(sorted_probs) >= 2
            and sorted_probs[1] > 0
            and sorted_probs[0] / sorted_probs[1] >= CONFIDENCE_RATIO
        )

    def _get_progress(self, session: QuizSession) -> dict:
        n = len(session.answered)
        sorted_probs = np.sort(session.posterior)[::-1]
        confidence = None
        if len(sorted_probs) >= 2 and sorted_probs[1] > 0:
            confidence = round(sorted_probs[0] / sorted_probs[1], 2)

        return {
            "current": n,
            "min_questions": MIN_QUESTIONS,
            "max_questions": MAX_QUESTIONS,
            "confidence": confidence,
        }

    # ── Results ────────────────────────────────────────────────────

    def get_results(self, session_id: str) -> dict:
        """Rank parties by posterior probability with evidence."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        max_prob = session.posterior.max()
        party_results = []

        for pi, pk in enumerate(self._party_keys):
            prob = session.posterior[pi]
            score = round(prob / max_prob * 100, 1) if max_prob > 0 else 0

            evidence = self._collect_evidence(session, pk)
            agreement = self._compute_topic_agreement(session, pi)
            info = self._party_info.get(pk, {"party": pk, "candidate": "", "photo_url": None})

            party_results.append({
                "party": info.get("party", pk),
                "candidate": info.get("candidate", ""),
                "photo_url": info.get("photo_url"),
                "score": score,
                "agreement_by_topic": agreement,
                "evidence": evidence[:5],
            })

        party_results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "top_candidates": party_results[:5],
            "user_profile": self._build_user_profile(session),
            "total_questions_answered": len(session.answered),
        }

    def _collect_evidence(self, session: QuizSession, party_key: str) -> list[dict]:
        """Collect question-level evidence for a party match."""
        evidence = []
        for qid, user_val in session.answered:
            q_idx = self._question_index.get(qid)
            if q_idx is None:
                continue
            q = self._questions[q_idx]
            ps = q.get("party_scores", {}).get(party_key, {})
            party_score = ps.get("score", 0)
            if abs(user_val) >= 1 or abs(party_score) >= 1:
                evidence.append({
                    "question": q.get("text", ""),
                    "user_answer": user_val,
                    "party_score": party_score,
                    "explanation": ps.get("evidence", ""),
                })
        # Best agreements first
        evidence.sort(key=lambda e: abs(e["user_answer"] - e["party_score"]))
        return evidence

    def _compute_topic_agreement(
        self, session: QuizSession, party_idx: int
    ) -> dict[str, float]:
        """Per-topic agreement percentage between user and party."""
        topic_scores: dict[str, tuple[float, int]] = {}

        for qid, user_val in session.answered:
            q_idx = self._question_index.get(qid)
            if q_idx is None:
                continue
            topic = self._questions[q_idx].get("topic", "")
            party_score = self._score_matrix[q_idx, party_idx]
            # Agreement: 1.0 when identical, 0.0 when max apart (diff=4)
            agreement = 1.0 - abs(user_val - party_score) / 4.0

            s, c = topic_scores.get(topic, (0.0, 0))
            topic_scores[topic] = (s + agreement, c + 1)

        return {
            topic: round(s / c * 100, 1)
            for topic, (s, c) in topic_scores.items()
            if c > 0
        }

    def _build_user_profile(self, session: QuizSession) -> dict[str, float]:
        """Summarize user's positions by topic.axis."""
        profile: dict[str, float] = {}
        for qid, val in session.answered:
            q_idx = self._question_index.get(qid)
            if q_idx is None:
                continue
            q = self._questions[q_idx]
            topic = q.get("topic", "")
            axis = q.get("primary_axis", "")
            if topic and axis:
                key = f"{topic}.{axis}"
                profile[key] = profile.get(key, 0) + val
        return {k: round(v, 2) for k, v in profile.items()}


# ── Utility ───────────────────────────────────────────────────────

def _entropy(p: np.ndarray) -> float:
    """Shannon entropy in bits."""
    p = p[p > 0]
    if len(p) == 0:
        return 0.0
    return float(-np.sum(p * np.log2(p)))
