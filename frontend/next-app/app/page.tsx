"use client"

import { useState } from "react"
import Image from "next/image"
import { Playfair_Display, DM_Serif_Display, Space_Mono, Libre_Baskerville, Poppins } from "next/font/google"

const playfair = Playfair_Display({ subsets: ["latin"], weight: ["400", "700"], style: ["normal", "italic"] })
const dmSerif = DM_Serif_Display({ subsets: ["latin"], weight: "400", style: ["normal", "italic"] })
const spaceMono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"] })
const libreBaskerville = Libre_Baskerville({ subsets: ["latin"], weight: ["400", "700"], style: ["normal", "italic"] })
const poppins = Poppins({ subsets: ["latin"], weight: ["300", "400", "500", "600"], style: ["normal", "italic"] })

const internships = [
  {
    role: "Product Design Intern",
    company: "Zomato",
    stipend: "₹40,000/mo",
    location: "Remote",
    branch: "Any",
    cgpa: "7.5+",
    type: "Design",
    duration: "3 months",
    mode: "Work from home",
    gender: "All genders",
    deadline: "May 15, 2025",
    link: "#apply",
    desc: "End-to-end product design for consumer-facing features. You'll own user research, wireframing, and handoff to engineering.",
    logo: "ZO",
    pay: "₹",
  },
  {
    role: "Software Engineer Intern",
    company: "Swiggy",
    stipend: "₹25,000/mo",
    location: "Bangalore",
    branch: "CS / IT / ECE",
    cgpa: "8.0+",
    type: "Engineering",
    duration: "2 months",
    mode: "In-office",
    gender: "All genders",
    deadline: "April 30, 2025",
    link: "#apply",
    desc: "Full-stack development on consumer-facing features using React and Node.js. Real production code from day one.",
    logo: "SW",
    pay: "₹",
  },
  {
    role: "Marketing Intern",
    company: "Mamaearth",
    stipend: "₹8,000/mo",
    location: "Delhi",
    branch: "Any",
    cgpa: "No cutoff",
    type: "Marketing",
    duration: "1 month",
    mode: "Hybrid",
    gender: "All genders",
    deadline: "May 5, 2025",
    link: "#apply",
    desc: "Social media strategy, content calendars, and campaign analytics for a leading D2C beauty brand.",
    logo: "MA",
    pay: "₹",
  },
  {
    role: "Data Science Intern",
    company: "Reliance",
    stipend: "₹50,000/mo",
    location: "Mumbai",
    branch: "CS / Math / Stats",
    cgpa: "8.5+",
    type: "Data",
    duration: "6 months",
    mode: "In-office",
    gender: "All genders",
    deadline: "June 1, 2025",
    link: "#apply",
    desc: "Build ML models and data pipelines for business intelligence at scale. Python, SQL, and a willingness to dig deep.",
    logo: "RL",
    pay: "₹₹",
  },
  {
    role: "UX Research Intern",
    company: "Razorpay",
    stipend: "₹20,000/mo",
    location: "Ahmedabad",
    branch: "Any",
    cgpa: "No cutoff",
    type: "Research",
    duration: "3 months",
    mode: "In-office",
    gender: "All genders",
    deadline: "May 20, 2025",
    link: "#apply",
    desc: "User interviews, usability testing & synthesis for B2B fintech platform.",
    logo: "RZ",
    pay: "₹",
  },
  {
    role: "Product Management Intern",
    company: "InMobi",
    stipend: "₹1,20,000/mo",
    location: "Remote",
    branch: "Any",
    cgpa: "8.0+",
    type: "Product",
    duration: "2 months",
    mode: "Work from home",
    gender: "All genders",
    deadline: "May 25, 2025",
    link: "#apply",
    desc: "Roadmap planning, sprint management & stakeholder communication.",
    logo: "IN",
    pay: "₹₹₹",
  },
]

