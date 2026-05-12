import sqlite3

def run():
    conn = sqlite3.connect("gunivox.db")
    c = conn.cursor()
    c.execute("SELECT phone_number FROM leads")
    phones = [r[0] for r in c.fetchall()]
    
    for c_phone in phones:
        c.execute("SELECT status, LOWER(lead_status), call_sid FROM calls WHERE phone_number = ? ORDER BY started_at ASC", (c_phone,))
        all_calls = c.fetchall()
        
        pos_count = 0
        final_stage = 'Cold call'
        last_sid = None
        not_answered_states = ['no-answer', 'failed', 'busy', 'canceled', 'ringing']
        
        for status, l_status, sid in all_calls:
            last_sid = sid
            if l_status == 'negative':
                final_stage = 'DNC'
                break
                
            if l_status in ['positive', 'warm', 'hot']:
                pos_count += 1
                if pos_count == 1: final_stage = 'Warm call'
                elif pos_count == 2: final_stage = 'Hot Call'
                elif pos_count >= 3: final_stage = 'CLOSE'
            elif status in not_answered_states:
                if final_stage == 'Cold call': final_stage = 'Cold'
                elif final_stage == 'Warm call': final_stage = 'warm'
                elif final_stage == 'Hot Call': final_stage = 'hot'
                
        c.execute("UPDATE leads SET stage = ? WHERE phone_number = ?", (final_stage, c_phone))
        conn.commit()
    conn.close()
    print("Fixed legacy leads based on robust historical calculation")

run()
