# Paper Spells 🪄

Bring your hand-drawn doodles to life with AI! Paper Spells is a monorepo project that takes your drawings, analyzes them with Gemini, generates a video using Google Veo, and displays them in an interactive, physics-enabled gallery.

## 🌟 Features

- **Doodle to Video**: Upload a drawing with a transparent or white background. The app processes it with a green screen and uses **Google Veo (veo-3.1-lite)** to animate it.
- **AI-Driven Prompts**: Uses **Gemini 2.5 Flash** to analyze the drawing and generate a descriptive prompt for Veo, ensuring the animation matches the character's style.
- **Smart Orientation**: Gemini detects if the character is facing left or right and ensures the video generates in that direction. The frontend physics engine flips the video naturally based on movement.
- **Chroma Key Gallery**: A beautiful floating gallery where videos are real-time "de-greened" on a Canvas, making the characters look like they are floating freely on the background.
- **Interactive Physics**: 
  - DVD-bounce style movement.
  - Drop a "food" emoji by clicking, and all characters will gather towards it and then scatter.
  - Social distancing: Characters gently repel each other to avoid overlapping.

## 🏗️ Architecture

This project is organized as a monorepo:

- **`apps/api-server`**: FastAPI backend that handles image uploads, database storage (SQLite), and communication with Google GenAI SDK (Gemini & Veo) and Cloudflare R2.
- **`apps/upload-web`**: React frontend for uploading and processing drawings.
- **`apps/gallery-web`**: React frontend for the interactive floating gallery.

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy, Google GenAI SDK, Boto3 (for Cloudflare R2).
- **Frontend**: React 18, Vite, TailwindCSS.
- **Storage**: Cloudflare R2 (Final video hosting), Google Cloud Storage (Veo intermediate output).
- **Database**: SQLite.

## 🚀 Getting Started

### Prerequisites

- Node.js & pnpm
- Python 3.9+ & UV (recommended)
- Google Cloud Project with Vertex AI enabled.
- Cloudflare R2 bucket.

### Backend Setup

1. Navigate to the API server:
   ```bash
   cd apps/api-server
   ```
2. Copy `.env.example` to `.env` and fill in your credentials:
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
   - `GOOGLE_APPLICATION_CREDENTIALS` (path to your JSON key)
   - `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`
3. Install dependencies and run:
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
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

## 🔒 CORS & Proxies

This project uses Vite proxies to avoid CORS issues during local development:
- Requests to `/api` are proxied to `http://localhost:8000`.
- Requests to `/videos` are proxied to your Cloudflare R2 public URL.
Make sure to disable any Chrome CORS extensions as they are no longer needed!
