---
name: via-vendored
description: Third-party VIA 2 annotation tool (Oxford VGG), vendored as-is — index.html, via.js, via.css, LICENSE_VIA
metadata:
  type: reference
---

# via_static/index.html, via.js, via.css, LICENSE_VIA (third-party, รวมเป็นโน้ตเดียว)

**หน้าที่**: เครื่องมือ annotation ภาพ VIA 2 (VGG Image Annotator) ของ Visual Geometry Group, Oxford University — วางไว้ตรงๆ ไม่แก้ไข (ตามหลักการที่ยึดไว้ตลอดโปรเจกต์: ไม่แตะไฟล์ third-party) การปรับแต่งทั้งหมดทำผ่าน [[_via_dfu]] ซึ่งฉีด CSS/ผูก event จากภายนอกเท่านั้น ⚠️ ไม่ได้วิเคราะห์โค้ดภายในไฟล์เหล่านี้แบบละเอียดในเอกสารชุดนี้ เพราะเป็นซอร์สโค้ดภายนอก ไม่ใช่โค้ดที่ทีมเขียนเอง — ดูเอกสารต้นฉบับที่ `www.robots.ox.ac.uk/~vgg/software/via/`

**ไฟล์ในกลุ่มนี้**:
- `index.html` — โครง UI ของ VIA (784 บรรทัด), โหลด `via.js` แล้วต่อด้วย `<script src="_via_dfu.js">`
- `via.js` — logic ทั้งหมดของ VIA (canvas, zoom, region drawing, project save/load ฯลฯ) เปิดเผย global function/variable จำนวนมากที่ [[_via_dfu]] เรียกใช้ (ดู [[via-global-state]])
- `via.css` — สไตล์ต้นฉบับของ VIA
- `LICENSE_VIA` — สัญญาอนุญาต BSD-style ของ VIA

**Called by**: เปิดตรงผ่าน URL `/via/index.html?rid=P0001` จาก [[pages-Roi]], [[pages-CrfDetail]], [[pages-Capture]]

**Depends on**: mount โดย [[server]] (`app.mount("/via", StaticFiles(directory=VIA_DIR, ...))`) — `index.html` โหลด `via.css`, `via.js`, [[_via_dfu]] ตามลำดับ
