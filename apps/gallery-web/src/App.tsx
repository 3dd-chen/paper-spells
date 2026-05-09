import { useEffect, useRef, useState, useCallback } from 'react';
import { Application, Sprite, Filter, Texture, Ticker } from 'pixi.js';

const vertexSource = `
in vec2 aPosition;
out vec2 vTextureCoord;
uniform mat3 uProjectionMatrix;
uniform mat3 uFilterMatrix;

void main(void) {
    gl_Position = vec4((uProjectionMatrix * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
    vTextureCoord = (uFilterMatrix * vec3(aPosition, 1.0)).xy;
}
`;

// Custom GLSL Fragment Shader to remove green screen
const fragmentSource = `
precision highp float;
in vec2 vTextureCoord;
out vec4 finalColor;
uniform sampler2D uTexture;

void main(void) {
    vec4 color = texture(uTexture, vTextureCoord);
    
    // Simple chroma keying for #00FF00
    float greenDiff = color.g - max(color.r, color.b);
    if (greenDiff > 0.2) {
        finalColor = vec4(0.0);
    } else {
        finalColor = color;
    }
}
`;

interface GalleryItem {
  id: string;
  video_url: string | null;
  image_path: string | null;
}

const API_URL = 'http://localhost:8000';
const POLL_INTERVAL = 10_000; // 10 seconds

export default function App() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [itemCount, setItemCount] = useState(0);
  const appRef = useRef<Application | null>(null);
  const spritesRef = useRef<Sprite[]>([]);
  const renderedIdsRef = useRef<Set<string>>(new Set());
  const chromaFilterRef = useRef<Filter | null>(null);

  const fetchGallery = useCallback(async (): Promise<GalleryItem[]> => {
    try {
      const res = await fetch(`${API_URL}/api/gallery`);
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('Gallery fetch failed:', err);
    }
    return [];
  }, []);

  const addSprite = useCallback((item: GalleryItem, app: Application) => {
    const mockCanvas = document.createElement('canvas');
    mockCanvas.width = 100;
    mockCanvas.height = 100;
    const ctx = mockCanvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#00FF00';
      ctx.fillRect(0, 0, 100, 100);
      ctx.fillStyle = '#000000';
      ctx.beginPath();
      const hash = item.id.charCodeAt(0) + item.id.charCodeAt(1);
      const shapeType = hash % 3;
      if (shapeType === 0) {
        ctx.arc(50, 50, 20 + (hash % 15), 0, Math.PI * 2);
      } else if (shapeType === 1) {
        ctx.rect(20 + (hash % 10), 20 + (hash % 10), 60 - (hash % 20), 60 - (hash % 20));
      } else {
        ctx.moveTo(50, 10 + (hash % 10));
        ctx.lineTo(90 - (hash % 10), 90 - (hash % 10));
        ctx.lineTo(10 + (hash % 10), 90 - (hash % 10));
        ctx.closePath();
      }
      ctx.fill();
    }
    const texture = Texture.from(mockCanvas);
    const sprite = new Sprite(texture);
    sprite.x = Math.random() * app.screen.width;
    sprite.y = Math.random() * app.screen.height;
    sprite.anchor.set(0.5);
    sprite.scale.set(0.5 + Math.random() * 0.5);
    sprite.rotation = Math.random() * Math.PI * 2;
    if (chromaFilterRef.current) {
      sprite.filters = [chromaFilterRef.current];
    }
    (sprite as any).vx = (Math.random() - 0.5) * 2;
    (sprite as any).vy = (Math.random() - 0.5) * 2;
    app.stage.addChild(sprite);
    spritesRef.current.push(sprite);
    renderedIdsRef.current.add(item.id);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    let destroyed = false;

    const initPixi = async () => {
      const app = new Application();
      await app.init({ 
        resizeTo: window, 
        background: '#0f172a', 
        hello: true 
      });
      if (destroyed) return;
      containerRef.current?.appendChild(app.canvas);
      appRef.current = app;

      let chromaFilter: Filter;
      try {
        chromaFilter = Filter.from({
          gl: { vertex: vertexSource, fragment: fragmentSource }
        });
      } catch (e) {
        console.warn("Could not create filter:", e);
        chromaFilter = new Filter({ glProgram: undefined } as any);
      }
      chromaFilterRef.current = chromaFilter;

      // Fetch initial gallery data and render sprites
      const items = await fetchGallery();
      setItemCount(items.length);
      for (const item of items) {
        addSprite(item, app);
      }

      // Main Render Loop
      app.ticker.add((ticker: Ticker) => {
        for (const s of spritesRef.current) {
          s.x += (s as any).vx * ticker.deltaTime;
          s.y += (s as any).vy * ticker.deltaTime;
          s.rotation += 0.01 * ticker.deltaTime;

          if (s.x > app.screen.width + 50) s.x = -50;
          if (s.x < -50) s.x = app.screen.width + 50;
          if (s.y > app.screen.height + 50) s.y = -50;
          if (s.y < -50) s.y = app.screen.height + 50;
        }
      });

      setIsLoaded(true);
    };

    initPixi();

    // Poll for new artworks every 10 seconds
    const interval = setInterval(async () => {
      if (!appRef.current) return;
      const items = await fetchGallery();
      setItemCount(items.length);
      // Diff: only add sprites for newly completed artworks
      const newItems = items.filter(item => !renderedIdsRef.current.has(item.id));
      for (const item of newItems) {
        addSprite(item, appRef.current);
      }
    }, POLL_INTERVAL);

    return () => {
      destroyed = true;
      clearInterval(interval);
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, [fetchGallery]);

  return (
    <div className="relative w-full h-screen overflow-hidden bg-slate-900">
      <div 
        ref={containerRef} 
        className="absolute inset-0"
      />
      
      {/* UI Overlay */}
      <div className="absolute top-0 left-0 w-full p-6 pointer-events-none flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-emerald-400 drop-shadow-lg">
            Virtual Gallery
          </h1>
          <p className="text-teal-100/80 font-medium mt-2 drop-shadow">
            {itemCount} Artworks Floating
          </p>
        </div>
        
        <div className="bg-black/40 backdrop-blur-md border border-white/10 rounded-xl px-4 py-2 flex items-center space-x-3 shadow-2xl">
          <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-emerald-50 font-mono text-sm font-semibold tracking-wider">
            {isLoaded ? 'SYSTEM ACTIVE' : 'INITIALIZING...'}
          </span>
        </div>
      </div>
    </div>
  );
}
