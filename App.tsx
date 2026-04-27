import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Phone,
  BarChart3,
  LogOut,
  PhoneCall,
  Download,
  Activity,
  User,
  CheckCircle,
  XCircle,
  Clock,
  ShieldCheck,
  Zap,
  Mic,
  Volume2,
  BookOpen,
  Edit2,
  Trash2,
  Plus,
  Search,
  Calendar,
  Trash
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- CONFIGURATION ---
const API_URL = "http://localhost:8000";

// --- TYPES ---
interface CallLog {
  id: number;
  call_sid: string;
  phone_number: string;
  status: string;
  started_at: string;
  user_name?: string;
  interest?: string;
  lead_status?: string;
  transcript?: string;
}

interface Stats {
  total_calls: number;
  positive_leads: number;
  recent_calls: CallLog[];
}

const App: React.FC = () => {
  // --- STATE ---
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [activeView, setActiveView] = useState<'dialer' | 'analytics' | 'courses'>('dialer');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Dialer State
  const [phoneNumber, setPhoneNumber] = useState("");
  const [callStatus, setCallStatus] = useState<"idle" | "calling" | "connected" | "ended">("idle");
  const [currentSid, setCurrentSid] = useState("");
  const [transcript, setTranscript] = useState<any[]>([]);

  // Analytics State
  const [stats, setStats] = useState<Stats | null>(null);
  const [logs, setLogs] = useState<CallLog[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedLog, setSelectedLog] = useState<CallLog | null>(null);

  // Course State
  interface Course {
    id?: number;
    name: string;
    description: string;
    fees: string;
    brochure_url?: string;
  }
  const [courses, setCourses] = useState<Course[]>([]);
  const [isCourseModalOpen, setIsCourseModalOpen] = useState(false);

  const [currentCourse, setCurrentCourse] = useState<Course>({ name: '', description: '', fees: '' });
  const [isEditingCourse, setIsEditingCourse] = useState(false);
  const [courseSearch, setCourseSearch] = useState("");

  const filteredCourses = courses.filter(c =>
    c.name.toLowerCase().includes(courseSearch.toLowerCase()) ||
    c.description.toLowerCase().includes(courseSearch.toLowerCase())
  );

  // --- HANDLERS ---

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      const res = await axios.post(`${API_URL}/api/login`, { username, password });
      if (res.data.token) {
        setIsLoggedIn(true);
      }
    } catch (err) {
      setError("Invalid Credentials. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCall = async () => {
    if (!phoneNumber) return;
    setCallStatus("calling");
    try {
      const res = await axios.post(`${API_URL}/api/call`, { phone_number: phoneNumber });
      if (res.data.success) {
        setCallStatus("connected");
        setCurrentSid(res.data.call_sid);
        setTranscript([{ role: "system", content: "Establishing secure connection..." }]);
      }
    } catch (err) {
      setCallStatus("idle");
      alert("Failed to initiate call. Check backend console.");
    }
  };

  const handleEndCall = async () => {
    if (!currentSid) return;
    try {
      await axios.post(`${API_URL}/api/end_call/${currentSid}`);
      setCallStatus("ended");
    } catch (err) {
      console.error("Failed to end call", err);
      // Force end in UI even if API fails
      setCallStatus("ended");
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/calls`, {
        params: {
          q: searchQuery,
          start_date: startDate,
          end_date: endDate
        }
      });
      // console.log("Fetched Logs:", res.data);
      setLogs(res.data);
    } catch (err) {
      console.error("Failed to fetch logs");
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/stats`, {
        params: { start_date: startDate, end_date: endDate }
      });
      setStats(res.data);
    } catch (err) {
      console.error("Failed to fetch stats");
    }
  };

  const handleDeleteLog = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this log?")) return;
    try {
      await axios.delete(`${API_URL}/api/calls/${id}`);
      fetchLogs(); // Refresh
      fetchStats(); // Update stats counters
    } catch (err) {
      alert("Failed to delete log.");
    }
  };

  const fetchCourses = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/courses`);
      setCourses(res.data);
    } catch (err) {
      console.error("Failed to fetch courses");
    }
  };

  const handleSaveCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (isEditingCourse && currentCourse.id) {
        await axios.put(`${API_URL}/api/courses/${currentCourse.id}`, currentCourse);
      } else {
        await axios.post(`${API_URL}/api/courses`, currentCourse);
      }
      setIsCourseModalOpen(false);
      resetCourseForm();
      fetchCourses();
    } catch (err) {
      alert("Failed to save course.");
    }
  };

  const handleDeleteCourse = async (id: number) => {
    if (!window.confirm("Delete this course?")) return;
    try {
      await axios.delete(`${API_URL}/api/courses/${id}`);
      fetchCourses();
    } catch (err) {
      alert("Failed to delete course.");
    }
  };

  const openEditCourse = (course: Course) => {
    setCurrentCourse(course);
    setIsEditingCourse(true);
    setIsCourseModalOpen(true);
  };

  const resetCourseForm = () => {
    setCurrentCourse({ name: '', description: '', fees: '' });
    setIsEditingCourse(false);
  };

  const downloadExcel = () => {
    let url = `${API_URL}/api/download`;
    if (startDate && endDate) {
      url += `?start_date=${startDate}&end_date=${endDate}`;
    }
    window.location.href = url;
  };

  useEffect(() => {
    let interval: any;
    if (activeView === 'analytics') {
      fetchStats();
      fetchLogs();
      interval = setInterval(() => { fetchStats(); fetchLogs(); }, 5000);
    } else if (activeView === 'courses') {
      fetchCourses();
    }
    return () => clearInterval(interval);
  }, [activeView, searchQuery, startDate, endDate]); // Re-fetch logs when search or date changes

  // Poll for Active Call Status & Transcript
  useEffect(() => {
    let interval: any;
    if (callStatus === 'connected' && currentSid) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_URL}/api/call/${currentSid}`);
          const { status, transcript } = res.data;

          if (transcript && transcript.length > 0) {
            setTranscript(transcript);
          }

          if (status === 'completed' || status === 'busy' || status === 'no-answer' || status === 'failed') {
            setCallStatus("ended");
            clearInterval(interval);
          }
        } catch (err) {
          console.error("Error polling call status:", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [callStatus, currentSid]);

  // --- UI COMPONENTS ---

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[conic-gradient(at_top_right,_var(--tw-gradient-stops))] from-slate-900 via-purple-900 to-slate-900 overflow-hidden relative">
        {/* Animated Background Elements */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-blue-600/20 rounded-full blur-3xl pointer-events-none"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-3xl pointer-events-none"
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="bg-white/5 backdrop-blur-xl border border-white/10 p-10 rounded-3xl w-full max-w-md shadow-2xl relative z-10"
        >
          <div className="flex flex-col items-center mb-8">
            <div className="w-20 h-20 bg-gradient-to-tr from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 mb-4 transform rotate-3 hover:rotate-0 transition-transform duration-300">
              <Zap className="text-white w-10 h-10" fill="currentColor" />
            </div>
            <h2 className="text-4xl font-bold text-white tracking-tight">GuniVox</h2>
            <p className="text-blue-200/80 mt-2 font-medium">Enterprise Intelligence Gateway</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-1">
              <label className="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Access ID</label>
              <div className="relative group">
                <User className="absolute left-4 top-3.5 text-slate-400 w-5 h-5 group-focus-within:text-blue-400 transition-colors" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl pl-12 pr-4 py-3.5 text-white focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all placeholder-slate-600 font-medium"
                  placeholder="Enter Username"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Secure Key</label>
              <div className="relative group">
                <ShieldCheck className="absolute left-4 top-3.5 text-slate-400 w-5 h-5 group-focus-within:text-blue-400 transition-colors" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl pl-12 pr-4 py-3.5 text-white focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all placeholder-slate-600 font-medium"
                  placeholder="••••••••••••"
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-red-500/10 border border-red-500/20 text-red-200 text-sm py-2 px-3 rounded-lg text-center font-medium flex items-center justify-center gap-2"
              >
                <XCircle size={16} /> {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-bold py-4 rounded-xl shadow-lg shadow-indigo-500/25 transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Authenticating...
                </span>
              ) : "Initialize System"}
            </button>
          </form>

          <div className="mt-8 text-center">
            <p className="text-xs text-slate-500 font-medium tracking-wide">SECURE ENCRYPTION ENABLED v3.0</p>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col md:flex-row font-sans text-slate-100 overflow-hidden relative">
      {/* Global Background Glow */}
      <div className="absolute top-0 left-0 w-full h-[300px] bg-gradient-to-b from-blue-900/10 to-transparent pointer-events-none" />

      {/* SIDEBAR */}
      <aside className="w-full md:w-72 bg-slate-900/80 backdrop-blur-md border-r border-white/5 flex flex-col justify-between p-6 z-20">
        <div>
          <div className="flex items-center gap-4 mb-12">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <Zap size={20} fill="currentColor" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight leading-none">GuniVox</h1>
              <span className="text-[10px] font-bold text-blue-400 tracking-wider uppercase">Pro Edition</span>
            </div>
          </div>

          <nav className="space-y-4">
            <button
              onClick={() => setActiveView('dialer')}
              className={`w-full group flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all duration-300 relative overflow-hidden ${activeView === 'dialer' ? 'bg-blue-600/20 text-blue-200' : 'hover:bg-slate-800/50 text-slate-400 hover:text-white'}`}
            >
              {activeView === 'dialer' && <motion.div layoutId="activeNav" className="absolute inset-0 bg-blue-600/10 border border-blue-500/20 rounded-2xl" />}
              <Phone size={20} className={activeView === 'dialer' ? 'text-blue-400' : ''} />
              <span className="font-semibold relative z-10">Smart Dialer</span>
            </button>
            <button
              onClick={() => setActiveView('analytics')}
              className={`w-full group flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all duration-300 relative overflow-hidden ${activeView === 'analytics' ? 'bg-purple-600/20 text-purple-200' : 'hover:bg-slate-800/50 text-slate-400 hover:text-white'}`}
            >
              {activeView === 'analytics' && <motion.div layoutId="activeNav" className="absolute inset-0 bg-purple-600/10 border border-purple-500/20 rounded-2xl" />}
              <BarChart3 size={20} className={activeView === 'analytics' ? 'text-purple-400' : ''} />
              <span className="font-semibold relative z-10">Analytics Hub</span>
            </button>
            <button
              onClick={() => setActiveView('courses')}
              className={`w-full group flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all duration-300 relative overflow-hidden ${activeView === 'courses' ? 'bg-emerald-600/20 text-emerald-200' : 'hover:bg-slate-800/50 text-slate-400 hover:text-white'}`}
            >
              {activeView === 'courses' && <motion.div layoutId="activeNav" className="absolute inset-0 bg-emerald-600/10 border border-emerald-500/20 rounded-2xl" />}
              <BookOpen size={20} className={activeView === 'courses' ? 'text-emerald-400' : ''} />
              <span className="font-semibold relative z-10">Courses</span>
            </button>
          </nav>
        </div>

        <button
          onClick={() => setIsLoggedIn(false)}
          className="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all mt-auto border border-transparent hover:border-white/5"
        >
          <LogOut size={18} />
          <span className="font-medium">Sign Out</span>
        </button>
      </aside>

      {/* MAIN CONTENT */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8 relative z-10">
        <div className="max-w-6xl mx-auto">

          <header className="mb-10 flex justify-between items-end">
            <div>
              <motion.h2
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                key={activeView}
                className="text-3xl font-bold text-white tracking-tight"
              >
                {activeView === 'dialer' ? "Command Center" : "Intelligence Reports"}
              </motion.h2>
              <p className="text-slate-400 mt-1 font-medium">
                {activeView === 'dialer' ? "Manage outbound communications." : activeView === 'analytics' ? "Analyze performance metrics." : "Manage university programs."}
              </p>
            </div>
            <div className="flex items-center gap-3 px-4 py-2 bg-emerald-500/10 text-emerald-300 rounded-full text-sm font-bold border border-emerald-500/20 backdrop-blur-sm shadow-lg shadow-emerald-500/10">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              System Operational
            </div>
          </header>

          <AnimatePresence mode="wait">
            {activeView === 'dialer' && (
              <motion.div
                key="dialer"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="grid lg:grid-cols-2 gap-8 h-[calc(100vh-200px)] min-h-[500px]"
              >
                {/* DIALER CARD */}
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-[2rem] border border-white/10 p-10 flex flex-col justify-center items-center text-center relative overflow-hidden group">
                  {/* Background Gradient Blob */}
                  <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-blue-500/5 to-transparent opacity-50 pointer-events-none" />

                  <div className="relative mb-8">
                    <motion.div
                      animate={{ scale: callStatus === 'connected' ? [1, 1.1, 1] : 1 }}
                      transition={{ repeat: Infinity, duration: 2 }}
                      className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-500 ${callStatus === 'connected'
                        ? 'bg-emerald-500/20 shadow-[0_0_60px_-10px_rgba(16,185,129,0.3)]'
                        : 'bg-slate-800 shadow-inner border border-slate-700'
                        }`}
                    >
                      <Phone className={`w-14 h-14 ${callStatus === 'connected' ? 'text-emerald-400' : 'text-slate-400'}`} />
                    </motion.div>
                    {callStatus === 'connected' && (
                      <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-emerald-500/20 text-emerald-300 text-xs font-bold px-3 py-1 rounded-full border border-emerald-500/30 backdrop-blur-sm">
                        LIVE
                      </span>
                    )}
                  </div>

                  <h3 className="text-xl font-medium text-slate-300 mb-6">Enter Destination Number</h3>

                  <div className="w-full max-w-sm relative mb-8">
                    <input
                      type="tel"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+91..."
                      className="w-full text-center bg-slate-950/50 border border-slate-700 rounded-2xl py-5 text-2xl font-mono text-white placeholder-slate-600 focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all shadow-inner"
                    />
                  </div>

                  <button
                    onClick={() => {
                      if (callStatus === 'connected') {
                        handleEndCall();
                      } else if (callStatus === 'ended') {
                        setCallStatus('idle');
                        setPhoneNumber("");
                        setTranscript([]);
                      } else {
                        handleCall();
                      }
                    }}
                    disabled={callStatus === 'calling'}
                    className={`w-full max-w-sm py-5 rounded-2xl font-bold text-lg shadow-xl hover:shadow-2xl transition-all transform hover:-translate-y-1 active:scale-95 flex items-center justify-center gap-3 
                        ${callStatus === 'connected'
                        ? 'bg-red-500/90 hover:bg-red-600 text-white shadow-red-900/20'
                        : callStatus === 'ended'
                          ? 'bg-slate-700 hover:bg-slate-600 text-white'
                          : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-900/20'
                      }`}
                  >
                    {callStatus === 'idle' && <><PhoneCall size={22} /> Initiate Call</>}
                    {callStatus === 'calling' && <><span className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></span> Connecting...</>}
                    {callStatus === 'connected' && <><Phone size={22} className="rotate-[135deg]" /> End Secure Call</>}
                    {callStatus === 'ended' && <><Zap size={22} /> Start New Call</>}
                  </button>

                  {callStatus === 'connected' && (
                    <p className="mt-6 text-sm text-slate-400 animate-pulse font-medium flex items-center gap-2">
                      <Mic size={14} className="text-emerald-400" /> Intelligence Active. Recording & Transcribing...
                    </p>
                  )}
                </div>

                {/* VISUALIZER CARD */}
                <div className="bg-slate-950 rounded-[2rem] border border-slate-800 p-8 flex flex-col overflow-hidden relative shadow-2xl">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-slate-200 font-semibold flex items-center gap-2">
                      <Activity className="text-blue-500" size={18} />
                      Live Waveform Analysis
                    </h3>
                    <div className="h-2 w-2 rounded-full bg-slate-800" />
                  </div>

                  {/* Waveform Visualizer */}
                  <div className="flex-1 flex items-center justify-center gap-2 min-h-[250px] relative">
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 to-transparent z-10 pointer-events-none" />

                    {[...Array(16)].map((_, i) => (
                      <motion.div
                        key={i}
                        className="w-3 rounded-full bg-gradient-to-t from-blue-600 to-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                        animate={{
                          height: callStatus === 'connected'
                            ? [20, Math.random() * 150 + 50, 20]
                            : 10,
                          opacity: callStatus === 'connected' ? 1 : 0.2
                        }}
                        transition={{
                          repeat: Infinity,
                          duration: 0.8 / (Math.random() * 0.5 + 0.5),
                          ease: "easeInOut",
                          delay: i * 0.05
                        }}
                      />
                    ))}
                  </div>

                  <div className="mt-6 pt-6 border-t border-slate-800 z-20">
                    <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest mb-3 flex items-center gap-2">
                      <Volume2 size={12} /> Live Transcription Stream
                    </p>
                    <div className="h-48 overflow-y-auto font-mono text-sm space-y-3 pr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                      {transcript.map((msg, idx) => (
                        <motion.div
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          key={idx}
                          className="flex gap-3"
                        >
                          <span className="text-slate-600 text-xs mt-1 shrink-0">[{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
                          <span className={msg.role === 'user' ? 'text-blue-200' : 'text-emerald-200'}>
                            {msg.content}
                          </span>
                        </motion.div>
                      ))}
                      {!transcript.length && (
                        <div className="flex items-center justify-center h-20 text-slate-600 italic text-xs">
                          Waiting for audio input stream...
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
            {activeView === 'analytics' && (
              <motion.div
                key="analytics"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-8"
              >
                {/* ACTIONS BAR: Search & Date */}
                <div className="flex flex-col md:flex-row gap-4 justify-between bg-slate-900/50 p-6 rounded-3xl border border-white/10 backdrop-blur-md">
                  <div className="relative flex-1">
                    <Search className="absolute left-4 top-3.5 text-slate-500" size={20} />
                    <input
                      type="text"
                      placeholder="Search History by Phone Number..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-12 pr-4 py-3 text-white focus:ring-2 focus:ring-purple-500/50 outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">From:</span>
                      <div className="relative group">
                        <Calendar className="absolute left-3 top-3.5 text-slate-500" size={16} />
                        <input
                          type="date"
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="bg-slate-950 border border-slate-700 rounded-xl pl-10 pr-4 py-3 text-white text-sm focus:ring-2 focus:ring-purple-500/50 outline-none"
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">To:</span>
                      <div className="relative group">
                        <Calendar className="absolute left-3 top-3.5 text-slate-500" size={16} />
                        <input
                          type="date"
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="bg-slate-950 border border-slate-700 rounded-xl pl-10 pr-4 py-3 text-white text-sm focus:ring-2 focus:ring-purple-500/50 outline-none"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <motion.div whileHover={{ y: -5 }} className="bg-slate-900/50 backdrop-blur-md p-8 rounded-3xl border border-white/10 shadow-lg relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10"><Phone size={64} /></div>
                    <p className="text-slate-400 text-sm font-bold uppercase tracking-wider">Total Calls</p>
                    <h3 className="text-4xl font-bold text-white mt-2">{stats?.total_calls || 0}</h3>
                    <div className="mt-4 text-xs text-green-400 flex items-center gap-1 font-medium bg-green-500/10 w-fit px-2 py-1 rounded-lg">
                      <Zap size={12} /> +12% this week
                    </div>
                  </motion.div>

                  <motion.div whileHover={{ y: -5 }} className="bg-slate-900/50 backdrop-blur-md p-8 rounded-3xl border border-white/10 shadow-lg relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10"><CheckCircle size={64} /></div>
                    <p className="text-slate-400 text-sm font-bold uppercase tracking-wider">Positive Leads</p>
                    <h3 className="text-4xl font-bold text-emerald-400 mt-2">{stats?.positive_leads || 0}</h3>
                    <div className="w-full bg-slate-800 h-1.5 mt-4 rounded-full overflow-hidden">
                      <div className="bg-emerald-500 h-full w-[65%]" />
                    </div>
                  </motion.div>

                  <motion.div
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={downloadExcel}
                    className="bg-gradient-to-br from-blue-600 to-indigo-700 p-8 rounded-3xl text-white shadow-xl shadow-blue-900/20 cursor-pointer flex flex-col justify-between group"
                  >
                    <div>
                      <div className="flex justify-between items-start mb-2">
                        <p className="text-blue-200 text-sm font-bold uppercase tracking-wider">Export Data</p>
                        <Download className="opacity-80 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <h3 className="text-2xl font-bold">Download Excel Report</h3>
                      <p className="text-sm text-blue-100 mt-2 opacity-80">Full transcripts & metadata included.</p>
                    </div>
                    <div className="self-end mt-4 bg-white/20 p-2 rounded-full backdrop-blur-sm group-hover:bg-white/30 transition-colors">
                      <Download size={20} />
                    </div>
                  </motion.div>
                </div>

                {/* Table */}
                <div className="bg-slate-900/50 backdrop-blur-md rounded-3xl border border-white/10 overflow-hidden shadow-2xl">
                  <div className="px-8 py-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                    <h3 className="font-bold text-lg text-white">Call History Database</h3>
                    <div className="flex gap-2">
                      <span className="text-xs text-slate-500 font-mono">
                        {logs.length} Records Found
                      </span>
                    </div>
                  </div>
                  <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-white/5 sticky top-0">
                        <tr>
                          <th className="px-8 py-5">Status</th>
                          <th className="px-8 py-5">Phone Number</th>
                          <th className="px-8 py-5">User Name</th>
                          <th className="px-8 py-5">Interest</th>
                          <th className="px-8 py-5">Lead Status</th>
                          <th className="px-8 py-5">Timestamp</th>
                          <th className="px-4 py-5">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {logs.map((call) => (
                          <tr
                            key={call.id}
                            onClick={() => setSelectedLog(call)}
                            className="hover:bg-white/[0.05] transition-colors group cursor-pointer"
                          >
                            <td className="px-8 py-5">
                              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${call.status === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                                : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                }`}>
                                {call.status === 'completed' ? <CheckCircle size={10} /> : <Clock size={10} />}
                                {call.status}
                              </span>
                            </td>
                            <td className="px-8 py-5 font-mono text-slate-300 group-hover:text-blue-300 transition-colors">{call.phone_number}</td>
                            <td className="px-8 py-5 text-white font-medium">{call.user_name || <span className="text-slate-600 italic">Unknown</span>}</td>
                            <td className="px-8 py-5 text-blue-400">{call.interest || "-"}</td>
                            <td className="px-8 py-5">
                              {call.lead_status === 'Positive'
                                ? <span className="text-emerald-400 font-bold bg-emerald-400/10 px-2 py-0.5 rounded">Positive</span>
                                : <span className="text-slate-500">{call.lead_status || "-"}</span>
                              }
                            </td>
                            <td className="px-8 py-5 text-slate-500">
                              {new Date(call.started_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </td>
                            <td className="px-4 py-5">
                              <button
                                onClick={(e) => handleDeleteLog(e, call.id)}
                                className="p-2 text-slate-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                                title="Delete Log"
                              >
                                <Trash size={16} />
                              </button>
                            </td>
                          </tr>
                        ))}
                        {logs.length === 0 && (
                          <tr>
                            <td colSpan={7} className="text-center py-12 text-slate-500">No records found matching your search.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </motion.div>
            )}
            {activeView === 'courses' && (
              <motion.div
                key="courses"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="flex justify-end">
                  <button
                    onClick={() => { resetCourseForm(); setIsCourseModalOpen(true); }}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 shadow-lg shadow-emerald-900/20 transition-all"
                  >
                    <Plus size={20} /> Add New Course
                  </button>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {courses.map((course) => (
                    <motion.div
                      layout
                      key={course.id}
                      className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-2xl p-6 hover:border-emerald-500/30 transition-all group"
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400">
                          <BookOpen size={24} />
                        </div>
                        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => openEditCourse(course)} className="p-2 hover:bg-white/10 rounded-lg text-blue-400 transition-colors"><Edit2 size={18} /></button>
                          <button onClick={() => handleDeleteCourse(course.id!)} className="p-2 hover:bg-white/10 rounded-lg text-red-400 transition-colors"><Trash2 size={18} /></button>
                        </div>
                      </div>
                      <h3 className="text-xl font-bold text-white mb-2">{course.name}</h3>
                      <p className="text-slate-400 text-sm mb-4 line-clamp-2">{course.description}</p>
                      <div className="flex items-center justify-between mt-auto pt-4 border-t border-white/5">
                        <span className="text-emerald-400 font-mono font-bold">{course.fees}</span>
                        {course.brochure_url && (
                          <a href={course.brochure_url} target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:underline flex items-center gap-1">
                            View Brochure <Download size={12} />
                          </a>
                        )}
                      </div>
                    </motion.div>
                  ))}
                  {courses.length === 0 && (
                    <div className="col-span-full text-center py-20 text-slate-500">
                      <BookOpen size={48} className="mx-auto mb-4 opacity-20" />
                      <p>No courses found. Add your first course to get started.</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {/* COURSE MODAL */}
      <AnimatePresence>
        {isCourseModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsCourseModalOpen(false)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-white/10 rounded-3xl shadow-2xl w-full max-w-lg relative z-10 p-8"
            >
              <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                {isEditingCourse ? <Edit2 className="text-blue-400" /> : <Plus className="text-emerald-400" />}
                {isEditingCourse ? "Edit Course" : "Add New Course"}
              </h2>
              <form onSubmit={handleSaveCourse} className="space-y-4">
                <div>
                  <label className="block text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Course Name</label>
                  <input
                    required
                    type="text"
                    value={currentCourse.name}
                    onChange={e => setCurrentCourse({ ...currentCourse, name: e.target.value })}
                    className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none"
                    placeholder="e.g. B.Tech Computer Engineering"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Yearly Fees</label>
                  <input
                    required
                    type="text"
                    value={currentCourse.fees}
                    onChange={e => setCurrentCourse({ ...currentCourse, fees: e.target.value })}
                    className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none"
                    placeholder="e.g. ₹1,40,000"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Description</label>
                  <textarea
                    required
                    value={currentCourse.description}
                    onChange={e => setCurrentCourse({ ...currentCourse, description: e.target.value })}
                    className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none h-24 resize-none"
                    placeholder="Short description of the course..."
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Brochure URL (Optional)</label>
                  <input
                    type="url"
                    value={currentCourse.brochure_url || ''}
                    onChange={e => setCurrentCourse({ ...currentCourse, brochure_url: e.target.value })}
                    className="w-full bg-slate-950/50 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none"
                    placeholder="https://..."
                  />
                </div>
                <div className="flex gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setIsCourseModalOpen(false)}
                    className="flex-1 py-3 rounded-xl bg-slate-800 text-slate-300 font-bold hover:bg-slate-700 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-3 rounded-xl bg-emerald-600 text-white font-bold hover:bg-emerald-500 transition-colors"
                  >
                    {isEditingCourse ? "Update Course" : "Create Course"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* LOG DETAILS MODAL */}
      <AnimatePresence>
        {selectedLog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelectedLog(null)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-white/10 rounded-3xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col relative z-10 overflow-hidden"
            >
              <div className="p-6 border-b border-white/5 flex justify-between items-start bg-slate-950/50">
                <div>
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <Phone size={20} className="text-blue-400" />
                    {selectedLog.phone_number}
                  </h3>
                  <p className="text-slate-400 text-sm mt-1">
                    {new Date(selectedLog.started_at).toLocaleString()} • ID: {selectedLog.call_sid}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="p-2 hover:bg-white/10 rounded-full transition-colors text-slate-400 hover:text-white"
                >
                  <XCircle size={24} />
                </button>
              </div>

              <div className="p-6 overflow-y-auto space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">User Name</p>
                    <p className="text-white font-medium text-lg">{selectedLog.user_name || "Unknown"}</p>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">Lead Status</p>
                    <p className={`${selectedLog.lead_status === 'Positive' ? 'text-emerald-400' : 'text-slate-300'} font-medium text-lg`}>
                      {selectedLog.lead_status || "Pending"}
                    </p>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">Interest</p>
                    <p className="text-blue-300 font-medium">{selectedLog.interest || "Not specified"}</p>
                  </div>
                  <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">Duration</p>
                    <p className="text-slate-300 font-medium">{selectedLog.status}</p>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Activity size={16} /> Transcript Analysis
                  </h4>
                  <div className="bg-slate-950 rounded-xl border border-white/10 p-4 max-h-60 overflow-y-auto font-mono text-sm space-y-3">
                    {(() => {
                      try {
                        const transcriptData = selectedLog.transcript ? JSON.parse(selectedLog.transcript) : [];
                        if (!transcriptData.length) return <p className="text-slate-500 italic">No transcript available.</p>;
                        return transcriptData.map((msg: any, i: number) => {
                          // Clean metadata tags from assistant messages for display
                          let displayText = msg.content;
                          if (msg.role === 'assistant') {
                            const textMatch = displayText.match(/TEXT:\s*(.*?)(?=\s*\||\s*NAME:|\s*INTEREST:|\s*STATUS:|$)/is);
                            if (textMatch) {
                              displayText = textMatch[1].trim();
                            } else {
                              // Fallback: strip all known tags
                              displayText = displayText
                                .replace(/LANG:\s*[a-z-]+\s*\|?/gi, '')
                                .replace(/NAME:\s*.*?(?=\s*\||$)/gi, '')
                                .replace(/INTEREST:\s*.*?(?=\s*\||$)/gi, '')
                                .replace(/STATUS:\s*.*?(?=\s*\||$)/gi, '')
                                .replace(/FOLLOW_UP:\s*.*?(?=\s*\||$)/gi, '')
                                .replace(/\|/g, '')
                                .trim();
                            }
                          }
                          return (
                            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                              <div className={`max-w-[80%] p-3 rounded-xl ${msg.role === 'user'
                                ? 'bg-blue-600/20 text-blue-100 rounded-tr-sm'
                                : 'bg-slate-800 text-slate-200 rounded-tl-sm'
                                }`}>
                                <p>{displayText}</p>
                              </div>
                            </div>
                          );
                        });
                      } catch (e) {
                        return <p className="text-red-400">Error parsing transcript data.</p>;
                      }
                    })()}
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-white/5 bg-slate-950/50 flex gap-3">
                <button
                  onClick={async () => {
                    try {
                      await axios.post(`${API_URL}/api/calls/${selectedLog.id}/reanalyze`);
                      fetchLogs();
                      // Re-fetch the updated log to refresh the modal
                      const res = await axios.get(`${API_URL}/api/calls`, { params: { q: selectedLog.phone_number } });
                      const updated = res.data.find((c: any) => c.id === selectedLog.id);
                      if (updated) setSelectedLog(updated);
                    } catch (err) {
                      console.error("Re-analysis failed");
                    }
                  }}
                  className="flex-1 py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <Activity size={18} /> Re-analyze Transcript
                </button>
                <button className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors flex items-center justify-center gap-2">
                  <Download size={18} /> Download Log Record
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default App;
