(() => {
  'use strict';

  // --- Dynamic Synthetic Beneficiary ID Sequence & Fresh State ---
  let visitSequence = parseInt(localStorage.getItem('swasthyavaani_visit_seq') || '101', 10);

  function generateDynamicBeneficiaryId() {
    visitSequence += 1;
    localStorage.setItem('swasthyavaani_visit_seq', String(visitSequence));
    return `SYN-ASHA-${visitSequence}`;
  }

  function createFreshVisitRecord(visitTypeHint) {
    const isImmu = (visitTypeHint === 'Immunization' || visitTypeHint === 'Immunisation');
    return {
      beneficiary_name: '',
      beneficiary_id: generateDynamicBeneficiaryId(),
      visit_type: isImmu ? 'Immunization' : (visitTypeHint || 'ANC / Maternal Care'),
      locked_visit_type: isImmu ? 'Immunization' : null,
      weight_kg: '',
      vaccinations_given: [],
      vaccinations_due: [],
      next_visit_date: '',
      phc_referral_needed: false,
      danger_signs_detected: [],
      confirmed: false,
      is_frozen: false,
    };
  }

  let activeVisit = createFreshVisitRecord();
  let activeRoom = null;
  let activeWakeLock = null;
  let highlightTimeouts = {};
  let currentLanguage = localStorage.getItem('swasthyavaani_voice_lang') || 'en-IN';
  let currentUILanguage = localStorage.getItem('swasthyavaani_ui_lang') || 'en-IN';

  // Function to completely reset active visit state for a fresh record
  function resetActiveVisitState(visitTypeHint) {
    activeVisit = createFreshVisitRecord(visitTypeHint);

    // Clear active emerald highlights
    for (const key of Object.keys(highlightTimeouts)) {
      clearTimeout(highlightTimeouts[key]);
    }
    highlightTimeouts = {};
    document.querySelectorAll('.field-updated').forEach((elem) => {
      elem.classList.remove('field-updated');
    });

    renderActiveVisitCard();

    // Reset spoken transcript / readback text
    const raw = el.rawNote();
    if (raw) raw.textContent = '“Listening for ASHA worker notes…”';

    // Hide danger banner and confirmed badges
    const phcBanner = el.phcBanner();
    if (phcBanner) phcBanner.classList.add('hidden');

    const confBadge = el.confirmedBadge();
    const draftStatus = el.draftStatusText();
    if (confBadge) confBadge.classList.add('hidden');
    if (draftStatus) draftStatus.classList.remove('hidden');

    // Inform backend WebSocket to clear previous visit memory
    if (activeStreamingSession && activeStreamingSession.ws && activeStreamingSession.ws.readyState === WebSocket.OPEN) {
      activeStreamingSession.sendJson('new_visit', {
        beneficiary_id: activeVisit.beneficiary_id,
        visit_type: activeVisit.visit_type,
      });
    }
  }

  window.startNewVisit = (hint) => {
    resetActiveVisitState(hint);
    const toast = document.getElementById('sync-success-toast');
    if (toast) {
      const title = document.getElementById('toast-title');
      const sub = document.getElementById('toast-subtitle');
      if (title) title.textContent = 'Fresh Record Initialized';
      if (sub) sub.textContent = `New ID: ${activeVisit.beneficiary_id} • Ready for new patient`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 2500);
    }
  };

  // --- UI References ---
  const el = {
    badge: () => document.getElementById('session-status-badge'),
    badgeDot: () => document.getElementById('session-status-dot'),
    badgeLabel: () => document.getElementById('session-status-label'),
    modalStatusText: () => document.getElementById('modal-status-text'),
    modalStatusDot: () => document.getElementById('status-indicator-dot'),
    voiceRecordBtn: () => document.getElementById('voice-record-btn'),
    voiceMicIcon: () => document.getElementById('voice-mic-icon'),
    voiceBtnSublabel: () => document.getElementById('voice-btn-sublabel'),
    rings: [
      () => document.getElementById('wave-ring-1'),
      () => document.getElementById('wave-ring-2'),
      () => document.getElementById('wave-ring-3'),
    ],
    waveformBars: () => document.querySelectorAll('.waveform-bar'),
    rawNote: () => document.getElementById('review-raw-note'),
    phcBanner: () => document.getElementById('phc-referral-banner'),
    dangerList: () => document.getElementById('danger-signs-list'),
    valBeneficiaryName: () => document.getElementById('val-beneficiary-name'),
    valBeneficiaryId: () => document.getElementById('val-beneficiary-id'),
    valVisitType: () => document.getElementById('val-visit-type'),
    valWeightKg: () => document.getElementById('val-weight-kg'),
    valVaccinationsGiven: () => document.getElementById('val-vaccinations-given'),
    valVaccinationsDue: () => document.getElementById('val-vaccinations-due'),
    valNextVisitDate: () => document.getElementById('val-next-visit-date'),
    fieldBeneficiary: () => document.getElementById('field-beneficiary'),
    fieldVisitType: () => document.getElementById('field-visit_type'),
    fieldWeightKg: () => document.getElementById('field-weight_kg'),
    fieldVaccinationsGiven: () => document.getElementById('field-vaccinations_given'),
    fieldVaccinationsDue: () => document.getElementById('field-vaccinations_due'),
    fieldNextVisitDate: () => document.getElementById('field-next_visit_date'),
    confirmedBadge: () => document.getElementById('confirmed-badge'),
    draftStatusText: () => document.getElementById('draft-status-text'),
    offlineBanner: () => document.getElementById('offline-banner'),
    audioSink: () => document.getElementById('audio-sink'),
    demoStrip: () => document.getElementById('demo-test-strip'),
  };

  // --- Visual State Management ---
  // States: 'idle' -> 'connecting' -> 'listening' -> 'speaking' -> 'error'
  function setSessionUIState(state, message) {
    const badge = el.badge();
    const badgeDot = el.badgeDot();
    const badgeLabel = el.badgeLabel();
    const statusText = el.modalStatusText();
    const statusDot = el.modalStatusDot();
    const micIcon = el.voiceMicIcon();
    const sublabel = el.voiceBtnSublabel();
    const micBtn = el.voiceRecordBtn();
    const bars = el.waveformBars();

    if (badge) badge.setAttribute('data-status', state);

    if (state === 'idle') {
      if (badgeLabel) badgeLabel.textContent = 'Online';
      if (badgeDot) badgeDot.className = 'w-2 h-2 rounded-full bg-secondary';
      if (statusText) statusText.textContent = 'Ready to Listen';
      if (statusDot) statusDot.className = 'w-2.5 h-2.5 rounded-full bg-secondary';
      if (micIcon) micIcon.textContent = 'mic';
      if (sublabel) sublabel.textContent = 'Tap to Talk';
      if (micBtn) {
        micBtn.className =
          'relative z-10 w-24 h-24 rounded-full bg-primary-container text-white flex flex-col items-center justify-center shadow-lg active:scale-95 transition-all hover:bg-primary';
      }
      bars.forEach((b) => {
        b.style.animationPlayState = 'paused';
        b.classList.remove('bg-error');
        b.classList.add('bg-secondary');
      });
    } else if (state === 'connecting') {
      if (badgeLabel) badgeLabel.textContent = 'Connecting...';
      if (badgeDot) badgeDot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-ping';
      if (statusText) statusText.textContent = message || 'Connecting to LiveKit...';
      if (statusDot) statusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse';
      if (micIcon) micIcon.textContent = 'sync';
      if (sublabel) sublabel.textContent = 'Connecting...';
      if (micBtn) {
        micBtn.className =
          'relative z-10 w-24 h-24 rounded-full bg-amber-600 text-white flex flex-col items-center justify-center shadow-lg active:scale-95 transition-all animate-pulse';
      }
      bars.forEach((b) => {
        b.style.animationPlayState = 'running';
        b.style.animationDuration = '0.7s';
        b.classList.remove('bg-error');
        b.classList.add('bg-amber-600');
      });
    } else if (state === 'listening') {
      if (badgeLabel) badgeLabel.textContent = 'Listening...';
      if (badgeDot) badgeDot.className = 'w-2 h-2 rounded-full bg-error animate-ping';
      if (statusText) statusText.textContent = message || 'Listening Live • Hands-Free';
      if (statusDot) statusDot.className = 'w-2.5 h-2.5 rounded-full bg-error animate-ping';
      if (micIcon) micIcon.textContent = 'mic_off';
      if (sublabel) sublabel.textContent = 'Tap to End';
      if (micBtn) {
        micBtn.className =
          'relative z-10 w-24 h-24 rounded-full bg-error text-white flex flex-col items-center justify-center shadow-xl active:scale-95 transition-all scale-105';
      }
      bars.forEach((b) => {
        b.style.animationPlayState = 'running';
        b.style.animationDuration = '0.5s';
        b.classList.remove('bg-secondary');
        b.classList.add('bg-error');
      });
    } else if (state === 'speaking') {
      if (badgeLabel) badgeLabel.textContent = 'Agent Speaking...';
      if (badgeDot) badgeDot.className = 'w-2 h-2 rounded-full bg-sky-500 animate-pulse';
      if (statusText) statusText.textContent = message || 'Agent Speaking (Timbre TTS)...';
      if (statusDot) statusDot.className = 'w-2.5 h-2.5 rounded-full bg-sky-500 animate-ping';
      if (micIcon) micIcon.textContent = 'graphic_eq';
      if (sublabel) sublabel.textContent = 'Tap to End';
      if (micBtn) {
        micBtn.className =
          'relative z-10 w-24 h-24 rounded-full bg-[#005b6b] text-white flex flex-col items-center justify-center shadow-xl active:scale-95 transition-all scale-105';
      }
      bars.forEach((b) => {
        b.style.animationPlayState = 'running';
        b.style.animationDuration = '0.4s';
        b.classList.remove('bg-error');
        b.classList.add('bg-secondary');
      });
    } else if (state === 'error') {
      if (badgeLabel) badgeLabel.textContent = 'Offline / Error';
      if (badgeDot) badgeDot.className = 'w-2 h-2 rounded-full bg-error';
      if (statusText) statusText.textContent = message || 'Backend Error';
      if (statusDot) statusDot.className = 'w-2.5 h-2.5 rounded-full bg-error';
      if (micIcon) micIcon.textContent = 'error';
      if (sublabel) sublabel.textContent = 'Tap to Retry';
      if (micBtn) {
        micBtn.className =
          'relative z-10 w-24 h-24 rounded-full bg-error text-white flex flex-col items-center justify-center shadow-lg active:scale-95 transition-all';
      }
      bars.forEach((b) => {
        b.style.animationPlayState = 'paused';
      });
    }
  }

  // --- Emerald Green Highlight for Updated Fields ---
  function highlightFieldElement(containerEl) {
    if (!containerEl) return;
    containerEl.classList.add('field-updated');
    const id = containerEl.id || Math.random().toString();
    if (highlightTimeouts[id]) {
      clearTimeout(highlightTimeouts[id]);
    }
    highlightTimeouts[id] = setTimeout(() => {
      containerEl.classList.remove('field-updated');
      delete highlightTimeouts[id];
    }, 2000);
  }

  // --- JSON Merge Patching & DOM Updates ---
  function applyJsonMergePatch(patch) {
    if (!patch || typeof patch !== 'object') return;
    if (activeVisit && (activeVisit.confirmed || activeVisit.is_frozen)) {
      // Record is confirmed and saved. Refuse late or accidental speech mutations!
      return;
    }
    const source = patch.record || patch.data || patch.patch || patch;

    const updated = [];

    // 1. Auto-extract Beneficiary Name & ID
    if (source.beneficiary_name || source.beneficiary_id || source.name || source.id) {
      if (source.beneficiary_name) activeVisit.beneficiary_name = String(source.beneficiary_name).trim();
      else if (source.name) activeVisit.beneficiary_name = String(source.name).trim();

      if (source.beneficiary_id) activeVisit.beneficiary_id = String(source.beneficiary_id).trim();
      else if (source.id) activeVisit.beneficiary_id = String(source.id).trim();

      updated.push('beneficiary');
    }

    // 2. Visit Type (Locked to Immunization when started from Immunization Tracking)
    if (source.visit_type) {
      if (activeVisit.locked_visit_type === 'Immunization') {
        activeVisit.visit_type = 'Immunization';
      } else {
        activeVisit.visit_type = String(source.visit_type).trim();
      }
      updated.push('visit_type');
    }

    // 3. Weight
    if (source.weight_kg !== undefined && source.weight_kg !== null && source.weight_kg !== '') {
      activeVisit.weight_kg = String(source.weight_kg).trim();
      updated.push('weight_kg');
    }

    // 4. Vaccinations Given & Due (Separate arrays, no truthiness collision)
    if (source.vaccinations_given !== undefined) {
      const given = Array.isArray(source.vaccinations_given)
        ? source.vaccinations_given.map((v) => String(v).trim()).filter(Boolean)
        : (source.vaccinations_given ? [String(source.vaccinations_given).trim()] : []);
      activeVisit.vaccinations_given = given;
      updated.push('vaccinations_given');
    }

    if (source.vaccinations_due !== undefined) {
      const due = Array.isArray(source.vaccinations_due)
        ? source.vaccinations_due.map((v) => String(v).trim()).filter(Boolean)
        : (source.vaccinations_due ? [String(source.vaccinations_due).trim()] : []);
      activeVisit.vaccinations_due = due;
      updated.push('vaccinations_due');
    }

    // 5. Next Visit Date
    if (source.next_visit_date) {
      activeVisit.next_visit_date = String(source.next_visit_date).trim();
      updated.push('next_visit_date');
    }

    // 6. Danger Signs & Urgent PHC Referral
    if (
      source.phc_referral_needed !== undefined ||
      source.danger_flag !== undefined ||
      source.danger_signs_detected ||
      source.danger_signs
    ) {
      activeVisit.phc_referral_needed = Boolean(
        source.phc_referral_needed ||
          source.danger_flag ||
          (source.danger_signs_detected && source.danger_signs_detected.length > 0) ||
          (source.danger_signs && source.danger_signs.length > 0),
      );

      const signs = source.danger_signs_detected || source.danger_signs || [];
      if (Array.isArray(signs) && signs.length > 0) {
        activeVisit.danger_signs_detected = signs.map((s) => String(s).trim()).filter(Boolean);
      }
      updated.push('phc_referral');
    }

    // 7. Confirmed & Saved
    if (source.confirmed === true) {
      activeVisit.confirmed = true;
      activeVisit.is_frozen = true;
      updated.push('confirmed');
      saveCurrentVisitToRegistry();
    }

    // Update DOM Fields
    renderActiveVisitCard(updated);
  }

  function renderActiveVisitCard(updatedFields = []) {
    // Beneficiary Display
    const nameEl = el.valBeneficiaryName();
    const idEl = el.valBeneficiaryId();
    if (nameEl) {
      if (activeVisit.beneficiary_name) {
        nameEl.textContent = activeVisit.beneficiary_name;
      } else {
        nameEl.textContent = getI18n('listening_placeholder');
      }
    }
    if (idEl) {
      idEl.textContent = activeVisit.beneficiary_id ? `ID: ${activeVisit.beneficiary_id}` : '';
    }
    if (updatedFields.includes('beneficiary')) {
      highlightFieldElement(el.fieldBeneficiary());
    }

    // Visit Type
    const visitTypeEl = el.valVisitType();
    if (visitTypeEl) {
      visitTypeEl.textContent = activeVisit.visit_type || '—';
    }
    if (updatedFields.includes('visit_type')) {
      highlightFieldElement(el.fieldVisitType());
    }

    // Weight (kg)
    const weightEl = el.valWeightKg();
    if (weightEl) {
      weightEl.textContent = activeVisit.weight_kg ? `${activeVisit.weight_kg} kg` : '—';
    }
    if (updatedFields.includes('weight_kg')) {
      highlightFieldElement(el.fieldWeightKg());
    }

    // Vaccines Given [Given]
    const vaxGivenEl = el.valVaccinationsGiven();
    if (vaxGivenEl) {
      if (activeVisit.vaccinations_given && activeVisit.vaccinations_given.length > 0) {
        vaxGivenEl.textContent = activeVisit.vaccinations_given.map((v) => `${v} [Given]`).join(', ');
      } else {
        vaxGivenEl.textContent = getI18n('none_recorded');
      }
    }
    if (updatedFields.includes('vaccinations_given')) {
      highlightFieldElement(el.fieldVaccinationsGiven());
    }

    // Vaccines Due [Due]
    const vaxDueEl = el.valVaccinationsDue();
    if (vaxDueEl) {
      if (activeVisit.vaccinations_due && activeVisit.vaccinations_due.length > 0) {
        vaxDueEl.textContent = activeVisit.vaccinations_due.map((v) => `${v} [Due]`).join(', ');
      } else {
        vaxDueEl.textContent = getI18n('none_recorded');
      }
    }
    if (updatedFields.includes('vaccinations_due')) {
      highlightFieldElement(el.fieldVaccinationsDue());
    }

    // Next Visit Date
    const nextDateEl = el.valNextVisitDate();
    if (nextDateEl) {
      nextDateEl.textContent = activeVisit.next_visit_date || '—';
    }
    if (updatedFields.includes('next_visit_date')) {
      highlightFieldElement(el.fieldNextVisitDate());
    }

    // PHC Danger Alert Banner
    const phcBanner = el.phcBanner();
    const dangerList = el.dangerList();
    if (phcBanner) {
      if (activeVisit.phc_referral_needed) {
        phcBanner.classList.remove('hidden');
        if (dangerList) {
          dangerList.replaceChildren();
          const signs =
            activeVisit.danger_signs_detected.length > 0
              ? activeVisit.danger_signs_detected
              : ['Critical maternal/infant symptoms requiring PHC doctor consultation'];
          for (const sign of signs) {
            const li = document.createElement('li');
            li.className = 'flex items-center gap-1.5';
            li.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-white shrink-0"></span><span>${sign}</span>`;
            dangerList.appendChild(li);
          }
        }
      } else {
        phcBanner.classList.add('hidden');
      }
    }

    // Confirmed & Saved Badge
    const confBadge = el.confirmedBadge();
    const draftStatus = el.draftStatusText();
    if (confBadge && draftStatus) {
      if (activeVisit.confirmed) {
        confBadge.classList.remove('hidden');
        draftStatus.classList.add('hidden');
      } else {
        confBadge.classList.add('hidden');
        draftStatus.classList.remove('hidden');
      }
    }
  }

  // --- Save Confirmed Visit to Today's Register ---
  function saveCurrentVisitToRegistry() {
    activeVisit.confirmed = true;
    const storageKey = 'swasthyavaani_saved_visits';
    let savedList = [];
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) savedList = JSON.parse(raw);
    } catch {
      savedList = [];
    }

    // Create entry
    const entry = {
      id: activeVisit.beneficiary_id || `SYN-${Date.now().toString().slice(-4)}`,
      name: activeVisit.beneficiary_name || 'Walk-in Beneficiary',
      visitType: activeVisit.visit_type || 'ANC Checkup',
      weightKg: activeVisit.weight_kg || '—',
      vaccinesGiven: activeVisit.vaccinations_given || [],
      vaccinesDue: activeVisit.vaccinations_due || [],
      vaccines: [
        ...(activeVisit.vaccinations_given || []).map((v) => `${v} [Given]`),
        ...(activeVisit.vaccinations_due || []).map((v) => `${v} [Due]`),
      ],
      nextVisit: activeVisit.next_visit_date || '—',
      danger: activeVisit.phc_referral_needed,
      dangerSigns: activeVisit.danger_signs_detected,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    savedList.unshift(entry);
    localStorage.setItem(storageKey, JSON.stringify(savedList));

    // Update Counter Badges (No arbitrary /8 target)
    const count = savedList.length;
    const visitsCountEl = document.getElementById('dashboard-visits-count');
    const drawerCounterEl = document.getElementById('drawer-saved-visits-counter');
    if (visitsCountEl) visitsCountEl.textContent = String(count);
    if (drawerCounterEl) drawerCounterEl.textContent = `${count} visits recorded today`;

    // Show Toast
    const toast = document.getElementById('sync-success-toast');
    if (toast) {
      const title = document.getElementById('toast-title');
      const sub = document.getElementById('toast-subtitle');
      if (title) title.textContent = `Visit Confirmed: ${entry.name}`;
      if (sub) sub.textContent = `Appended to Today's Saved Visits (Ward 4 Register)`;
      toast.classList.remove('hidden');
      setTimeout(() => {
        toast.classList.add('hidden');
      }, 4500);
    }
  }

  window.confirmAndSaveCurrentVisit = async () => {
    activeVisit.confirmed = true;
    activeVisit.is_frozen = true;
    renderActiveVisitCard(['confirmed']);
    saveCurrentVisitToRegistry();

    // Inform backend if WebSocket is active
    if (activeStreamingSession && activeStreamingSession.ws && activeStreamingSession.ws.readyState === WebSocket.OPEN) {
      activeStreamingSession.sendJson('confirm_record', { beneficiary_id: activeVisit.beneficiary_id });
    }

    // Stop mic and voice loop immediately so AI agent stops and fields stay frozen!
    await endVoiceSession();
    setSessionUIState('idle');
  };

  // --- 1-Click CSV Export for Today's Saved Visits ---
  function escapeCsvCell(value) {
    if (value === undefined || value === null) return '""';
    const str = String(value).replace(/"/g, '""');
    return `"${str}"`;
  }

  function exportVisitsToCSV() {
    const storageKey = 'swasthyavaani_saved_visits';
    let savedList = [];
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) savedList = JSON.parse(raw);
    } catch {
      savedList = [];
    }

    // Default sample entries if list is currently empty
    if (savedList.length === 0) {
      savedList = [
        {
          name: 'Priya Devi',
          id: 'SYN-ASHA-001',
          visitType: 'ANC Checkup',
          weightKg: '54.5',
          vaccines: ['TT-1'],
          nextVisit: '15 December',
          danger: false,
          dangerSigns: [],
          confirmed: true,
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
          dangerSigns: [],
          confirmed: true,
          timestamp: '10:30 AM',
        },
      ];
      localStorage.setItem(storageKey, JSON.stringify(savedList));
    }

    const headers = [
      'Timestamp',
      'Beneficiary Name',
      'Beneficiary ID',
      'Visit Type',
      'Weight (kg)',
      'Vaccinations Due',
      'Next Visit Date',
      'Danger Signs',
      'PHC Referral Needed',
      'Confirmed',
    ];

    const rows = [headers.map(escapeCsvCell).join(',')];

    for (const record of savedList) {
      const timestamp = record.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const name = record.name || record.beneficiary_name || 'Walk-in Beneficiary';
      const id = record.id || record.beneficiary_id || '—';
      const visitType = record.visitType || record.visit_type || 'ANC Checkup';
      const weight = record.weightKg || record.weight_kg || '—';
      const vax = Array.isArray(record.vaccines || record.vaccinations_due)
        ? (record.vaccines || record.vaccinations_due).join('; ')
        : String(record.vaccines || record.vaccinations_due || 'None');
      const nextVisit = record.nextVisit || record.next_visit_date || '—';
      const dangerSigns = Array.isArray(record.dangerSigns || record.danger_signs_detected)
        ? (record.dangerSigns || record.danger_signs_detected).join('; ')
        : String(record.dangerSigns || record.danger_signs_detected || 'None');
      const referral = Boolean(record.danger || record.phc_referral_needed) ? 'YES' : 'NO';
      const confirmed = record.confirmed !== false ? 'YES' : 'NO';

      const rowValues = [
        timestamp,
        name,
        id,
        visitType,
        weight,
        vax,
        nextVisit,
        dangerSigns,
        referral,
        confirmed,
      ];

      rows.push(rowValues.map(escapeCsvCell).join(','));
    }

    const csvContent = rows.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const today = new Date().toISOString().slice(0, 10);
    const filename = `SwasthyaVaani_ASHA_Visits_${today}.csv`;

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    // Show Confirmation Toast
    const toast = document.getElementById('sync-success-toast');
    if (toast) {
      const title = document.getElementById('toast-title');
      const sub = document.getElementById('toast-subtitle');
      if (title) title.textContent = 'Visit log exported as CSV';
      if (sub) sub.textContent = `Downloaded ${filename} (${savedList.length} records)`;
      toast.classList.remove('hidden');
      setTimeout(() => {
        toast.classList.add('hidden');
      }, 4500);
    }
  }

  window.exportVisitsToCSV = exportVisitsToCSV;

  // --- Wake Lock Management ---
  async function acquireWakeLock() {
    try {
      if ('wakeLock' in navigator && navigator.wakeLock) {
        activeWakeLock = await navigator.wakeLock.request('screen');
      }
    } catch (e) {
      console.warn('Screen wakeLock request not granted:', e);
    }
  }

  async function releaseWakeLock() {
    try {
      if (activeWakeLock) {
        await activeWakeLock.release();
        activeWakeLock = null;
      }
    } catch {
      activeWakeLock = null;
    }
  }

  let activeStreamingSession = null;

  // --- SwasthyaVaani Real-Time Streaming Voice Engine (/ws/voice) ---
  async function startStreamingVoiceSession() {
    setSessionUIState('connecting', 'Connecting to SwasthyaVaani voice backend...');

    try {
      if (activeStreamingSession) {
        activeStreamingSession.disconnect();
        activeStreamingSession = null;
      }

      if (!window.AshaAPI) {
        throw new Error('AshaAPI client library not loaded. Ensure /api.js is included.');
      }

      activeStreamingSession = window.AshaAPI.createVoiceSession({
        status: (newStatus) => {
          if (newStatus === 'listening') {
            setSessionUIState('listening', 'Connected to SwasthyaVaani • Listening');
          } else if (newStatus === 'connecting') {
            setSessionUIState('connecting', 'Connecting to streaming engine...');
          } else if (newStatus === 'idle') {
            setSessionUIState('idle');
          } else if (newStatus === 'error') {
            setSessionUIState('error', 'Voice connection error');
          }
        },
        session_ready: (p) => {
          console.log('SwasthyaVaani voice session ready:', p);
        },
        agent_speaking: (p) => {
          setSessionUIState('speaking', 'Agent Speaking (Timbre TTS)...');
          const raw = el.rawNote();
          if (raw && p && p.text) {
            raw.textContent = `“${p.text}”`;
          }
        },
        transcript_partial: (p) => {
          const raw = el.rawNote();
          if (raw && p && p.text) {
            raw.textContent = `“${p.text}…”`;
          }
        },
        transcript_final: (p) => {
          const raw = el.rawNote();
          if (raw && p && p.text) {
            raw.textContent = `“${p.text}”`;
          }
        },
        danger_alert: (p) => {
          applyJsonMergePatch({
            phc_referral_needed: true,
            danger_signs_detected: p.labels && p.labels.length ? p.labels : (p.signs || ['Urgent PHC Referral Required']),
          });
        },
        language_detected: (p) => {
          console.log('Language auto-detected by backend:', p);
          if (p && p.language && typeof window.setAppLanguage === 'function') {
            window.setAppLanguage(p.language);
          }
        },
        record_draft: (p) => {
          if (p && p.record) {
            applyJsonMergePatch(p.record);
          }
        },
        save_blocked: (p) => {
          console.warn('Save blocked by backend safety guard — missing fields:', p);
          const toast = document.getElementById('sync-success-toast');
          if (toast) {
            const title = document.getElementById('toast-title');
            const sub = document.getElementById('toast-subtitle');
            if (title) title.textContent = 'Clinical Record Incomplete';
            if (sub) sub.textContent = p && p.message ? p.message : 'Please provide or declare missing fields before saving.';
            toast.classList.remove('hidden');
            setTimeout(() => toast.classList.add('hidden'), 3500);
          }
        },
        record_confirmed: async (p) => {
          activeVisit.confirmed = true;
          activeVisit.is_frozen = true;
          applyJsonMergePatch(p.record);
          saveCurrentVisitToRegistry();
          renderActiveVisitCard(['confirmed']);

          // Stop mic and voice loop immediately so AI agent stops and fields stay frozen!
          await endVoiceSession();
          setSessionUIState('idle');
        },
        error: (msg) => {
          console.error('Streaming session error:', msg);
          setSessionUIState('error', msg);
        },
      });

      await activeStreamingSession.connect(currentLanguage);

      // Send session_start event per frozen protocol
      activeStreamingSession.sendJson('session_start', {
        language: currentLanguage,
        mode: 'vad',
      });

      // Start mic capture & resampled 16 kHz PCM streaming
      const micOk = await activeStreamingSession.startMic();
      if (!micOk) {
        console.warn('Microphone access not permitted.');
      }

      // Acquire screen wake lock
      await acquireWakeLock();

      setSessionUIState('listening', 'Connected to SwasthyaVaani • Listening');
    } catch (err) {
      console.warn('Direct WebSocket streaming error, checking LiveKit fallback:', err);
      if (window.LivekitClient) {
        try {
          await startLiveKitVoiceSession();
          return;
        } catch (lkErr) {
          console.warn('LiveKit fallback failed:', lkErr);
        }
      }
      setSessionUIState('error', err.message || 'Connection failed');
    }
  }

  // --- LiveKit UMD Client Voice Session Loop (Fallback) ---
  async function startLiveKitVoiceSession() {
    // Extract LivekitClient UMD global
    const Livekit = window.LivekitClient;
    if (!Livekit || !Livekit.Room) {
      console.error('window.LivekitClient UMD is not loaded.');
      setSessionUIState('error', 'LiveKit client library not available');
      return;
    }

    const { Room, RoomEvent, Track } = Livekit;

    setSessionUIState('connecting', 'Requesting session token (?room=asha-demo)...');

    try {
      // 1. Fetch token from /token?room=asha-demo (strictly without beneficiary_id)
      const tokenRes = await fetch('/token?room=asha-demo');
      if (!tokenRes.ok) {
        const errJson = await tokenRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned HTTP ${tokenRes.status}`);
      }
      const tokenData = await tokenRes.json();
      const { url, token } = tokenData;

      if (!url || !token) {
        throw new Error('Incomplete LiveKit credentials returned by /token');
      }

      // 2. Instantiate LiveKit Room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      activeRoom = room;

      // 3. CRITICAL: Mobile Audio Unlock for remote Gnani Timbre TTS playback
      await room.startAudio();

      // 4. Setup Remote Audio Subscription
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio || track.kind === 'audio') {
          const sink = el.audioSink() || document.body;
          track.attach(sink);
        }
      });

      // 5. Setup LiveKit DataReceived event for JSON Merge Patching
      room.on(RoomEvent.DataReceived, (payload) => {
        try {
          let text;
          if (payload instanceof Uint8Array || payload instanceof ArrayBuffer) {
            text = new TextDecoder().decode(payload);
          } else {
            text = String(payload);
          }
          const data = JSON.parse(text);

          // If payload contains speech transcript or agent text
          const rawNoteEl = el.rawNote();
          if (rawNoteEl) {
            if (data.text || data.transcript) {
              rawNoteEl.textContent = `“${data.text || data.transcript}”`;
            } else if (data.agent_speech) {
              rawNoteEl.textContent = `“${data.agent_speech}”`;
            }
          }

          // Apply JSON Merge Patch
          applyJsonMergePatch(data);
        } catch (e) {
          console.warn('Failed to parse incoming LiveKit data packet:', e);
        }
      });

      // 6. Speaking detection (ASHA Worker vs Remote AI Agent)
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (!speakers || speakers.length === 0) {
          setSessionUIState('listening', 'Listening Live • Hands-Free');
          return;
        }

        const isRemoteAgentSpeaking = speakers.some((s) => !s.isLocal);
        if (isRemoteAgentSpeaking) {
          setSessionUIState('speaking', 'Agent Speaking (Timbre TTS)...');
        } else {
          setSessionUIState('listening', 'ASHA Speaking...');
        }
      });

      // 7. Handle Disconnection
      room.on(RoomEvent.Disconnected, () => {
        cleanupVoiceSession();
        setSessionUIState('idle');
      });

      // 8. Connect to room
      await room.connect(url, token);

      // 9. Enable Microphone with required noise filters
      await room.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      });

      // 10. Request Screen Wake Lock
      await acquireWakeLock();

      setSessionUIState('listening', 'Connected to LiveKit • Listening');
    } catch (err) {
      console.error('LiveKit connection error:', err);
      cleanupVoiceSession();
      setSessionUIState('error', err.message || 'Connection failed');
    }
  }

  async function endVoiceSession() {
    if (activeStreamingSession) {
      try {
        activeStreamingSession.disconnect();
      } catch (e) {
        console.warn('Error disconnecting streaming session:', e);
      }
      activeStreamingSession = null;
    }
    if (activeRoom) {
      try {
        await activeRoom.disconnect();
      } catch (e) {
        console.warn('Error disconnecting room:', e);
      }
      activeRoom = null;
    }
    cleanupVoiceSession();
    setSessionUIState('idle');
  }

  function cleanupVoiceSession() {
    activeStreamingSession = null;
    activeRoom = null;
    void releaseWakeLock();
  }

  // --- Voice Record Button Handler ---
  function handleMicButtonClick() {
    if (activeStreamingSession || activeRoom) {
      void endVoiceSession();
    } else {
      resetActiveVisitState();
      void startStreamingVoiceSession();
    }
  }

  // --- Dev / Judge Simulation turns (Strictly shown if ?demo=true) ---
  function runSimulatedTurn(type) {
    let noteText = '';
    if (type === 'normal') {
      noteText = 'Priya Devi ka ANC visit hai, second trimester, weight 55 kilo hai, TT-1 injection diya.';
      applyJsonMergePatch({
        beneficiary_name: 'Priya Devi',
        beneficiary_id: 'SYN-ASHA-001',
        visit_type: 'ANC',
        weight_kg: 55.0,
        vaccinations_given: ['TT-1'],
        next_visit_date: '2026-12-15',
      });
      const raw = el.rawNote();
      if (raw) raw.textContent = `“${noteText}”`;
    } else if (type === 'correction') {
      noteText = 'Nahi, weight 58 kilo tha.';
      applyJsonMergePatch({
        weight_kg: 58.0,
      });
      const raw = el.rawNote();
      if (raw) raw.textContent = `“${noteText}”`;
    } else if (type === 'danger') {
      noteText = 'Priya Devi ko tez bleeding shuru ho gayi hai aur chakkar aa rahe hain.';
      applyJsonMergePatch({
        phc_referral_needed: true,
        danger_signs_detected: ['Severe vaginal bleeding (HRP)', 'Severe dizziness / shock'],
      });
      const raw = el.rawNote();
      if (raw) raw.textContent = `“${noteText}”`;
    } else if (type === 'confirm') {
      noteText = 'Haan theek hai, save karo.';
      applyJsonMergePatch({
        confirmed: true,
      });
      const raw = el.rawNote();
      if (raw) raw.textContent = `“${noteText}”`;
    }

    // When connected to backend WebSocket, send debug turn so real pipeline processes it live
    if (activeStreamingSession && activeStreamingSession.ws && activeStreamingSession.ws.readyState === WebSocket.OPEN && noteText) {
      activeStreamingSession.sendJson('text_turn_debug', { text: noteText });
    }
  }

  // --- Multi-Language UI Translation Engine ---
  const UI_LANGUAGES = {
    'hi-IN': { name: 'हिन्दी', short: 'हिन्दी' },
    'kn-IN': { name: 'ಕನ್ನಡ', short: 'ಕನ್ನಡ' },
    'ta-IN': { name: 'தமிழ்', short: 'தமிழ்' },
    'te-IN': { name: 'తెలుగు', short: 'తెలుగు' },
    'mr-IN': { name: 'मराठी', short: 'मराठी' },
    'bn-IN': { name: 'বাংলা', short: 'বাংলা' },
    'gu-IN': { name: 'ગુજરાતી', short: 'ગુજરાતી' },
    'pa-IN': { name: 'ਪੰਜਾਬੀ', short: 'ਪੰਜਾਬੀ' },
    'ml-IN': { name: 'മലയാളം', short: 'മലയാളം' },
    'en-IN': { name: 'English', short: 'EN' },
  };

  const UI_TRANSLATIONS = {
    'en-IN': {
      app_subtitle: 'Voice Field Register • PS1',
      asha_greeting: 'ASHA Kavita • Ward 4',
      location_shivajinagar: 'Shivajinagar',
      households_count: '42 Households',
      visits_label: 'Visits',
      tap_to_speak: 'Tap to Speak',
      hero_maternal_title: 'Maternal & Child Care (ANC/PNC)',
      hero_immu_title: 'Immunization Tracking',
      emergency_108_title: 'Emergency Ambulance (108)',
      emergency_108_sub: 'Immediate maternal & pediatric emergency dispatch',
      dial_btn: 'Dial',
      drawer_saved_title: "Today's Saved Visits",
      drawer_voice_lang_title: 'Voice Language',
      drawer_voice_lang_desc: 'AI assistant will speak and transcribe in this language.',
      drawer_ui_lang_title: 'UI Display Language',
      drawer_ui_lang_desc: 'All labels, buttons, and cards will display in this language.',
      drawer_login_title: 'ASHA Worker Login',
      login_modal_title: 'ASHA Worker Profile Login',
      label_worker_name: 'Worker Name',
      label_worker_id: 'Worker ID',
      label_ward_area: 'Assigned Ward / Village',
      btn_cancel: 'Cancel',
      btn_save_profile: 'Save & Login',
      new_record_btn: 'New Record',
      modal_title: 'Tap to Speak',
      modal_subtitle: 'Speak naturally in your mother tongue or Hindi-English mix.',
      example_cue_maternal: '💬 <strong>Say:</strong> &ldquo;Sunita Devi, ID 104, ANC checkup, weight 54.5 kilo, TT injection given, next visit 15 December&rdquo;',
      example_cue_immu: '💬 <strong>Say:</strong> &ldquo;Baby Aarav, ID 208, BCG vaccine, weight 6.2 kilo, next visit 10 January&rdquo;',
      tap_to_talk: 'Tap to Talk',
      listening: 'Listening...',
      agent_speaking: 'Agent Speaking...',
      tap_to_end: 'Tap to End',
      status_ready: 'Ready to Listen',
      live_transcript_heading: 'Live Voice Transcript / AI Read-back',
      phc_alert_title: 'Urgent PHC Referral Required',
      phc_alert_text: 'Danger signs detected! Refer beneficiary immediately to the Primary Health Centre (PHC).',
      live_card_title: 'Live Visit Record',
      extracting_badge: 'Extracting from speech',
      confirmed_badge: 'Confirmed & Saved',
      field_beneficiary: 'Beneficiary Name / ID',
      listening_placeholder: 'Listening for beneficiary name / ID...',
      field_visit_type: 'Visit Type',
      field_weight: 'Weight (kg)',
      field_vaccinations: 'Vaccinations Due / Given',
      field_vaccines_given: 'Vaccines Given',
      field_vaccines_due: 'Vaccines Due',
      none_recorded: 'None recorded',
      field_next_date: 'Next Scheduled Date',
      confirm_save_btn: 'Confirm & Save',
      dept_maternal: 'Maternal & Child Care • Ward 4',
      dept_immu: 'Immunization Tracking • Ward 4 (Fixed)',
    },
    'hi-IN': {
      app_subtitle: 'आवाज़ फ़ील्ड रजिस्टर • PS1',
      asha_greeting: 'आशा कविता • वार्ड 4',
      location_shivajinagar: 'शिवाजीनगर',
      households_count: '42 परिवार',
      visits_label: 'विज़िट्स',
      tap_to_speak: 'बोलने के लिए टैप करें',
      hero_maternal_title: 'मातृ एवं शिशु देखभाल (ANC/PNC)',
      hero_immu_title: 'टीकाकरण ट्रैकिंग (Immunization)',
      emergency_108_title: 'आपातकालीन एम्बुलेंस (108)',
      emergency_108_sub: 'तत्काल मातृ एवं शिशु आपातकालीन सेवा',
      dial_btn: 'कॉल',
      drawer_saved_title: 'आज के सहेजे गए विज़िट',
      drawer_voice_lang_title: 'आवाज़ की भाषा',
      drawer_voice_lang_desc: 'एआई सहायक इस भाषा में बोलेगा और सुनेगा।',
      drawer_ui_lang_title: 'ऐप डिस्प्ले भाषा',
      drawer_ui_lang_desc: 'सभी लेबल, बटन और कार्ड इस भाषा में दिखाई देंगे।',
      drawer_login_title: 'आशा कार्यकर्ता लॉगिन',
      login_modal_title: 'आशा कार्यकर्ता प्रोफ़ाइल लॉगिन',
      label_worker_name: 'कार्यकर्ता का नाम',
      label_worker_id: 'कार्यकर्ता पहचान (ID)',
      label_ward_area: 'वार्ड / गाँव',
      btn_cancel: 'रद्द करें',
      btn_save_profile: 'सहेजें और लॉगिन करें',
      new_record_btn: 'नया रिकॉर्ड',
      modal_title: 'बोलने के लिए टैप करें',
      modal_subtitle: 'अपनी मातृभाषा या हिन्दी-अंग्रेजी मिक्स में सहजता से बोलें।',
      example_cue_maternal: '💬 <strong>कहें:</strong> &ldquo;सुनीता देवी, पहचान 104, एएनसी चेकअप, वजन 54.5 किलो, टीटी टीका दिया, अगली विज़िट 15 दिसंबर&rdquo;',
      example_cue_immu: '💬 <strong>कहें:</strong> &ldquo;बच्चा आरव, पहचान 208, बीसीजी टीका दिया, वजन 6.2 किलो, अगली विज़िट 10 जनवरी&rdquo;',
      tap_to_talk: 'बोलने के लिए टैप करें',
      listening: 'सुन रहे हैं...',
      agent_speaking: 'सहायक बोल रहा है...',
      tap_to_end: 'समाप्त करने के लिए टैप करें',
      status_ready: 'सुनने के लिए तैयार',
      live_transcript_heading: 'लाइव वॉइस ट्रांसक्रिप्ट / एआई पुष्टिकरण',
      phc_alert_title: 'तत्काल पीएचसी रेफरल आवश्यक',
      phc_alert_text: 'खतरे के लक्षण मिले! लाभार्थी को तुरंत प्राथमिक स्वास्थ्य केंद्र (PHC) रेफर करें।',
      live_card_title: 'लाइव विज़िट रिकॉर्ड',
      extracting_badge: 'आवाज़ से विवरण निकाला जा रहा है',
      confirmed_badge: 'पुष्ट और सहेजा गया',
      field_beneficiary: 'लाभार्थी का नाम / पहचान संख्या',
      listening_placeholder: 'लाभार्थी का नाम या पहचान संख्या सुन रहे हैं...',
      field_visit_type: 'विज़िट का प्रकार',
      field_weight: 'वजन (किग्रा)',
      field_vaccinations: 'नियत / दिए गए टीके',
      field_vaccines_given: 'दिए गए टीके',
      field_vaccines_due: 'बाकी / नियत टीके',
      none_recorded: 'कोई दर्ज नहीं',
      field_next_date: 'अगली नियत तिथि',
      confirm_save_btn: 'पुष्टि करें और सहेजें',
      dept_maternal: 'मातृ एवं शिशु देखभाल • वार्ड 4',
      dept_immu: 'टीकाकरण ट्रैकिंग • वार्ड 4 (अनिवार्य)',
    },
    'kn-IN': {
      app_subtitle: 'ಧ್ವನಿ ಫೀಲ್ಡ್ ರಿಜಿಸ್ಟರ್ • PS1',
      asha_greeting: 'ಆಶಾ ಕವಿತಾ • ವಾರ್ಡ್ 4',
      location_shivajinagar: 'ಶಿವಾಜಿನಗರ',
      households_count: '42 ಕುಟುಂಬಗಳು',
      visits_label: 'ಭೇಟಿಗಳು',
      tap_to_speak: 'ಮಾತನಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
      hero_maternal_title: 'ತಾಯಿ ಮತ್ತು ಮಗುವಿನ ಆರೈಕೆ (ANC/PNC)',
      hero_immu_title: 'ಲಸಿಕೆ ಟ್ರ್ಯಾಕಿಂಗ್ (Immunization)',
      emergency_108_title: 'ತುರ್ತು ಆಂಬ್ಯುಲೆನ್ಸ್ (108)',
      emergency_108_sub: 'ತುರ್ತು ತಾಯಿ ಮತ್ತು ಮಕ್ಕಳ ಸೇವೆ',
      dial_btn: 'ಕರೆ',
      drawer_saved_title: 'ಇಂದಿನ ಉಳಿಸಿದ ಭೇಟಿಗಳು',
      drawer_voice_lang_title: 'ಧ್ವನಿ ಭಾಷೆ',
      drawer_voice_lang_desc: 'AI ಸಹಾಯಕ ಈ ಭಾಷೆಯಲ್ಲಿ ಮಾತನಾಡುತ್ತದೆ.',
      drawer_ui_lang_title: 'ಅಪ್ಲಿಕೇಶನ್ ಭಾಷೆ',
      drawer_ui_lang_desc: 'ಎಲ್ಲಾ ಬಟನ್‌ಗಳು ಮತ್ತು ಕಾರ್ಡ್‌ಗಳು ಈ ಭಾಷೆಯಲ್ಲಿ ಕಾಣಿಸುತ್ತವೆ.',
      drawer_login_title: 'ಆಶಾ ಕಾರ್ಯಕರ್ತೆ ಲಾಗಿನ್',
      login_modal_title: 'ಆಶಾ ಕಾರ್ಯಕರ್ತೆ ಪ್ರೊಫೈಲ್ ಲಾಗಿನ್',
      label_worker_name: 'ಕಾರ್ಯಕರ್ತೆಯ ಹೆಸರು',
      label_worker_id: 'ಕಾರ್ಯಕರ್ತೆ ಐಡಿ',
      label_ward_area: 'ನಿಗದಿಪಡಿಸಿದ ವಾರ್ಡ್ / ಗ್ರಾಮ',
      btn_cancel: 'ರದ್ದುಮಾಡಿ',
      btn_save_profile: 'ಉಳಿಸಿ ಮತ್ತು ಲಾಗಿನ್ ಮಾಡಿ',
      new_record_btn: 'ಹೊಸ ದಾಖಲೆ',
      modal_title: 'ಮಾತನಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
      modal_subtitle: 'ನಿಮ್ಮ ಮಾತೃಭಾಷೆ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಮುಕ್ತವಾಗಿ ಮಾತನಾಡಿ.',
      example_cue_maternal: '💬 <strong>ಹೇಳಿ:</strong> &ldquo;ಸುನೀತಾ ದೇವಿ, ಐಡಿ 104, ANC ತಪಾಸಣೆ, ತೂಕ 54.5 ಕೆಜಿ, ಮುಂದಿನ ಭೇಟಿ 15 ಡಿಸೆಂಬರ್&rdquo;',
      example_cue_immu: '💬 <strong>ಹೇಳಿ:</strong> &ldquo;ಮಗು ಆರವ್, ಐಡಿ 208, ಬಿಸಿಜಿ ಲಸಿಕೆ, ತೂಕ 6.2 ಕೆಜಿ, ಮುಂದಿನ ಭೇಟಿ 10 ಜನವರಿ&rdquo;',
      tap_to_talk: 'ಮಾತನಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
      listening: 'ಆಲಿಸಲಾಗುತ್ತಿದೆ...',
      agent_speaking: 'ಸಹಾಯಕ ಮಾತನಾಡುತ್ತಿದ್ದಾನೆ...',
      tap_to_end: 'ಮುಗಿಸಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
      status_ready: 'ಆಲಿಸಲು ಸಿದ್ಧ',
      live_transcript_heading: 'ಲೈವ್ ಧ್ವನಿ ಲಿಪ್ಯಂತರ / AI ದೃಢೀಕರಣ',
      phc_alert_title: 'ತಕ್ಷಣ PHC ಗೆ ಕಳುಹಿಸಿ',
      phc_alert_text: 'ಅಪಾಯಕಾರಿ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ! ತಕ್ಷಣ ಹತ್ತಿರದ PHC ಗೆ ರವಾನಿಸಿ.',
      live_card_title: 'ಲೈವ್ ಭೇಟಿ ದಾಖಲೆ',
      extracting_badge: 'ಧ್ವನಿಯಿಂದ ವಿವರ ಪಡೆಯಲಾಗುತ್ತಿದೆ',
      confirmed_badge: 'ದೃಢೀಕರಿಸಿ ಉಳಿಸಲಾಗಿದೆ',
      field_beneficiary: 'ಫಲಾನುಭವಿ ಹೆಸರು / ಐಡಿ',
      listening_placeholder: 'ಫಲಾನುಭವಿ ಹೆಸರು/ಐಡಿಗಾಗಿ ಆಲಿಸಲಾಗುತ್ತಿದೆ...',
      field_visit_type: 'ಭೇಟಿಯ ವಿಧ',
      field_weight: 'ತೂಕ (ಕೆಜಿ)',
      field_vaccinations: 'ನೀಡಿದ ಲಸಿಕೆಗಳು',
      field_vaccines_given: 'ನೀಡಿದ ಲಸಿಕೆಗಳು',
      field_vaccines_due: 'ಬಾಕಿ ಇರುವ ಲಸಿಕೆಗಳು',
      none_recorded: 'ಯಾವುದೂ ದಾಖಲಾಗಿಲ್ಲ',
      field_next_date: 'ಮುಂದಿನ ನಿಗದಿತ ದಿನಾಂಕ',
      confirm_save_btn: 'ದೃಢೀಕರಿಸಿ ಮತ್ತು ಉಳಿಸಿ',
      dept_maternal: 'ತಾಯಿ ಮತ್ತು ಮಗುವಿನ ಆರೈಕೆ • ವಾರ್ಡ್ 4',
      dept_immu: 'ಲಸಿಕೆ ಟ್ರ್ಯಾಕಿಂಗ್ • ವಾರ್ಡ್ 4 (ಸ್ಥಿರ)',
    },
    'ta-IN': {
      app_subtitle: 'குரல் களப் பதிவேடு • PS1',
      asha_greeting: 'ஆஷா கவிதா • வார்டு 4',
      location_shivajinagar: 'சிவாஜிநகர்',
      households_count: '42 குடும்பங்கள்',
      visits_label: 'பார்வைகள்',
      tap_to_speak: 'பேச தட்டவும்',
      hero_maternal_title: 'தாய் மற்றும் சேய் பராமரிப்பு (ANC/PNC)',
      hero_immu_title: 'தடுப்பூசி கண்காணிப்பு (Immunization)',
      emergency_108_title: 'அவசர ஆம்புலன்ஸ் (108)',
      emergency_108_sub: 'உடனடி அவசர சிகிச்சை சேவை',
      dial_btn: 'அழை',
      drawer_saved_title: 'இன்றைய சேமிக்கப்பட்ட பதிவுகள்',
      drawer_voice_lang_title: 'குரல் மொழி',
      drawer_voice_lang_desc: 'AI உதவியாளர் இந்த மொழியில் பேசும்.',
      drawer_ui_lang_title: 'பயன்பாட்டு மொழி',
      drawer_ui_lang_desc: 'அனைத்து லேபிள்களும் இந்த மொழியில் தோன்றும்.',
      drawer_login_title: 'ஆஷா பணியாளர் உள்நுழைவு',
      login_modal_title: 'ஆஷா பணியாளர் சுயவிவரம்',
      label_worker_name: 'பணியாளர் பெயர்',
      label_worker_id: 'பணியாளர் ஐடி',
      label_ward_area: 'வார்டு / கிராமம்',
      btn_cancel: 'ரத்து செய்',
      btn_save_profile: 'சேமித்து உள்நுழையவும்',
      new_record_btn: 'புதிய பதிவு',
      modal_title: 'பேச தட்டவும்',
      modal_subtitle: 'உங்கள் தாய்மொழியில் அல்லது தமிழில் இயல்பாக பேசுங்கள்.',
      example_cue_maternal: '💬 <strong>கூறுங்கள்:</strong> &ldquo;சுனிதா தேவி, ஐடி 104, ANC பரிசோதனை, எடை 54.5 கிலோ...&rdquo;',
      example_cue_immu: '💬 <strong>கூறுங்கள்:</strong> &ldquo;குழந்தை ஆரவ், ஐடி 208, பிசிஜி தடுப்பூசி, எடை 6.2 கிலோ...&rdquo;',
      tap_to_talk: 'பேச தட்டவும்',
      listening: 'கேட்கிறது...',
      agent_speaking: 'உதவியாளர் பேசுகிறார்...',
      tap_to_end: 'முடிக்க தட்டவும்',
      status_ready: 'கேட்க தயார்',
      live_transcript_heading: 'நேரடி உரை / AI வாசிப்பு',
      phc_alert_title: 'உடனடி PHC பரிந்துரை தேவை',
      phc_alert_text: 'ஆபத்து அறிகுறிகள் கண்டறியப்பட்டன! உடனடியாக PHC-க்கு அனுப்பவும்.',
      live_card_title: 'நேரடி பார்வை பதிவு',
      extracting_badge: 'குரலிலிருந்து பிரித்தெடுக்கப்படுகிறது',
      confirmed_badge: 'உறுதி செய்யப்பட்டு சேமிக்கப்பட்டது',
      field_beneficiary: 'பயனாளி பெயர் / ஐடி',
      listening_placeholder: 'பயனாளி பெயரை கேட்கிறது...',
      field_visit_type: 'பார்வை வகை',
      field_weight: 'எடை (கிலோ)',
      field_vaccinations: 'தடுப்பூசிகள்',
      field_vaccines_given: 'போடப்பட்ட தடுப்பூசிகள்',
      field_vaccines_due: 'நிலுவையிலுள்ள தடுப்பூசிகள்',
      none_recorded: 'பதிவு செய்யப்படவில்லை',
      field_next_date: 'அடுத்த தேதி',
      confirm_save_btn: 'உறுதி செய்து சேமி',
      dept_maternal: 'தாய் & சேய் பராமரிப்பு • வார்டு 4',
      dept_immu: 'தடுப்பூசி கண்காணிப்பு • வார்டு 4',
    },
    'te-IN': {
      app_subtitle: 'వాయిస్ ఫీల్డ్ రిజిస్టర్ • PS1',
      asha_greeting: 'ఆశా కవిత • వార్డు 4',
      location_shivajinagar: 'శివాజీనగర్',
      households_count: '42 గృహాలు',
      visits_label: 'సందర్శనలు',
      tap_to_speak: 'మాట్లాడటానికి నొక్కండి',
      hero_maternal_title: 'తల్లీ పిల్లల సంరక్షణ (ANC/PNC)',
      hero_immu_title: 'టీకా ట్రాకింగ్ (Immunization)',
      emergency_108_title: 'అత్యవసర అంబులెన్స్ (108)',
      emergency_108_sub: 'తక్షణ అత్యవసర సహాయం',
      dial_btn: 'కాల్',
      drawer_saved_title: 'ఈరోజు సేవ్ చేసిన సందర్శనలు',
      drawer_voice_lang_title: 'వాయిస్ భాష',
      drawer_voice_lang_desc: 'AI సహాయకుడు ఈ భాషలో మాట్లాడుతుంది.',
      drawer_ui_lang_title: 'యాప్ డిస్ప్లే భాష',
      drawer_ui_lang_desc: 'అన్ని లేబుల్స్ ఈ భాషలో కనిపిస్తాయి.',
      drawer_login_title: 'ఆశా కార్యకర్త లాగిన్',
      login_modal_title: 'ఆశా కార్యకర్త ప్రొఫైల్ లాగిన్',
      label_worker_name: 'కార్యకర్త పేరు',
      label_worker_id: 'కార్యకర్త ఐడీ',
      label_ward_area: 'వార్డు / గ్రామం',
      btn_cancel: 'రద్దు చేయి',
      btn_save_profile: 'సేవ్ చేసి లాగిన్ చేయండి',
      new_record_btn: 'కొత్త రికార్డు',
      modal_title: 'మాట్లాడటానికి నొక్కండి',
      modal_subtitle: 'మీ మాతృభాషలో సహజంగా మాట్లాడండి.',
      example_cue_maternal: '💬 <strong>చెప్పండి:</strong> &ldquo;సునీత దేవి, ఐడీ 104, ANC చెకప్, బరువు 54.5 కిలోలు...&rdquo;',
      example_cue_immu: '💬 <strong>చెప్పండి:</strong> &ldquo;బాబు ఆరవ్, ఐడీ 208, బీసీజీ టీకా, బరువు 6.2 కిలోలు...&rdquo;',
      tap_to_talk: 'మాట్లాడటానికి నొక్కండి',
      listening: 'వింటోంది...',
      agent_speaking: 'సహాయకుడు మాట్లాడుతున్నారు...',
      tap_to_end: 'ముగించడానికి నొక్కండి',
      status_ready: 'వినడానికి సిద్ధంగా ఉంది',
      live_transcript_heading: 'లైవ్ వాయిస్ ట్రాన్స్‌క్రిప్ట్ / AI నిర్ధారణ',
      phc_alert_title: 'తక్షణమే PHC కి రెఫర్ చేయండి',
      phc_alert_text: 'ప్రమాద సంకేతాలు గుర్తించబడ్డాయి! వెంటనే సమీప PHC కి తరలించండి.',
      live_card_title: 'లైవ్ విజిట్ రికార్డు',
      extracting_badge: 'వాయిస్ నుండి సేకరిస్తోంది',
      confirmed_badge: 'ధృవీకరించి భద్రపరచబడింది',
      field_beneficiary: 'లబ్ధిదారుని పేరు / ఐడీ',
      listening_placeholder: 'లబ్ధిదారుని పేరు కోసం వింటోంది...',
      field_visit_type: 'విజిట్ రకం',
      field_weight: 'బరువు (కిలోలు)',
      field_vaccinations: 'టీకాలు',
      field_vaccines_given: 'ఇచ్చిన టీకాలు',
      field_vaccines_due: 'బాకీ ఉన్న టీకాలు',
      none_recorded: 'ఏమీ నమోదు కాలేదు',
      field_next_date: 'తదుపరి తేదీ',
      confirm_save_btn: 'నిర్ధారించి సేవ్ చేయండి',
      dept_maternal: 'తల్లీ పిల్లల సంరక్షణ • వార్డు 4',
      dept_immu: 'టీకా ట్రాకింగ్ • వార్డు 4',
    },
    'mr-IN': {
      app_subtitle: 'व्हॉइस फील्ड रजिस्टर • PS1',
      asha_greeting: 'आशा कविता • वॉर्ड 4',
      location_shivajinagar: 'शिवाजीनगर',
      households_count: '42 कुटुंबे',
      visits_label: 'भेटी',
      tap_to_speak: 'बोलण्यासाठी टॅप करा',
      hero_maternal_title: 'माता व बाल संगोपन (ANC/PNC)',
      hero_immu_title: 'लसीकरण ट्रॅकिंग (Immunization)',
      emergency_108_title: 'तातडीची रुग्णवाहिका (108)',
      emergency_108_sub: 'तातडीची वैद्यकीय मदत',
      dial_btn: 'कॉल',
      drawer_saved_title: 'आजच्या नोंदवलेल्या भेटी',
      drawer_voice_lang_title: 'आवाजाची भाषा',
      drawer_voice_lang_desc: 'AI सहाय्यक या भाषेत बोलेल आणि ऐकेल.',
      drawer_ui_lang_title: 'अ‍ॅप भाषा',
      drawer_ui_lang_desc: 'सर्व माहिती या भाषेत दिसेल.',
      drawer_login_title: 'आशा सेविका लॉगिन',
      login_modal_title: 'आशा सेविका प्रोफाइल लॉगिन',
      label_worker_name: 'सेविकेचे नाव',
      label_worker_id: 'सेविका आयडी',
      label_ward_area: 'नेमून दिलेला वॉर्ड / गाव',
      btn_cancel: 'रद्द करा',
      btn_save_profile: 'जतन करा आणि लॉगिन करा',
      new_record_btn: 'नवीन नोंद',
      modal_title: 'बोलण्यासाठी टॅप करा',
      modal_subtitle: 'मराठी किंवा तुमच्या भाषेत सहज बोला.',
      example_cue_maternal: '💬 <strong>बोला:</strong> &ldquo;सुनीता देवी, आयडी 104, वजन 54.5 किलो, टीटी लस दिली...&rdquo;',
      example_cue_immu: '💬 <strong>बोला:</strong> &ldquo;बाळ आरव, आयडी 208, बीसीजी लस, वजन 6.2 किलो...&rdquo;',
      tap_to_talk: 'बोलण्यासाठी टॅप करा',
      listening: 'ऐकत आहे...',
      agent_speaking: 'सहाय्यक बोलत आहे...',
      tap_to_end: 'थांबवण्यासाठी टॅप करा',
      status_ready: 'ऐकण्यासाठी सज्ज',
      live_transcript_heading: 'थेट व्हॉइस ट्रान्सक्रिप्ट / AI वाचन',
      phc_alert_title: 'तातडीने PHC ला पाठवा',
      phc_alert_text: 'धोक्याची लक्षणे आढळली! रुग्णाला तातडीने PHC मध्ये पाठवा.',
      live_card_title: 'थेट भेट नोंद',
      extracting_badge: 'माहिती काढत आहे',
      confirmed_badge: 'नोंदवून जतन केले',
      field_beneficiary: 'लाभार्थी नाव / आयडी',
      listening_placeholder: 'लाभार्थ्याचे नाव ऐकत आहे...',
      field_visit_type: 'भेटीचा प्रकार',
      field_weight: 'वजन (किलो)',
      field_vaccinations: 'दिलेल्या लसी',
      field_vaccines_given: 'दिलेल्या लसी',
      field_vaccines_due: 'बाकी / आवश्यक लसी',
      none_recorded: 'नोंद नाही',
      field_next_date: 'पुढील तारीख',
      confirm_save_btn: 'पुष्टी करा आणि जतन करा',
      dept_maternal: 'माता व बाल संगोपन • वॉर्ड 4',
      dept_immu: 'लसीकरण ट्रॅकिंग • वॉर्ड 4',
    },
  };

  function getI18n(key, lang) {
    const active = lang || currentUILanguage || 'en-IN';
    const dict = UI_TRANSLATIONS[active] || UI_TRANSLATIONS['en-IN'] || UI_TRANSLATIONS['hi-IN'];
    return dict[key] || (UI_TRANSLATIONS['en-IN'] ? UI_TRANSLATIONS['en-IN'][key] : key);
  }

  function applyTranslations(lang) {
    currentUILanguage = lang;
    localStorage.setItem('swasthyavaani_ui_lang', lang);

    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (key) {
        const trans = getI18n(key, lang);
        if (trans) {
          if (key.startsWith('example_cue') || key === 'phc_alert_text') {
            el.innerHTML = trans;
          } else {
            el.textContent = trans;
          }
        }
      }
    });

    // Update Header Language Pill Label
    const headerLabel = document.getElementById('header-lang-label');
    if (headerLabel) {
      const info = UI_LANGUAGES[lang] || { short: lang };
      headerLabel.textContent = info.short;
    }

    // Sync Dropdown Selectors
    const uiSelect = document.getElementById('ui-language-select');
    if (uiSelect) uiSelect.value = lang;

    const voiceSelect = document.getElementById('voice-language-select');
    if (voiceSelect) voiceSelect.value = lang;
  }

  window.toggleHeaderLangMenu = () => {
    const menu = document.getElementById('header-lang-menu');
    if (menu) menu.classList.toggle('hidden');
  };

  window.setAppLanguage = (langCode) => {
    applyTranslations(langCode);
    currentLanguage = langCode;
    localStorage.setItem('swasthyavaani_voice_lang', langCode);

    // Close header menu
    const menu = document.getElementById('header-lang-menu');
    if (menu) menu.classList.add('hidden');

    // Notify active streaming backend of language change
    if (activeStreamingSession && activeStreamingSession.ws && activeStreamingSession.ws.readyState === WebSocket.OPEN) {
      activeStreamingSession.sendJson('language_change', { language: langCode });
    }
  };

  // --- Modal Open / Close Controller ---
  window.openVoiceModalForDept = (deptKey) => {
    const modal = document.getElementById('voice-department-modal');
    const sheet = document.getElementById('voice-modal-sheet');
    const badge = document.getElementById('modal-badge-dept');
    const badgeIcon = document.getElementById('modal-badge-icon');
    const cue = document.getElementById('spoken-example-cue-text');

    const isImmu = (deptKey === 'immunization');
    if (badge) {
      badge.textContent = isImmu ? getI18n('dept_immu') : getI18n('dept_maternal');
    }
    if (badgeIcon) {
      badgeIcon.textContent = isImmu ? '💉' : '🌱';
    }
    if (cue) {
      cue.innerHTML = isImmu ? getI18n('example_cue_immu') : getI18n('example_cue_maternal');
    }

    if (modal && sheet) {
      modal.classList.remove('pointer-events-none', 'opacity-0', 'invisible');
      modal.classList.add('opacity-100');
      sheet.classList.remove('translate-y-full', 'pointer-events-none');
      sheet.classList.add('translate-y-0', 'pointer-events-auto');
    }
    document.documentElement.classList.add('modal-scroll-lock');
  };

  window.closeVoiceModal = () => {
    const modal = document.getElementById('voice-department-modal');
    const sheet = document.getElementById('voice-modal-sheet');
    if (modal && sheet) {
      modal.classList.remove('opacity-100');
      modal.classList.add('opacity-0', 'pointer-events-none', 'invisible');
      sheet.classList.remove('translate-y-0', 'pointer-events-auto');
      sheet.classList.add('translate-y-full', 'pointer-events-none');
    }
    document.documentElement.classList.remove('modal-scroll-lock');
  };

  // --- Navigation Drawer Controller ---
  window.toggleNavMenu = (open) => {
    const drawer = document.getElementById('nav-menu-drawer');
    const panel = document.getElementById('nav-menu-panel');
    if (!drawer || !panel) return;
    if (open) {
      drawer.classList.remove('pointer-events-none', 'opacity-0', 'invisible');
      drawer.classList.add('opacity-100');
      panel.classList.remove('translate-x-full');
      panel.classList.add('translate-x-0');
      document.documentElement.classList.add('modal-scroll-lock');
    } else {
      drawer.classList.remove('opacity-100');
      drawer.classList.add('opacity-0', 'pointer-events-none', 'invisible');
      panel.classList.remove('translate-x-0');
      panel.classList.add('translate-x-full');
      document.documentElement.classList.remove('modal-scroll-lock');
    }
  };

  // --- Direct Full-Card Hero Voice Trigger ---
  async function triggerVoiceFromHeroCard(dept, visitHint) {
    // 1. Open the live voice visit sheet with department context
    window.openVoiceModalForDept(dept);

    // 2. Fresh state reset with department hint & new dynamic ID
    const hint = visitHint || (dept === 'immunization' ? 'Immunization' : 'ANC / Maternal Care');
    resetActiveVisitState(hint);

    // 3. Automatically start streaming voice session directly to SwasthyaVaani backend
    if (!activeStreamingSession && !activeRoom) {
      await startStreamingVoiceSession();
    }
  }

  // --- ASHA Worker Login Controller ---
  window.openLoginModal = () => {
    const modal = document.getElementById('asha-login-modal');
    if (!modal) return;
    let profile = { name: 'Kavita', id: 'ASHA-KN-408', ward: 'Ward 4' };
    try {
      const stored = localStorage.getItem('swasthyavaani_worker_profile');
      if (stored) profile = JSON.parse(stored);
    } catch (e) {}
    const nameInp = document.getElementById('login-worker-name');
    const idInp = document.getElementById('login-worker-id');
    const wardInp = document.getElementById('login-ward-area');
    if (nameInp) nameInp.value = profile.name || '';
    if (idInp) idInp.value = profile.id || '';
    if (wardInp) wardInp.value = profile.ward || '';

    modal.classList.remove('pointer-events-none', 'opacity-0', 'invisible');
    modal.classList.add('opacity-100');
    document.documentElement.classList.add('modal-scroll-lock');
  };

  window.closeLoginModal = () => {
    const modal = document.getElementById('asha-login-modal');
    if (!modal) return;
    modal.classList.remove('opacity-100');
    modal.classList.add('opacity-0', 'pointer-events-none', 'invisible');
    document.documentElement.classList.remove('modal-scroll-lock');
  };

  window.handleAshaLogin = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const nameInp = document.getElementById('login-worker-name');
    const idInp = document.getElementById('login-worker-id');
    const wardInp = document.getElementById('login-ward-area');

    const name = (nameInp && nameInp.value.trim()) || 'Kavita';
    const id = (idInp && idInp.value.trim()) || 'ASHA-KN-408';
    const ward = (wardInp && wardInp.value.trim()) || 'Ward 4';

    const profile = { name, id, ward };
    localStorage.setItem('swasthyavaani_worker_profile', JSON.stringify(profile));

    applyWorkerProfile(profile);
    window.closeLoginModal();

    // Show toast
    const toast = document.getElementById('sync-success-toast');
    if (toast) {
      const title = document.getElementById('toast-title');
      const sub = document.getElementById('toast-subtitle');
      if (title) title.textContent = 'Profile Updated';
      if (sub) sub.textContent = `Logged in as ${name} (${id})`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 2500);
    }
  };

  function applyWorkerProfile(profile) {
    const greetingEl = document.getElementById('asha-header-greeting');
    const subtextEl = document.getElementById('drawer-login-subtext');
    if (greetingEl) {
      greetingEl.textContent = `ASHA ${profile.name} • ${profile.ward}`;
    }
    if (subtextEl) {
      subtextEl.textContent = `${profile.name} (${profile.id}) • Switch`;
    }
  }

  // --- Large Field Readability Mode (Preserved safely) ---
  function applyLargeTextMode(enabled) {
    document.documentElement.setAttribute('data-large-text', String(enabled));
    if (enabled) {
      document.body.classList.add('large-text-mode');
    } else {
      document.body.classList.remove('large-text-mode');
    }
    localStorage.setItem('swasthyavaani_large_text', String(enabled));
  }

  // --- Initialization ---
  function init() {
    // 0. Initialize UI Language Translation
    applyTranslations(currentUILanguage);

    // 0b. Restore ASHA Worker Profile
    let profile = { name: 'Kavita', id: 'ASHA-KN-408', ward: 'Ward 4' };
    try {
      const stored = localStorage.getItem('swasthyavaani_worker_profile');
      if (stored) profile = JSON.parse(stored);
    } catch (e) {}
    applyWorkerProfile(profile);

    const loginForm = document.getElementById('asha-login-form');
    if (loginForm) {
      loginForm.addEventListener('submit', window.handleAshaLogin);
    }

    // Close header language menu when clicking outside
    document.addEventListener('click', (e) => {
      const btn = document.getElementById('header-lang-btn');
      const menu = document.getElementById('header-lang-menu');
      if (menu && !menu.classList.contains('hidden')) {
        if (btn && !btn.contains(e.target) && !menu.contains(e.target)) {
          menu.classList.add('hidden');
        }
      }
    });

    // 1. Probe SwasthyaVaani backend connection health on startup
    if (window.AshaAPI) {
      window.AshaAPI.checkHealth().then((health) => {
        if (health.ok) {
          console.log('SwasthyaVaani backend connected at', window.AshaAPI.BASE_URL);
          setSessionUIState('idle');
        } else {
          console.warn('Backend not reachable:', health.error);
          setSessionUIState('error', `Cannot connect to backend at ${window.AshaAPI.BASE_URL}`);
        }
      }).catch((e) => {
        console.warn('Health check error:', e);
      });
    } else {
      setSessionUIState('idle');
    }

    // 2. Bind single glowing Tap to Talk mic circle button
    const micBtn = document.getElementById('voice-record-btn');
    if (micBtn) {
      micBtn.addEventListener('click', handleMicButtonClick);
    }

    // 3. Bind Hero Cards as Direct Full-Card Voice Triggers (Zero Clutter, 1-Tap Start)
    const maternalCard = document.getElementById('hero-card-maternal');
    if (maternalCard) {
      const handleMaternal = () => {
        void triggerVoiceFromHeroCard('maternal', 'ANC / Maternal Care');
      };
      maternalCard.addEventListener('click', handleMaternal);
      maternalCard.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleMaternal();
        }
      });
    }

    const immunizationCard = document.getElementById('hero-card-immunization');
    if (immunizationCard) {
      const handleImm = () => {
        void triggerVoiceFromHeroCard('immunization', 'Immunization');
      };
      immunizationCard.addEventListener('click', handleImm);
      immunizationCard.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleImm();
        }
      });
    }

    // 4. Large Readability Mode (if toggle element is present)
    const largeToggle = document.getElementById('large-text-toggle');
    const storedLarge = localStorage.getItem('swasthyavaani_large_text');
    const isLarge = storedLarge !== null ? storedLarge === 'true' : true;
    if (largeToggle) {
      largeToggle.checked = isLarge;
      largeToggle.addEventListener('change', (e) => {
        applyLargeTextMode(e.target.checked);
      });
    }
    applyLargeTextMode(isLarge);

    // 5. Language Selectors in Drawer
    const voiceLangSelect = document.getElementById('voice-language-select');
    if (voiceLangSelect) {
      voiceLangSelect.value = currentLanguage;
      voiceLangSelect.addEventListener('change', (e) => {
        currentLanguage = e.target.value;
        localStorage.setItem('swasthyavaani_voice_lang', currentLanguage);
        if (activeStreamingSession && activeStreamingSession.ws && activeStreamingSession.ws.readyState === WebSocket.OPEN) {
          activeStreamingSession.sendJson('language_change', { language: currentLanguage });
        }
      });
    }

    const uiLangSelect = document.getElementById('ui-language-select');
    if (uiLangSelect) {
      uiLangSelect.value = currentUILanguage;
      uiLangSelect.addEventListener('change', (e) => {
        window.setAppLanguage(e.target.value);
      });
    }

    // 6. Demo strip visibility (strictly if ?demo=true)
    const urlParams = new URLSearchParams(window.location.search);
    const demoStrip = document.getElementById('demo-test-strip');
    if (demoStrip) {
      if (urlParams.get('demo') === 'true') {
        demoStrip.classList.remove('hidden');
      } else {
        demoStrip.classList.add('hidden');
      }
    }

    // 7. Bind Demo strip buttons
    document.querySelectorAll('[data-sim-type]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const type = btn.getAttribute('data-sim-type');
        if (type) runSimulatedTurn(type);
      });
    });

    const resetBtn = document.getElementById('reset-record-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        activeVisit = { ...DEFAULT_VISIT };
        renderActiveVisitCard();
        const raw = el.rawNote();
        if (raw) raw.textContent = '“Tap to Talk and dictate your visit notes hands-free.”';
      });
    }

    // 8. Register Service Worker for PWA
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((err) => {
          console.warn('SW registration failed:', err);
        });
      });
    }

    // 9. Initial Render
    renderActiveVisitCard();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
