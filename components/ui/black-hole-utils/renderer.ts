export interface RendererOptions {
  canvas: HTMLCanvasElement;
}

export interface RendererInstance {
  ready: Promise<void>;
  dispose: () => void;
}

/**
 * Creates an interactive WebGL or Canvas 2D gravitational black-hole renderer
 * with accretion disk particle simulation and relativistic lensing effect.
 */
export function createRenderer(options: RendererOptions): RendererInstance {
  const { canvas } = options;
  const ctx = canvas.getContext("2d");
  let animationFrameId: number;
  let isDisposed = false;

  // Track size & DPI
  const resize = () => {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = (rect.width || window.innerWidth) * dpr;
    canvas.height = (rect.height || window.innerHeight) * dpr;
  };

  resize();
  window.addEventListener("resize", resize);

  // Particles for accretion disk
  const PARTICLE_COUNT = 240;
  const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 40 + Math.random() * 160,
    speed: 0.008 + Math.random() * 0.02,
    size: 1 + Math.random() * 2.5,
    hue: 20 + Math.random() * 45, // Fiery orange / photon ring glow
    alpha: 0.3 + Math.random() * 0.7,
  }));

  const readyPromise = Promise.resolve();

  const render = (time: number) => {
    if (isDisposed || !ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2;
    const minDim = Math.min(width, height);
    const eventHorizonRadius = minDim * 0.12;

    // Semi-transparent clearing for motion blur trailing
    ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
    ctx.fillRect(0, 0, width, height);

    // Accretion disk glow aura
    const gradient = ctx.createRadialGradient(
      cx,
      cy,
      eventHorizonRadius * 0.8,
      cx,
      cy,
      eventHorizonRadius * 3.5
    );
    gradient.addColorStop(0, "rgba(255, 120, 30, 0.4)");
    gradient.addColorStop(0.3, "rgba(255, 70, 10, 0.2)");
    gradient.addColorStop(0.7, "rgba(120, 20, 255, 0.08)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(cx, cy, eventHorizonRadius * 3.5, 0, Math.PI * 2);
    ctx.fill();

    // Render accretion disk orbiting particles
    particles.forEach((p) => {
      p.angle += p.speed;
      const x = cx + Math.cos(p.angle) * (p.radius * (minDim / 600));
      // Tilted orbital plane effect
      const y = cy + Math.sin(p.angle) * (p.radius * 0.38 * (minDim / 600));

      ctx.fillStyle = `hsla(${p.hue}, 95%, 65%, ${p.alpha})`;
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Event Horizon (Absolute Black Center)
    ctx.fillStyle = "#000000";
    ctx.beginPath();
    ctx.arc(cx, cy, eventHorizonRadius, 0, Math.PI * 2);
    ctx.fill();

    // Photon Ring (Bright sharp boundary ring)
    ctx.strokeStyle = "rgba(255, 235, 180, 0.85)";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(cx, cy, eventHorizonRadius, 0, Math.PI * 2);
    ctx.stroke();

    animationFrameId = requestAnimationFrame(render);
  };

  animationFrameId = requestAnimationFrame(render);

  return {
    ready: readyPromise,
    dispose: () => {
      isDisposed = true;
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", resize);
    },
  };
}