const companies = [
  "Zomato", "Swiggy", "Razorpay", "Mamaearth", "Reliance", "InMobi",
  "Meesho", "CRED", "upGrad", "Byju's", "PhonePe", "Ola", "Flipkart"
]

const teamMembers = [
  { 
    name: "Falguni Dhingra", 
    bio: "Hello! I am Falguni Dhingra. Although by my ID card, I am a first year student pursuing a B.tech in Chemical Engineering from IIT Roorkee, I have tried my hand in many different pursuits of excellence. I have taught myself basics of developing, AI-ML, design and even consult. I like to put my best into everything and build things worthwhile for the world. This passion is what guided me while working on the \"it girls\" website. I wanted to solve the problems that my seniors faced while navigating the maze of mentorship programs or internships.",
    photo: "/team/falguni.jpg"
  },
  { 
    name: "Avani Singhal", 
    bio: "Hey!! I'm Avani Singhal, a first-year Data Science & AI student at IIT Roorkee. While most people see data as just numbers, I see a puzzle of Data Structures waiting to be solved. I joined this project because I wanted to take the theories I'm learning in class and crash-test them against the real-world web. If there's a way to implement a more elegant or efficient way to handle data, I'm probably obsessing over it right now.",
    photo: "/team/avani.jpg"
  },
  { 
    name: "Anushna Chakrabarti", 
    bio: "Hii!! I am Anushna Chakrabarti,  a student at IIT Roorkee  in Metallurgical and Materials Engineering. I am someone with a creative and analytical mind. And design is something that satisfies both these sides of my brain together for me. Which is why I had a special fascination with this project, it was the perfect amalgamation of creativity and analytics.",
    photo: "/team/anushna.jpg"
  },
]

