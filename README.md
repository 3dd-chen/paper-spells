# Paper Spells 🪄

Bring your hand-drawn doodles to life with AI! Paper Spells is a monorepo project that takes your drawings, analyzes them with Gemini, generates a video using Google Veo, and displays them in an interactive, physics-enabled gallery.

## 🌟 Killer Features & Architecture

This project is built to showcase a highly scalable, edge-native architecture:

1. **Python on Edge (Cloudflare Workers)**: The FastAPI backend runs directly on Cloudflare's Edge network using Pyodide/ASGI. No traditional container or VM is required, bringing extreme scalability and low latency.
2. **Web Crypto JWT Authentication**: Hand-crafted Google Cloud OAuth 2.0 flow using the Web Crypto API (`gcp_auth.py`). By manually parsing Service Account PEMs and signing JWTs, it bypasses the need for standard Python `cryptography` libraries, which are unavailable in Edge environments.
3. **Dependency Injection (DI) & SOLID Design**: The backend architecture is strictly decoupled. `AIProvider`, `StorageInterface`, and `HttpClientInterface` ensure that the core logic is isolated from Cloudflare bindings or specific API SDKs.
4. **Web Worker Image Processing**: The frontend offloads heavy chroma-key green screen and aspect ratio calculations to an `OffscreenCanvas` inside a Web Worker, ensuring a jank-free 60fps React UI.
5. **Interactive Physics Gallery**: Uses a custom React hook to simulate DVD-bounce physics and "social distancing" between characters, allowing them to chase a dropped "food" emoji across the screen.

## 🏗️ Tech Stack

- **Backend**: Python 3.9+, FastAPI, Google Vertex AI (Gemini & Veo REST APIs).
- **Edge Deployment**: Cloudflare Workers (Pyodide), D1 (Database), R2 (Storage).
- **Frontend**: React 18, Vite, TailwindCSS, SWR, Sonner.

## 🚀 Getting Started

### Prerequisites

- Node.js & pnpm
- Google Cloud Project with Vertex AI enabled.
- Cloudflare R2 bucket & D1 Database.

### Backend Setup (Edge / Wrangler)

1. Navigate to the API server:
   ```bash
   cd apps/api-server
   ```
2. Run the `upload_secrets.py` or manually use `wrangler secret put` to upload your credentials:
   - `GEMINI_API_KEY`, `GCP_SERVICE_ACCOUNT`
   - `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
3. Start the local worker:
   ```bash
   npx wrangler dev
   ```

### Frontend Setup

1. From the root directory, install dependencies:
   ```bash
   pnpm install
   ```
2. Run the upload app:
   ```bash
   cd apps/upload-web
   pnpm dev
   ```
3. Run the gallery app:
   ```bash
   cd apps/gallery-web
   pnpm dev
   ```
