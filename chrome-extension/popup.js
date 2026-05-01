
  const API = 'https://naagazz-interview-checker.hf.space/voice';

  // ── State ──────────────────────────────────────────────────────────────────
  const state = {
    candidateId: '',
    personal:  { blob: null, recording: false, timer: null, elapsed: 0 },
    technical: { blob: null, recording: false, timer: null, elapsed: 0 },
    mediaRecorder:  { personal: null, technical: null },
    personalDone:   false,
    technicalDone:  false,
  };

  // ── Refs ───────────────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);

  // ── Toast ──────────────────────────────────────────────────────────────────
  let _toastT;
  function toast(msg, type = 'error') {
    const el = $('toast');
    el.textContent = (type === 'error' ? '⚠️ ' : '✓ ') + msg;
    el.className = 'toast ' + type;
    el.style.display = 'block';
    clearTimeout(_toastT);
    _toastT = setTimeout(() => { el.style.display = 'none'; }, 6000);
  }

  // ── Candidate ID setup ─────────────────────────────────────────────────────
  $('btnGenId').addEventListener('click', () => {
    const id = 'cand_' + Math.random().toString(36).slice(2, 8).toUpperCase();
    $('candidateId').value = id;
  });

  $('btnSetId').addEventListener('click', confirmId);
  $('candidateId').addEventListener('keydown', e => { if (e.key === 'Enter') confirmId(); });

  function confirmId() {
    const val = $('candidateId').value.trim();
    if (!val) { toast('Please enter or generate a candidate ID'); return; }
    state.candidateId = val;

    // Update UI
    $('idStatus').innerHTML = `<span class="dot green"></span> Session active: <strong>${val}</strong>`;
    $('cardSetup').classList.add('active');
    $('badge0').textContent = '✓';
    $('badge0').style.cssText = 'background:rgba(16,185,129,.15);border-color:rgba(16,185,129,.3);color:var(--green)';
    $('btnSaveP').disabled = false;
    updateProgress(2);
  }

  // ── Tab switching ──────────────────────────────────────────────────────────
  function switchTab(type, mode) {
    const pfx = type === 'personal' ? 'P' : 'T';
    $(`tabPMic, tabPUp, tabTMic, tabTUp`.split(', ').find(id => id === `tab${pfx}Mic`));
    // Personal
    if (type === 'personal') {
      $('tabPMic').classList.toggle('active', mode === 'mic');
      $('tabPUp').classList.toggle('active', mode !== 'mic');
      $('panelPMic').style.display = mode === 'mic' ? '' : 'none';
      $('panelPUp').style.display  = mode !== 'mic' ? '' : 'none';
    } else {
      $('tabTMic').classList.toggle('active', mode === 'mic');
      $('tabTUp').classList.toggle('active', mode !== 'mic');
      $('panelTMic').style.display = mode === 'mic' ? '' : 'none';
      $('panelTUp').style.display  = mode !== 'mic' ? '' : 'none';
    }
  }

  // ── File select ────────────────────────────────────────────────────────────
  function onFileSelect(type) {
    const fileInput = type === 'personal' ? $('fileP') : $('fileT');
    const nameEl    = type === 'personal' ? $('filePName') : $('fileTName');
    if (!fileInput.files[0]) return;
    const file = fileInput.files[0];
    state[type].blob = file;
    nameEl.textContent = '📎 ' + file.name;
    updateStatusBar(type, 'amber', `File ready: ${file.name}`);
  }

  // ── Recording ──────────────────────────────────────────────────────────────
  async function toggleRecord(type) {
    const st = state[type];
    if (st.recording) {
      stopRecording(type);
    } else {
      await startRecording(type);
    }
  }

  async function startRecording(type) {
    if (!state.candidateId) { toast('Set candidate ID first'); return; }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      toast('Microphone access denied: ' + e.message); return;
    }

    const chunks = [];
    const mr = new MediaRecorder(stream, { mimeType: bestMime() });
    state.mediaRecorder[type] = mr;
    mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    mr.onstop = () => {
      state[type].blob = new Blob(chunks, { type: mr.mimeType });
      stream.getTracks().forEach(t => t.stop());
      setRecordUI(type, false);
      updateStatusBar(type, 'amber', `Recorded ${fmtTime(state[type].elapsed)} — ready to save`);
    };
    mr.start(200);

    state[type].recording = true;
    state[type].elapsed   = 0;
    setRecordUI(type, true);
    state[type].timer = setInterval(() => {
      state[type].elapsed++;
      const id = type === 'personal' ? 'timerP' : 'timerT';
      $(id).textContent = fmtTime(state[type].elapsed);
    }, 1000);
  }

  function stopRecording(type) {
    clearInterval(state[type].timer);
    state[type].recording = false;
    if (state.mediaRecorder[type] && state.mediaRecorder[type].state !== 'inactive') {
      state.mediaRecorder[type].stop();
    }
  }

  function setRecordUI(type, isRec) {
    const pfx   = type === 'personal' ? 'P' : 'T';
    const zone  = $('recZone' + pfx);
    const btn   = $('micBtn'  + pfx);
    const hint  = $('hint'    + pfx);
    const wave  = $('wave'    + pfx);
    if (isRec) {
      zone.classList.add('recording');
      btn.classList.add('recording');
      btn.textContent = '⏹';
      hint.textContent = 'Recording… click to stop';
      wave.classList.add('recording');
    } else {
      zone.classList.remove('recording');
      btn.classList.remove('recording');
      btn.textContent = '🎙️';
      hint.textContent = 'Click to record again';
      wave.classList.remove('recording');
    }
  }

  function bestMime() {
    const types = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4'];
    return types.find(t => MediaRecorder.isTypeSupported(t)) || '';
  }

  function fmtTime(s) {
    return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
  }

  // ── Save personal ──────────────────────────────────────────────────────────
  $('btnSaveP').addEventListener('click', () => saveResponse('personal'));
  $('btnSaveT').addEventListener('click', () => saveResponse('technical'));

  async function saveResponse(type) {
    if (!state.candidateId) { toast('Set candidate ID first'); return; }

    const saveBtn = type === 'personal' ? $('btnSaveP') : $('btnSaveT');
    const textEl  = type === 'personal' ? $('savePText') : $('saveTText');
    const spnEl   = type === 'personal' ? $('spnP') : $('spnT');
    const tEl     = type === 'personal' ? $('transcriptP') : $('transcriptT');
    const blob    = state[type].blob;

    // ── If audio recorded/uploaded → transcribe it first ───────────────────
    if (blob) {
      saveBtn.disabled = true;
      textEl.style.display = 'none';
      spnEl.style.display  = 'inline-block';
      updateStatusBar(type, 'amber', 'Transcribing audio via Deepgram…');

      const form = new FormData();
      form.append('audio', blob, `${type}_${state.candidateId}.webm`);
      form.append('type', type);

      try {
        const resp = await fetch(`${API}/transcribe-chunk`, { method: 'POST', body: form });
        const json = await resp.json();
        if (!resp.ok) throw new Error(json.detail || resp.statusText);

        // Populate editable textarea with transcription
        tEl.value = json.text || '';
        // Clear blob so next click goes to the confirm path (not re-transcribe)
        state[type].blob = null;
        updateStatusBar(type, 'amber', `Transcribed — ${json.word_count} words. Edit if needed, then click Confirm again.`);
        toast('✏️ Edit if needed, then click Confirm again!', 'success');

      } catch (err) {
        updateStatusBar(type, 'red', '✗ Transcription error: ' + err.message);
        toast('Transcription failed: ' + err.message);
        saveBtn.disabled = false;
        textEl.style.display = '';
        spnEl.style.display  = 'none';
        return;
      } finally {
        textEl.style.display = '';
        spnEl.style.display  = 'none';
        saveBtn.disabled = false;
      }
    }

    // ── Confirm: read text from textarea (edited or typed directly) ─────────
    const text = tEl.value.trim();
    if (!text) {
      toast('No text to save — record audio or type in the box above');
      return;
    }

    updateStatusBar(type, 'green', `✓ ${text.split(' ').length} words confirmed`);

    if (type === 'personal') {
      state.personalDone = true;
      $('badge1').textContent = '✓';
      styleBadge($('badge1'), 'green');
      $('btnSaveT').disabled = false;
      $('cardTech').classList.add('active');
      $('dotT').className = 'dot amber';
      $('labelT').textContent = 'Ready to record or type technical response';
      updateProgress(3);
    } else {
      state.technicalDone = true;
      $('badge2').textContent = '✓';
      styleBadge($('badge2'), 'green');
      $('btnCompare').disabled = false;
      $('cardCompare').classList.add('active');
      updateProgress(4);
    }
    toast(`${cap(type)} response confirmed!`, 'success');
  }


  // ── Verdict logic ──────────────────────────────────────────────────────────
  // Called whenever we have fresh style AND/OR plagiarism data.
  let _styleData  = null;   // analysis object from /text-compare
  let _plagScore  = null;   // number or null

  function computeVerdict(styleShift, plagPct) {
    // 4-tier verdict: strictly follows shift thresholds, plagiarism boosts severity
    const veryHigh = styleShift === 'VERY HIGH';
    const high     = styleShift === 'HIGH';
    const moderate = styleShift === 'MODERATE';
    const highPlag = plagPct !== null && plagPct >= 40;
    const modPlag  = plagPct !== null && plagPct >= 15;

    if (veryHigh)                          return { label:'Highly Suspicious', icon:'\ud83d\udea8', css:'inconsistent'  };
    if (high && highPlag)                  return { label:'Highly Suspicious', icon:'\ud83d\udea8', css:'inconsistent'  };
    if (high || highPlag)                  return { label:'Suspicious',         icon:'\ud83d\udd0d', css:'needs-review' };
    if (moderate && modPlag)               return { label:'Suspicious',         icon:'\ud83d\udd0d', css:'needs-review' };
    if (moderate || modPlag)               return { label:'Slight Concern',     icon:'\u26a0\ufe0f', css:'needs-review' };
    return                                        { label:'Genuine',            icon:'\u2705', css:'consistent'  };
  }

  function updateVerdict() {
    if (!_styleData) return;
    const v = computeVerdict(_styleData.style_shift, _plagScore);
    $('verdictBanner').className = 'verdict-banner ' + v.css;
    $('verdictIcon').textContent  = v.icon;
    $('verdictLabel').textContent = v.label;

    const shift = _styleData.style_shift;
    const pStr  = _plagScore !== null ? `Plagiarism: ${_plagScore.toFixed(1)}%` : 'Plagiarism: checking...';
    $('verdictSub').textContent = `Candidate: ${state.candidateId}  \u00b7  Style Shift: ${shift}  \u00b7  ${pStr}`;

    // Update plagiarism tile
    const plagHtml = _plagScore !== null
      ? `<div class="plag-score-big ${_plagScore<15?'safe':_plagScore<40?'warn':'danger'}" style="font-size:2.2rem;font-weight:900;line-height:1">${_plagScore.toFixed(1)}%</div>
         <div style="margin-top:4px"><span class="badge ${_plagScore<15?'badge-green':_plagScore<40?'badge-amber':'badge-red'}">${_plagScore<15?'Original':_plagScore<40?'Review Needed':'High Risk'}</span></div>`
      : `<div style="font-size:1rem;color:var(--muted);margin-bottom:4px">Checking...</div><div class="spinner" style="margin:0 auto"></div>`;

    $('scoresGrid').innerHTML = buildTiles(_styleData, plagHtml);
  }

  function buildTiles(a, plagHtml) {
    const shiftCls = a.style_shift==='VERY HIGH'?'badge-red':a.style_shift==='HIGH'?'badge-amber':a.style_shift==='MODERATE'?'badge-amber':'badge-green';
    return `
      <div class="score-tile">
        <div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Authenticity Score</div>
        <div class="score-num ${gradClass(a.authenticity_score)}" style="font-size:2.2rem;font-weight:900;line-height:1">${a.authenticity_score}</div>
        <div style="margin-top:4px"><span class="badge ${badgeClass(a.authenticity_score)}">/100</span></div>
      </div>
      <div class="score-tile">
        <div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Style Shift</div>
        <div style="font-size:1.6rem;font-weight:900;color:var(--text)">${a.style_shift}</div>
        <div style="margin-top:4px"><span class="badge ${shiftCls}">Score: ${a.shift_score}/100</span></div>
      </div>
      <div class="score-tile">
        <div style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Plagiarism Score</div>
        ${plagHtml}
      </div>`;
  }

  // ── Deep-dive toggle (kept for compatibility, no-op) ───────────────────────
  function toggleDeepDive() {}

  // ── Compare ────────────────────────────────────────────────────────────────
  $('btnCompare').addEventListener('click', runCompare);
  $('btnRecompare').addEventListener('click', runCompare);

  async function runCompare() {
    if (!state.candidateId) { toast('No candidate ID'); return; }
    const personalText  = $('transcriptP').value.trim();
    const technicalText = $('transcriptT').value.trim();
    if (!personalText)  { toast('Personal response is empty \u2014 record or type it first');  return; }
    if (!technicalText) { toast('Technical response is empty \u2014 record or type it first'); return; }

    _styleData = null; _plagScore = null;
    setLoading(true);
    $('resultsSection').style.display = 'none';
    $('plagCard').style.display       = 'none';

    try {
      const resp = await fetch(`${API}/text-compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_id: state.candidateId, personal: personalText, technical: technicalText }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || resp.statusText);
      renderResults(data);
      $('resultsSection').style.display = 'block';
      $('badge3').textContent = '\u2713'; styleBadge($('badge3'), 'green');
      setTimeout(() => $('resultsSection').scrollIntoView({ behavior:'smooth', block:'start' }), 80);
      runPlagiarismCheck(technicalText);   // non-blocking
    } catch (err) {
      toast('Analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(on) {
    const btn = $('btnCompare');
    $('cmpText').style.display = on ? 'none' : '';
    $('spnCmp').style.display  = on ? 'inline-block' : 'none';
    btn.disabled = on;
  }

  // ── Plagiarism check (technical only) ─────────────────────────────────────
  async function runPlagiarismCheck(technical) {
    $('plagCard').style.display = 'block';
    $('plagLoading').classList.add('active');
    $('plagError').classList.remove('active');
    $('plagResults').innerHTML = '';
    try {
      const resp = await fetch(`${API}/plagiarism`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ technical }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || resp.statusText);
      renderPlagiarism(data);
    } catch (e) {
      const msg = e.message || '';
      let friendly = 'Plagiarism check unavailable. Please try again later.';
      if (/429|rate.?limit|quota|already submitted/i.test(msg)) {
        friendly = 'Plagiarism check unavailable \u2014 API limit reached. Results will show without plagiarism score.';
      } else if (/timeout|network|failed to fetch/i.test(msg)) {
        friendly = 'Plagiarism check timed out. The service may be busy \u2014 try re-analysing.';
      } else if (/token|api.?key|auth/i.test(msg)) {
        friendly = 'Plagiarism API not configured. Add PLAGIARISM_API_TOKEN to your .env file.';
      }
      $('plagError').textContent = '\u26a0\ufe0f ' + friendly;
      $('plagError').classList.add('active');
    } finally {
      $('plagLoading').classList.remove('active');
    }
  }

  function renderPlagiarism(data) {
    const tech       = data.technical || {};
    const plagResult = tech.plagiarism || tech || {};
    const aiResult   = tech.ai_detection || {};

    const p_hasErr  = !plagResult || plagResult.error;
    const p_pct     = p_hasErr ? null : (plagResult.score ?? 0);

    const a_hasErr  = !aiResult || aiResult.error;
    const a_pct     = a_hasErr ? null : (aiResult.score ?? 0);

    _plagScore = p_pct;
    updateVerdict();   // recompute final verdict now that plagiarism is known

    // Hide global error banner, we'll show individual errors per tile if needed
    $('plagError').classList.remove('active');

    // 1. Plagiarism Tile HTML
    let plagHtml = '';
    if (p_hasErr) {
        const errStr = plagResult.error || 'Check failed';
        let friendly = 'Unavailable';
        if (/short|minimum/i.test(errStr)) friendly = 'Text too short (<100 chars)';
        plagHtml = `<div style="color:var(--red);font-size:.85rem;margin-top:10px">\u26a0\ufe0f ${friendly}</div>`;
    } else {
        const cls = p_pct < 15 ? 'safe' : p_pct < 40 ? 'warn' : 'danger';
        const sources = plagResult.sources || [];
        const srcHtml = sources.length
          ? `<div class="plag-sources-title">Top Sources</div>` +
            sources.slice(0,5).map(s =>
              `<div class="plag-source-item">
                <a href="${esc(s.url||s.link||'#')}" target="_blank" rel="noopener">${esc(s.title||s.url||s.link||'Source')}</a>
                <span class="plag-source-pct">${(s.similarity||s.percent||0)}%</span>
               </div>`).join('')
          : '';
        plagHtml = `
          <div style="display:flex;align-items:center;gap:18px;margin-bottom:14px">
            <div class="plag-score-big ${cls}" style="flex-shrink:0">${p_pct.toFixed(1)}%</div>
            <div>
              <div style="font-size:.75rem;color:var(--muted)">Plagiarised Match</div>
              <span class="badge ${cls==='safe'?'badge-green':cls==='warn'?'badge-amber':'badge-red'}" style="margin-top:6px">${cls==='safe'?'Original':cls==='warn'?'Review Needed':'High Risk'}</span>
            </div>
          </div>
          ${srcHtml}`;
    }

    // 2. AI Detection Tile HTML
    let aiHtml = '';
    if (a_hasErr) {
        const errStr = aiResult.error || 'Check failed';
        let friendly = 'Unavailable';
        if (/short|minimum/i.test(errStr)) friendly = 'Text too short (<300 chars for AI detection)';
        aiHtml = `<div style="color:var(--red);font-size:.85rem;margin-top:10px">\u26a0\ufe0f ${friendly}</div>`;
    } else {
        const cls = a_pct < 20 ? 'safe' : a_pct < 60 ? 'warn' : 'danger';
        aiHtml = `
          <div style="display:flex;align-items:center;gap:18px;margin-bottom:14px">
            <div class="plag-score-big ${cls}" style="flex-shrink:0">${a_pct.toFixed(1)}%</div>
            <div>
              <div style="font-size:.75rem;color:var(--muted)">AI Generated Probability</div>
              <span class="badge ${cls==='safe'?'badge-green':cls==='warn'?'badge-amber':'badge-red'}" style="margin-top:6px">${cls==='safe'?'Human-written':cls==='warn'?'AI Assisted':'Highly AI Generated'}</span>
            </div>
          </div>`;
    }

    $('plagResults').innerHTML = `
      <div class="plag-response-grid" style="grid-template-columns:1fr 1fr; gap:16px;">
        <div class="preview-block">
          <div class="pb-label">AI CONTENT DETECTION</div>
          ${aiHtml}
        </div>
        <div class="preview-block">
          <div class="pb-label">PLAGIARISM DETECTION</div>
          ${plagHtml}
        </div>
      </div>
    `;
  }

  // ── Render style results ───────────────────────────────────────────────────
  function renderResults(data) {
    const a = data.analysis || {};
    _styleData = a;

    // Initial tiles (plagiarism tile shows spinner)
    $('scoresGrid').innerHTML = buildTiles(a,
      `<div style="font-size:1rem;color:var(--muted);margin-bottom:8px">Checking...</div><div class="spinner" style="margin:0 auto"></div>`);

    // Summary
    $('summaryPill').textContent = a.summary || 'Analysis complete.';

    // Style flags
    const fw = $('flagsWrap'); fw.innerHTML = '';
    const flags = a.flags || [];
    if (!flags.length) {
      fw.innerHTML = '<div class="flag-item partial"><span class="flag-icon">\u2705</span> No style inconsistencies detected.</div>';
    } else {
      flags.forEach(f => {
        const d = document.createElement('div');
        d.className = 'flag-item contradiction';
        d.innerHTML = `<span class="flag-icon">\u26a1</span><span>${esc(f)}</span>`;
        fw.appendChild(d);
      });
    }

    // Initial verdict (style only, plagiarism pending)
    updateVerdict();
  }


    function colorClass(v) {
    if (v === null || v === undefined) return '';
    if (v >= 70) return 'green';
    if (v >= 40) return 'amber';
    return 'red';
  }

  function gradClass(v) {
    if (v >= 70) return 'green-grad';
    if (v >= 40) return 'amber-grad';
    return 'red-grad';
  }
  function badgeClass(v) {
    if (v >= 70) return 'badge-green';
    if (v >= 40) return 'badge-amber';
    return 'badge-red';
  }

  // Also add these CSS classes dynamically for tile-num gradient
  const _sty = document.createElement('style');
  _sty.textContent = '.green-grad{background:linear-gradient(135deg,#10b981,#059669);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}.amber-grad{background:linear-gradient(135deg,#f59e0b,#d97706);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}.red-grad{background:linear-gradient(135deg,#ef4444,#b91c1c);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}';
  document.head.appendChild(_sty);

  function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function updateStatusBar(type, dotClass, msg) {
    const pfx = type === 'personal' ? 'P' : 'T';
    $('dot'   + pfx).className = 'dot ' + dotClass;
    $('label' + pfx).textContent = msg;
  }

  function styleBadge(el, color) {
    const map = {
      green: 'background:rgba(16,185,129,.15);border-color:rgba(16,185,129,.3);color:var(--green)',
      amber: 'background:rgba(245,158,11,.15);border-color:rgba(245,158,11,.3);color:var(--amber)',
      red:   'background:rgba(239,68,68,.15);border-color:rgba(239,68,68,.3);color:var(--red)',
    };
    el.style.cssText = map[color] || '';
  }

  function updateProgress(step) {
    for (let i = 1; i <= 4; i++) {
      const el = $('ps' + i);
      el.classList.remove('active', 'done');
      if (i < step)  el.classList.add('done');
      if (i === step) el.classList.add('active');
    }
  }

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
