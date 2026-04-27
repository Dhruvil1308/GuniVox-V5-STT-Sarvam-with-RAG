
import React from 'react';
import { COURSE_DB, UNIVERSITY_PROFILE } from '../data';
import { BookOpen, CheckCircle, Clock, IndianRupee, MapPin, Award, Users, Globe, Info } from 'lucide-react';

interface InfoDisplayProps {
  type: 'courses' | 'university';
}

const InfoDisplay: React.FC<InfoDisplayProps> = ({ type }) => {
  if (type === 'courses') {
    return (
      <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {COURSE_DB.map((course, idx) => (
            <div key={idx} className="bg-white border border-slate-200 rounded-2xl p-5 hover:border-blue-300 transition-all shadow-sm group">
              <div className="flex items-start justify-between mb-3">
                <span className="text-[10px] font-bold uppercase tracking-widest text-blue-500 bg-blue-50 px-2 py-1 rounded-md">
                  {course.department}
                </span>
                <div className="text-right">
                  <p className="text-[10px] text-slate-400 font-bold uppercase">Yearly Fees</p>
                  <p className="text-sm font-bold text-slate-800 flex items-center justify-end">
                    <IndianRupee size={14} /> {course.fees_yearly.toLocaleString()}
                  </p>
                </div>
              </div>
              <h3 className="font-bold text-slate-800 group-hover:text-blue-600 transition-colors mb-2 leading-tight">
                {course.course_name}
              </h3>
              <p className="text-xs text-slate-500 mb-4 line-clamp-2">
                {course.description}
              </p>
              
              <div className="grid grid-cols-2 gap-4 mt-auto border-t border-slate-50 pt-4">
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-slate-400" />
                  <span className="text-xs text-slate-600 font-medium">{course.duration_years} Years</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle size={14} className="text-green-500" />
                  <span className="text-[10px] text-slate-600 leading-tight">Eligible: {course.eligibility}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-8 pr-2 custom-scrollbar">
      {/* University Hero Card */}
      <div className="bg-blue-900 rounded-3xl p-8 text-white relative overflow-hidden shadow-xl">
        <div className="relative z-10">
          <h2 className="text-3xl font-extrabold mb-2">{UNIVERSITY_PROFILE.university_name}</h2>
          <p className="text-blue-200 max-w-lg mb-6 leading-relaxed">
            {UNIVERSITY_PROFILE.type_legal_status} Established in 2005.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] uppercase font-bold text-blue-300 tracking-wider">Accreditation</span>
              <div className="flex items-center gap-2">
                <Award size={18} className="text-yellow-400" />
                <span className="font-bold">{UNIVERSITY_PROFILE.accreditation_naac}</span>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] uppercase font-bold text-blue-300 tracking-wider">Campus Size</span>
              <div className="flex items-center gap-2">
                <MapPin size={18} className="text-red-400" />
                <span className="font-bold">{UNIVERSITY_PROFILE.campus_size}</span>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] uppercase font-bold text-blue-300 tracking-wider">Students</span>
              <div className="flex items-center gap-2">
                <Users size={18} className="text-green-400" />
                <span className="font-bold">{UNIVERSITY_PROFILE.student_strength}</span>
              </div>
            </div>
          </div>
        </div>
        {/* Abstract background elements */}
        <div className="absolute -right-20 -bottom-20 w-64 h-64 bg-white/5 rounded-full"></div>
        <div className="absolute right-10 top-10 w-20 h-20 bg-blue-500/20 rounded-full blur-2xl"></div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Info size={18} className="text-blue-500" />
            Establishment
          </h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            {UNIVERSITY_PROFILE.act_establishment}
          </p>
          <div className="mt-4 pt-4 border-t border-slate-50 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase">Recognized By</span>
            <span className="text-xs font-bold text-slate-800">{UNIVERSITY_PROFILE.ugc_recognition}</span>
          </div>
        </section>

        <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Globe size={18} className="text-blue-500" />
            Digital Presence
          </h3>
          <div className="space-y-3">
            <a href={UNIVERSITY_PROFILE.official_website} target="_blank" className="block p-3 rounded-xl bg-slate-50 hover:bg-slate-100 text-sm font-medium text-blue-600 truncate transition-colors">
              Official: {UNIVERSITY_PROFILE.official_website}
            </a>
            <a href={UNIVERSITY_PROFILE.admissions_portal} target="_blank" className="block p-3 rounded-xl bg-slate-50 hover:bg-slate-100 text-sm font-medium text-blue-600 truncate transition-colors">
              Admissions: {UNIVERSITY_PROFILE.admissions_portal}
            </a>
          </div>
        </section>
      </div>

      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        <h3 className="font-bold text-slate-800 mb-4">Constituent Schools</h3>
        <p className="text-sm text-slate-600 leading-relaxed">
          {UNIVERSITY_PROFILE.major_schools}
        </p>
      </div>
    </div>
  );
};

export default InfoDisplay;
