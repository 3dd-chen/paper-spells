import { useEffect, useRef, useCallback } from 'react';

export interface PhysicsInstance {
  x: number;
  y: number;
  vx: number;
  vy: number;
  scale: number;
  element: HTMLDivElement | null;
  facingDirection?: string;
}

interface FoodState {
  x: number;
  y: number;
  active: boolean;
  timer: number;
}

const DVD_SPEED = 2.0;
const MARGIN = 110;

/**
 * Runs a DVD-bounce physics loop for all instances.
 * Also handles the "food" gather + slow scatter interaction.
 *
 * Returns:
 *  - instancesRef  → attach to each video wrapper via ref callback
 *  - foodRef       → update when user clicks to drop food
 */
export function usePhysicsEngine(onFoodEnd?: () => void) {
  const instancesRef = useRef<Record<string, PhysicsInstance>>({});
  const foodRef = useRef<FoodState>({ x: 0, y: 0, active: false, timer: 0 });

  useEffect(() => {
    let animationId: number;

    const loop = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const foodState = foodRef.current;

      // Advance food timer
      if (foodState.active) {
        foodState.timer++;
        if (foodState.timer === 90) {
          onFoodEnd?.(); // Visual food disappears when scatter starts
        }
        if (foodState.timer > 180) {
          foodState.active = false;
        }
      }

      for (const inst of Object.values(instancesRef.current)) {
        if (!inst.element) continue;

        const speed = Math.sqrt(inst.vx * inst.vx + inst.vy * inst.vy) || 0.001;

        if (!foodState.active) {
          // ── DVD Bounce: maintain constant speed ──────────────────────────
          inst.vx = (inst.vx / speed) * DVD_SPEED;
          inst.vy = (inst.vy / speed) * DVD_SPEED;
        } else {
          // ── Food Interaction ──────────────────────────────────────────────
          const dx = foodState.x - inst.x;
          const dy = foodState.y - inst.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;

          if (foodState.timer < 90) {
            // Gather phase: nudge towards food
            if (dist > 50) {
              inst.vx += (dx / dist) * 0.3;
              inst.vy += (dy / dist) * 0.3;
            } else {
              inst.vx *= 0.9;
              inst.vy *= 0.9;
            }
          } else {
            // Scatter phase: only push away if close enough to have "eaten"
            if (dist < 150) {
              inst.vx -= (dx / dist) * 0.4;
              inst.vy -= (dy / dist) * 0.4;
            }
          }

          const maxSpeed = foodState.timer < 90 ? 5 : 3.5;
          const curSpeed = Math.sqrt(inst.vx * inst.vx + inst.vy * inst.vy) || 1;
          if (curSpeed > maxSpeed) {
            inst.vx = (inst.vx / curSpeed) * maxSpeed;
            inst.vy = (inst.vy / curSpeed) * maxSpeed;
          }
        }

        // ── Inter-instance Repulsion (Separation) ──────────────────────────
        // Keep characters away from each other
        const instances = Object.values(instancesRef.current);
        for (const other of instances) {
          if (other === inst || !other.element) continue;
          const dx = inst.x - other.x;
          const dy = inst.y - other.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const minD = 150; // Minimum desired distance between characters
          
          if (dist < minD) {
            const force = (minD - dist) * 0.005; // Push away force (softer)
            inst.vx += (dx / dist) * force;
            inst.vy += (dy / dist) * force;
          }
        }

        // Update position
        inst.x += inst.vx;
        inst.y += inst.vy;

        // Bounce off walls
        if (inst.x < MARGIN)        { inst.x = MARGIN;        inst.vx =  Math.abs(inst.vx); }
        if (inst.x > width - MARGIN) { inst.x = width - MARGIN; inst.vx = -Math.abs(inst.vx); }
        if (inst.y < MARGIN)        { inst.y = MARGIN;        inst.vy =  Math.abs(inst.vy); }
        if (inst.y > height - MARGIN){ inst.y = height - MARGIN; inst.vy = -Math.abs(inst.vy); }

        // Apply to DOM — GPU-accelerated, use translate(-50%, -50%) to center perfectly
        // Since every video in the gallery is generated as right-facing (left-facing inputs are pre-flipped on upload),
        // we flip horizontally (scaleX < 0) when moving left (vx < 0), and render normally when moving right (vx >= 0).
        const flipX = inst.vx < 0 ? -1 : 1;
        inst.element.style.transform =
          `translate3d(${inst.x}px, ${inst.y}px, 0) translate(-50%, -50%) scale(${inst.scale * flipX}, ${inst.scale})`;
      }

      animationId = requestAnimationFrame(loop);
    };

    animationId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animationId);
  }, []);

  const initInstance = useCallback((id: string, facingDirection?: string) => {
    if (!instancesRef.current[id]) {
      const angle = Math.random() * Math.PI * 2;
      instancesRef.current[id] = {
        x: 150 + Math.random() * (window.innerWidth - 300),
        y: 150 + Math.random() * (window.innerHeight - 300),
        vx: Math.cos(angle) * DVD_SPEED,
        vy: Math.sin(angle) * DVD_SPEED,
        scale: 0.7 + Math.random() * 0.4,
        element: null,
        facingDirection,
      };
    }
  }, []);

  return { instancesRef, foodRef, initInstance };
}
