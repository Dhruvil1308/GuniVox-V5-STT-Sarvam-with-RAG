
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { GoogleGenAI, LiveServerMessage, Modality } from '@google/genai';
import { 
  MicOff, PhoneCall, PhoneOff, MessageSquare, Cpu, Activity, Info, 
  WifiOff, Languages, Wifi, Loader2, AlertCircle, RefreshCw
} from 'lucide-react';
import { decodeBase64, encodeBase64, decodeAudioData } from '../services/audioUtils';
import { COURSE_DB, UNIVERSITY_PROFILE, HELPDESK_DB } from '../data';
import { TranscriptionItem } from '../types';

const SYSTEM_INSTRUCTION = `
You are GuniVox, the intelligent voice assistant for Ganpat University (GUNI) admissions.
Location: Ganpat Vidyanagar, Mehsana–Gandhinagar Highway, Gujarat, India.

STRICT OPERATIONAL GUIDELINES:
1. INITIAL GREETING: "Hello! Welcome to Ganpat University Admissions. I am GuniVox. How can I assist you with your course inquiry today?"
2. MULTILINGUAL: Detect and respond in the user's language (English, Hindi, or Gujarati). If they switch, you switch immediately.
3. CONCISION: Keep spoken answers under 20 words.
4. KNOWLEDGE: Use the provided data for GUNI courses, fees, and eligibility.
5. ESCALATION: If the user asks for a human or specific help, provide the admissions hotline: +91-81006-16161.

DATASET:
${JSON.stringify({ university: UNIVERSITY_PROFILE, courses: COURSE_DB, helpdesk: HELPDESK_DB })}
`;

