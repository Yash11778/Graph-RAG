import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import {
  Zap, Brain, Database, Network, Clock, DollarSign, Hash,
  CheckCircle2, XCircle, History, BarChart2, Moon, Sun,
  Sparkles, TrendingDown, Award, ChevronDown, BookOpen,
  Layers, GitMerge,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

/* ─── Pipeline registry (single source of truth) ─── */
const PIPELINE_KEYS    = ['llm_only', 'basic_rag', 'graphrag'];
const PIPELINE_COLORS  = { llm_only: '#ef4444', basic_rag: '#f97316', graphrag: '#16a34a' };
const PIPELINE_LABELS  = { llm_only: 'LLM-Only', basic_rag: 'Basic RAG', graphrag: 'GraphRAG' };
const PIPELINE_ICONS   = { llm_only: Brain, basic_rag: Database, graphrag: Network };
const PIPELINE_DESC    = {
  llm_only:  'No retrieval — pure parametric knowledge',
  basic_rag: 'FAISS vector search · top-5 chunks',
  graphrag:  'TigerGraph multi-hop · num_hops=2',
};

/* ─── Featured questions — each entity verified to exist in the LIVE TigerGraph graph
   and the answer confirmed on-topic. No pre-computed reduction numbers here: the only
   percentages shown anywhere are the genuine ones measured live after a query runs. ─── */
const FEATURED_QUESTIONS = [
  {
    label: 'Free Software',
    icon: '💻',
    question: 'What freedoms does free software give users?',
    answer: 'Free software gives users the freedom to run, copy, distribute, study, change, and improve the software.',
    hint: 'free-software → the four freedoms',
  },
  {
    label: 'Napoleon Bonaparte',
    icon: '🏛️',
    question: 'Who was Napoleon Bonaparte and what was his role in the Egypt expedition?',
    answer: 'Napoleon Bonaparte was a French military and political leader who led the French expedition in Egypt.',
    hint: 'napoleon-bonaparte → aboukir-bay, egypt (1-hop)',
  },
  {
    label: 'Roman Empire',
    icon: '🏺',
    question: 'What was the Roman Empire?',
    answer: 'The Roman Empire was an ancient state that controlled vast territories across Europe and the Mediterranean, ruled by emperors such as Augustus.',
    hint: 'roman-empire → augustus (1-hop)',
  },
  {
    label: 'Nelson Mandela',
    icon: '✊',
    question: 'Who was Nelson Mandela?',
    answer: 'Nelson Mandela was a South African anti-apartheid revolutionary and political leader.',
    hint: 'nelson-mandela → south-africa (1-hop)',
  },
  {
    label: 'World War II',
    icon: '⚔️',
    question: 'What was World War II and when did it take place?',
    answer: 'World War II was a global conflict between the Axis and Allied powers that lasted from 1939 to 1945.',
    hint: 'world-war-ii → axis, allies (1-hop)',
  },
  {
    label: 'Cold War',
    icon: '🌐',
    question: 'What was the Cold War?',
    answer: 'The Cold War was a period of geopolitical tension between the Soviet Union and the United States.',
    hint: 'cold-war → soviet-union, united-states',
  },
];

/* ─── Domain questions — all verified PASS in GraphRAG eval (eval/results/eval_results.csv).
   Each carries its ground-truth answer so selecting it enables LLM Judge + BERTScore. ─── */
const DOMAIN_QUESTIONS = [
  {
    domain: '💻 Free Software & Open Source',
    questions: [
      { question: 'What is free software?', answer: 'Free software is software that gives users the freedom to run, copy, distribute, study, change, and improve it.' },
      { question: 'What freedoms does free software give users?', answer: 'Free software gives users the freedom to run, copy, distribute, study, change, and improve the software.' },
      { question: 'What is the Free Software Foundation?', answer: 'The Free Software Foundation is a nonprofit organization that promotes the development and use of free software.' },
      { question: 'What are the core principles of the free software movement?', answer: 'The free software movement is built on four freedoms: the freedom to run, study, modify, and redistribute software without restriction.' },
      { question: 'How does free software protect users from proprietary restrictions?', answer: 'Free software licenses ensure users can use, modify, and share software without being locked into proprietary systems.' },
      { question: 'What is the free software movement?', answer: 'The free software movement is a social movement that campaigns for users to have the freedom to run, study, share, and modify software.' },
      { question: 'What is the difference between free software and proprietary software?', answer: 'Free software grants users four essential freedoms, while proprietary software restricts users from viewing, modifying, or distributing the source code.' },
      { question: 'How does free software relate to software in general?', answer: 'Free software is a category of software defined by the freedoms it grants users to run, study, change, and distribute it.' },
      { question: 'What is open source software?', answer: 'Open source software is software whose source code is available for anyone to inspect, modify, and distribute.' },
      { question: 'What is the significance of the Free Software Foundation?', answer: 'The Free Software Foundation promotes free software, maintains key licenses, and advocates for digital rights and user freedom worldwide.' },
      { question: 'Why did the free software movement become important?', answer: 'The free software movement became important because it ensured users, not corporations, control the software they use and can share it freely.' },
      { question: 'Why is software freedom important?', answer: 'Software freedom is important because it allows users to control the software they use and prevents dependence on proprietary vendors.' },
      { question: 'What is a free software license?', answer: 'A free software license grants users the freedom to use, study, modify, and distribute software without restriction.' },
      { question: 'How has free software impacted the technology industry?', answer: 'Free software has democratized software development, enabled global collaboration, reduced costs, and powered critical infrastructure like Linux and the internet.' },
    ],
  },
  {
    domain: '🌍 World War II',
    questions: [
      { question: 'What was World War II and when did it take place?', answer: 'World War II was a global conflict between the Axis and Allied powers that lasted from 1939 to 1945.' },
      { question: 'What were the Axis powers in World War II?', answer: 'The Axis powers were the primary military alliance opposing the Allies in World War II, led by Germany under Adolf Hitler.' },
      { question: 'What were the two opposing alliances in World War II?', answer: 'The two opposing alliances in World War II were the Axis powers and the Allied powers.' },
      { question: 'What role did Germany play in World War II?', answer: 'Germany, led by Adolf Hitler, was the principal Axis power in World War II.' },
      { question: 'What role did Japan play in World War II?', answer: 'Japan was one of the Axis powers in World War II, fighting in the Pacific theater.' },
      { question: 'What role did the United States play in World War II?', answer: 'The United States was one of the Allied powers in World War II, joining after the attack on Pearl Harbor in 1941.' },
      { question: 'What role did France play in World War II?', answer: 'France was invaded and occupied by Germany during World War II and was one of the Allied powers.' },
      { question: 'What was the Manhattan Project?', answer: 'The Manhattan Project was the US research effort during World War II that developed the first atomic bombs.' },
      { question: 'What did the Manhattan Project develop?', answer: 'The Manhattan Project developed the first atomic bombs, which were dropped on Hiroshima and Nagasaki in 1945.' },
      { question: 'Who was Adolf Hitler?', answer: 'Adolf Hitler was the dictator of Nazi Germany who led the Axis powers during World War II.' },
      { question: 'Who was Winston Churchill?', answer: 'Winston Churchill was the British Prime Minister who led the United Kingdom during World War II.' },
      { question: 'What were the Allied powers in World War II?', answer: 'The Allied powers were the countries that fought against the Axis in World War II, including the United States, United Kingdom, and Soviet Union.' },
      { question: 'How did World War II end?', answer: 'World War II ended in 1945 with the defeat of Germany in Europe and Japan\'s surrender after atomic bombs were dropped on Hiroshima and Nagasaki.' },
      { question: 'Why did the United States drop atomic bombs on Japan?', answer: 'The United States dropped atomic bombs on Hiroshima and Nagasaki in 1945 to force Japan\'s surrender and end World War II.' },
      { question: 'What were the consequences of World War II?', answer: 'World War II led to the deaths of over 70 million people, the formation of the United Nations, the beginning of the Cold War, and the end of European colonial empires.' },
    ],
  },
  {
    domain: '🥶 Cold War & Global Alliances',
    questions: [
      { question: 'What was the Cold War?', answer: 'The Cold War was a period of geopolitical tension between the Soviet Union and the United States from 1947 to 1991.' },
      { question: 'Who fought in the Cold War?', answer: 'The Cold War was fought between the Soviet Union and the United States without direct military conflict.' },
      { question: 'Which countries were the main rivals during the Cold War?', answer: 'The main rivals during the Cold War were the United States and the Soviet Union.' },
      { question: 'What was the Soviet Union?', answer: 'The Soviet Union was a socialist federal state in Eurasia that existed from 1922 to 1991.' },
      { question: 'What is NATO?', answer: 'NATO is the North Atlantic Treaty Organization, a military alliance of North American and European countries formed in 1949.' },
      { question: 'What is the United Nations?', answer: 'The United Nations is an international organization founded in 1945 to promote international peace and cooperation.' },
      { question: 'What was the Korean War?', answer: 'The Korean War was a conflict between North Korea and South Korea from 1950 to 1953, with US and UN forces supporting South Korea.' },
      { question: 'What was the Vietnam War?', answer: 'The Vietnam War was a conflict in Vietnam from 1955 to 1975 involving North Vietnam, South Vietnam, and the United States.' },
      { question: 'What role did the United States play in the Cold War?', answer: 'The United States was the leading Western power during the Cold War, opposing Soviet expansion through NATO and various military interventions.' },
      { question: 'What role did the Soviet Union play in the Cold War?', answer: 'The Soviet Union was the leading communist superpower during the Cold War, competing with the United States for global influence.' },
      { question: 'Why was NATO formed?', answer: 'NATO was formed in 1949 as a collective defense alliance among Western nations to counter the Soviet threat during the Cold War.' },
      { question: 'What was the purpose of the United Nations?', answer: 'The United Nations was founded in 1945 to maintain international peace, promote human rights, and foster cooperation among nations.' },
      { question: 'What happened in the Korean War?', answer: 'In the Korean War, North Korea invaded South Korea in 1950; UN forces led by the United States intervened, and the war ended in an armistice in 1953.' },
      { question: 'How did the Cold War affect global politics?', answer: 'The Cold War divided the world into Western and Eastern blocs, led to the arms race, and influenced conflicts like the Korean and Vietnam Wars.' },
      { question: 'What was the nuclear arms race during the Cold War?', answer: 'The nuclear arms race was a competition between the United States and Soviet Union to develop and stockpile more powerful nuclear weapons during the Cold War.' },
      { question: 'How did the Soviet Union build its Cold War alliances against NATO?', answer: 'The Soviet Union built Cold War alliances by forming a bloc of Eastern European communist states to counter NATO and extend its sphere of influence.' },
      { question: 'What caused the Cold War to begin?', answer: 'The Cold War began after World War II due to ideological and political tensions between the United States and the Soviet Union over the spread of communism.' },
    ],
  },
  {
    domain: '🏛️ Leaders & Empires',
    questions: [
      { question: 'What was Napoleon Bonaparte known for?', answer: 'Napoleon Bonaparte was a French military and political leader who conquered much of Europe in the early 19th century.' },
      { question: 'Who was Napoleon Bonaparte and what was his role in the Egypt expedition?', answer: 'Napoleon Bonaparte was a French military and political leader who led the French expedition in Egypt.' },
      { question: 'What did Napoleon accomplish during the Egypt expedition?', answer: 'During the Egypt expedition of 1798, Napoleon sought to disrupt British trade routes and expand French influence in the Middle East.' },
      { question: 'Who was Nelson Mandela?', answer: 'Nelson Mandela was a South African anti-apartheid revolutionary and political leader who became South Africa\'s first democratically elected president.' },
      { question: 'What did Nelson Mandela fight against?', answer: 'Nelson Mandela fought against apartheid, the system of racial segregation in South Africa.' },
      { question: 'What was apartheid in South Africa?', answer: 'Apartheid was a system of institutionalised racial segregation enforced by South Africa\'s government from 1948 to the early 1990s.' },
      { question: 'What was the Roman Empire?', answer: 'The Roman Empire was an ancient state that controlled vast territories across Europe and the Mediterranean, ruled by emperors such as Augustus.' },
      { question: 'Who was Augustus?', answer: 'Augustus was the first emperor of the Roman Empire, ruling from 27 BC to 14 AD.' },
      { question: 'Who was the first emperor of the Roman Empire?', answer: 'Augustus was the first emperor of the Roman Empire, transforming Rome from a republic to an empire.' },
      { question: 'What territories did the Roman Empire control?', answer: 'The Roman Empire controlled vast territories spanning Europe, North Africa, and the Middle East at its peak.' },
      { question: 'What were Napoleon Bonaparte\'s greatest military achievements?', answer: 'Napoleon Bonaparte\'s greatest military achievements included the Battle of Austerlitz, the Italian campaigns, and the Egypt expedition, making him one of history\'s greatest commanders.' },
      { question: 'How long did Nelson Mandela spend in prison?', answer: 'Nelson Mandela spent 27 years in prison for his anti-apartheid activities before being released in 1990.' },
      { question: 'What was ancient Egypt\'s role in Napoleon\'s campaigns?', answer: 'Napoleon led a military expedition to Egypt in 1798 seeking to disrupt British trade routes and expand French influence in the Middle East.' },
      { question: 'What was the significance of the Roman Empire?', answer: 'The Roman Empire was significant for spreading Roman law, language, and culture across Europe and the Mediterranean world.' },
      { question: 'How did Napoleon Bonaparte reshape Europe through his campaigns?', answer: 'Napoleon reshaped Europe by spreading revolutionary ideals, redrawing national boundaries, and challenging the old monarchical order through his military campaigns.' },
      { question: 'How did apartheid end in South Africa?', answer: 'Apartheid ended in South Africa in 1994 when Nelson Mandela was elected as the country\'s first democratically elected president.' },
      { question: 'How did Augustus Caesar establish and consolidate the Roman Empire?', answer: 'Augustus Caesar established the Roman Empire by defeating his rivals, creating the Principate system, expanding Roman territory, and ushering in the Pax Romana.' },
      { question: 'What was Napoleon Bonaparte\'s military legacy?', answer: 'Napoleon Bonaparte\'s military legacy includes his tactical genius at battles like Austerlitz and the Egypt expedition, which transformed European warfare and strategy.' },
    ],
  },
  {
    domain: '⚛️ Science & Medicine',
    questions: [
      { question: 'What was the Manhattan Project?', answer: 'The Manhattan Project was the US-led research programme during World War II that developed the first nuclear weapons.' },
      { question: 'What did the atomic bomb achieve?', answer: 'The atomic bomb, developed by the Manhattan Project, ended World War II in the Pacific after being dropped on Hiroshima and Nagasaki in 1945.' },
      { question: 'What is penicillin?', answer: 'Penicillin is a group of antibiotics derived from Penicillium fungi, used to treat bacterial infections.' },
      { question: 'Who discovered penicillin?', answer: 'Alexander Fleming discovered penicillin in 1928 when he noticed that Penicillium mould inhibited bacterial growth.' },
      { question: 'What diseases does penicillin treat?', answer: 'Penicillin is used to treat bacterial infections including pneumonia, meningitis, strep throat, and syphilis.' },
      { question: 'How did penicillin change medicine?', answer: 'Penicillin revolutionised medicine by providing the first effective treatment for many bacterial infections, saving millions of lives.' },
      { question: 'What was the impact of the atomic bomb on World War II?', answer: 'The atomic bombs dropped on Hiroshima and Nagasaki in August 1945 led directly to Japan\'s surrender and the end of World War II.' },
      { question: 'What was the scientific basis of the atomic bomb?', answer: 'The atomic bomb was based on nuclear fission, in which uranium or plutonium atoms are split to release enormous amounts of energy.' },
      { question: 'What countries were involved in the Manhattan Project?', answer: 'The Manhattan Project was primarily a United States effort but also involved scientists from the United Kingdom and Canada.' },
      { question: 'Why was the Manhattan Project secret?', answer: 'The Manhattan Project was kept secret to prevent Nazi Germany from learning about the US effort to develop nuclear weapons during World War II.' },
      { question: 'How did penicillin transform medical treatment in the 20th century?', answer: 'Penicillin transformed medicine by providing the first effective antibiotic, saving millions of lives from previously fatal bacterial infections and enabling modern surgery.' },
      { question: 'What were the global consequences of the atomic bomb beyond World War II?', answer: 'Beyond World War II, the atomic bomb triggered the nuclear arms race, the doctrine of mutually assured destruction, and ongoing nuclear non-proliferation efforts.' },
      { question: 'How was penicillin discovered and what made it revolutionary?', answer: 'Penicillin was discovered in 1928 when mould contaminating a petri dish killed surrounding bacteria, leading to the first antibiotic that could cure life-threatening infections.' },
      { question: 'What is the legacy of the Manhattan Project?', answer: 'The Manhattan Project led to the development of nuclear weapons that ended World War II and also laid the groundwork for nuclear energy and Cold War arms race.' },
    ],
  },
  {
    domain: '🌐 Nations & Geopolitics',
    questions: [
      { question: 'What role did the United States play in World War II?', answer: 'The United States joined the Allied powers in World War II after the attack on Pearl Harbor in 1941 and played a decisive role in both the European and Pacific theaters.' },
      { question: 'What role did the United Kingdom play in World War II?', answer: 'The United Kingdom was one of the main Allied powers in World War II, fighting against Nazi Germany from 1939 under Prime Minister Winston Churchill.' },
      { question: 'What was Germany\'s role in World War II?', answer: 'Germany, under Adolf Hitler and the Nazi Party, started World War II by invading Poland in 1939 and was the primary Axis power in Europe.' },
      { question: 'What was Japan\'s role in World War II?', answer: 'Japan was a major Axis power that fought in the Pacific theater, attacking Pearl Harbor in 1941 and surrendering in 1945 after atomic bombs were dropped.' },
      { question: 'What was France\'s involvement in World War II?', answer: 'France was invaded and occupied by Germany in 1940 but continued fighting through the Free French Forces and was liberated in 1944.' },
      { question: 'What is North Korea?', answer: 'North Korea is a country in East Asia that fought against South Korea in the Korean War from 1950 to 1953 and remains ruled by an authoritarian government.' },
      { question: 'What is South Korea?', answer: 'South Korea is a democratic country in East Asia that was defended by United Nations forces during the Korean War from 1950 to 1953.' },
      { question: 'What is South Africa known for?', answer: 'South Africa is known for its history of apartheid racial segregation and the role of Nelson Mandela in leading the country to democracy.' },
      { question: 'Why did the United States join World War II?', answer: 'The United States joined World War II after Japan\'s surprise attack on the US naval base at Pearl Harbor, Hawaii, on December 7, 1941.' },
      { question: 'What was the Soviet Union\'s role in World War II?', answer: 'The Soviet Union was a major Allied power in World War II that bore the brunt of fighting on the Eastern Front against Nazi Germany.' },
      { question: 'What countries formed the Allied powers in World War II?', answer: 'The main Allied powers were the United States, United Kingdom, Soviet Union, France, and China, plus many other nations.' },
      { question: 'How did the United Nations help in the Korean War?', answer: 'The United Nations authorised and coordinated a multinational military force led by the United States to defend South Korea against the North Korean invasion.' },
      { question: 'What is the relationship between NATO and the Cold War?', answer: 'NATO was created in 1949 directly in response to Soviet expansion after World War II, and it served as the primary Western military alliance throughout the Cold War.' },
      { question: 'What happened to the Soviet Union after the Cold War?', answer: 'The Soviet Union dissolved in 1991, splitting into 15 independent countries including Russia, Ukraine, and other former Soviet republics.' },
      { question: 'What was the role of China in the Korean War?', answer: 'China intervened in the Korean War in 1950, sending hundreds of thousands of troops to support North Korea against the United Nations forces.' },
      { question: 'How did the Cold War affect nations in Asia and beyond?', answer: 'The Cold War shaped Asia through the Korean War, the Vietnam War, and superpower competition, drawing many nations into conflict between the United States and Soviet Union.' },
    ],
  },
  {
    domain: '⚔️ Major Conflicts & Battles',
    questions: [
      { question: 'What was the Korean War?', answer: 'The Korean War was a conflict from 1950 to 1953 where North Korea, backed by China and the Soviet Union, invaded South Korea, which was defended by United Nations forces.' },
      { question: 'What was the outcome of the Korean War?', answer: 'The Korean War ended in an armistice in 1953, leaving Korea divided at the 38th parallel, a situation that persists today.' },
      { question: 'What was the Vietnam War about?', answer: 'The Vietnam War was a Cold War conflict from 1955 to 1975 between communist North Vietnam and South Vietnam, with the United States intervening to support the South.' },
      { question: 'What was the outcome of the Vietnam War?', answer: 'The Vietnam War ended with North Vietnam capturing Saigon in 1975, leading to the reunification of Vietnam under communist rule.' },
      { question: 'What role did the United States play in the Vietnam War?', answer: 'The United States intervened in Vietnam to prevent a communist takeover of South Vietnam, sending hundreds of thousands of troops before withdrawing in 1973.' },
      { question: 'What was the significance of Pearl Harbor in World War II?', answer: 'The Japanese attack on Pearl Harbor on December 7, 1941, brought the United States into World War II and transformed it into a truly global conflict.' },
      { question: 'What battles were fought during World War II?', answer: 'Major World War II battles include D-Day at Normandy, the Battle of Stalingrad, the Battle of Midway, and the Battle of the Bulge.' },
      { question: 'What was the Cold War\'s relationship to the Korean War?', answer: 'The Korean War was the first major armed conflict of the Cold War, where the US-led UN forces and Soviet-backed North Korea fought by proxy.' },
      { question: 'How many people died in World War II?', answer: 'World War II caused an estimated 70–85 million deaths, making it the deadliest conflict in human history.' },
      { question: 'What ended the Vietnam War for the United States?', answer: 'The United States signed the Paris Peace Accords in 1973 and withdrew its forces, with South Vietnam falling to the North in 1975.' },
      { question: 'What was the Eastern Front in World War II?', answer: 'The Eastern Front was the theatre of war between Nazi Germany and the Soviet Union, the largest and most deadly theatre of World War II.' },
      { question: 'What was D-Day in World War II?', answer: 'D-Day was the Allied amphibious invasion of Normandy, France, on June 6, 1944, a decisive turning point that opened a second front against Nazi Germany.' },
      { question: 'What was the role of naval power in deciding World War II?', answer: 'Naval power was decisive in World War II through battles in the Pacific against Japan and the Atlantic convoys that supplied Allied forces in Europe.' },
      { question: 'How did the United States respond to the Pearl Harbor attack and enter World War II?', answer: 'After Japan attacked Pearl Harbor on December 7, 1941, the United States declared war on Japan, and Germany and Italy then declared war on the US, bringing it fully into World War II.' },
    ],
  },
];

/* ─── Themes ─── */
const THEMES = {
  light: {
    pageBg: '#f0f4f8',
    heroBg: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
    surface: '#ffffff', surface2: '#f8fafc', surfaceHover: '#f1f5f9',
    border: '#e2e8f0', borderStrong: '#cbd5e1',
    text: '#0f172a', textMuted: '#475569', textSubtle: '#94a3b8',
    inputBg: '#ffffff', metricBg: '#f8fafc',
    graphragBorder: '#16a34a',
    graphragBg: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
    graphragGlow: '0 0 0 2px #16a34a40, 0 8px 32px rgba(22,163,74,0.15)',
    errorBg: '#fef2f2', errorBorder: '#fca5a5', errorText: '#dc2626',
    badgePassBg: '#dcfce7', badgePassText: '#15803d',
    badgeFailBg: '#fee2e2', badgeFailText: '#dc2626',
    chartGrid: '#e2e8f0', tooltipBg: '#ffffff',
    spinnerTrack: '#e2e8f0', spinnerHead: '#16a34a',
    btnGradient: 'linear-gradient(135deg, #16a34a, #15803d)',
    btnDisabledBg: '#e2e8f0', btnDisabledText: '#94a3b8',
    tableRowBorder: '#f1f5f9',
    toggleBg: 'rgba(255,255,255,0.15)',
    tagBg: '#f1f5f9', tagText: '#475569',
    bertBg: 'linear-gradient(135deg, #eff6ff, #dbeafe)', bertBorder: '#93c5fd', bertText: '#1e40af',
    accentGlow: 'rgba(22,163,74,0.1)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
    reductionStat: '#15803d',
    statCard: 'rgba(255,255,255,0.12)', statCardBorder: 'rgba(255,255,255,0.2)',
    statText: '#ffffff', statSubtext: 'rgba(255,255,255,0.7)',
    sectionBg: '#f8fafc',
  },
  dark: {
    pageBg: '#0a0f1a',
    heroBg: 'linear-gradient(135deg, #0a0f1a 0%, #0d1f2d 50%, #0a1628 100%)',
    surface: '#111827', surface2: '#0f172a', surfaceHover: '#1e293b',
    border: '#1e293b', borderStrong: '#334155',
    text: '#f1f5f9', textMuted: '#94a3b8', textSubtle: '#475569',
    inputBg: '#111827', metricBg: '#0f172a',
    graphragBorder: '#22c55e',
    graphragBg: 'linear-gradient(135deg, #052e16 0%, #14532d 100%)',
    graphragGlow: '0 0 0 2px #22c55e40, 0 8px 32px rgba(34,197,94,0.2)',
    errorBg: '#450a0a', errorBorder: '#ef4444', errorText: '#fca5a5',
    badgePassBg: '#14532d', badgePassText: '#4ade80',
    badgeFailBg: '#450a0a', badgeFailText: '#f87171',
    chartGrid: '#1e293b', tooltipBg: '#111827',
    spinnerTrack: '#1e293b', spinnerHead: '#22c55e',
    btnGradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
    btnDisabledBg: '#1e293b', btnDisabledText: '#475569',
    tableRowBorder: '#111827',
    toggleBg: 'rgba(255,255,255,0.1)',
    tagBg: '#1e293b', tagText: '#94a3b8',
    bertBg: 'linear-gradient(135deg, #0c1929, #0f2040)', bertBorder: '#3b82f6', bertText: '#93c5fd',
    accentGlow: 'rgba(34,197,94,0.08)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.3)',
    reductionStat: '#4ade80',
    statCard: 'rgba(255,255,255,0.07)', statCardBorder: 'rgba(255,255,255,0.12)',
    statText: '#ffffff', statSubtext: 'rgba(255,255,255,0.6)',
    sectionBg: '#0f172a',
  },
};

/* ─── Animated counter ─── */
function AnimatedNumber({ value, duration = 800, suffix = '' }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const start     = prev.current;
    const end       = parseFloat(value);
    const startTime = performance.now();
    function tick(now) {
      const p     = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(start + (end - start) * eased);
      if (p < 1) requestAnimationFrame(tick);
      else { prev.current = end; setDisplay(end); }
    }
    requestAnimationFrame(tick);
  }, [value, duration]);
  return (
    <>
      {typeof value === 'number' && !Number.isInteger(value)
        ? display.toFixed(1)
        : Math.round(display).toLocaleString()}
      {suffix}
    </>
  );
}

