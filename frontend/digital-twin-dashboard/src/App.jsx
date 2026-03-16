import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Brain,
  Download,
  FileUp,
  Moon,
  RefreshCw,
  Sun,
  UploadCloud,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";

const MODES = [
  { key: "overview", label: "Wellness Overview", icon: Activity },
  { key: "analytics", label: "Analytics Dashboard", icon: BarChart3 },
  { key: "dataset", label: "Dataset Insights", icon: FileUp },
];

const FEATURE_COLUMNS = [
  "age",
  "gender",
  "sleep_hours",
  "daily_steps",
  "heart_rate",
  "calories_burned",
  "stress_level",
  "water_intake",
  "exercise_minutes",
];

const CATEGORY_COLORS = {
  Poor: "#ef4444",
  Average: "#f59e0b",
  Good: "#22c55e",
  Excellent: "#06b6d4",
};

const INITIAL_FORM = {
  age: 29,
  gender: "Male",
  sleep_hours: 7,
  daily_steps: 6500,
  heart_rate: 78,
  calories_burned: 2200,
  stress_level: 4,
  water_intake: 2.3,
  exercise_minutes: 35,
};

function toPredictPayload(data) {
  return {
    age: Number(data.age),
    gender: data.gender,
    sleep_hours: Number(data.sleep_hours),
    daily_steps: Number(data.daily_steps),
    heart_rate: Number(data.heart_rate),
    calories_burned: Number(data.calories_burned),
    stress_level: Number(data.stress_level),
    water_intake: Number(data.water_intake),
    exercise_minutes: Number(data.exercise_minutes),
  };
}

function toHistoryChart(history) {
  return history
    .map((item, index) => ({
      index: index + 1,
      sleep_hours: Number(item.input.sleep_hours || 0),
      stress_level: Number(item.input.stress_level || 0),
      daily_steps: Number(item.input.daily_steps || 0),
      heart_rate: Number(item.input.heart_rate || 0),
      wellness_score: Number(item.wellness_score || 0),
      wellness_category: item.wellness_category,
    }))
    .reverse();
}

function categoryClass(category) {
  if (category === "Excellent") return "bg-cyan-500/20 text-cyan-600 dark:text-cyan-300";
  if (category === "Good") return "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300";
  if (category === "Average") return "bg-amber-500/20 text-amber-600 dark:text-amber-300";
  return "bg-rose-500/20 text-rose-600 dark:text-rose-300";
}

function errorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.message ||
    "Request failed. Ensure backend is running on http://localhost:8000."
  );
}

function artifactFile(path) {
  return String(path || "").split(/[/\\]/).pop();
}

