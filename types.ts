
export interface Course {
  course_name: string;
  spoken_name: string;
  department: string;
  duration_years: number;
  fees_yearly: number;
  aliases: string[];
  description: string;
  eligibility: string;
}

export interface UniversityProfile {
  university_name: string;
  official_short_name: string;
  type_legal_status: string;
  act_establishment: string;
  location_address: string;
  campus_size: string;
  accreditation_naac: string;
  ugc_recognition: string;
  memberships_affiliations: string;
  president_patron: string;
  director_general: string;
  student_strength: string;
  faculty_staff: string;
  major_schools: string;
  core_offerings: string;
  rankings_ratings: string;
  achievements_awards: string;
  official_website: string;
  admissions_portal: string;
  international_admissions: string;
  contact_phone: string;
  contact_email: string;
  international_email: string;
  alumni_count: string;
  research_incubation: string;
  notes: string;
}

export interface HelpdeskContact {
  institute_name: string;
  contact_person_1: string;
  contact_person_2: string;
  phone_number_1: string;
  phone_number_2: string;
  email: string;
  whatsapp_number: string;
  office_timings: string;
}

export interface TranscriptionItem {
  text: string;
  sender: 'user' | 'model';
  timestamp: number;
}