/* ─── JudgeBadge ─── */
function JudgeBadge({ judge, t }) {
  if (!judge) return null;
  const pass = judge === 'PASS';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: pass ? t.badgePassBg : t.badgeFailBg,
      color: pass ? t.badgePassText : t.badgeFailText,
      borderRadius: 20, padding: '3px 10px', fontSize: 11, fontWeight: 700,
    }}>
      {pass ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
      {judge}
    </span>
  );
}

/* ─── Token Bar ─── */
function TokenBar({ label, tokens, maxTokens, color, t }) {
  const pct = Math.min((tokens / maxTokens) * 100, 100);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 800, color }}>{tokens.toLocaleString()} tokens</span>
      </div>
      <div style={{ height: 8, borderRadius: 99, background: t.border, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, background: color,
          borderRadius: 99, transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </div>
    </div>
  );
}

/* ─── Spinner ─── */
function Spinner({ t }) {
  const [step, setStep] = useState(0);
  const steps = [
    { label: 'Querying LLM-Only…',   icon: Brain,    color: '#ef4444' },
    { label: 'Running Basic RAG…',   icon: Database, color: '#f97316' },
    { label: 'Traversing TigerGraph…', icon: Network, color: '#16a34a' },
  ];
  useEffect(() => {
    const id = setInterval(() => setStep(s => (s + 1) % steps.length), 2000);
    return () => clearInterval(id);
  }, []);
  const StepIcon = steps[step].icon;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '52px 24px', gap: 24 }}>
      <div style={{ position: 'relative', width: 72, height: 72 }}>
        <svg width="72" height="72" style={{ position: 'absolute', top: 0, left: 0, animation: 'spin 1.2s linear infinite' }}>
          <circle cx="36" cy="36" r="30" fill="none" stroke={t.spinnerTrack} strokeWidth="3" />
          <circle cx="36" cy="36" r="30" fill="none" stroke={steps[step].color} strokeWidth="3"
            strokeDasharray="50 140" strokeLinecap="round" />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <StepIcon size={22} color={steps[step].color} />
        </div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: t.text, marginBottom: 6 }}>
          Running all 3 pipelines in parallel
        </div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 16 }}>{steps[step].label}</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          {PIPELINE_KEYS.map((key, i) => {
            const StepIcon = steps[i].icon;
            return (
              <div key={key} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 12px', borderRadius: 20,
                background: i === step ? `${steps[i].color}20` : t.surface2,
                border: `1px solid ${i === step ? steps[i].color : t.border}`,
                transition: 'all 0.3s',
              }}>
                <StepIcon size={11} color={i === step ? steps[i].color : t.textSubtle} />
                <span style={{ fontSize: 11, color: i === step ? steps[i].color : t.textSubtle, fontWeight: 600 }}>
                  {PIPELINE_LABELS[key]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ─── Pipeline Card ─── */
function PipelineCard({ name, data, judge, t }) {
  const [expanded, setExpanded] = useState(true);
  const color  = PIPELINE_COLORS[name];
  const Icon   = PIPELINE_ICONS[name];
  const isGrag = name === 'graphrag';

  return (
    <div
      style={{
        background: isGrag ? t.graphragBg : t.surface,
        border: `1.5px solid ${isGrag ? t.graphragBorder : t.border}`,
        boxShadow: isGrag ? t.graphragGlow : t.cardShadow,
        borderRadius: 16, overflow: 'hidden',
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={e => { if (!isGrag) e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
    >
      <div style={{ height: 4, background: `linear-gradient(90deg, ${color}, ${color}99)` }} />

      <div style={{ padding: '16px 20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              background: `${color}18`, borderRadius: 10,
              width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: `1px solid ${color}30`,
            }}>
              <Icon size={17} color={color} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 800, fontSize: 15, color }}>{PIPELINE_LABELS[name]}</span>
                {isGrag && data.graph_context_found !== false && (
                  <span style={{
                    background: 'linear-gradient(135deg, #16a34a, #15803d)',
                    color: '#fff', borderRadius: 6, padding: '1px 7px',
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                  }}>BEST</span>
                )}
                {isGrag && data.graph_context_found === false && (
                  <span style={{
                    background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                    color: '#fff', borderRadius: 6, padding: '1px 7px',
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                  }}>NO MATCH</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: t.textSubtle, marginTop: 1 }}>{PIPELINE_DESC[name]}</div>
            </div>
          </div>
          <JudgeBadge judge={judge} t={t} />
        </div>

        {/* Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
          {[
            { icon: Hash,        label: 'Tokens',  value: data.total_tokens.toLocaleString(), color },
            { icon: Clock,       label: 'Latency', value: `${data.latency_s}s`,              color: t.textMuted },
            { icon: DollarSign,  label: 'Cost',    value: `$${data.cost_usd.toFixed(5)}`,    color: t.textMuted },
          ].map(({ icon: MIcon, label, value, color: c }) => (
            <div key={label} style={{
              background: t.metricBg, border: `1px solid ${t.border}`,
              borderRadius: 10, padding: '10px 12px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                <MIcon size={10} color={t.textSubtle} />
                <span style={{ fontSize: 10, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  {label}
                </span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 800, color: c }}>{value}</div>
            </div>
          ))}
        </div>

        {/* GraphRAG tags */}
        {isGrag && data.retriever && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12 }}>
            {[data.retriever, 'num_hops=2', 'Community+Chunk'].map(tag => (
              <span key={tag} style={{
                background: 'rgba(22,163,74,0.1)', color: '#16a34a',
                borderRadius: 6, padding: '2px 8px', fontSize: 10, fontWeight: 600,
                border: '1px solid rgba(22,163,74,0.2)',
              }}>{tag}</span>
            ))}
          </div>
        )}

        {/* Answer toggle */}
        <button
          onClick={() => setExpanded(x => !x)}
          style={{
            background: 'none', border: `1px solid ${t.border}`, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            width: '100%', padding: '8px 12px', borderRadius: 8,
            fontSize: 12, fontWeight: 600, color: t.textMuted,
            marginBottom: expanded ? 8 : 0,
          }}
        >
          <span>Answer</span>
          <ChevronDown size={13} style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
        </button>
        {expanded && (
          <div style={{
            background: t.metricBg, border: `1px solid ${t.border}`,
            borderRadius: 10, padding: '12px 14px',
            fontSize: 13, color: t.textMuted, lineHeight: 1.75,
            maxHeight: 160, overflowY: 'auto',
          }}>
            {data.answer || <em style={{ color: t.textSubtle }}>No answer returned.</em>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Results Section ─── */
function ResultsSection({ result, t }) {
  const pct    = result.token_reduction_pct;
  const graphFailed  = result.graphrag_status && result.graphrag_status !== 'ok';
  const basicRagFailed = result.basic_rag?.status === 'faiss_unavailable';
  const maxTok = Math.max(...PIPELINE_KEYS.map(k => result[k].total_tokens));
  const chartData = PIPELINE_KEYS.map(k => ({
    name: PIPELINE_LABELS[k], tokens: result[k].total_tokens, color: PIPELINE_COLORS[k],
  }));

  return (
    <div className="animate-fade-up">
      {/* GraphRAG failure notice — only shown when GraphRAG itself failed */}
      {graphFailed && (
        <div style={{
          background: t.errorBg, border: `1px solid ${t.errorBorder}`,
          borderRadius: 20, padding: '24px 28px', marginBottom: 20,
          display: 'flex', alignItems: 'flex-start', gap: 16,
        }}>
          <XCircle size={28} color={t.errorText} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: t.errorText, marginBottom: 6 }}>
              {result.graphrag_status === 'tg_unavailable'
                ? 'TigerGraph knowledge-graph service is offline'
                : 'GraphRAG found no matching entities in the knowledge graph'}
            </div>
            <div style={{ fontSize: 14, color: t.textMuted, lineHeight: 1.6 }}>
              {result.graphrag_status === 'tg_unavailable' ? (
                <>
                  The graph backend didn't respond, so no context could be retrieved — and therefore{' '}
                  <strong>no token reduction is reported</strong> (rather than a fake percentage).
                  Resume the TigerGraph instance and try again.
                </>
              ) : (
                <>
                  This question references entities that aren't in the knowledge graph, so there's
                  no genuine context to retrieve — and therefore <strong>no token reduction to report</strong>.
                  Try one of the <strong style={{ color: '#16a34a' }}>Featured Questions</strong> above,
                  which are verified to exist in the graph.
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Basic RAG unavailable notice — separate from GraphRAG status */}
      {!graphFailed && basicRagFailed && (
        <div style={{
          background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.35)',
          borderRadius: 20, padding: '18px 24px', marginBottom: 20,
          display: 'flex', alignItems: 'flex-start', gap: 14,
        }}>
          <Database size={22} color="#f97316" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f97316', marginBottom: 4 }}>
              Basic RAG unavailable — FAISS index not on this server
            </div>
            <div style={{ fontSize: 13, color: t.textMuted, lineHeight: 1.6 }}>
              GraphRAG retrieved context successfully and answered your question.
              Token reduction vs Basic RAG cannot be shown because the FAISS vector index isn't deployed on this server.
            </div>
          </div>
        </div>
      )}

      {/* Token Reduction Hero — only when GraphRAG retrieved AND Basic RAG is available to compare */}
      {!graphFailed && !basicRagFailed && (
      <div style={{
        background: 'linear-gradient(135deg, #052e16 0%, #14532d 50%, #166534 100%)',
        borderRadius: 20, padding: '32px 36px', marginBottom: 20,
        border: '1px solid rgba(34,197,94,0.3)',
        boxShadow: '0 8px 32px rgba(22,163,74,0.2)',
        display: 'flex', alignItems: 'center', gap: 40, flexWrap: 'wrap',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'rgba(34,197,94,0.05)' }} />
        <div style={{ position: 'absolute', bottom: -20, right: 80, width: 80, height: 80, borderRadius: '50%', background: 'rgba(34,197,94,0.08)' }} />

        {/* Token reduction stat */}
        <div style={{ textAlign: 'center', position: 'relative' }}>
          <div style={{ fontSize: 11, color: 'rgba(74,222,128,0.8)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            Token Reduction
          </div>
          <div style={{ fontSize: 64, fontWeight: 900, lineHeight: 1, color: '#4ade80', letterSpacing: '-2px' }}>
            <AnimatedNumber value={pct} suffix="%" />
          </div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>GraphRAG vs Basic RAG</div>
        </div>

        <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.1)' }} />

        {/* Token bars */}
        <div style={{ flex: 1, minWidth: 240 }}>
          {PIPELINE_KEYS.map(k => (
            <TokenBar
              key={k}
              label={PIPELINE_LABELS[k]}
              tokens={result[k].total_tokens}
              maxTokens={maxTok}
              color={PIPELINE_COLORS[k]}
              t={{ ...t, border: 'rgba(255,255,255,0.1)', textMuted: 'rgba(255,255,255,0.6)' }}
            />
          ))}
        </div>

        <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.1)' }} />

        {/* Cost reduction stat */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: 'rgba(74,222,128,0.8)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            Cost Saved
          </div>
          <div style={{ fontSize: 36, fontWeight: 900, color: '#86efac', letterSpacing: '-1px' }}>
            {result.cost_reduction_pct > 0 ? '-' : '+'}<AnimatedNumber value={Math.abs(result.cost_reduction_pct)} suffix="%" />
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>per query vs Basic RAG</div>
        </div>
      </div>
      )}

      {/* Chart + Pipeline cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, marginBottom: 20 }}>
        {/* Bar chart */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 16, padding: '20px', boxShadow: t.cardShadow,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>
            Token Comparison
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} vertical={false} />
              <XAxis dataKey="name" stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`, borderRadius: 10, boxShadow: t.cardShadow, fontSize: 13 }}
                labelStyle={{ color: t.text, fontWeight: 700 }}
                itemStyle={{ color: t.textMuted }}
                cursor={{ fill: t.accentGlow }}
              />
              <Bar dataKey="tokens" radius={[8, 8, 0, 0]} maxBarSize={56}>
                {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

        </div>

        {/* Pipeline cards — driven by PIPELINE_KEYS registry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {PIPELINE_KEYS.map(key => (
            <PipelineCard key={key} name={key} data={result[key]} judge={result[`judge_${key}`]} t={t} />
          ))}
        </div>
      </div>

      {/* BERTScore */}
      {result.bertscore && result.bertscore.raw_f1 > 0 && (
        <div style={{
          background: t.bertBg, border: `1px solid ${t.bertBorder}`,
          borderRadius: 16, padding: '18px 24px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 28, flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Award size={18} color={t.bertText} />
            <span style={{ fontWeight: 700, fontSize: 14, color: t.bertText }}>BERTScore</span>
          </div>
          {[
            { label: 'Raw F1',      value: result.bertscore.raw_f1 },
            { label: 'Rescaled F1', value: result.bertscore.rescaled_f1 },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ fontSize: 10, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2, fontWeight: 600 }}>{label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: t.bertText }}>{value}</div>
            </div>
          ))}
          <div style={{ marginLeft: 'auto' }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: result.bertscore.bonus_hit ? t.badgePassBg : t.badgeFailBg,
              color: result.bertscore.bonus_hit ? t.badgePassText : t.badgeFailText,
              borderRadius: 20, padding: '5px 14px', fontSize: 12, fontWeight: 700,
            }}>
              {result.bertscore.bonus_hit ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              {result.bertscore.bonus_hit ? 'BONUS HIT' : 'BONUS MISSED'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main App ─── */
export default function App() {
  const [question,  setQuestion]  = useState('');
  const [groundTruth, setGT]      = useState('');
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState('');
  const [history,   setHistory]   = useState([]);
  const [darkMode,  setDarkMode]  = useState(false);
  const [selDomain, setDomain]    = useState('');
  const [showHist,  setShowHist]  = useState(false);
  const inputRef = useRef();

  const t          = THEMES[darkMode ? 'dark' : 'light'];
  const domainData = DOMAIN_QUESTIONS.find(d => d.domain === selDomain);

  async function handleRun(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const { data } = await axios.post(`${API_BASE}/compare`, {
        question:     question.trim(),
        ground_truth: groundTruth.trim(),
      });
      setResult(data);
      setHistory(prev => [{
        question:        question.trim(),
        graphrag_tokens: data.graphrag.total_tokens,
        reduction_pct:   data.token_reduction_pct,
        judge:           data.judge_graphrag || '—',
        bertscore:       data.bertscore?.raw_f1 ?? '—',
      }, ...prev].slice(0, 20));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  function selectQuestion(q, a = '') {
    setQuestion(q); setGT(a); setResult(null); setError('');
    setTimeout(() => inputRef.current?.focus(), 100);
  }

  const inputStyle = {
    background: t.inputBg, border: `1.5px solid ${t.border}`,
    borderRadius: 14, padding: '16px 20px', fontSize: 16,
    color: t.text, outline: 'none', width: '100%',
    transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box', fontFamily: 'inherit',
  };

  return (
    <div style={{
      minHeight: '100vh', background: t.pageBg, color: t.text,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      transition: 'background 0.3s',
    }}>

      {/* ═══ HERO ═══ */}
      <div style={{ background: t.heroBg, padding: '0 24px 0', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: -80, left: -80, width: 300, height: 300, borderRadius: '50%', background: 'rgba(22,163,74,0.08)', filter: 'blur(40px)' }} />
        <div style={{ position: 'absolute', top: -40, right: 100, width: 200, height: 200, borderRadius: '50%', background: 'rgba(59,130,246,0.06)', filter: 'blur(30px)' }} />

        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          {/* Nav */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 0 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ade80', boxShadow: '0 0 8px #4ade80', animation: 'pulse-ring 2s ease infinite' }} />
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                TigerGraph GraphRAG · Wikipedia Knowledge Graph
              </span>
            </div>
            <button
              onClick={() => setDarkMode(d => !d)}
              style={{
                background: t.toggleBg, color: '#fff',
                border: '1px solid rgba(255,255,255,0.2)', borderRadius: 10,
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                backdropFilter: 'blur(10px)',
              }}
            >
              {darkMode ? <Sun size={14} /> : <Moon size={14} />}
              {darkMode ? 'Light' : 'Dark'}
            </button>
          </div>

          {/* Hero text */}
          <div style={{ padding: '60px 0 52px', textAlign: 'center' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              background: 'rgba(22,163,74,0.15)', border: '1px solid rgba(22,163,74,0.35)',
              borderRadius: 24, padding: '8px 22px', marginBottom: 28,
            }}>
              <Network size={15} color="#4ade80" />
              <span style={{ fontSize: 14, color: '#4ade80', fontWeight: 700, letterSpacing: '0.02em' }}>
                100M Token Wikipedia Knowledge Graph
              </span>
            </div>
            <h1 style={{
              fontSize: 'clamp(36px, 6vw, 68px)', fontWeight: 900, color: '#ffffff',
              margin: '0 0 20px', letterSpacing: '-2px', lineHeight: 1.05,
            }}>
              GraphRAG Pipeline{' '}
              <span style={{ background: 'linear-gradient(135deg, #4ade80, #22c55e)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Comparison
              </span>
            </h1>
            <p style={{
              fontSize: 20, color: 'rgba(255,255,255,0.65)', margin: '0 0 44px',
              maxWidth: 600, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.65, fontWeight: 400,
            }}>
              See how <strong style={{ color: '#4ade80', fontWeight: 700 }}>GraphRAG</strong> reduces token usage by{' '}
              <strong style={{ color: '#4ade80', fontWeight: 700 }}>up to ~80%</strong> while maintaining accuracy
              over Basic RAG and LLM-Only pipelines
            </p>

            {/* Stat cards */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 32 }}>
              {[
                { icon: BookOpen, value: '100,850',    label: 'Wikipedia Articles' },
                { icon: Hash,     value: '102.9M',     label: 'Tokens Indexed' },
                { icon: Layers,   value: '464,739',    label: 'FAISS Chunks' },
                { icon: GitMerge, value: 'num_hops=2', label: 'Graph Traversal' },
              ].map(({ icon: Icon, value, label }) => (
                <div key={label} style={{
                  background: t.statCard, border: `1px solid ${t.statCardBorder}`,
                  borderRadius: 18, padding: '20px 28px', minWidth: 150,
                  backdropFilter: 'blur(10px)', textAlign: 'center',
                }}>
                  <Icon size={20} color="#4ade80" style={{ marginBottom: 10, display: 'block', margin: '0 auto 10px' }} />
                  <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', letterSpacing: '-0.5px' }}>{value}</div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', marginTop: 4, fontWeight: 500 }}>{label}</div>
                </div>
              ))}
            </div>

            {/* Knowledge domain pills */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 14 }}>
                102.9M tokens span 7 knowledge domains
              </div>
              <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 10 }}>
                {[
                  { icon: '💻', label: 'Free Software & Tech' },
                  { icon: '🌍', label: 'World War II' },
                  { icon: '🥶', label: 'Cold War & Alliances' },
                  { icon: '🏛️', label: 'Leaders & Empires' },
                  { icon: '⚛️', label: 'Science & Medicine' },
                  { icon: '🌐', label: 'Nations & Geopolitics' },
                  { icon: '⚔️', label: 'Wars & Conflicts' },
                ].map(({ icon, label }) => (
                  <div key={label} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 7,
                    background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.13)',
                    borderRadius: 24, padding: '7px 16px',
                    backdropFilter: 'blur(8px)',
                  }}>
                    <span style={{ fontSize: 15 }}>{icon}</span>
                    <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)', fontWeight: 600 }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '36px 32px 80px' }}>

        {/* ── Featured Questions ── */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 24, padding: '32px 36px', marginBottom: 24,
          boxShadow: t.cardShadow,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 10, padding: 10 }}>
                <Sparkles size={20} color="#16a34a" />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>Featured Questions</div>
                <div style={{ fontSize: 13, color: t.textSubtle, marginTop: 2 }}>Verified working questions with highest token reduction</div>
              </div>
            </div>
            <span style={{
              background: 'rgba(22,163,74,0.1)', color: '#16a34a',
              borderRadius: 20, padding: '4px 12px', fontSize: 11, fontWeight: 700,
              border: '1px solid rgba(22,163,74,0.2)',
            }}>Best Reduction</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14, marginBottom: 28 }}>
            {FEATURED_QUESTIONS.map(sq => (
              <button
                key={sq.question}
                onClick={() => selectQuestion(sq.question, sq.answer)}
                style={{
                  background: t.surface2, border: `1.5px solid ${t.border}`,
                  borderRadius: 16, padding: '20px 22px', textAlign: 'left',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#16a34a';
                  e.currentTarget.style.background = 'rgba(22,163,74,0.05)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(22,163,74,0.12)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = t.border;
                  e.currentTarget.style.background = t.surface2;
                  e.currentTarget.style.transform = 'none';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 20 }}>{sq.icon}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#16a34a', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{sq.label}</span>
                  </div>
                </div>
                <div style={{ fontSize: 15, color: t.text, lineHeight: 1.55, fontWeight: 600, marginBottom: 10 }}>{sq.question}</div>
                <div style={{ fontSize: 12, color: t.textSubtle, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <TrendingDown size={12} /> {sq.hint}
                </div>
              </button>
            ))}
          </div>

          {/* Browse by Domain */}
          <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 8, padding: '7px 9px', display: 'flex', alignItems: 'center' }}>
                <BookOpen size={16} color="#16a34a" />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: t.text }}>Browse by Domain</div>
                <div style={{ fontSize: 14, color: t.textSubtle, marginTop: 2 }}>Try more questions from different topics</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <select
                value={selDomain}
                onChange={e => setDomain(e.target.value)}
                style={{
                  background: t.inputBg, border: `1.5px solid ${t.border}`,
                  borderRadius: 12, padding: '12px 18px', fontSize: 14,
                  color: selDomain ? t.text : t.textMuted,
                  cursor: 'pointer', outline: 'none', minWidth: 260,
                  fontFamily: 'inherit', fontWeight: 500,
                }}
              >
                <option value="">Select a domain…</option>
                {DOMAIN_QUESTIONS.map(d => (
                  <option key={d.domain} value={d.domain}>{d.domain}</option>
                ))}
              </select>

              {domainData && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, flex: 1 }}>
                  {domainData.questions.map(item => (
                    <button
                      key={item.question}
                      onClick={() => selectQuestion(item.question, item.answer)}
                      style={{
                        background: t.surface2, border: `1px solid ${t.border}`,
                        borderRadius: 22, padding: '8px 18px', fontSize: 13,
                        color: t.text, cursor: 'pointer', transition: 'all 0.15s',
                        fontFamily: 'inherit', fontWeight: 500,
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = '#16a34a';
                        e.currentTarget.style.color = '#16a34a';
                        e.currentTarget.style.background = 'rgba(22,163,74,0.06)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = t.border;
                        e.currentTarget.style.color = t.text;
                        e.currentTarget.style.background = t.surface2;
                      }}
                    >
                      {item.question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Query Form ── */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 24, padding: '32px 36px', marginBottom: 28,
          boxShadow: t.cardShadow,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
            <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 10, padding: 10 }}>
              <Zap size={20} color="#16a34a" />
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>Ask a Question</div>
              <div style={{ fontSize: 13, color: t.textSubtle, marginTop: 2 }}>
                Runs LLM-Only · Basic RAG · GraphRAG in parallel
              </div>
            </div>
          </div>
          <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              ref={inputRef}
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="e.g. Who discovered penicillin?"
              style={inputStyle}
              onFocus={e => { e.target.style.borderColor = '#16a34a'; e.target.style.boxShadow = '0 0 0 3px rgba(22,163,74,0.1)'; }}
              onBlur={e => { e.target.style.borderColor = t.border; e.target.style.boxShadow = 'none'; }}
            />
            <input
              value={groundTruth}
              onChange={e => setGT(e.target.value)}
              placeholder="Ground truth (optional) — enables LLM Judge + BERTScore evaluation"
              style={{ ...inputStyle, color: t.textMuted }}
              onFocus={e => { e.target.style.borderColor = '#16a34a'; e.target.style.boxShadow = '0 0 0 3px rgba(22,163,74,0.1)'; }}
              onBlur={e => { e.target.style.borderColor = t.border; e.target.style.boxShadow = 'none'; }}
            />
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                style={{
                  background: (loading || !question.trim()) ? t.btnDisabledBg : 'linear-gradient(135deg, #16a34a, #15803d)',
                  color: (loading || !question.trim()) ? t.btnDisabledText : '#fff',
                  border: 'none', borderRadius: 14, padding: '16px 40px',
                  fontSize: 16, fontWeight: 700, cursor: (loading || !question.trim()) ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 10,
                  boxShadow: (loading || !question.trim()) ? 'none' : '0 6px 20px rgba(22,163,74,0.4)',
                  transition: 'all 0.2s', fontFamily: 'inherit',
                }}
              >
                <BarChart2 size={18} />
                {loading ? 'Running all 3 pipelines…' : 'Run All 3 Pipelines'}
              </button>
              {(question || result) && !loading && (
                <button
                  type="button"
                  onClick={() => { setQuestion(''); setGT(''); setResult(null); setError(''); }}
                  style={{
                    background: 'none', border: `1px solid ${t.border}`,
                    borderRadius: 14, padding: '16px 24px',
                    fontSize: 15, color: t.textMuted, cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  Clear
                </button>
              )}
              {result && !loading && result.token_reduction_pct != null && (
                <div style={{
                  marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(22,163,74,0.1)', border: '1px solid rgba(22,163,74,0.2)',
                  borderRadius: 10, padding: '8px 14px',
                }}>
                  <TrendingDown size={14} color="#16a34a" />
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#16a34a' }}>
                    {result.token_reduction_pct}% token reduction achieved
                  </span>
                </div>
              )}
              {result && !loading && result.token_reduction_pct == null && result.graphrag?.status === 'ok' && (
                <div style={{
                  marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.35)',
                  borderRadius: 10, padding: '8px 14px',
                }}>
                  <Database size={14} color="#f97316" />
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#f97316' }}>
                    Basic RAG unavailable — token reduction not computed
                  </span>
                </div>
              )}
              {result && !loading && result.graphrag_status && result.graphrag_status !== 'ok' && (
                <div style={{
                  marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8,
                  background: t.errorBg, border: `1px solid ${t.errorBorder}`,
                  borderRadius: 10, padding: '8px 14px',
                }}>
                  <XCircle size={14} color={t.errorText} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: t.errorText }}>
                    No graph context — not in knowledge graph
                  </span>
                </div>
              )}
            </div>
          </form>
        </div>

        {/* ── Error ── */}
        {error && (
          <div style={{
            background: t.errorBg, border: `1px solid ${t.errorBorder}`,
            borderRadius: 14, padding: '14px 18px', marginBottom: 20,
            color: t.errorText, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <XCircle size={16} /> {error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 20, marginBottom: 20, boxShadow: t.cardShadow,
          }}>
            <Spinner t={t} />
          </div>
        )}

        {/* ── Results ── */}
        {result && !loading && <ResultsSection result={result} t={t} />}

        {/* ── History ── */}
        {history.length > 0 && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 20, boxShadow: t.cardShadow, overflow: 'hidden',
          }}>
            <button
              onClick={() => setShowHist(h => !h)}
              style={{
                width: '100%', padding: '18px 24px',
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
                borderBottom: showHist ? `1px solid ${t.border}` : 'none',
              }}
            >
              <History size={15} color={t.textMuted} />
              <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Query History</span>
              <span style={{
                background: t.surface2, border: `1px solid ${t.border}`,
                borderRadius: 20, padding: '1px 9px', fontSize: 11, color: t.textMuted, fontWeight: 600,
              }}>{history.length}</span>
              <ChevronDown size={14} color={t.textSubtle} style={{ marginLeft: 'auto', transform: showHist ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
            </button>
            {showHist && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: t.surface2 }}>
                      {['Question', 'GraphRAG Tokens', 'Reduction', 'Judge', 'BERTScore'].map(h => (
                        <th key={h} style={{
                          padding: '10px 16px', borderBottom: `1px solid ${t.border}`,
                          color: t.textSubtle, textAlign: 'left', fontWeight: 700,
                          fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.07em',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((row, i) => (
                      <tr
                        key={i}
                        style={{ borderBottom: `1px solid ${t.border}`, cursor: 'pointer' }}
                        onClick={() => selectQuestion(row.question)}
                        onMouseEnter={e => e.currentTarget.style.background = t.surfaceHover}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <td style={{ padding: '11px 16px', color: t.text, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.question}</td>
                        <td style={{ padding: '11px 16px', color: PIPELINE_COLORS.graphrag, fontWeight: 700 }}>{row.graphrag_tokens.toLocaleString()}</td>
                        <td style={{ padding: '11px 16px', fontWeight: 800, color: row.reduction_pct == null ? t.textSubtle : t.reductionStat }}>
                          {row.reduction_pct == null ? 'no match' : `${row.reduction_pct > 0 ? '-' : '+'}${Math.abs(row.reduction_pct)}%`}
                        </td>
                        <td style={{ padding: '11px 16px' }}>
                          {row.judge !== '—' ? <JudgeBadge judge={row.judge} t={t} /> : <span style={{ color: t.textSubtle }}>—</span>}
                        </td>
                        <td style={{ padding: '11px 16px', color: t.textMuted, fontWeight: 600 }}>{row.bertscore}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── Footer ── */}
        <div style={{ marginTop: 48, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 8 }}>
            <Network size={14} color="#16a34a" />
            <span style={{ fontSize: 13, fontWeight: 700, color: t.textMuted }}>
              TigerGraph GraphRAG Pipeline Comparison
            </span>
          </div>
          <div style={{ fontSize: 12, color: t.textSubtle, lineHeight: 1.6 }}>
            Powered by <strong style={{ color: t.textMuted }}>Gemini 2.5 Flash</strong> ·{' '}
            <strong style={{ color: t.textMuted }}>TigerGraph</strong> Knowledge Graph ·{' '}
            <strong style={{ color: t.textMuted }}>FAISS</strong> Vector Index ·{' '}
            <strong style={{ color: t.textMuted }}>102.9M</strong> tokens indexed
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-ring {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(1.3); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-up { animation: fadeUp 0.4s ease forwards; }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
      `}</style>
    </div>
  );
}
