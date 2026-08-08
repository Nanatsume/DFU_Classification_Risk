---
name: vite-config
description: Vite build config — multi-page app mode with 8 HTML entries, output to ../static, dev-server proxy to FastAPI
metadata:
  type: reference
---

# frontend/vite.config.ts

**หน้าที่**: ตั้งค่า Vite ให้ build แบบ multi-page app (MPA) แทน SPA/React Router — แต่ละ route มีไฟล์ `.html` จริงของตัวเอง ตรงกับ URL scheme เดิมของระบบทุกประการ กำหนด `build.outDir = '../static'` (ผลลัพธ์ build ไปอยู่ที่ `capture_app/static/`, [[server]] เสิร์ฟจากที่นี่) และ dev-server proxy `/api` ไปที่ `http://127.0.0.1:8000` (ให้ `npm run dev` คุยกับ backend จริงได้โดยไม่ต้องตั้ง CORS)

**Functions/Variables (global scope)**:
- `defineConfig({...})` — export default การตั้งค่า Vite ทั้งหมด: `plugins` (react, tailwindcss), `resolve.alias` (`@` → `./src`), `server.proxy`, `build.outDir`, `build.emptyOutDir`, `build.rollupOptions.input` (8 entries: index, login, crf-form, crf-list, crf-detail, capture, roi, gallery)

**Called by**: เรียกโดย Vite เองตอน `npm run dev` / `npm run build` (ไม่มีไฟล์ในโปรเจกต์ import ไฟล์นี้ตรงๆ)

**Depends on**: `@vitejs/plugin-react`, `@tailwindcss/vite` (npm packages) — ระบุ path ไปยัง [[html-index]], [[html-login]], [[html-crf-form]], [[html-crf-list]], [[html-crf-detail]], [[html-capture]], [[html-roi]], [[html-gallery]]
