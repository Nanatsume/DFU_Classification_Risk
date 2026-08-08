---
name: main-home
description: Vite entry script that mounts Home inside AuthGuard onto #root of index.html
metadata:
  type: reference
---

# frontend/src/main-home.tsx

**หน้าที่**: entry script ของ `index.html` — สร้าง React root แล้ว render `<AuthGuard><Home /></AuthGuard>` ไม่มี logic ของตัวเอง เป็นแค่จุดต่อสาย Vite entry ↔ React component

**Functions/Variables (global scope)**: ไม่มี (top-level `createRoot(...).render(...)` เท่านั้น)

**Called by**: `index.html` (`<script type="module" src="/src/main-home.tsx">`, ดู [[html-index]])

**Depends on**: [[lib-auth]] (`AuthGuard`), [[pages-Home]], `frontend/src/index.css` ([[index-css]])
