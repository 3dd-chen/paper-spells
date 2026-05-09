import { useEffect, useRef, useState } from 'react';
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

export default function App() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    let app: Application;

    const initPixi = async () => {
      app = new Application();
      await app.init({ 
        resizeTo: window, 
        background: '#0f172a', 
        hello: true 
      });
      containerRef.current?.appendChild(app.canvas);

      let chromaFilter: Filter;
      try {
        chromaFilter = Filter.from({
          gl: { vertex: vertexSource, fragment: fragmentSource }
        });
      } catch (e) {
         console.warn("Could not create filter:", e);
         chromaFilter = new Filter({ glProgram: undefined } as any);
      }

      // Generate a mock green-screen video texture
      // For this prototype, we'll create a canvas texture that flashes green and white
      // to simulate the video texture loading, since we don't have a real MP4 yet.
      const mockCanvas = document.createElement('canvas');
      mockCanvas.width = 100;
      mockCanvas.height = 100;
      const ctx = mockCanvas.getContext('2d');
      if (ctx) {
          ctx.fillStyle = '#00FF00'; // Green background
          ctx.fillRect(0, 0, 100, 100);
          ctx.fillStyle = '#000000'; // Black drawing
          ctx.beginPath();
          ctx.arc(50, 50, 20, 0, Math.PI * 2);
          ctx.fill();
      }
      const mockTexture = Texture.from(mockCanvas);

      // Render up to 1000 items
      const sprites: Sprite[] = [];
      const numItems = 1000;

      for (let i = 0; i < numItems; i++) {
        const sprite = new Sprite(mockTexture);
        sprite.x = Math.random() * app.screen.width;
        sprite.y = Math.random() * app.screen.height;
        sprite.anchor.set(0.5);
        
        // Random scale and rotation
        sprite.scale.set(0.5 + Math.random() * 0.5);
        sprite.rotation = Math.random() * Math.PI * 2;
        
        // Apply the WebGL Fragment Shader to remove green
        if (chromaFilter) {
           sprite.filters = [chromaFilter];
        }

        // Custom velocity properties for the render loop
        (sprite as any).vx = (Math.random() - 0.5) * 2;
        (sprite as any).vy = (Math.random() - 0.5) * 2;

        app.stage.addChild(sprite);
        sprites.push(sprite);
      }

      // Main Render Loop for massive concurrency
      app.ticker.add((ticker: Ticker) => {
        for (let i = 0; i < sprites.length; i++) {
          const s = sprites[i];
          s.x += (s as any).vx * ticker.deltaTime;
          s.y += (s as any).vy * ticker.deltaTime;
          s.rotation += 0.01 * ticker.deltaTime;

          // Screen wrapping (Culling/Wrapping)
          if (s.x > app.screen.width + 50) s.x = -50;
          if (s.x < -50) s.x = app.screen.width + 50;
          if (s.y > app.screen.height + 50) s.y = -50;
          if (s.y < -50) s.y = app.screen.height + 50;
        }
      });

      setIsLoaded(true);
    };

    initPixi();

    return () => {
      if (app) {
        app.destroy(true, { children: true });
      }
    };
  }, []);

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
            Rendering 1,000 Concurrent Animated Shaders
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
