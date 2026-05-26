import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "../api";

const DAILY_DEFAULT = {
  log_date: new Date().toISOString().slice(0, 10),
  sleep_hours: 7.2,
  daily_steps: 7400,
  heart_rate: 76,
  calories_burned: 2300,
  stress_level: 4,
  water_intake: 2.4,
  exercise_minutes: 36,
};

const SIMULATION_DEFAULT = {
  sleep_hours: 8,
  daily_steps: 9000,
  exercise_minutes: 45,
};

const FOOD_DEFAULT = {
  log_date: new Date().toISOString().slice(0, 10),
  meal_type: "lunch",
  food_name: "",
  calories: 420,
  protein_g: 24,
  carbs_g: 48,
  fats_g: 14,
  fiber_g: 8,
  notes: "",
};

function normalizeError(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || "Invalid input").join(" | ");
  return error?.message || fallback;
}

function statusClass(riskLevel) {
  if (riskLevel === "low") return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  if (riskLevel === "moderate") return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
  if (riskLevel === "high") return "bg-orange-500/15 text-orange-700 dark:text-orange-300";
  return "bg-rose-500/15 text-rose-700 dark:text-rose-300";
}

export default function DashboardPage() {
  const [dailyLogForm, setDailyLogForm] = useState(DAILY_DEFAULT);
  const [simulationForm, setSimulationForm] = useState(SIMULATION_DEFAULT);
  const [foodForm, setFoodForm] = useState(FOOD_DEFAULT);
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [latestPrediction, setLatestPrediction] = useState(null);
  const [simulationResult, setSimulationResult] = useState(null);
  const [macroSummary, setMacroSummary] = useState(null);
  const [foodLogs, setFoodLogs] = useState([]);
  const [modelMetrics, setModelMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const fetchAll = async () => {
    const [overviewResponse, historyResponse, forecastResponse, foodResponse, metricResponse] =
      await Promise.all([
        api.get("/dashboard/overview"),
        api.get("/predictions/history", { params: { limit: 90 } }),
        api.get("/predictions/forecast", { params: { days: 7 } }),
        api.get("/nutrition/logs", { params: { limit: 50 } }),
        api.get("/ml/metrics", { params: { limit: 20 } }),
      ]);
    setOverview(overviewResponse.data);
    setHistory(historyResponse.data || []);
    setForecast(forecastResponse.data?.points || []);
    setFoodLogs(foodResponse.data || []);
    setModelMetrics(metricResponse.data || []);
  };

  useEffect(() => {
    const init = async () => {
      try {
        await fetchAll();
      } catch (err) {
        setError(normalizeError(err, "Failed loading dashboard data."));
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const refreshNutritionSummary = async (logDate) => {
    try {
      const { data } = await api.get(`/nutrition/summary/${logDate}`);
      setMacroSummary(data);
    } catch {
      setMacroSummary(null);
    }
  };

  useEffect(() => {
    refreshNutritionSummary(foodForm.log_date);
  }, [foodForm.log_date]);

  const handleDailyLogSubmit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.post("/daily-logs", {
        ...dailyLogForm,
        sleep_hours: Number(dailyLogForm.sleep_hours),
        daily_steps: Number(dailyLogForm.daily_steps),
        heart_rate: Number(dailyLogForm.heart_rate),
        calories_burned: Number(dailyLogForm.calories_burned),
        stress_level: Number(dailyLogForm.stress_level),
        water_intake: Number(dailyLogForm.water_intake),
        exercise_minutes: Number(dailyLogForm.exercise_minutes),
      });
      setMessage("Daily log saved.");
      await fetchAll();
    } catch (err) {
      setError(normalizeError(err, "Unable to save daily log."));
    } finally {
      setBusy(false);
    }
  };

  const handleRunPrediction = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data } = await api.post("/predictions/run", {
        source: "manual",
        overrides: { log_date: dailyLogForm.log_date },
      });
      setLatestPrediction(data);
      setMessage("Prediction generated.");
      await fetchAll();
    } catch (err) {
      setError(normalizeError(err, "Prediction failed."));
    } finally {
      setBusy(false);
    }
  };

  const handleSimulation = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/predictions/simulate", {
        base_log_date: dailyLogForm.log_date,
        scenario: {
          sleep_hours: Number(simulationForm.sleep_hours),
          daily_steps: Number(simulationForm.daily_steps),
          exercise_minutes: Number(simulationForm.exercise_minutes),
        },
      });
      setSimulationResult(data);
      await fetchAll();
    } catch (err) {
      setError(normalizeError(err, "Simulation failed."));
    } finally {
      setBusy(false);
    }
  };

  const handleFoodSubmit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/nutrition/logs", {
        ...foodForm,
        calories: Number(foodForm.calories),
        protein_g: Number(foodForm.protein_g),
        carbs_g: Number(foodForm.carbs_g),
        fats_g: Number(foodForm.fats_g),
        fiber_g: Number(foodForm.fiber_g),
      });
      setFoodForm((value) => ({ ...value, food_name: "", notes: "" }));
      await fetchAll();
      await refreshNutritionSummary(foodForm.log_date);
      setMessage("Food log added.");
    } catch (err) {
      setError(normalizeError(err, "Food log save failed."));
    } finally {
      setBusy(false);
    }
  };

  const weeklyTrendData = useMemo(
    () =>
      (overview?.weekly_trend || []).map((item) => ({
        ...item,
        label: new Date(item.period_start).toLocaleDateString(),
      })),
    [overview]
  );

  const monthlyTrendData = useMemo(
    () =>
      (overview?.monthly_trend || []).map((item) => ({
        ...item,
        label: new Date(item.period_start).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      })),
    [overview]
  );

  const forecastData = useMemo(
    () =>
      forecast.map((item) => ({
        ...item,
        label: new Date(item.target_date).toLocaleDateString(undefined, { weekday: "short" }),
      })),
    [forecast]
  );

  const habitImpactData = useMemo(() => {
    if (!overview?.habit_impact) return [];
    return [
      { name: "Sleep", value: Number(overview.habit_impact.sleep_impact_percent || 0) },
      { name: "Exercise", value: Number(overview.habit_impact.exercise_impact_percent || 0) },
      { name: "Steps", value: Number(overview.habit_impact.steps_impact_percent || 0) },
      { name: "Stress", value: Number(overview.habit_impact.stress_impact_percent || 0) },
    ];
  }, [overview]);

  if (loading) {
    return <div className="panel p-6">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-5">
      {error && <div className="panel border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-300">{error}</div>}
      {message && <div className="panel border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-300">{message}</div>}

      <section className="grid gap-4 md:grid-cols-3">
        <div className="panel p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Current Score</div>
          <div className="mt-1 font-heading text-4xl font-bold">
            {overview?.current_state?.score?.toFixed?.(2) ?? "--"}
          </div>
          <div className="mt-2 text-sm">{overview?.current_state?.category || "No data yet"}</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Next 7-Day Predicted Avg</div>
          <div className="mt-1 font-heading text-4xl font-bold">
            {overview?.predicted_state?.next_7d_average_score?.toFixed?.(2) ?? "--"}
          </div>
          <div className="mt-2 text-sm">
            Risk:{" "}
            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(overview?.predicted_state?.projected_risk_level)}`}>
              {overview?.predicted_state?.projected_risk_level || "unknown"}
            </span>
          </div>
        </div>
        <div className="panel p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Digital Twin Status</div>
          <div className="mt-2 flex items-center gap-3">
            <div className="h-16 w-10 rounded-full bg-gradient-to-b from-cyan-500 to-emerald-500" />
            <div className="text-sm">
              <div className="font-semibold">
                {latestPrediction?.digital_twin?.health_status || overview?.current_state?.category || "Awaiting Prediction"}
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                {latestPrediction?.digital_twin?.visual_state || "stable"}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[360px,1fr]">
        <aside className="space-y-5">
          <form onSubmit={handleDailyLogSubmit} className="panel space-y-3 p-4">
            <h2 className="font-heading text-lg font-semibold">Daily Log</h2>
            <label className="block text-xs">
              Date
              <input
                type="date"
                value={dailyLogForm.log_date}
                onChange={(e) => setDailyLogForm((value) => ({ ...value, log_date: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            {[
              ["sleep_hours", "Sleep Hours", 0.1],
              ["daily_steps", "Daily Steps", 1],
              ["heart_rate", "Heart Rate", 1],
              ["calories_burned", "Calories Burned", 1],
              ["stress_level", "Stress (1-10)", 1],
              ["water_intake", "Water Intake (L)", 0.1],
              ["exercise_minutes", "Exercise Minutes", 1],
            ].map(([key, label, step]) => (
              <label key={key} className="block text-xs">
                {label}
                <input
                  type="number"
                  step={step}
                  value={dailyLogForm[key]}
                  onChange={(e) => setDailyLogForm((value) => ({ ...value, [key]: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
                />
              </label>
            ))}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-70"
              >
                Save Log
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleRunPrediction}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-70"
              >
                Predict
              </button>
            </div>
          </form>

          <form onSubmit={handleSimulation} className="panel space-y-3 p-4">
            <h2 className="font-heading text-lg font-semibold">What-If Simulation</h2>
            <label className="block text-xs">
              Sleep Hours
              <input
                type="number"
                step="0.1"
                value={simulationForm.sleep_hours}
                onChange={(e) => setSimulationForm((value) => ({ ...value, sleep_hours: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            <label className="block text-xs">
              Daily Steps
              <input
                type="number"
                value={simulationForm.daily_steps}
                onChange={(e) => setSimulationForm((value) => ({ ...value, daily_steps: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            <label className="block text-xs">
              Exercise Minutes
              <input
                type="number"
                value={simulationForm.exercise_minutes}
                onChange={(e) => setSimulationForm((value) => ({ ...value, exercise_minutes: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-70"
            >
              Run Simulation
            </button>
            {simulationResult && (
              <div className="rounded-lg bg-slate-900/5 p-2 text-xs dark:bg-white/10">
                Scenario delta score: <span className="font-semibold">{simulationResult.delta_score}</span>
              </div>
            )}
          </form>

          <form onSubmit={handleFoodSubmit} className="panel space-y-3 p-4">
            <h2 className="font-heading text-lg font-semibold">Food Log</h2>
            <label className="block text-xs">
              Date
              <input
                type="date"
                value={foodForm.log_date}
                onChange={(e) => setFoodForm((value) => ({ ...value, log_date: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            <label className="block text-xs">
              Meal
              <select
                value={foodForm.meal_type}
                onChange={(e) => setFoodForm((value) => ({ ...value, meal_type: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              >
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
            </label>
            <label className="block text-xs">
              Food Name
              <input
                type="text"
                value={foodForm.food_name}
                onChange={(e) => setFoodForm((value) => ({ ...value, food_name: e.target.value }))}
                className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                ["calories", "Calories"],
                ["protein_g", "Protein(g)"],
                ["carbs_g", "Carbs(g)"],
                ["fats_g", "Fats(g)"],
                ["fiber_g", "Fiber(g)"],
              ].map(([key, label]) => (
                <label key={key} className="block text-xs">
                  {label}
                  <input
                    type="number"
                    step="0.1"
                    value={foodForm[key]}
                    onChange={(e) => setFoodForm((value) => ({ ...value, [key]: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-300/40 bg-white/70 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/50"
                  />
                </label>
              ))}
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-70"
            >
              Add Food
            </button>
            {macroSummary && (
              <div className="rounded-lg bg-slate-900/5 p-2 text-xs dark:bg-white/10">
                <div>Protein: {macroSummary.protein_g}g | Carbs: {macroSummary.carbs_g}g | Fats: {macroSummary.fats_g}g</div>
                <div className="mt-1 text-slate-600 dark:text-slate-300">{macroSummary.recommendation}</div>
              </div>
            )}
          </form>
        </aside>

        <main className="space-y-5">
          <section className="grid gap-4 md:grid-cols-2">
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">Weekly Trend</h3>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={weeklyTrendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="average_score" stroke="#0ea5e9" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">Monthly Trend</h3>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={monthlyTrendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="average_score" stroke="#22c55e" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">7-Day Forecast</h3>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="forecast_score" stroke="#f97316" strokeWidth={2} name="Forecast Score" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">Habit Impact Analysis</h3>
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={habitImpactData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#14b8a6" name="Impact %" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">Detected Anomalies</h3>
              <div className="mt-2 space-y-2 text-sm">
                {(overview?.anomalies || []).length === 0 && <div className="text-slate-500">No significant anomalies detected.</div>}
                {(overview?.anomalies || []).slice(0, 6).map((item, index) => (
                  <div key={`${item.date}-${index}`} className="rounded-md bg-slate-900/5 px-3 py-2 dark:bg-white/10">
                    <div className="font-semibold">{new Date(item.date).toLocaleDateString()}</div>
                    <div>
                      Score: {item.score} | Z-score: {item.z_score}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-300">{item.reason}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel p-4">
              <h3 className="font-heading font-semibold">Model Metrics (Latest)</h3>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 dark:text-slate-400">
                      <th className="py-1 pr-2">Model</th>
                      <th className="py-1 pr-2">Acc</th>
                      <th className="py-1 pr-2">F1</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelMetrics.slice(0, 7).map((item, index) => (
                      <tr key={`${item.model_name}-${index}`} className="border-t border-slate-300/20">
                        <td className="py-1 pr-2">{item.model_name}</td>
                        <td className="py-1 pr-2">{item.accuracy ?? "N/A"}</td>
                        <td className="py-1 pr-2">{item.f1_score ?? "N/A"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section className="panel p-4">
            <h3 className="font-heading font-semibold">Recent Predictions</h3>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500 dark:text-slate-400">
                    <th className="py-1 pr-3">Date</th>
                    <th className="py-1 pr-3">Source</th>
                    <th className="py-1 pr-3">Score</th>
                    <th className="py-1 pr-3">Category</th>
                    <th className="py-1 pr-3">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 10).map((item) => (
                    <tr key={item.id} className="border-t border-slate-300/20">
                      <td className="py-1 pr-3">{new Date(item.created_at).toLocaleString()}</td>
                      <td className="py-1 pr-3">{item.source}</td>
                      <td className="py-1 pr-3">{item.wellness_score}</td>
                      <td className="py-1 pr-3">{item.wellness_category}</td>
                      <td className="py-1 pr-3">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(item.risk_level)}`}>
                          {item.risk_level}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel p-4">
            <h3 className="font-heading font-semibold">Recent Food Logs</h3>
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {foodLogs.slice(0, 8).map((item) => (
                <div key={item.id} className="rounded-lg bg-slate-900/5 p-2 text-sm dark:bg-white/10">
                  <div className="font-semibold">
                    {item.food_name} ({item.meal_type})
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-300">
                    {item.log_date} | {item.calories} kcal | P:{item.protein_g} C:{item.carbs_g} F:{item.fats_g}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </main>
      </section>
    </div>
  );
}
