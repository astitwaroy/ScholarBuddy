import { useEffect, useState } from 'react';

export interface Profile {
  state?: string;
  category?: 'general' | 'ews' | 'obc' | 'ebc' | 'dnt' | 'sc' | 'st';
  gender?: 'female' | 'male' | 'transgender';
  disability_pct?: number;
  income?: number;
  level?: 'class_9_10' | 'class_11_12' | 'diploma' | 'ug' | 'pg' | 'phd';
  course_type?: 'technical' | 'medical' | 'general' | 'professional_other' | 'mba_mca';
  study_mode?: 'regular' | 'distance';
  class12_percentile?: number;
  qualifying_marks_pct?: number;
  school_type?: 'government' | 'govt_aided' | 'local_body' | 'private' | 'kv_jnv';
  top_institution?: boolean;
  studying_abroad?: boolean;
  other_scholarship?: boolean;
  age?: number;
  flags: string[];
  flags_answered: boolean;
}

export const emptyProfile: Profile = { flags: [], flags_answered: false };
const KEY = 'scholarsathi.profile.v1';

/** The profile lives only in this browser; the server never stores it. */
export function useProfile() {
  const [p, setP] = useState<Profile>(() => {
    try {
      return { ...emptyProfile, ...(JSON.parse(localStorage.getItem(KEY) ?? 'null') ?? {}) };
    } catch {
      return emptyProfile;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(p));
    } catch {
      /* storage unavailable */
    }
  }, [p]);
  return [p, setP] as const;
}

export const hasProfile = (p: Profile) => Object.entries(p).some(([k, v]) => k !== 'flags' && k !== 'flags_answered' && v !== undefined);

export const STATES: [string, string][] = [
  ['AN', 'Andaman & Nicobar'], ['AP', 'Andhra Pradesh'], ['AR', 'Arunachal Pradesh'], ['AS', 'Assam'], ['BR', 'Bihar'],
  ['CH', 'Chandigarh'], ['CT', 'Chhattisgarh'], ['DN', 'Dadra & Nagar Haveli and Daman & Diu'], ['DL', 'Delhi'], ['GA', 'Goa'],
  ['GJ', 'Gujarat'], ['HR', 'Haryana'], ['HP', 'Himachal Pradesh'], ['JK', 'Jammu & Kashmir'], ['JH', 'Jharkhand'],
  ['KA', 'Karnataka'], ['KL', 'Kerala'], ['LA', 'Ladakh'], ['LD', 'Lakshadweep'], ['MP', 'Madhya Pradesh'], ['MH', 'Maharashtra'],
  ['MN', 'Manipur'], ['ML', 'Meghalaya'], ['MZ', 'Mizoram'], ['NL', 'Nagaland'], ['OR', 'Odisha'], ['PY', 'Puducherry'],
  ['PB', 'Punjab'], ['RJ', 'Rajasthan'], ['SK', 'Sikkim'], ['TN', 'Tamil Nadu'], ['TG', 'Telangana'], ['TR', 'Tripura'],
  ['UP', 'Uttar Pradesh'], ['UT', 'Uttarakhand'], ['WB', 'West Bengal'],
];

export const FLAGS: [string, string][] = [
  ['orphan', 'I am an orphan'],
  ['parent_died_covid', 'I lost a parent to Covid-19'],
  ['ward_martyred_armed_forces', 'Child of Armed Forces / CAPF personnel martyred in action'],
  ['ward_capf_ar', 'Child or widow of CAPF / Assam Rifles personnel (below officer rank)'],
  ['ward_police_martyred', 'Child of State Police personnel killed in a terror or Naxal attack'],
  ['ward_ex_servicemen', 'Child or widow of an ex-serviceman or ex-Coast Guard'],
  ['single_girl_child', 'I am a single girl child'],
  ['tn_govt_school_6_12', 'Studied Class 6–12 in Tamil Nadu government schools (aided schools too, per 2024 reports)'],
];

export const LEVELS: [NonNullable<Profile['level']>, string][] = [
  ['class_9_10', 'Class 9–10'], ['class_11_12', 'Class 11–12'], ['diploma', 'Diploma / ITI / polytechnic'],
  ['ug', 'Undergraduate degree'], ['pg', 'Postgraduate (incl. MBA/MCA)'], ['phd', 'PhD'],
];

export const rupees = (n: number) =>
  n >= 100000 ? `₹${(n / 100000).toLocaleString('en-IN', { maximumFractionDigits: 2 })} lakh` : `₹${n.toLocaleString('en-IN')}`;
