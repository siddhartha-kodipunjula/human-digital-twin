import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";

const DEFAULT_PROFILE = {
  age: 28,
  gender: "male",
  height_cm: 170,
  weight_kg: 70,
  food_preference: "veg",
  diet_pattern: "balanced",
  pre_existing_conditions: "",
  fitness_goal: "maintenance",
};

function normalizeError(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || "Invalid value").join(" | ");
  return error?.message || "Profile request failed.";
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState(DEFAULT_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");

  const bmiPreview = useMemo(() => {
    const h = Number(formData.height_cm) / 100;
    const w = Number(formData.weight_kg);
    if (!h || !w) return "--";
    return (w / (h * h)).toFixed(2);
  }, [formData.height_cm, formData.weight_kg]);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const { data } = await api.get("/profile");
        setFormData({
          ...data,
          pre_existing_conditions: (data.pre_existing_conditions || []).join(", "),
        });
      } catch (errorResponse) {
        if (errorResponse?.response?.status !== 404) {
          setError(normalizeError(errorResponse));
        }
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSavedMessage("");
    try {
      const payload = {
        ...formData,
        age: Number(formData.age),
        height_cm: Number(formData.height_cm),
        weight_kg: Number(formData.weight_kg),
        pre_existing_conditions: formData.pre_existing_conditions
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      };
      await api.put("/profile", payload);
      setSavedMessage("Profile saved successfully.");
      navigate("/dashboard");
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="panel p-6">Loading profile...</div>;
  }

  return (
    <div className="panel p-6">
      <h1 className="font-heading text-2xl font-bold">Digital Twin Profile</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
        Static profile attributes personalize your AI predictions and recommendations.
      </p>
      {error && <div className="mt-3 rounded-lg bg-rose-500/10 p-2 text-sm text-rose-700 dark:text-rose-300">{error}</div>}
      {savedMessage && <div className="mt-3 rounded-lg bg-emerald-500/10 p-2 text-sm text-emerald-700 dark:text-emerald-300">{savedMessage}</div>}

      <form onSubmit={handleSubmit} className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="text-sm font-medium">
          Age
          <input
            type="number"
            min={10}
            max={100}
            value={formData.age}
            onChange={(e) => setFormData((value) => ({ ...value, age: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          />
        </label>
        <label className="text-sm font-medium">
          Gender
          <select
            value={formData.gender}
            onChange={(e) => setFormData((value) => ({ ...value, gender: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          Height (cm)
          <input
            type="number"
            min={100}
            max={240}
            value={formData.height_cm}
            onChange={(e) => setFormData((value) => ({ ...value, height_cm: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          />
        </label>
        <label className="text-sm font-medium">
          Weight (kg)
          <input
            type="number"
            min={30}
            max={250}
            value={formData.weight_kg}
            onChange={(e) => setFormData((value) => ({ ...value, weight_kg: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          />
        </label>
        <div className="rounded-lg border border-slate-300/30 bg-slate-900/5 px-3 py-2 text-sm dark:border-slate-700 dark:bg-white/5">
          BMI (auto): <span className="font-semibold">{bmiPreview}</span>
        </div>
        <div />
        <label className="text-sm font-medium">
          Food Preference
          <select
            value={formData.food_preference}
            onChange={(e) => setFormData((value) => ({ ...value, food_preference: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          >
            <option value="veg">Veg</option>
            <option value="non-veg">Non-Veg</option>
            <option value="vegan">Vegan</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          Diet Pattern
          <select
            value={formData.diet_pattern}
            onChange={(e) => setFormData((value) => ({ ...value, diet_pattern: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          >
            <option value="balanced">Balanced</option>
            <option value="high_protein">High Protein</option>
            <option value="junk_heavy">Junk Heavy</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          Fitness Goal
          <select
            value={formData.fitness_goal}
            onChange={(e) => setFormData((value) => ({ ...value, fitness_goal: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          >
            <option value="weight_loss">Weight Loss</option>
            <option value="muscle_gain">Muscle Gain</option>
            <option value="maintenance">Maintenance</option>
          </select>
        </label>
        <label className="text-sm font-medium md:col-span-2">
          Pre-existing conditions (comma separated)
          <input
            type="text"
            value={formData.pre_existing_conditions}
            placeholder="diabetes, bp, thyroid"
            onChange={(e) => setFormData((value) => ({ ...value, pre_existing_conditions: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
          />
        </label>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-70"
          >
            {saving ? "Saving..." : "Save Profile"}
          </button>
        </div>
      </form>
    </div>
  );
}