function App() {
  const [mode, setMode] = useState("overview");
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [performance, setPerformance] = useState([]);
  const [trainingMeta, setTrainingMeta] = useState(null);
  const [datasetInsights, setDatasetInsights] = useState(null);
  const [datasetPreview, setDatasetPreview] = useState([]);
  const [uploadChartData, setUploadChartData] = useState([]);
  const [loadingPredict, setLoadingPredict] = useState(false);
  const [loadingUpload, setLoadingUpload] = useState(false);
  const [loadingTrain, setLoadingTrain] = useState(false);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(() => localStorage.getItem("digital-twin-theme") || "light");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("digital-twin-theme", theme);
  }, [theme]);

  const fetchHistory = async () => {
    const { data } = await api.get("/prediction-history", { params: { limit: 150 } });
    setHistory(data.history || []);
  };

  const fetchPerformance = async () => {
    const { data } = await api.get("/model-performance");
    setPerformance(data.performance || []);
    setTrainingMeta(data.latest_training_payload || null);
  };

  useEffect(() => {
    const init = async () => {
      try {
        await Promise.all([fetchHistory(), fetchPerformance()]);
      } catch (apiError) {
        setError(errorMessage(apiError));
      }
    };
    init();
  }, []);

  const analyticsData = useMemo(
    () => (uploadChartData.length ? uploadChartData : toHistoryChart(history)),
    [history, uploadChartData]
  );

  const categoryDistribution = useMemo(() => {
    const counts = {};
    analyticsData.forEach((item) => {
      const key = item.wellness_category || "Unknown";
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: CATEGORY_COLORS[name] || "#94a3b8",
    }));
  }, [analyticsData]);

  const handlePredict = async (event) => {
    event.preventDefault();
    setLoadingPredict(true);
    setError("");
    try {
      const { data } = await api.post("/predict", toPredictPayload(formData));
      setPrediction(data);
      await fetchHistory();
      setMode("overview");
    } catch (apiError) {
      setError(errorMessage(apiError));
    } finally {
      setLoadingPredict(false);
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoadingUpload(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/upload-data", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDatasetInsights(data.insights || null);
      setDatasetPreview(data.preview_records || []);
      setUploadChartData(data.chart_data || []);
      await fetchHistory();
      setMode("dataset");
    } catch (apiError) {
      setError(errorMessage(apiError));
    } finally {
      setLoadingUpload(false);
      event.target.value = "";
    }
  };

  const handleTrain = async () => {
    setLoadingTrain(true);
    setError("");
    try {
      await api.post("/train-model", {
        force_generate: false,
        records: 7000,
        lstm_epochs: 15,
      });
      await fetchPerformance();
    } catch (apiError) {
      setError(errorMessage(apiError));
    } finally {
      setLoadingTrain(false);
    }
  };

  const exportHistory = () => {
    if (!history.length) return;
    const header = [
      "created_at",
      "source",
      "age",
      "gender",
      "sleep_hours",
      "daily_steps",
      "heart_rate",
      "calories_burned",
      "stress_level",
      "water_intake",
      "exercise_minutes",
      "wellness_score",
      "wellness_category",
    ];
    const lines = history.map((item) => {
      const row = [
        item.created_at,
        item.source,
        item.input.age,
        item.input.gender,
        item.input.sleep_hours,
        item.input.daily_steps,
        item.input.heart_rate,
        item.input.calories_burned,
        item.input.stress_level,
        item.input.water_intake,
        item.input.exercise_minutes,
        item.wellness_score,
        item.wellness_category,
      ];
      return row.join(",");
    });
    const csv = `${header.join(",")}\n${lines.join("\n")}`;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.setAttribute("download", "prediction_history.csv");
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const downloadReport = () => {
    if (!prediction) return;
    const lines = [
      "Human Digital Twin Wellness Report",
      `Generated: ${new Date().toISOString()}`,
      "",
      `Wellness Score: ${prediction.wellness_score}`,
      `Wellness Category: ${prediction.wellness_category}`,
      "",
      "Input Parameters:",
      ...Object.entries(prediction.input).map(([key, value]) => `- ${key}: ${value}`),
      "",
      "Recommendations:",
      ...prediction.recommendations.map((item) => `- ${item}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "wellness_report.txt";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const twinColor = prediction ? CATEGORY_COLORS[prediction.wellness_category] || "#64748b" : "#64748b";

  return (
    <div className="min-h-screen bg-mesh px-4 py-6 md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="panel px-6 py-5 shadow-glow">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="font-heading text-2xl font-bold md:text-3xl">
                Human Digital Twin For Personal Wellness Optimization
              </h1>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                AI-powered simulation and wellness analytics using Logistic Regression, Random Forest, and LSTM.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleTrain}
                className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-60"
                disabled={loadingTrain}
              >
                <RefreshCw size={16} className={loadingTrain ? "animate-spin" : ""} />
                {loadingTrain ? "Training..." : "Train Models"}
              </button>
              <button
                onClick={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
                className="rounded-lg border border-slate-400/30 bg-white/70 p-2 text-slate-700 transition hover:bg-white dark:bg-slate-900/70 dark:text-slate-200"
              >
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>
          </div>
        </header>

        <nav className="grid grid-cols-1 gap-2 md:grid-cols-3">
          {MODES.map((item) => {
            const Icon = item.icon;
            const active = mode === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setMode(item.key)}
                className={`panel px-4 py-3 text-left transition ${
                  active ? "ring-2 ring-cyan-500" : "hover:-translate-y-0.5"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon size={18} />
                  <span className="font-semibold">{item.label}</span>
                </div>
              </button>
            );
          })}
        </nav>

        {error && (
          <div className="panel border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
            {error}
          </div>
        )}

        <section className="grid gap-6 lg:grid-cols-[350px,1fr]">
          <aside className="space-y-6">
            <form onSubmit={handlePredict} className="panel space-y-3 p-4">
              <h2 className="font-heading text-lg font-semibold">Manual Data Entry</h2>

              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-slate-600 dark:text-slate-300">
                  Age
                  <input
                    type="number"
                    value={formData.age}
                    onChange={(e) => setFormData((value) => ({ ...value, age: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-300/60 bg-white/80 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/60"
                  />
                </label>
                <label className="text-xs text-slate-600 dark:text-slate-300">
                  Gender
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData((value) => ({ ...value, gender: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-300/60 bg-white/80 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/60"
                  >
                    <option>Male</option>
                    <option>Female</option>
                    <option>Other</option>
                  </select>
                </label>
              </div>

              {[
                ["sleep_hours", "Sleep Hours"],
                ["daily_steps", "Daily Steps"],
                ["heart_rate", "Heart Rate"],
                ["calories_burned", "Calories Burned"],
                ["stress_level", "Stress Level (1-10)"],
                ["water_intake", "Water Intake (L)"],
                ["exercise_minutes", "Exercise Minutes"],
              ].map(([key, label]) => (
                <label key={key} className="block text-xs text-slate-600 dark:text-slate-300">
                  {label}
                  <input
                    type="number"
                    step={key === "water_intake" || key === "sleep_hours" ? "0.1" : "1"}
                    value={formData[key]}
                    onChange={(e) => setFormData((value) => ({ ...value, [key]: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-300/60 bg-white/80 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900/60"
                  />
                </label>
              ))}

              <button
                className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-60"
                disabled={loadingPredict}
              >
                {loadingPredict ? "Predicting..." : "Generate Prediction"}
              </button>
            </form>

            <div className="panel p-4">
              <h2 className="font-heading text-lg font-semibold">Dataset Upload</h2>
              <label className="mt-3 flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-cyan-500/40 bg-cyan-500/5 p-5 text-center">
                <UploadCloud size={28} className="text-cyan-600 dark:text-cyan-300" />
                <span className="text-sm text-slate-600 dark:text-slate-300">
                  Upload CSV or Excel for batch predictions
                </span>
                <input type="file" className="hidden" accept=".csv,.xlsx,.xls" onChange={handleUpload} />
              </label>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Required columns: {FEATURE_COLUMNS.join(", ")}
              </p>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {loadingUpload ? "Processing uploaded dataset..." : "Batch analysis updates Dataset Insights mode."}
              </p>
            </div>

            <div className="panel p-4">
              <h2 className="font-heading text-lg font-semibold">Digital Twin Panel</h2>
              <div className="mt-3 flex items-center justify-between gap-4">
                <div className="relative h-36 w-24">
                  <div className="absolute left-1/2 top-0 h-8 w-8 -translate-x-1/2 rounded-full" style={{ backgroundColor: twinColor }} />
                  <div className="absolute left-1/2 top-8 h-14 w-10 -translate-x-1/2 rounded-lg" style={{ backgroundColor: twinColor }} />
                  <div className="absolute left-1 top-12 h-4 w-6 rounded-md" style={{ backgroundColor: twinColor }} />
                  <div className="absolute right-1 top-12 h-4 w-6 rounded-md" style={{ backgroundColor: twinColor }} />
                  <div className="absolute left-5 top-[88px] h-12 w-5 rounded-md" style={{ backgroundColor: twinColor }} />
                  <div className="absolute right-5 top-[88px] h-12 w-5 rounded-md" style={{ backgroundColor: twinColor }} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Twin Status</div>
                  <div className={`mt-1 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${categoryClass(prediction?.wellness_category || "Poor")}`}>
                    {prediction?.wellness_category || "Awaiting Prediction"}
                  </div>
                </div>
              </div>
            </div>
          </aside>

          <main className="space-y-6">
            <AnimatePresence mode="wait">
              {mode === "overview" && (
                <motion.div
                  key="overview"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-6"
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="panel p-5">
                      <div className="text-sm text-slate-500 dark:text-slate-400">Wellness Score</div>
                      <div className="mt-2 flex items-end gap-3">
                        <div className="font-heading text-5xl font-bold">{prediction?.wellness_score ?? "--"}</div>
                        <div className={`rounded-full px-3 py-1 text-sm font-semibold ${categoryClass(prediction?.wellness_category || "Poor")}`}>
                          {prediction?.wellness_category || "No category"}
                        </div>
                      </div>
                      <div className="mt-4 h-2 rounded-full bg-slate-300/40">
                        <div
                          className="h-2 rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500"
                          style={{ width: `${prediction?.wellness_score || 0}%` }}
                        />
                      </div>
                    </div>

                    <div className="panel p-5">
                      <div className="mb-2 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                        <Brain size={16} />
                        AI Recommendations
                      </div>
                      <ul className="space-y-2 text-sm">
                        {(prediction?.recommendations || ["Generate a prediction to receive personalized recommendations."]).map((item, index) => (
                          <li key={`${item}-${index}`} className="rounded-md bg-slate-500/10 px-3 py-2">
                            {item}
                          </li>
                        ))}
                      </ul>
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={exportHistory}
                          className="inline-flex items-center gap-2 rounded-md border border-slate-400/40 px-3 py-1.5 text-xs font-semibold"
                        >
                          <Download size={14} />
                          Export History CSV
                        </button>
                        <button
                          onClick={downloadReport}
                          className="inline-flex items-center gap-2 rounded-md border border-slate-400/40 px-3 py-1.5 text-xs font-semibold"
                          disabled={!prediction}
                        >
                          <Download size={14} />
                          Download Report
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="panel overflow-x-auto p-4">
                    <h3 className="font-heading text-lg font-semibold">Model Performance</h3>
                    <table className="mt-3 min-w-full text-sm">
                      <thead className="text-left text-slate-500 dark:text-slate-400">
                        <tr>
                          <th className="py-2">Model</th>
                          <th className="py-2">Accuracy</th>
                          <th className="py-2">Precision</th>
                          <th className="py-2">Recall</th>
                          <th className="py-2">F1</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.map((item) => (
                          <tr key={item.model_name} className="border-t border-slate-400/15">
                            <td className="py-2 font-semibold">{item.model_name}</td>
                            <td className="py-2">{item.accuracy ?? "N/A"}</td>
                            <td className="py-2">{item.precision ?? "N/A"}</td>
                            <td className="py-2">{item.recall ?? "N/A"}</td>
                            <td className="py-2">{item.f1_score ?? "N/A"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {trainingMeta?.artifacts && (
                      <div className="mt-4 grid gap-3 md:grid-cols-3">
                        {Object.entries(trainingMeta.artifacts)
                          .filter(([name]) => name.includes("confusion_matrix"))
                          .map(([name, path]) => (
                            <img
                              key={name}
                              src={`http://localhost:8000/artifacts/${artifactFile(path)}`}
                              alt={name}
                              className="h-40 w-full rounded-lg object-cover"
                            />
                          ))}
                      </div>
                    )}
                  </div>

                  <div className="panel overflow-x-auto p-4">
                    <h3 className="font-heading text-lg font-semibold">Prediction History</h3>
                    <table className="mt-3 min-w-full text-sm">
                      <thead className="text-left text-slate-500 dark:text-slate-400">
                        <tr>
                          <th className="py-2">Time</th>
                          <th className="py-2">Source</th>
                          <th className="py-2">Score</th>
                          <th className="py-2">Category</th>
                          <th className="py-2">Sleep</th>
                          <th className="py-2">Steps</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.slice(0, 12).map((item) => (
                          <tr key={item.id} className="border-t border-slate-400/15">
                            <td className="py-2">{new Date(item.created_at).toLocaleString()}</td>
                            <td className="py-2">{item.source}</td>
                            <td className="py-2 font-semibold">{item.wellness_score}</td>
                            <td className="py-2">
                              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${categoryClass(item.wellness_category)}`}>
                                {item.wellness_category}
                              </span>
                            </td>
                            <td className="py-2">{item.input.sleep_hours}</td>
                            <td className="py-2">{item.input.daily_steps}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </motion.div>
              )}

              {mode === "analytics" && (
                <motion.div
                  key="analytics"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="grid gap-4 md:grid-cols-2"
                >
                  <div className="panel p-4">
                    <h3 className="mb-2 font-heading font-semibold">Sleep vs Wellness</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" dataKey="sleep_hours" name="Sleep" />
                          <YAxis type="number" dataKey="wellness_score" name="Wellness" />
                          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                          <Scatter data={analyticsData} fill="#0ea5e9" />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="panel p-4">
                    <h3 className="mb-2 font-heading font-semibold">Stress vs Wellness</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" dataKey="stress_level" name="Stress" />
                          <YAxis type="number" dataKey="wellness_score" name="Wellness" />
                          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                          <Scatter data={analyticsData} fill="#f97316" />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="panel p-4">
                    <h3 className="mb-2 font-heading font-semibold">Daily Steps vs Wellness</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={analyticsData.slice(0, 40)}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="index" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="daily_steps" fill="#14b8a6" name="Daily Steps" />
                          <Bar dataKey="wellness_score" fill="#22c55e" name="Wellness Score" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="panel p-4">
                    <h3 className="mb-2 font-heading font-semibold">Heart Rate Trends</h3>
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={analyticsData.slice(0, 90)}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="index" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="heart_rate" stroke="#f43f5e" strokeWidth={2} />
                          <Line type="monotone" dataKey="wellness_score" stroke="#0ea5e9" strokeWidth={2} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </motion.div>
              )}

              {mode === "dataset" && (
                <motion.div
                  key="dataset"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-6"
                >
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="panel p-4">
                      <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Rows</div>
                      <div className="font-heading text-3xl font-semibold">{datasetInsights?.rows ?? "--"}</div>
                    </div>
                    <div className="panel p-4">
                      <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Columns</div>
                      <div className="font-heading text-3xl font-semibold">{datasetInsights?.columns ?? "--"}</div>
                    </div>
                    <div className="panel p-4">
                      <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Avg Score</div>
                      <div className="font-heading text-3xl font-semibold">{datasetInsights?.score_summary?.mean ?? "--"}</div>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="panel p-4">
                      <h3 className="mb-2 font-heading font-semibold">Prediction Category Distribution</h3>
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={categoryDistribution}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={100}
                              label
                            >
                              {categoryDistribution.map((entry) => (
                                <Cell key={entry.name} fill={entry.color} />
                              ))}
                            </Pie>
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="panel overflow-x-auto p-4">
                      <h3 className="mb-2 font-heading font-semibold">Correlation Snapshot</h3>
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="text-left text-slate-500 dark:text-slate-400">
                            <th className="py-2">Feature</th>
                            <th className="py-2">Predicted Score Correlation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(datasetInsights?.correlations || {})
                            .filter(([key]) => key !== "predicted_wellness_score")
                            .slice(0, 10)
                            .map(([feature, values]) => (
                              <tr key={feature} className="border-t border-slate-400/15">
                                <td className="py-2">{feature}</td>
                                <td className="py-2">{values.predicted_wellness_score ?? "--"}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="panel overflow-x-auto p-4">
                    <h3 className="font-heading text-lg font-semibold">Uploaded Dataset Preview</h3>
                    <table className="mt-3 min-w-full text-xs md:text-sm">
                      <thead className="text-left text-slate-500 dark:text-slate-400">
                        <tr>
                          {datasetPreview[0] &&
                            Object.keys(datasetPreview[0]).map((column) => (
                              <th key={column} className="whitespace-nowrap py-2 pr-4">
                                {column}
                              </th>
                            ))}
                        </tr>
                      </thead>
                      <tbody>
                        {datasetPreview.slice(0, 14).map((row, index) => (
                          <tr key={`row-${index}`} className="border-t border-slate-400/15">
                            {Object.entries(row).map(([key, value]) => (
                              <td key={`${index}-${key}`} className="whitespace-nowrap py-2 pr-4">
                                {String(value)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </main>
        </section>
      </div>
    </div>
  );
}

export default App;