export default function Home() {
  const [selectedInternship, setSelectedInternship] = useState<number | null>(null)

  return (
    <div className="min-h-screen bg-[#FFFFFA] text-[#000F08]">
      {/* Paper texture overlay */}
      <div 
        className="fixed inset-0 pointer-events-none z-[9999] opacity-50"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='400' height='400' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E")`
        }}
      />

      {/* SVG Filters */}
      <svg className="absolute w-0 h-0">
        <defs>
          <filter id="paper-crumple">
            <feTurbulence type="fractalNoise" baseFrequency="0.02 0.03" numOctaves={3} seed={8} result="noise"/>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={3} xChannelSelector="R" yChannelSelector="G"/>
          </filter>
        </defs>
      </svg>

      {/* Crumple lines */}
      <svg className="fixed inset-0 pointer-events-none z-[1]">
        <line x1="15%" y1="0" x2="22%" y2="100%" stroke="#928779" strokeWidth="0.5" opacity="0.3"/>
        <line x1="45%" y1="0" x2="40%" y2="100%" stroke="#928779" strokeWidth="0.5" opacity="0.2"/>
        <line x1="72%" y1="0" x2="78%" y2="100%" stroke="#928779" strokeWidth="0.5" opacity="0.25"/>
        <line x1="88%" y1="0" x2="91%" y2="100%" stroke="#928779" strokeWidth="0.3" opacity="0.15"/>
      </svg>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-[100] bg-[#7D0013] px-12 h-14 flex items-center justify-between">
        <a href="/" className="no-underline text-inherit">
          <div className={`${playfair.className} !text-4x1 font-bold italic text-[#FFFFFA] tracking-tight cursor-pointer`}>
            it girls
          </div>
         </a>
        <div className="flex items-center">
          <a className={`${spaceMono.className} text-[0.7rem] tracking-[0.08em] uppercase text-[#7D0013] px-6 h-10 flex items-center bg-[#FFFFFA] rounded-t-lg cursor-pointer border border-white/10 border-b-0 mr-1`}>
            Internships
          </a>
          <a className={`${spaceMono.className} text-[0.7rem] tracking-[0.08em] uppercase text-[#FFFFFA] px-6 h-10 flex items-center bg-white/10 rounded-t-lg cursor-pointer border border-white/10 border-b-0 mr-1 hover:bg-[#FFFFFA] hover:text-[#7D0013] transition-colors`}>
            Mentorships
          </a>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="min-h-screen pt-14 relative flex flex-col items-center overflow-hidden">
        <div className="relative z-[2] w-full max-w-[1200px] px-12 py-16 flex flex-col items-center">
          {/* Quote */}
          <div className="text-center mb-16 animate-fadeUp">
            <span className={`${playfair.className} text-4xl md:text-5xl lg:text-[4.5rem] font-normal text-[#000F08] leading-tight block`}>
              build the career
            </span>
            <span className={`${playfair.className} text-4xl md:text-5xl lg:text-[5rem] font-normal text-[#7D0013] leading-tight block`}>
              they said you couldn&apos;t.
            </span>
            <p className={`${spaceMono.className} text-[0.72rem] tracking-[0.15em] text-[#928779] uppercase mt-5`}>
              curated internships & mentorships for women in tech & beyond
            </p>
          </div>

          {/* Folders Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-[1100px] px-4 pb-16">
            {internships.map((intern, index) => (
              <div 
                key={index}
                className="cursor-pointer flex flex-col animate-fadeUp"
                style={{ animationDelay: `${0.6 + index * 0.15}s` }}
                onClick={() => setSelectedInternship(index)}
              >
                {/* Tabs */}
                <div className="flex items-end gap-1 pl-0.5">
                  <div className={`${spaceMono.className} h-[30px] px-2.5 bg-[#6b5f57] rounded-t-lg flex items-center text-[0.68rem] text-[#f5e8c8] tracking-wide border border-white/10 border-b-0`}>
                    {intern.pay}
                  </div>
                  <div className={`${spaceMono.className} h-[30px] px-2.5 bg-[#7a7167] rounded-t-lg flex items-center text-[0.68rem] text-[#FFFFFA] tracking-wide border border-white/10 border-b-0`}>
                    {intern.duration}
                  </div>
                  <div className={`${spaceMono.className} h-[30px] px-2.5 bg-[#84796e] rounded-t-lg flex items-center text-[0.68rem] text-[#FFFFFA] tracking-wide border border-white/10 border-b-0`}>
                    {intern.location}
                  </div>
                </div>
                {/* Folder Body */}
                <div className="bg-[#928779] rounded-tr-md rounded-b-md overflow-hidden relative flex-1 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
                  <div 
                    className="absolute inset-0 opacity-70 mix-blend-multiply pointer-events-none"
                    style={{
                      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.18'/%3E%3C/svg%3E")`
                    }}
                  />
                  <div className="relative z-[1] p-4 flex flex-col justify-between min-h-[160px]">
                    <div>
                     <div className={`${poppins.className} text-[1.375rem] font-semibold text-[#FFFFFA] leading-tight`}>          {intern.role}
                     
                      </div>

                      <div className={`${spaceMono.className} text-[0.8rem] text-white/70 leading-relaxed mt-1`}>
                        {intern.desc.slice(0, 80)}...
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`${spaceMono.className} w-7 h-7 rounded-md bg-[#FFFFFA] flex items-center justify-center text-[0.55rem] font-bold text-[#6b6358] tracking-tight`}>
                          {intern.logo}
                        </div>
                        <div className={`${spaceMono.className} text-[0.66rem] text-white/80 tracking-wide`}>
                          {intern.company}
                        </div>
                      </div>
                      <div className={`${spaceMono.className} text-[0.61rem] text-white/40 tracking-[0.08em] uppercase`}>
                        tap to open →
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Companies Carousel */}
      <section className="py-16 bg-[#FFFFFA] overflow-hidden relative border-t border-[#928779]/20">
        <p className={`${spaceMono.className} text-[0.65rem] tracking-[0.18em] uppercase text-[#928779] text-center mb-8`}>
          companies we&apos;ve featured
        </p>
        <div className="flex gap-12 animate-scroll hover:[animation-play-state:paused]">
          {[...companies, ...companies].map((company, i) => (
            <div 
              key={i}
              className={`${spaceMono.className} text-[0.75rem] tracking-[0.08em] text-[#6b6358] px-5 py-2 border border-[#b5a898] rounded-full whitespace-nowrap bg-[#928779]/5 hover:bg-[#7D0013] hover:text-[#FFFFFA] hover:border-[#7D0013] transition-colors cursor-pointer`}
            >
              {company}
            </div>
          ))}
        </div>
      </section>

      {/* Feedback Section */}
      <section className="py-16 px-12 bg-[#f5f0e8] relative">
        <p className={`${spaceMono.className} text-[0.65rem] tracking-[0.18em] uppercase text-[#928779] text-center mb-10`}>
          what they said
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-[1100px] mx-auto items-end">
          {[
            {
              quote: "Found my Razorpay internship here within a week. The folder format made it so easy to filter by stipend — I wasn't wasting time on unpaid roles.",
              author: "Priya M. — IIT Delhi, CSE '25"
            },
            {
              quote: "I was able to find the perfect mentorship program by applying the filters on the site..",
              author: "Anika R. — BITS Pilani, EEE '24"
            },
            {
              quote: "Applied for three internships in one sitting. Everything I needed — branch eligibility, cgpa cutoff, deadline — was right there. No chasing seniors for info.",
              author: "Sneha T. — NIT Trichy, ECE '25"
            }
          ].map((feedback, i) => (
            <div 
              key={i}
              className="bg-[#FFFFFA] p-6 pb-12 relative border-l border-r border-t border-[#928779]/20"
              style={{
                clipPath: "polygon(0 0, 100% 0, 100% 88%, 96% 92%, 92% 88%, 88% 93%, 84% 88%, 80% 92%, 76% 88%, 72% 92%, 68% 88%, 64% 93%, 60% 88%, 56% 92%, 52% 88%, 48% 93%, 44% 88%, 40% 92%, 36% 88%, 32% 93%, 28% 88%, 24% 92%, 20% 88%, 16% 93%, 12% 88%, 8% 92%, 4% 88%, 0 92%)",
                transform: i === 1 ? "rotate(-1.5deg)" : i === 2 ? "rotate(1deg)" : undefined
              }}
            >
              <div className={`${poppins.className} text-base italic text-[#000F08] leading-relaxed mb-4`}>
                &quot;{feedback.quote}&quot;
              </div>
              <div className={`${spaceMono.className} text-[0.6rem] text-[#928779] tracking-[0.1em] uppercase`}>
                {feedback.author}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* About Us Section - New Folder Design */}
      <AboutSection teamMembers={teamMembers} spaceMono={spaceMono} dmSerif={dmSerif} poppins={poppins} />

      {/* Footer */}
      <footer className={`${spaceMono.className} bg-[#000F08] text-white/40 text-center py-8 text-[0.6rem] tracking-[0.12em] uppercase`}>
        © 2025 The Intern Files — built with intention, for you
      </footer>

      {/* Notebook Modal */}
      {selectedInternship !== null && (
        <div 
          className="fixed inset-0 bg-[#000F08]/70 z-[500] flex items-center justify-center backdrop-blur-sm animate-fadeIn"
          onClick={() => setSelectedInternship(null)}
        >
          <div 
            className="w-[min(680px,90vw)] max-h-[80vh] bg-[#faf8f2] rounded-r-xl relative flex animate-scaleIn"
            onClick={e => e.stopPropagation()}
          >
            {/* Spiral binding */}
            <div className="w-9 bg-[#d4cfc4] flex-shrink-0 flex flex-col items-center pt-5 gap-3.5 border-r border-[#c8c3b8]">
              {Array.from({ length: 20 }).map((_, i) => (
                <div key={i} className="w-4.5 h-4.5 border-2 border-[#7D0013] rounded-full bg-transparent" />
              ))}
            </div>
            {/* Content */}
            <div 
              className="flex-1 p-8 pl-6 overflow-y-auto relative"
              style={{
                background: `repeating-linear-gradient(transparent, transparent 27px, rgba(125,0,19,0.08) 27px, rgba(125,0,19,0.08) 28px)`,
                backgroundSize: "100% 28px",
                backgroundPosition: "0 8px"
              }}
            >
              {/* Red margin line */}
              <div className="absolute left-14 top-0 bottom-0 w-px bg-red-400/25 pointer-events-none" />
              
              <button 
                className={`${spaceMono.className} absolute top-3 right-4 text-[0.7rem] text-[#928779] hover:text-[#7D0013] tracking-wide`}
                onClick={() => setSelectedInternship(null)}
              >
                close ✕
              </button>

              <h2 className={`${poppins.className} text-2xl text-[#7D0013] italic mb-1`}>
                {internships[selectedInternship].role}
              </h2>
              <p className={`${spaceMono.className} text-[0.65rem] text-[#928779] tracking-[0.1em] uppercase mb-6`}>
                {internships[selectedInternship].company}
              </p>

              <div className="w-full h-px bg-[#7D0013]/15 my-4" />

              {[
                { label: "Stipend", value: internships[selectedInternship].stipend, highlight: true },
                { label: "Duration", value: internships[selectedInternship].duration },
                { label: "Location", value: internships[selectedInternship].location },
                { label: "Mode", value: internships[selectedInternship].mode },
                { label: "Branch", value: internships[selectedInternship].branch },
                { label: "CGPA", value: internships[selectedInternship].cgpa },
                { label: "Deadline", value: internships[selectedInternship].deadline, highlight: true },
              ].map((row, i) => (
                <div key={i} className="flex gap-4 mb-2.5 items-baseline">
                  <span className={`${spaceMono.className} text-[0.6rem] text-[#928779] uppercase tracking-[0.1em] min-w-[90px] flex-shrink-0`}>
                    {row.label}
                  </span>
                  <span className={`${row.highlight ? `${poppins.className} text-sm text-[#7D0013] italic` : `${libreBaskerville.className} text-sm text-[#000F08]`}`}>
                    {row.value}
                  </span>
                </div>
              ))}

              <div className="w-full h-px bg-[#7D0013]/15 my-4" />

              <p className={`${libreBaskerville.className} text-sm text-[#000F08] leading-relaxed`}>
                {internships[selectedInternship].desc}
              </p>

              <button className={`${spaceMono.className} mt-6 px-8 py-3 bg-[#7D0013] text-[#FFFFFA] text-[0.7rem] tracking-[0.1em] uppercase rounded-sm hover:bg-[#5a000e] transition-colors`}>
                Apply Now →
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(24px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleIn {
          from { opacity: 0; transform: translateY(30px) scale(0.95); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-fadeUp {
          animation: fadeUp 0.8s ease forwards;
          opacity: 0;
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease forwards;
        }
        .animate-scaleIn {
          animation: scaleIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
        .animate-scroll {
          animation: scroll 22s linear infinite;
          width: max-content;
        }
      `}</style>
    </div>
  )
}

// About Section Component with new folder design
function AboutSection({ 
  teamMembers, 
  spaceMono, 
  dmSerif,
  poppins
}: { 
  teamMembers: { name: string; bio: string; photo: string }[]
  spaceMono: { className: string }
  dmSerif: { className: string }
  poppins: { className: string }
}) {
  const [selectedMember, setSelectedMember] = useState<number | null>(null)
  
  return (
    <section className="py-20 px-8 flex justify-center bg-[#FFFFFA] border-t border-[#928779]/15">
      <div className="relative w-full max-w-[700px]">
        {/* Main folder */}
        <div className="relative">
          {/* Tabs at top */}
          <div className="flex items-end gap-1 pl-4 relative z-20">
            {teamMembers.map((member, i) => (
              <button 
                key={i}
                onClick={() => setSelectedMember(selectedMember === i ? null : i)}
                className={`${spaceMono.className} h-9 px-4 rounded-t-lg flex items-center text-[0.77rem] tracking-wide border border-[#c4b8a8]/50 border-b-0 transition-all duration-200 cursor-pointer ${
                  selectedMember === i 
                    ? "bg-[#e8d5e0] text-[#7D0013] border-[#e8d5e0]" 
                    : "bg-[#c4b8a8] text-[#5a5048] hover:bg-[#d4c8b8]"
                }`}
              >
                {member.name}
              </button>
            ))}
          </div>

          {/* Folder body with vertical tab */}
          <div className="relative flex">
            {/* Vertical "About Us" tab on the left - connected to folder */}
            <button 
              onClick={() => setSelectedMember(null)}
              className={`w-10 bg-[#c4b8a8] text-[#5a5048] text-[0.99rem] tracking-wide border border-[#c4b8a8]/50 border-r-0 flex items-center justify-center cursor-pointer hover:bg-[#d4c8b8] transition-all duration-200 self-stretch font-[family-name:var(--font-inter)]`}
              style={{ writingMode: 'vertical-rl', textOrientation: 'mixed', transform: 'rotate(180deg)' }}
            >
              About Us
            </button>

            {/* Folder body */}
            <div className="relative flex-1 bg-[#d4c8b8] rounded-tr-lg rounded-br-lg rounded-bl-lg overflow-visible shadow-xl">
              {/* Paper texture */}
              <div 
                className="absolute inset-0 opacity-60 mix-blend-multiply pointer-events-none rounded-tr-lg rounded-br-lg rounded-bl-lg"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.15'/%3E%3C/svg%3E")`
                }}
              />

              {/* Inner content */}
              <div className="relative z-10 p-8 min-h-[350px]">
                {selectedMember === null ? (
                  // Default content - About The Intern Files
                  <div className="flex flex-col items-center justify-center h-full text-center py-4">
                    <h3 className={`${playfair.className} text-2xl font semi-bold text-[#2a2520] mb-2`}>
                      it girls
                    </h3>
                  <p className={`${spaceMono.className} text-[0.715rem] text-[#7D0013] tracking-[0.15em] uppercase mb-5`}>
                    A project by women, built by women at IIT Roorkee
                  </p>
                  <p className="text-sm text-[#5a5048] leading-relaxed max-w-[480px]">
                    We were tired of missing deadlines, chasing seniors, and finding out about internships two days too late. So we built the thing we wished existed — a clean, honest, no-fluff board of opportunities curated for college women who are serious about their careers.
                  </p>
                  <p className={`${spaceMono.className} text-[0.66rem] text-[#928779] mt-6 tracking-wide`}>
                    (click a name to learn more)
                  </p>
                </div>
              ) : (
                // Selected member content
                <div className="flex gap-6 items-start py-2">
                  {/* Photo */}
                  <div className="w-44 h-56 flex-shrink-0 border-2 border-[#5a5048] bg-[#e8e0d4] overflow-hidden relative">
                    <Image 
                      src={teamMembers[selectedMember].photo}
                      alt={teamMembers[selectedMember].name}
                      fill
                      className="object-cover"
                    />
                  </div>
                  
                  {/* Bio content */}
                  <div className="flex-1">
                    <div className="font-[family-name:var(--font-caveat)] text-2xl text-[#2a2520] mb-1 border-b border-[#5a5048]/30 pb-1">
                      {teamMembers[selectedMember].name}
                    </div>
                    {/* Handwritten lines effect */}
                    <div className="mt-4 space-y-4">
                      <p className="text-sm text-[#5a5048] leading-relaxed border-b border-[#5a5048]/20 pb-2">
                        {teamMembers[selectedMember].bio}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          </div>
        </div>
      </div>
    </section>
  )
}
