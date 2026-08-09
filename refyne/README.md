# Refyne

Refyne is a standalone React + TypeScript requirement-engineering workspace. It has no Supabase dependency, authentication, database, Storage bucket, or credentials.

## Run locally

1. Install Node.js 20+ and run `npm install`.
2. Copy `.env.example` to `.env.local`. `VITE_API_BASE_URL` is optional and connects a future AI backend.
3. Run `npm run dev`.

Commands: `npm run dev`, `npm run build`, `npm run preview`, `npm run lint`.

## Local data

Projects, workspaces, chats, messages, and uploaded-file metadata persist in this browser through local storage. File contents remain in the user’s browser and are not retained after reload; attach a storage backend later if persistent files are needed.

AI generation is intentionally not fabricated. `src/services/aiService.ts` calls `POST {VITE_API_BASE_URL}/ai/generate` when configured; otherwise it explicitly reports that the generation service is not configured.
