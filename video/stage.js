// The stage's own behaviour: no app logic, no data of its own. record.spec.ts calls
// window.stage.* with cues built from the take's capture (decision 0027, ported from
// hl-create-design).
;(() => {
  const $ = (id) => document.getElementById(id)
  const LAYERS = ['Browser', 'FastAPI', 'Agent', 'Model', 'Tools', 'Validators', 'Manual', 'SAP', 'CAD', 'Blender']
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

  function pipeline(active) {
    $('pipeline').innerHTML = LAYERS.map(
      (l, i) => `${i ? '<i>›</i>' : ''}<span class="${l === active ? 'on' : ''}">${esc(l)}</span>`,
    ).join('')
  }

  function loadApp() {
    return new Promise((resolve) => {
      const app = $('app')
      app.addEventListener('load', () => resolve(), { once: true })
      app.src = '/'
    })
  }

  function init({ banner, provider }) {
    $('banner').textContent = banner
    $('provider').textContent = provider
    pipeline(null)
  }

  /** One storyboard row: subtitle, layer, callouts (file:line + excerpt), payload JSON. */
  function show(cue) {
    $('subs').textContent = cue.subtitle || ''
    $('row-id').textContent = cue.id ? `row ${cue.id}` : ''
    if (cue.layer) pipeline(cue.layer)
    $('callouts').innerHTML = (cue.callouts || [])
      .slice(0, cue.payload ? 2 : 3)
      .map((c) => `<div class="callout"><div class="where">${esc(c.file)}:${c.line} · ${esc(c.symbol)}</div><pre>${esc(c.excerpt)}</pre></div>`)
      .join('')
    const box = $('payload')
    if (cue.payload) {
      box.classList.remove('empty')
      $('payload-label').textContent = cue.payload.label
      $('payload-note').textContent = cue.payload.note || ''
      $('payload-json').textContent = JSON.stringify(cue.payload.value, null, 2)
    } else {
      box.classList.add('empty')
    }
    if (cue.slide) slide(cue.slide, cue.slideData)
    else hideSlide()
  }

  const SLIDES = {
    hook: () => `
      <h1>Bead Studio</h1>
      <p class="lead">A designer describes a glass bead in plain words. A real model guides; plain code checks every rule of the Product Design Manual, SAP issues the SKU, CadQuery builds the model, and Blender renders it.</p>`,
    map: () => `
      <h2>The pieces</h2>
      <div class="boxes">
        <div class="box"><b>Browser</b><span>React studio: chat, parameter panel, 3D viewer, cards.</span></div><div class="arrow">→</div>
        <div class="box"><b>FastAPI</b><span>The chat stream, and the confirm endpoint that the designer's click calls.</span></div><div class="arrow">→</div>
        <div class="box hot"><b>Agent loop</b><span>Bounded tool loop. The model picks tools; none has a side effect.</span></div><div class="arrow">→</div>
        <div class="box"><b>Tools</b><span>Validators, manual search (SQLite FTS5), SapClient, CadQuery, the render queue.</span></div>
      </div>`,
    end: (d) => `
      <h1>The AI guides. The code decides.</h1>
      <p class="lead" style="margin-bottom:34px">And the designer clicks. Every step is traced.</p>
      <p class="lead">${esc(d.repo || '')}</p>
      ${d.author ? `<p class="lead" style="margin-top:34px">${esc(d.author)}</p>` : ''}
      ${d.linkedin ? `<p class="lead">${esc(d.linkedin)}</p>` : ''}`,
  }

  function slide(name, data = {}) {
    $('slide-inner').innerHTML = SLIDES[name](data)
    $('slide').classList.add('on')
  }

  function hideSlide() {
    $('slide').classList.remove('on')
  }

  /** The app frame's text, without what the recorder masks: for the no-paths check. */
  function appText() {
    const doc = $('app').contentDocument
    if (!doc) return ''
    const clone = doc.body.cloneNode(true)
    clone.querySelectorAll('[data-video-masked]').forEach((n) => n.remove())
    return clone.innerText || clone.textContent || ''
  }

  window.stage = { init, loadApp, show, slide, hideSlide, appText }
})()
