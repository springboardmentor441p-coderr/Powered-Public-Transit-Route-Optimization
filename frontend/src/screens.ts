// Top-bar tabs, in order. Each maps to a spec 9.16.2 screen (see NOTES.md Step 67b).
export const TABS = [
  { to: '/', label: 'Start', end: true, question: 'Where do I begin?' },                       // Network overview
  { to: '/closer-look', label: 'Closer look', question: 'Which routes deserve a closer look?' }, // Review priorities
  { to: '/route', label: 'One route', question: 'How is one route doing?' },                    // Route detail
  { to: '/alike', label: 'Alike', question: 'Which routes are alike?' },                        // Route groups
  { to: '/shared-stops', label: 'Shared stops', question: 'Which routes share stops?' },        // overlap review
  { to: '/compare', label: 'Compare', question: 'How do these routes differ?' },                 // Compare routes
  { to: '/data', label: 'Data', question: 'Can I trust these numbers?' },                       // Data and coverage
] as const
