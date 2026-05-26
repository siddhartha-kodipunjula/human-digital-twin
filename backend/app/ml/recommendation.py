from __future__ import annotations

from typing import Any


def _history_trend(history_scores: list[float]) -> float:
    if len(history_scores) < 2:
        return 0.0
    return history_scores[-1] - history_scores[0]


def generate_recommendations(
    profile: dict[str, Any],
    daily: dict[str, Any],
    prediction_payload: dict[str, Any],
    history_scores: list[float],
) -> list[str]:
    recs: list[str] = []
    sleep = float(daily["sleep_hours"])
    stress = float(daily["stress_level"])
    steps = float(daily["daily_steps"])
    exercise = float(daily["exercise_minutes"])
    water = float(daily["water_intake"])
    category = prediction_payload["wellness_category"]
    score = float(prediction_payload["wellness_score"])
    risk_level = prediction_payload["risk_level"]

    if sleep < 6 and stress > 7:
        recs.append("Recovery priority: sleep 7.5-8 hours and add 10 minutes of breathwork before bed.")
    if sleep < 6:
        recs.append("Sleep debt detected. Advance bedtime by 30 minutes for at least 5 consecutive nights.")
    if steps < 6000:
        recs.append("Increase movement by adding two 12-minute walks to push daily steps above 7,500.")
    if exercise < 25:
        recs.append("Schedule 30-40 minutes of moderate exercise at least 4 days this week.")
    if water < 2.2:
        recs.append("Hydration is low. Target 2.5L of water with reminders every 2 hours.")
    if stress >= 8:
        recs.append("Stress is elevated. Use a no-screen cooldown and short mindfulness session tonight.")
    if float(daily["heart_rate"]) > 95:
        recs.append("Resting heart-rate trend is high. Prioritize light activity and recovery tomorrow.")

    conditions = {c.lower() for c in (profile.get("pre_existing_conditions") or [])}
    if "diabetes" in conditions:
        recs.append("For glucose control, prefer low-glycemic meals and a 10-minute walk after major meals.")
    if "bp" in conditions or "hypertension" in conditions:
        recs.append("Maintain sodium-aware meals and include 20 minutes of low-intensity cardio daily.")
    if "thyroid" in conditions:
        recs.append("Keep meal timing consistent and discuss fatigue swings with your clinician if persistent.")

    goal = str(profile.get("fitness_goal", "maintenance")).lower()
    if goal == "weight_loss":
        recs.append("Weight-loss focus: keep protein high and maintain a moderate calorie deficit.")
    elif goal == "muscle_gain":
        recs.append("Muscle-gain focus: add progressive resistance training and adequate post-workout protein.")

    trend = _history_trend(history_scores[-7:])
    if trend < -8:
        recs.append("Recent trend is downward. Reset with a lighter schedule and strict sleep consistency.")
    elif trend > 8:
        recs.append("Great upward trend. Sustain your current routine and increase challenge gradually.")

    if score < 50:
        recs.append("Critical improvement window: focus on one habit per day and avoid all-or-nothing changes.")
    if category in {"Good", "Excellent"}:
        recs.append("Stability mode: maintain habits and review progress weekly to prevent regression.")

    model_outputs = prediction_payload.get("model_outputs", {})
    confidence = float(model_outputs.get("confidence", 0))
    if confidence < 0.45:
        recs.append("Prediction confidence is low; log more daily data to improve personalization accuracy.")

    recs.append(f"Current risk level is {risk_level}. Reassess using daily logs over the next 7 days.")
    return recs[:8]


def nutrition_recommendation(
    goal: str,
    conditions: list[str],
    protein_g: float,
    carbs_g: float,
    fats_g: float,
) -> str:
    goal = goal.lower()
    condition_set = {c.lower() for c in conditions}
    messages: list[str] = []

    if protein_g < 70:
        messages.append("Increase lean protein intake.")
    if carbs_g > 320 and "diabetes" in condition_set:
        messages.append("Reduce refined carbs due to diabetes risk.")
    if fats_g > 90 and ("bp" in condition_set or "hypertension" in condition_set):
        messages.append("Limit saturated fat and sodium-heavy foods.")

    if goal == "muscle_gain" and protein_g < 95:
        messages.append("Add post-workout protein to support muscle gain.")
    if goal == "weight_loss" and carbs_g > 250:
        messages.append("Shift from refined carbs to high-fiber complex carbs.")

    if not messages:
        return "Macronutrient balance is on track for your current goal."
    return " ".join(messages)
