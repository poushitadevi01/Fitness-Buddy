import os
import json
import requests
from datetime import datetime
from flask import (
    Flask, render_template, request, session,
    jsonify, redirect, url_for, flash
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fitness-buddy-secret-2024")

# ── IBM watsonx configuration ──────────────────────────────────────────────────
WATSONX_API_KEY    = os.getenv("WATSONX_API_KEY", "3n4P6HO3e-6DS7lT1tHu49DsBkKg-e91fAyaYIwROZtg")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "7456c6c7-5423-4813-ba5f-8b603d9c4584")
WATSONX_URL        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_MODEL_ID   = os.getenv("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"

# ── IAM token cache ────────────────────────────────────────────────────────────
_iam_token_cache: dict = {}


def get_iam_token() -> str:
    """Fetch (and cache) an IBM Cloud IAM bearer token."""
    global _iam_token_cache
    now = datetime.utcnow().timestamp()
    if _iam_token_cache.get("token") and now < _iam_token_cache.get("expires", 0):
        return _iam_token_cache["token"]

    resp = requests.post(
        IAM_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": WATSONX_API_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _iam_token_cache = {
        "token": data["access_token"],
        "expires": now + int(data.get("expires_in", 3600)) - 60,
    }
    return _iam_token_cache["token"]


def query_watsonx(prompt: str, max_tokens: int = 800) -> str:
    """Send a prompt to IBM watsonx and return the generated text."""
    if not WATSONX_API_KEY or not WATSONX_PROJECT_ID:
        return _fallback_response(prompt)

    try:
        token = get_iam_token()
        url = f"{WATSONX_URL}/ml/v1/text/generation?version=2023-05-29"
        payload = {
            "model_id": WATSONX_MODEL_ID,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": max_tokens,
                "min_new_tokens": 10,
                "repetition_penalty": 1.1,
                "stop_sequences": ["Human:", "User:"],
            },
            "project_id": WATSONX_PROJECT_ID,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        return result["results"][0]["generated_text"].strip()
    except Exception as exc:
        app.logger.error("watsonx error: %s", exc)
        return _fallback_response(prompt)


def _fallback_response(prompt: str) -> str:
    """Friendly fallback when watsonx is not configured."""
    return (
        "⚠️ IBM watsonx is not configured yet. "
        "Please add your WATSONX_API_KEY and WATSONX_PROJECT_ID to the .env file. "
        "Once configured, I'll provide personalised AI-powered fitness advice!\n\n"
        "In the meantime, explore the BMI Calculator, Workout Planner, and Meal "
        "Suggestions from the navigation menu."
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_profile() -> dict:
    return session.get("profile", {})


def profile_context(profile: dict) -> str:
    if not profile:
        return "The user has not set up a profile yet."
    return (
        f"User profile – Age: {profile.get('age', 'N/A')}, "
        f"Gender: {profile.get('gender', 'N/A')}, "
        f"Height: {profile.get('height', 'N/A')} cm, "
        f"Weight: {profile.get('weight', 'N/A')} kg, "
        f"Fitness goal: {profile.get('goal', 'N/A')}, "
        f"Fitness level: {profile.get('level', 'N/A')}."
    )


def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str, str]:
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    if bmi < 18.5:
        category, advice = "Underweight", "Consider increasing calorie intake with nutritious foods and strength training."
    elif bmi < 25:
        category, advice = "Normal weight", "Great job! Maintain your healthy weight with balanced diet and regular exercise."
    elif bmi < 30:
        category, advice = "Overweight", "Focus on cardio exercises and a calorie-controlled diet to reach a healthy weight."
    else:
        category, advice = "Obese", "Consult a healthcare professional. Start with low-impact exercise and dietary changes."
    return round(bmi, 1), category, advice


def daily_water_ml(weight_kg: float, activity: str = "moderate") -> int:
    base = weight_kg * 35
    activity_extra = {"low": 0, "moderate": 350, "high": 700, "very_high": 1050}
    return int(base + activity_extra.get(activity, 350))


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    profile = get_profile()
    motivation = None
    if profile:
        prompt = (
            f"You are an enthusiastic fitness coach. {profile_context(profile)} "
            "Give a short (2–3 sentence) motivational message for today's workout. "
            "Be energetic and personal."
        )
        motivation = query_watsonx(prompt, max_tokens=120)
    return render_template("index.html", profile=profile, motivation=motivation)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        session["profile"] = {
            "name":   request.form.get("name", "").strip(),
            "age":    request.form.get("age", ""),
            "gender": request.form.get("gender", ""),
            "height": request.form.get("height", ""),
            "weight": request.form.get("weight", ""),
            "goal":   request.form.get("goal", ""),
            "level":  request.form.get("level", ""),
        }
        flash("Profile saved successfully! 🎉", "success")
        return redirect(url_for("index"))
    return render_template("profile.html", profile=get_profile())


@app.route("/bmi", methods=["GET", "POST"])
def bmi():
    result = None
    if request.method == "POST":
        try:
            weight = float(request.form["weight"])
            height = float(request.form["height"])
            bmi_val, category, advice = calculate_bmi(weight, height)
            result = {
                "bmi": bmi_val,
                "category": category,
                "advice": advice,
                "weight": weight,
                "height": height,
            }
            # AI-enhanced advice
            profile = get_profile()
            prompt = (
                f"The user has a BMI of {bmi_val} ({category}). {profile_context(profile)} "
                "Provide 3 concise, actionable tips to improve or maintain their health. "
                "Format as a numbered list."
            )
            result["ai_tips"] = query_watsonx(prompt, max_tokens=300)
        except (ValueError, KeyError):
            flash("Please enter valid weight and height values.", "danger")
    return render_template("bmi.html", result=result, profile=get_profile())


@app.route("/workout", methods=["GET", "POST"])
def workout():
    plan = None
    profile = get_profile()
    if request.method == "POST":
        duration  = request.form.get("duration", "30")
        focus     = request.form.get("focus", "full body")
        equipment = request.form.get("equipment", "none")

        prompt = (
            f"You are a certified personal trainer. {profile_context(profile)} "
            f"Create a detailed {duration}-minute home workout plan. "
            f"Focus: {focus}. Available equipment: {equipment}. "
            "Include warm-up (5 min), main workout with sets/reps/rest, and cool-down (5 min). "
            "Format clearly with sections and bullet points."
        )
        plan = query_watsonx(prompt, max_tokens=700)
    return render_template("workout.html", plan=plan, profile=profile)


@app.route("/meal", methods=["GET", "POST"])
def meal():
    suggestions = None
    profile = get_profile()
    if request.method == "POST":
        meal_type    = request.form.get("meal_type", "all")
        dietary_pref = request.form.get("dietary_pref", "none")
        calories     = request.form.get("calories", "2000")

        prompt = (
            f"You are a registered dietitian. {profile_context(profile)} "
            f"Suggest healthy {meal_type} meal ideas. "
            f"Dietary preference/restriction: {dietary_pref}. "
            f"Daily calorie target: {calories} kcal. "
            "Provide 3 meal options with ingredients, approximate calories, and preparation tips. "
            "Format with clear headings."
        )
        suggestions = query_watsonx(prompt, max_tokens=700)
    return render_template("meal.html", suggestions=suggestions, profile=profile)


@app.route("/hydration")
def hydration():
    profile = get_profile()
    water_info = None
    if profile and profile.get("weight"):
        try:
            weight   = float(profile["weight"])
            activity = profile.get("level", "moderate")
            level_map = {
                "beginner":     "low",
                "intermediate": "moderate",
                "advanced":     "high",
                "athlete":      "very_high",
            }
            water_ml  = daily_water_ml(weight, level_map.get(activity, "moderate"))
            water_l   = round(water_ml / 1000, 1)
            glasses   = round(water_ml / 250)
            water_info = {
                "ml": water_ml,
                "liters": water_l,
                "glasses": glasses,
            }
        except (ValueError, TypeError):
            pass
    return render_template("hydration.html", water_info=water_info, profile=profile)


@app.route("/chat")
def chat():
    return render_template("chat.html", profile=get_profile())


@app.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data    = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        history = data.get("history", [])
        profile = get_profile()

        if not message:
            return jsonify({"error": "Empty message"}), 400

        # Build conversation context
        conv = ""
        for turn in history[-6:]:   # last 6 turns for context
            role = "User" if turn.get("role") == "user" else "Assistant"
            conv += f"{role}: {turn.get('content', '')}\n"

        prompt = (
            "You are FitBuddy, a friendly and knowledgeable AI fitness assistant. "
            "You specialise in workouts, nutrition, wellness, and motivation. "
            f"{profile_context(profile)}\n"
            "Answer concisely and practically. Use bullet points where helpful.\n\n"
            f"{conv}"
            f"User: {message}\n"
            "FitBuddy:"
        )
        reply = query_watsonx(prompt, max_tokens=500)
        return jsonify({"reply": reply})
    except Exception as exc:
        app.logger.error("api_chat error: %s", exc)
        return jsonify({"error": "An error occurred. Please try again."}), 500


@app.route("/api/motivation")
def api_motivation():
    profile = get_profile()
    prompt = (
        f"You are an energetic fitness coach. {profile_context(profile)} "
        "Give one short (1–2 sentence) motivational quote or tip for today. "
        "Be uplifting and specific to their fitness goal."
    )
    quote = query_watsonx(prompt, max_tokens=80)
    return jsonify({"quote": quote})


@app.route("/api/quick-workout")
def api_quick_workout():
    profile = get_profile()
    prompt = (
        f"You are a personal trainer. {profile_context(profile)} "
        "Suggest a quick 10-minute energising exercise routine. "
        "List 4–5 exercises with reps/duration. Keep it concise."
    )
    workout_text = query_watsonx(prompt, max_tokens=300)
    return jsonify({"workout": workout_text})


# ── Error handlers ─────────────────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500


# ── Template context processors ────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.utcnow().year,
        "app_name": "FitBuddy AI",
    }


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
