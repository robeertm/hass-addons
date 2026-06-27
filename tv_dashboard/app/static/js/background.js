/* Wetter-Background: Sterne nachts, Wolken/Sonne tagsüber, Regen-Drops bei rainy, Funkeln bei clear */
(function() {
  const canvas = document.getElementById('bg-canvas');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = window.devicePixelRatio || 1;
  let mode = 'partlycloudy', isNight = false;
  let particles = [];
  let raf = null;

  function resize() {
    W = canvas.clientWidth = window.innerWidth;
    H = canvas.clientHeight = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    rebuild();
  }

  function rand(a, b) { return a + Math.random() * (b - a); }

  function rebuild() {
    particles = [];
    if (isNight) {
      // Sterne
      const n = Math.min(180, Math.floor(W * H / 14000));
      for (let i = 0; i < n; i++) {
        particles.push({
          type: 'star',
          x: Math.random() * W,
          y: Math.random() * H * 0.7,
          r: rand(0.4, 1.8),
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: rand(0.005, 0.025),
        });
      }
    } else if (mode === 'rainy' || mode === 'pouring' || mode === 'lightning-rainy') {
      // Regen
      const n = mode === 'pouring' ? 250 : 140;
      for (let i = 0; i < n; i++) {
        particles.push({
          type: 'rain',
          x: Math.random() * W * 1.2,
          y: Math.random() * H,
          speed: rand(8, 14),
          len: rand(12, 24),
        });
      }
    } else if (mode === 'snowy' || mode === 'snowy-rainy') {
      // Schnee
      const n = 120;
      for (let i = 0; i < n; i++) {
        particles.push({
          type: 'snow',
          x: Math.random() * W,
          y: Math.random() * H,
          r: rand(1, 3),
          speed: rand(0.3, 1.2),
          drift: rand(-0.4, 0.4),
          drifth: rand(0, Math.PI * 2),
        });
      }
    } else if (mode === 'sunny' || mode === 'clear-night') {
      // Funkeln + leichte Lichtflecken
      const n = 40;
      for (let i = 0; i < n; i++) {
        particles.push({
          type: 'spark',
          x: Math.random() * W,
          y: Math.random() * H,
          r: rand(1, 2),
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: rand(0.01, 0.04),
        });
      }
    } else {
      // partlycloudy / cloudy: wenige driftende Lichtblobs
      const n = 8;
      for (let i = 0; i < n; i++) {
        particles.push({
          type: 'blob',
          x: Math.random() * W,
          y: Math.random() * H,
          r: rand(80, 180),
          drift: rand(0.05, 0.2),
          alpha: rand(0.04, 0.10),
          hue: rand(230, 280),
        });
      }
    }
  }

  function step() {
    ctx.clearRect(0, 0, W, H);

    for (const p of particles) {
      if (p.type === 'star') {
        p.twinkle += p.twinkleSpeed;
        const a = 0.4 + Math.sin(p.twinkle) * 0.4;
        ctx.globalAlpha = a;
        ctx.fillStyle = '#cdd6f4';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.type === 'rain') {
        p.y += p.speed;
        p.x -= p.speed * 0.3;
        if (p.y > H) { p.y = -p.len; p.x = Math.random() * W * 1.2; }
        ctx.globalAlpha = 0.25;
        ctx.strokeStyle = '#89b4fa';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + p.speed * 0.3, p.y + p.len);
        ctx.stroke();
      } else if (p.type === 'snow') {
        p.drifth += 0.02;
        p.x += Math.sin(p.drifth) * p.drift;
        p.y += p.speed;
        if (p.y > H) { p.y = -p.r; p.x = Math.random() * W; }
        ctx.globalAlpha = 0.7;
        ctx.fillStyle = '#cdd6f4';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.type === 'spark') {
        p.twinkle += p.twinkleSpeed;
        const a = 0.2 + Math.sin(p.twinkle) * 0.2;
        ctx.globalAlpha = a;
        ctx.fillStyle = '#fab387';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.type === 'blob') {
        p.x += p.drift;
        if (p.x > W + p.r) p.x = -p.r;
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        grad.addColorStop(0, `hsla(${p.hue}, 70%, 65%, ${p.alpha})`);
        grad.addColorStop(1, `hsla(${p.hue}, 70%, 65%, 0)`);
        ctx.globalAlpha = 1;
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(step);
  }

  window.bgSetMode = function(weatherState, night) {
    const newMode = weatherState || 'partlycloudy';
    if (newMode !== mode || night !== isNight) {
      mode = newMode;
      isNight = !!night;
      rebuild();
    }
  };

  window.addEventListener('resize', resize);
  resize();
  step();
})();