const VoiceAgent: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [transcription, setTranscription] = useState<TranscriptionItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isActiveSpeaker, setIsActiveSpeaker] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [detectedLang, setDetectedLang] = useState<string>('English');

  const audioContextInRef = useRef<AudioContext | null>(null);
  const audioContextOutRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);
  const sessionRef = useRef<any>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const transcriptionContainerRef = useRef<HTMLDivElement>(null);
  
  const currentInputTranscription = useRef('');
  const currentOutputTranscription = useRef('');
  const isClosingRef = useRef(false);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 3;

  useEffect(() => {
    if (transcriptionContainerRef.current) {
      transcriptionContainerRef.current.scrollTop = transcriptionContainerRef.current.scrollHeight;
    }
  }, [transcription]);

  const disconnect = useCallback((errorMsg: string | null = null, silent = false) => {
    isClosingRef.current = true;
    
    if (sessionRef.current) {
      try { sessionRef.current.close(); } catch (e) {}
      sessionRef.current = null;
    }
    
    sourcesRef.current.forEach(source => {
      try { source.stop(); } catch (e) {}
    });
    sourcesRef.current.clear();
    
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.onaudioprocess = null;
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (audioContextInRef.current) {
      try { audioContextInRef.current.close(); } catch (e) {}
      audioContextInRef.current = null;
    }
    if (audioContextOutRef.current) {
      try { audioContextOutRef.current.close(); } catch (e) {}
      audioContextOutRef.current = null;
    }
    
    setIsConnected(false);
    setIsConnecting(false);
    setIsReconnecting(false);
    setIsProcessing(false);
    setIsActiveSpeaker(false);
    nextStartTimeRef.current = 0;
    
    if (errorMsg && !silent) {
      setError(errorMsg);
    }
    isClosingRef.current = false;
  }, []);

  const connect = async (isRetry = false) => {
    if (!isRetry) {
      if (isConnected || isConnecting) return;
      retryCountRef.current = 0;
      setError(null);
      setIsConnecting(true);
    } else {
      setIsReconnecting(true);
    }

    isClosingRef.current = false;

    try {
      // Setup Audio Contexts
      const ctxIn = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      const ctxOut = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      
      if (ctxIn.state === 'suspended') await ctxIn.resume();
      if (ctxOut.state === 'suspended') await ctxOut.resume();

      audioContextInRef.current = ctxIn;
      audioContextOutRef.current = ctxOut;
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
      
      const session = await ai.live.connect({
        model: 'gemini-2.5-flash-native-audio-preview-12-2025',
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Kore' } },
          },
          systemInstruction: SYSTEM_INSTRUCTION,
          inputAudioTranscription: {},
          outputAudioTranscription: {},
        },
        callbacks: {
          onopen: () => {
            setIsConnected(true);
            setIsConnecting(false);
            setIsReconnecting(false);
            retryCountRef.current = 0;
            setError(null);

            const source = audioContextInRef.current!.createMediaStreamSource(stream);
            const scriptProcessor = audioContextInRef.current!.createScriptProcessor(4096, 1, 1);
            scriptProcessorRef.current = scriptProcessor;
            
            scriptProcessor.onaudioprocess = (e) => {
              if (isClosingRef.current || !sessionRef.current) return;

              const inputData = e.inputBuffer.getChannelData(0);
              const int16 = new Int16Array(inputData.length);
              for (let i = 0; i < inputData.length; i++) {
                int16[i] = inputData[i] * 32768;
              }
              const base64Data = encodeBase64(new Uint8Array(int16.buffer));
              
              try {
                // Ensure session is actually ready before pushing bits
                sessionRef.current.sendRealtimeInput({ 
                  media: { data: base64Data, mimeType: 'audio/pcm;rate=16000' } 
                });
              } catch (err) {
                console.debug("Dropped audio frame during socket fluctuation.");
              }
            };

            source.connect(scriptProcessor);
            scriptProcessor.connect(audioContextInRef.current!.destination);
          },
          onmessage: async (message: LiveServerMessage) => {
            if (message.serverContent?.modelTurn) setIsProcessing(false);

            const base64Audio = message.serverContent?.modelTurn?.parts?.[0]?.inlineData?.data;
            if (base64Audio) {
              setIsActiveSpeaker(true);
              const ctx = audioContextOutRef.current;
              if (!ctx) return;

              nextStartTimeRef.current = Math.max(nextStartTimeRef.current, ctx.currentTime);
              
              try {
                const audioBuffer = await decodeAudioData(decodeBase64(base64Audio), ctx, 24000, 1);
                const source = ctx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(ctx.destination);
                source.onended = () => {
                  sourcesRef.current.delete(source);
                  if (sourcesRef.current.size === 0) setIsActiveSpeaker(false);
                };
                
                source.start(nextStartTimeRef.current);
                nextStartTimeRef.current += audioBuffer.duration;
                sourcesRef.current.add(source);
              } catch (err) {
                console.error("Audio Playback Error:", err);
              }
            }

            if (message.serverContent?.inputTranscription) {
              const text = message.serverContent.inputTranscription.text;
              currentInputTranscription.current += text;
              setIsProcessing(true);

              if (/[\u0A80-\u0AFF]/.test(text)) setDetectedLang('Gujarati');
              else if (/[\u0900-\u097F]/.test(text)) setDetectedLang('Hindi');
              else if (/[a-zA-Z]{4,}/.test(text)) setDetectedLang('English');
            }
            
            if (message.serverContent?.outputTranscription) {
              currentOutputTranscription.current += message.serverContent.outputTranscription.text;
            }

            if (message.serverContent?.turnComplete) {
              setIsProcessing(false);
              if (currentInputTranscription.current) {
                setTranscription(prev => [...prev, {
                  text: currentInputTranscription.current,
                  sender: 'user',
                  timestamp: Date.now()
                }]);
                currentInputTranscription.current = '';
              }
              if (currentOutputTranscription.current) {
                setTranscription(prev => [...prev, {
                  text: currentOutputTranscription.current,
                  sender: 'model',
                  timestamp: Date.now()
                }]);
                currentOutputTranscription.current = '';
              }
            }

            if (message.serverContent?.interrupted) {
              sourcesRef.current.forEach(s => { try { s.stop(); } catch (e) {} });
              sourcesRef.current.clear();
              nextStartTimeRef.current = 0;
              setIsActiveSpeaker(false);
              setIsProcessing(false);
            }
          },
          onerror: (e: any) => {
            console.error("GuniVox Socket Failure:", e);
            handleReconnect();
          },
          onclose: (e) => {
            if (!isClosingRef.current && !e.wasClean) {
              handleReconnect();
            }
          }
        }
      });

      sessionRef.current = session;
    } catch (err: any) {
      console.error("Connection Failed:", err);
      if (!isRetry) {
        disconnect("Check your internet connection or microphone permissions.");
      } else {
        handleReconnect();
      }
    }
  };

  const handleReconnect = useCallback(() => {
    if (isClosingRef.current) return;
    
    if (retryCountRef.current < MAX_RETRIES) {
      retryCountRef.current++;
      const delay = Math.pow(2, retryCountRef.current) * 1000;
      console.log(`Retrying connection in ${delay}ms...`);
      
      disconnect(null, true);
      setIsReconnecting(true);
      
      setTimeout(() => {
        if (!isClosingRef.current) connect(true);
      }, delay);
    } else {
      disconnect("The link is unstable. Please check your network and try again.");
    }
  }, [connect, disconnect]);

  const renderStatus = () => {
    if (error) return (
      <div className="flex items-center gap-2 bg-red-500/10 text-red-500 px-3 py-1.5 rounded-full border border-red-500/20">
        <AlertCircle size={14} />
        <span className="text-[10px] font-black uppercase tracking-widest">Signal Error</span>
      </div>
    );
    if (isReconnecting) return (
      <div className="flex items-center gap-2 bg-blue-500/10 text-blue-500 px-3 py-1.5 rounded-full border border-blue-500/20">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-[10px] font-black uppercase tracking-widest">Repairing Link...</span>
      </div>
    );
    if (isConnecting) return (
      <div className="flex items-center gap-2 bg-amber-500/10 text-amber-500 px-3 py-1.5 rounded-full border border-amber-500/20">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-[10px] font-black uppercase tracking-widest">Handshake...</span>
      </div>
    );
    if (isConnected) return (
      <div className="flex items-center gap-2 bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full border border-green-500/20">
        <Wifi size={14} className="animate-pulse" />
        <span className="text-[10px] font-black uppercase tracking-widest">Online</span>
      </div>
    );
    return (
      <div className="flex items-center gap-2 bg-slate-500/10 text-slate-500 px-3 py-1.5 rounded-full border border-slate-500/20">
        <MicOff size={14} />
        <span className="text-[10px] font-black uppercase tracking-widest">Offline</span>
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden relative">
      {/* Header */}
      <div className="bg-gradient-to-br from-[#0a192f] to-[#112240] p-6 flex flex-col gap-4 shadow-xl z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-5">
            <div className={`relative w-16 h-16 rounded-full border-4 border-blue-500/30 flex items-center justify-center transition-all duration-500 ${isConnected ? 'bg-blue-600 shadow-[0_0_20px_rgba(37,99,235,0.3)]' : 'bg-slate-800'}`}>
              {isConnected && <div className="absolute inset-0 rounded-full animate-ping bg-blue-400/20 scale-150"></div>}
              {isConnected ? <Activity className="text-white animate-pulse" size={28} /> : <MicOff className="text-white/40" size={28} />}
            </div>
            <div>
              <h2 className="text-white font-black text-2xl tracking-tight">GuniVox Live</h2>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                {renderStatus()}
                {isConnected && (
                  <div className="flex items-center gap-1.5 text-blue-300 text-[10px] font-black bg-white/5 px-3 py-1.5 rounded-full border border-white/10">
                    <Languages size={14} />
                    <span>{detectedLang.toUpperCase()}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <button
            onClick={isConnected ? () => disconnect() : () => connect()}
            disabled={isConnecting || isReconnecting}
            className={`group flex items-center gap-3 px-8 py-4 rounded-2xl font-black transition-all shadow-xl active:scale-95 ${
              isConnected ? 'bg-rose-500 text-white hover:bg-rose-600' : 'bg-white text-[#0a192f] hover:bg-blue-50'
            }`}
          >
            {isConnected ? <PhoneOff size={22} /> : <PhoneCall size={22} className={isConnecting ? "animate-spin" : ""} />}
            {isConnected ? 'END CALL' : isConnecting ? 'CONNECTING...' : 'START CALL'}
          </button>
        </div>
      </div>

      {/* Main Feed */}
      <div ref={transcriptionContainerRef} className="flex-1 p-8 overflow-y-auto space-y-8 bg-slate-50/20 custom-scrollbar relative">
        {!isConnected && !isConnecting && transcription.length === 0 && !error && (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-8">
            <div className="w-28 h-28 bg-blue-100 rounded-[2.5rem] flex items-center justify-center text-blue-600 rotate-6 shadow-inner">
               <MessageSquare size={56} />
            </div>
            <div>
              <h3 className="text-[#0a192f] font-black text-3xl tracking-tight">AI Admission Desk</h3>
              <p className="text-slate-500 text-sm mt-3 leading-relaxed font-medium">
                GuniVox is ready to help you with course details, fees, and admissions in English, Hindi, or Gujarati.
              </p>
            </div>
          </div>
        )}

        {transcription.map((item, idx) => (
          <div key={idx} className={`flex flex-col ${item.sender === 'user' ? 'items-end' : 'items-start'} animate-in slide-in-from-bottom-4 duration-500`}>
            <span className={`text-[10px] uppercase font-black mb-2 px-4 tracking-widest ${item.sender === 'user' ? 'text-blue-500' : 'text-slate-400'}`}>
              {item.sender === 'user' ? 'APPLICANT' : 'GUNIVOX'}
            </span>
            <div className={`max-w-[80%] rounded-[2rem] px-7 py-5 text-sm shadow-xl border transition-all ${
              item.sender === 'user' ? 'bg-[#112240] text-white rounded-tr-none' : 'bg-white text-[#0a192f] rounded-tl-none font-bold'
            }`}>
              <p className="leading-relaxed">{item.text}</p>
            </div>
          </div>
        ))}
        
        {isActiveSpeaker && (
           <div className="flex flex-col items-start animate-in fade-in duration-500">
              <span className="text-[10px] uppercase font-black text-slate-400 mb-2 px-4 tracking-widest">AI VOICE</span>
              <div className="bg-white border-2 border-blue-100 text-blue-600 rounded-[2rem] px-7 py-5 flex items-center gap-5 shadow-2xl">
                <div className="flex items-end gap-2 h-5">
                  <div className="w-2 bg-blue-300 rounded-full animate-[voice_0.8s_ease-in-out_infinite]"></div>
                  <div className="w-2 bg-blue-500 rounded-full animate-[voice_0.6s_ease-in-out_infinite_0.1s]"></div>
                  <div className="w-2 bg-blue-700 rounded-full animate-[voice_1s_ease-in-out_infinite_0.2s]"></div>
                </div>
                <span className="text-sm font-black tracking-widest uppercase">Responding...</span>
              </div>
           </div>
        )}
      </div>

      {/* Error Overlay */}
      {error && (
        <div className="absolute inset-0 z-50 bg-white/95 backdrop-blur-sm flex items-center justify-center p-8 animate-in fade-in">
          <div className="bg-white border border-slate-200 p-10 rounded-[3rem] flex flex-col items-center text-center gap-8 shadow-2xl max-w-sm">
            <div className="w-20 h-20 rounded-full bg-rose-50 flex items-center justify-center text-rose-500 animate-bounce">
              <WifiOff size={40} />
            </div>
            <div className="space-y-2">
              <p className="text-xl font-black text-[#0a192f] uppercase tracking-wider">Line Disturbance</p>
              <p className="text-sm text-slate-500 font-medium">{error}</p>
            </div>
            <button onClick={() => connect()} className="w-full flex items-center justify-center gap-3 px-8 py-4 bg-blue-600 text-white rounded-2xl text-xs font-black uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg active:scale-95">
              <RefreshCw size={16} /> Reconnect
            </button>
          </div>
        </div>
      )}

      {/* Waveform Footer */}
      <div className="h-24 border-t border-slate-50 flex flex-col items-center justify-center bg-white relative px-12">
        <div className="flex items-center justify-center gap-1.5 w-full max-w-4xl h-12">
          {[...Array(50)].map((_, i) => (
            <div 
              key={i} 
              className={`w-1 rounded-full transition-all duration-150 ${isConnected ? (isActiveSpeaker ? 'bg-blue-600' : isProcessing ? 'bg-yellow-400' : 'bg-slate-200') : 'bg-slate-100'}`} 
              style={{ 
                height: isConnected ? `${Math.max(4, Math.random() * (isActiveSpeaker ? 48 : isProcessing ? 24 : 8))}px` : '4px' 
              }}
            ></div>
          ))}
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes voice { 0%, 100% { height: 4px; } 50% { height: 16px; } }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
      `}} />
    </div>
  );
};

export default VoiceAgent;
