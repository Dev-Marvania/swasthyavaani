(() => {
  'use strict';

  // Seed data for Maternal and Immunization field rosters
  const MATERNAL_ROSTER = [
    {
      id: 'SYN-ASHA-001',
      name: 'Priya Devi',
      age: 24,
      household: 'H-14, Shivajinagar',
      stage: 'ANC • 26 Weeks',
      visitType: 'ANC Checkup',
      highRisk: true,
      riskReason: 'Mild anemia (Hb 9.4 g/dL)',
      weightKg: '54.5',
      nextVisit: '2026-12-19',
    },
    {
      id: 'SYN-ASHA-002',
      name: 'Meena Kumari',
      age: 28,
      household: 'H-22, Ward 4 East',
      stage: 'PNC • Day 10',
      visitType: 'PNC Checkup',
      highRisk: false,
      riskReason: '',
      weightKg: '51.2',
      nextVisit: '2026-12-05',
    },
    {
      id: 'SYN-ASHA-003',
      name: 'Kavitha S',
      age: 26,
      household: 'H-09, Shivajinagar',
      stage: 'ANC • 32 Weeks',
      visitType: 'ANC Checkup',
      highRisk: true,
      riskReason: 'Previous C-Section (HRP)',
      weightKg: '61.0',
      nextVisit: '2026-12-12',
    },
    {
      id: 'SYN-ASHA-004',
      name: 'Lakshmi R',
      age: 22,
      household: 'H-31, Anganwadi Lane',
      stage: 'ANC • 18 Weeks',
      visitType: 'ANC Checkup',
      highRisk: false,
      riskReason: '',
      weightKg: '52.8',
      nextVisit: '2026-12-28',
    },
    {
      id: 'SYN-ASHA-005',
      name: 'Sunita Bai',
      age: 27,
      household: 'H-37, Ward 4 West',
      stage: 'ANC • 29 Weeks',
      visitType: 'ANC Checkup',
      highRisk: false,
      riskReason: '',
      weightKg: '57.4',
      nextVisit: '2026-12-16',
    },
  ];

  const IMMUNIZATION_ROSTER = [
    {
      id: 'SYN-ASHA-006',
      childName: 'Baby Aarav',
      motherName: 'Anjali Devi',
      ageLabel: '10 Weeks',
      household: 'H-18, Shivajinagar',
      vaccines: ['Pentavalent-2', 'OPV-2', 'Rotavirus-2'],
      status: 'overdue',
      dueDate: '2026-11-19',
      weightKg: '5.6',
    },
    {
      id: 'SYN-ASHA-007',
      childName: 'Baby Diya',
      motherName: 'Fatima Bee',
      ageLabel: '9 Months',
      household: 'H-05, Ward 4 North',
      vaccines: ['Measles-Rubella 1', 'Vitamin A'],
      status: 'overdue',
      dueDate: '2026-11-18',
      weightKg: '8.2',
    },
    {
      id: 'SYN-ASHA-008',
      childName: 'Baby Rohan',
      motherName: 'Radha M',
      ageLabel: '14 Weeks',
      household: 'H-27, Anganwadi Lane',
      vaccines: ['Pentavalent-3', 'IPV-2', 'OPV-3'],
      status: 'due',
      dueDate: '2026-11-21',
      weightKg: '6.3',
    },
  ];

  // Helper to open the workspace bottom sheet
  function openWorkspace(title, subtitle, contentHtml) {
    const modal = document.getElementById('workspace-modal');
    const sheet = document.getElementById('workspace-sheet');
    const titleEl = document.getElementById('workspace-title');
    const subtitleEl = document.getElementById('workspace-subtitle');
    const bodyEl = document.getElementById('workspace-body');

    if (titleEl) titleEl.textContent = title;
    if (subtitleEl) subtitleEl.textContent = subtitle;
    if (bodyEl) bodyEl.innerHTML = contentHtml;

    if (modal && sheet) {
      modal.classList.remove('pointer-events-none', 'opacity-0', 'invisible');
      modal.classList.add('opacity-100');
      sheet.classList.remove('translate-y-full', 'pointer-events-none');
      sheet.classList.add('translate-y-0', 'pointer-events-auto');
      document.documentElement.classList.add('modal-scroll-lock');
    }
  }

  window.closeWorkspace = () => {
    const modal = document.getElementById('workspace-modal');
    const sheet = document.getElementById('workspace-sheet');
    if (modal && sheet) {
      modal.classList.remove('opacity-100');
      modal.classList.add('opacity-0', 'pointer-events-none', 'invisible');
      sheet.classList.remove('translate-y-0', 'pointer-events-auto');
      sheet.classList.add('translate-y-full', 'pointer-events-none');
      document.documentElement.classList.remove('modal-scroll-lock');
    }
  };

  // 1. Render Today's Saved Visits
  function showSavedVisitsWorkspace() {
    let saved = [];
    try {
      const raw = localStorage.getItem('swasthyavaani_saved_visits');
      if (raw) saved = JSON.parse(raw);
    } catch {
      saved = [];
    }

    // Default sample entries if none yet
    if (saved.length === 0) {
      saved = [
        {
          name: 'Priya Devi',
          id: 'SYN-ASHA-001',
          visitType: 'ANC Checkup',
          weightKg: '54.5',
          vaccines: ['TT-1'],
          nextVisit: '15 December',
          danger: false,
          timestamp: '09:45 AM',
        },
        {
          name: 'Meena Kumari',
          id: 'SYN-ASHA-002',
          visitType: 'PNC Checkup',
          weightKg: '51.2',
          vaccines: [],
          nextVisit: '22 December',
          danger: false,
          timestamp: '10:30 AM',
        },
      ];
      localStorage.setItem('swasthyavaani_saved_visits', JSON.stringify(saved));
    }

    let cardsHtml = `
      <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between pb-2 border-b border-surface-container">
          <span class="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Confirmed Field Records (${saved.length})</span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              id="export-csv-btn"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-container hover:bg-primary text-on-primary text-[12px] font-bold shadow-sm active:scale-95 transition-all cursor-pointer"
              onclick="window.exportVisitsToCSV()"
            >
              <span class="material-symbols-outlined text-[16px]">download</span>
              <span>Export CSV</span>
            </button>
            <button type="button" class="text-xs font-bold text-error hover:underline px-1 py-1" onclick="clearTodayVisits()">Clear</button>
          </div>
        </div>
    `;

    for (const item of saved) {
      cardsHtml += `
        <div class="p-3.5 rounded-2xl bg-white border ${item.danger ? 'border-error bg-error-container/20' : 'border-surface-container'} shadow-sm flex flex-col gap-2">
          <div class="flex items-start justify-between">
            <div class="flex flex-col">
              <span class="text-[15px] font-bold text-on-surface">${item.name}</span>
              <span class="text-[12px] font-semibold text-secondary">ID: ${item.id} • ${item.visitType}</span>
            </div>
            ${
              item.danger
                ? `<span class="px-2 py-0.5 rounded-full bg-error text-white text-[11px] font-bold">PHC Referral</span>`
                : `<span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[11px] font-bold">Saved</span>`
            }
          </div>
          <div class="grid grid-cols-2 gap-2 text-[12px] text-on-surface-variant pt-1 border-t border-surface-container">
            <div><strong>Weight:</strong> ${item.weightKg || '—'} kg</div>
            <div><strong>Next Visit:</strong> ${item.nextVisit || '—'}</div>
            <div class="col-span-2">
              <strong>Vaccines:</strong> ${
                item.vaccinesGiven && item.vaccinesGiven.length > 0
                  ? `<span class="text-secondary font-semibold">${item.vaccinesGiven.map(v => v + ' [Given]').join(', ')}</span>`
                  : ''
              } ${
                item.vaccinesDue && item.vaccinesDue.length > 0
                  ? `<span class="text-amber-700 font-semibold">${item.vaccinesDue.map(v => v + ' [Due]').join(', ')}</span>`
                  : ''
              } ${
                (!item.vaccinesGiven || item.vaccinesGiven.length === 0) && (!item.vaccinesDue || item.vaccinesDue.length === 0)
                  ? (Array.isArray(item.vaccines) && item.vaccines.length > 0 ? item.vaccines.join(', ') : 'None recorded')
                  : ''
              }
            </div>
          </div>
          <div class="text-[10px] text-slate-400 text-right">Recorded at ${item.timestamp || 'Today'}</div>
        </div>
      `;
    }

    cardsHtml += `</div>`;

    openWorkspace("Today's Saved Visits", 'Confirmed visits for Ward 4 • Shivajinagar', cardsHtml);
  }

  window.clearTodayVisits = () => {
    localStorage.removeItem('swasthyavaani_saved_visits');
    const visitsCountEl = document.getElementById('dashboard-visits-count');
    const drawerCounterEl = document.getElementById('drawer-saved-visits-counter');
    if (visitsCountEl) visitsCountEl.textContent = '0';
    if (drawerCounterEl) drawerCounterEl.textContent = '0 visits recorded today';
    window.closeWorkspace();
  };

  // 2. Render Maternal Roster
  function showMaternalRoster() {
    let cardsHtml = `
      <div class="flex flex-col gap-3">
        <span class="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Maternal Patients (${MATERNAL_ROSTER.length})</span>
    `;

    for (const p of MATERNAL_ROSTER) {
      cardsHtml += `
        <div class="p-3.5 rounded-2xl bg-white border border-surface-container shadow-sm flex flex-col gap-2">
          <div class="flex items-start justify-between">
            <div class="flex flex-col">
              <div class="flex items-center gap-1.5">
                <span class="text-[15px] font-bold text-on-surface">${p.name}</span>
                ${p.highRisk ? `<span class="px-2 py-0.5 rounded-full bg-error text-white text-[10px] font-bold">HRP</span>` : ''}
              </div>
              <span class="text-[12px] font-semibold text-secondary">ID: ${p.id} • ${p.stage}</span>
            </div>
            <button
              type="button"
              class="px-3 py-1.5 rounded-xl bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold shadow-sm active:scale-95"
              onclick="window.closeWorkspace(); window.openVoiceModalForDept('maternal');"
            >
              Voice Note
            </button>
          </div>
          <div class="grid grid-cols-2 gap-2 text-[12px] text-on-surface-variant pt-1 border-t border-surface-container">
            <div><strong>Location:</strong> ${p.household}</div>
            <div><strong>Next Due:</strong> ${p.nextVisit}</div>
          </div>
          ${p.riskReason ? `<div class="text-[11px] text-error font-semibold">${p.riskReason}</div>` : ''}
        </div>
      `;
    }

    cardsHtml += `</div>`;
    openWorkspace('Maternal & Child Care Roster', 'Active pregnant & postpartum mothers in Ward 4', cardsHtml);
  }

  // 3. Render Immunization Roster
  function showImmunizationRoster() {
    let cardsHtml = `
      <div class="flex flex-col gap-3">
        <span class="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Infant Vaccine Cohort (${IMMUNIZATION_ROSTER.length})</span>
    `;

    for (const p of IMMUNIZATION_ROSTER) {
      cardsHtml += `
        <div class="p-3.5 rounded-2xl bg-white border border-surface-container shadow-sm flex flex-col gap-2">
          <div class="flex items-start justify-between">
            <div class="flex flex-col">
              <span class="text-[15px] font-bold text-on-surface">${p.childName}</span>
              <span class="text-[12px] font-semibold text-secondary">Mother: ${p.motherName} (${p.ageLabel})</span>
            </div>
            <button
              type="button"
              class="px-3 py-1.5 rounded-xl bg-secondary-fixed text-on-secondary-fixed text-[12px] font-bold shadow-sm active:scale-95"
              onclick="window.closeWorkspace(); window.openVoiceModalForDept('immunization');"
            >
              Voice Note
            </button>
          </div>
          <div class="text-[12px] text-on-surface-variant">
            <strong>Vaccines:</strong> ${p.vaccines.join(', ')}
          </div>
          <div class="flex items-center justify-between text-[12px] pt-1 border-t border-surface-container">
            <span class="text-on-surface-variant">Due: ${p.dueDate}</span>
            <span class="font-bold ${p.status === 'overdue' ? 'text-error' : 'text-secondary'} uppercase text-[11px]">${p.status}</span>
          </div>
        </div>
      `;
    }

    cardsHtml += `</div>`;
    openWorkspace('Immunization Tracking Roster', 'Anganwadi camp vaccination cohort for Ward 4', cardsHtml);
  }

  // Attach event listeners
  document.addEventListener('DOMContentLoaded', () => {
    // 1. Drawer "Today's Saved Visits" button
    const drawerSavedBtn = document.getElementById('drawer-saved-visits-btn');
    if (drawerSavedBtn) {
      drawerSavedBtn.addEventListener('click', () => {
        window.toggleNavMenu(false);
        showSavedVisitsWorkspace();
      });
    }

    // 2. Header dial shortcut to Today's Saved Visits
    const visitsShortcut = document.getElementById('today-saved-visits-shortcut');
    if (visitsShortcut) {
      visitsShortcut.addEventListener('click', showSavedVisitsWorkspace);
    }

    // 3. Hero Card "View Roster" buttons
    document.querySelectorAll('.dept-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const dept = btn.getAttribute('data-dept');
        if (dept === 'immunization') {
          showImmunizationRoster();
        } else {
          showMaternalRoster();
        }
      });
    });

    // 4. Update initial visits counter (count of confirmed visits only, no arbitrary /8 target)
    try {
      const raw = localStorage.getItem('swasthyavaani_saved_visits');
      const count = raw ? JSON.parse(raw).length : 0;
      const visitsCountEl = document.getElementById('dashboard-visits-count');
      const drawerCounterEl = document.getElementById('drawer-saved-visits-counter');
      if (visitsCountEl) visitsCountEl.textContent = String(count);
      if (drawerCounterEl) drawerCounterEl.textContent = `${count} visits recorded today`;
    } catch {
      // Ignored
    }
  });
})();
