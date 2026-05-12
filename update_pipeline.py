import sys

with open('App.tsx', 'r') as f:
    content = f.read()

start_marker = "{activeView === 'pipeline' && ("
end_marker = "            {activeView === 'analytics' && ("

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

pipeline_code = """{activeView === 'pipeline' && (
              <motion.div
                key="pipeline"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="h-full flex flex-col"
              >
                <div className="flex flex-wrap gap-4 items-center justify-between bg-slate-900/50 p-6 rounded-3xl border border-white/10 backdrop-blur-md mb-6">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-1">Lead Flow Pipeline</h2>
                        <p className="text-slate-400 text-sm">Leads automatically move through these stages based on conversation outcomes.</p>
                    </div>
                </div>

                <div className="flex-1 overflow-x-auto min-h-[600px] flex gap-6 pb-6 items-start hide-scrollbar">
                  
                  {[ 
                    { id: 'Start', title: 'Start', color: 'slate' },
                    { id: 'Cold call', title: 'Cold Call', color: 'blue' },
                    { id: 'Warm call', title: 'Warm Call', color: 'orange' },
                    { id: 'Hot Call', title: 'Hot Call', color: 'red' },
                    { id: 'CLOSE', title: 'CLOSE', color: 'emerald' },
                    { id: 'DNC', title: 'DNC', color: 'slate' },
                    { id: 'Cold', title: 'Unanswered (Cold)', color: 'slate' },
                    { id: 'warm', title: 'Unanswered (Warm)', color: 'slate' },
                    { id: 'hot', title: 'Unanswered (Hot)', color: 'slate' },
                  ].map(col => {
                    const colLeads = leads.filter(l => l.stage === col.id);
                    return (
                      <div key={col.id} className={`w-80 shrink-0 flex flex-col bg-slate-900/60 backdrop-blur-xl border border-${col.color}-500/20 rounded-[2rem] overflow-hidden`}>
                        <div className={`bg-${col.color}-900/40 px-6 py-5 border-b border-${col.color}-500/20 flex justify-between items-center sticky top-0 z-10`}>
                          <h3 className={`font-bold text-${col.color}-100`}>{col.title}</h3>
                          <span className={`bg-${col.color}-500/20 text-${col.color}-300 text-xs px-3 py-1.5 rounded-full font-bold`}>
                            {colLeads.length}
                          </span>
                        </div>
                        <div className="p-4 flex-1 overflow-y-auto space-y-4 min-h-[200px] max-h-[650px] scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                           <AnimatePresence>
                            {colLeads.map(lead => (
                              <motion.div 
                                layout
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                key={lead.phone_number} 
                                className={`bg-slate-950/80 p-5 rounded-2xl border border-slate-800 hover:border-${col.color}-500/40 transition-colors shadow-lg group`}
                              >
                                <div className="flex justify-between items-start mb-3">
                                  <div className={`font-mono text-sm text-${col.color}-300 font-bold group-hover:text-${col.color}-200 transition-colors`}>{lead.phone_number}</div>
                                  <div className="text-[10px] text-slate-500 bg-slate-900 px-2 py-1 rounded-md">{new Date(lead.updated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                                </div>
                                <div className="text-white text-sm font-medium mb-1 truncate">{lead.user_name || "Unknown User"}</div>
                                <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-slate-800">
                                  {lead.interest && lead.interest !== 'Unknown' && <span className="bg-slate-900 text-blue-300 text-[10px] px-2 py-1 rounded-md font-medium">{lead.interest}</span>}
                                  {lead.lead_status && lead.lead_status !== 'Unknown' && <span className={`bg-slate-900 text-[10px] px-2 py-1 rounded-md font-medium text-${col.color}-300`}>{lead.lead_status}</span>}
                                </div>
                              </motion.div>
                            ))}
                          </AnimatePresence>
                          {colLeads.length === 0 && (
                            <div className="h-full flex items-center justify-center text-slate-600 text-sm py-12 border-2 border-dashed border-slate-800/50 rounded-2xl">
                              Drop zone
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  
                </div>
              </motion.div>
            )}
"""

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + pipeline_code + content[end_idx:]
    with open('App.tsx', 'w') as f:
        f.write(new_content)
    print("Done replacing pipeline")
else:
    print("Markers not found")

