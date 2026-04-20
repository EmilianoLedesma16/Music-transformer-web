(() => {
  const piano = document.querySelector(".piano");
  if (!piano) return;

  const whiteWrap = piano.querySelector(".white-keys");
  const blackWrap = piano.querySelector(".black-keys");
  const OCTAVES   = Math.max(1, Math.min(3, parseInt(piano.dataset.octaves    || "2", 10)));
  const START_OCT = parseInt(piano.dataset.startOctave || "4", 10);

  piano.style.setProperty("--octaves",     OCTAVES);
  piano.style.setProperty("--white-count", OCTAVES * 7);
  piano.style.setProperty("--cols",        OCTAVES * 7);

  whiteWrap.innerHTML = "";
  blackWrap.innerHTML = "";

  const whites = ["C","D","E","F","G","A","B"];
  const blacks = ["C#","D#",null,"F#","G#","A#",null];

  for (let o = 0; o < OCTAVES; o++) {
    const oct = START_OCT + o;
    whites.forEach(n => {
      const b = document.createElement("button");
      b.className = "key-white"; b.type = "button"; b.dataset.note = `${n}${oct}`;
      whiteWrap.appendChild(b);
    });
    blacks.forEach((n, idx) => {
      if (!n) return;
      const b = document.createElement("button");
      b.className = "key-black"; b.type = "button"; b.dataset.note = `${n}${oct}`;
      b.style.setProperty("--i", o * 7 + (idx + 1));
      blackWrap.appendChild(b);
    });
  }

  let audioCtx = null;
  const getCtx = () => {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  };

  const SEMI = {C:0,"C#":1,D:2,"D#":3,E:4,F:5,"F#":6,G:7,"G#":8,A:9,"A#":10,B:11};

  function noteToFreq(n) {
    const m = /^([A-G])(#?)(-?\d+)$/.exec(n);
    if (!m) return null;
    const midi = (parseInt(m[3],10) + 1) * 12 + SEMI[m[1] + m[2]];
    return 440 * Math.pow(2, (midi - 69) / 12);
  }

  function createVoice(freq) {
    const ctx = getCtx(), now = ctx.currentTime;
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(freq, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.linearRampToValueAtTime(1.0,   now + 0.01);
    gain.gain.linearRampToValueAtTime(0.001, now + 0.19);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now); osc.stop(now + 2.5);
    let ended = false;
    osc.onended = () => ended = true;
    return { release() {
      if (ended) return;
      const t = ctx.currentTime;
      gain.gain.cancelScheduledValues(t);
      gain.gain.setValueAtTime(Math.max(0.0001, gain.gain.value), t);
      gain.gain.linearRampToValueAtTime(0.0001, t + 0.25);
    }};
  }

  piano.querySelectorAll(".key-white, .key-black").forEach(k => {
    k._voices = Object.create(null);
    k.addEventListener("pointerdown", e => {
      e.preventDefault();
      const f = noteToFreq(k.dataset.note);
      if (!f) return;
      k._voices[e.pointerId] = createVoice(f);
      k.classList.add("is-down");
      try { k.setPointerCapture(e.pointerId); } catch {}
    });
    const end = e => {
      const v = k._voices[e.pointerId];
      if (v) { v.release(); delete k._voices[e.pointerId]; }
      if (Object.keys(k._voices).length === 0) k.classList.remove("is-down");
    };
    k.addEventListener("pointerup",     end);
    k.addEventListener("pointercancel", end);
  });
})();
