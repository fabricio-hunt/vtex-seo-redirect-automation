"use client";

import { useEffect, useRef } from "react";

interface Star {
  x: number;
  y: number;
  radius: number;
  baseOpacity: number;
  twinkleSpeed: number;
  twinklePhase: number;
  driftX: number;
  driftY: number;
}

const STAR_DENSITY = 0.00012; // stars per square px, tuned for a subtle field
const MAX_STARS = 220;

function createStars(width: number, height: number): Star[] {
  const count = Math.min(MAX_STARS, Math.round(width * height * STAR_DENSITY));
  return Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    radius: Math.random() * 1.1 + 0.4,
    baseOpacity: Math.random() * 0.35 + 0.15,
    twinkleSpeed: Math.random() * 0.6 + 0.2,
    twinklePhase: Math.random() * Math.PI * 2,
    driftX: (Math.random() - 0.5) * 0.012,
    driftY: Math.random() * 0.01 + 0.004,
  }));
}

export function StarfieldBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let width = window.innerWidth;
    let height = window.innerHeight;
    let stars = createStars(width, height);

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      stars = createStars(width, height);
    }

    resize();
    window.addEventListener("resize", resize);

    function draw(time: number) {
      ctx!.clearRect(0, 0, width, height);
      for (const star of stars) {
        if (!reduceMotion) {
          star.x += star.driftX;
          star.y += star.driftY;
          if (star.x < -2) star.x = width + 2;
          if (star.x > width + 2) star.x = -2;
          if (star.y > height + 2) {
            star.y = -2;
            star.x = Math.random() * width;
          }
        }
        const twinkle = reduceMotion ? 1 : 0.6 + 0.4 * Math.sin(time * 0.001 * star.twinkleSpeed + star.twinklePhase);
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(237, 237, 237, ${star.baseOpacity * twinkle})`;
        ctx!.fill();
      }
    }

    if (reduceMotion) {
      draw(0);
      return () => window.removeEventListener("resize", resize);
    }

    let frameId: number;
    function loop(time: number) {
      draw(time);
      frameId = requestAnimationFrame(loop);
    }
    frameId = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frameId);
    };
  }, []);

  return <canvas ref={canvasRef} className="starfield-background" aria-hidden="true" />;
}
