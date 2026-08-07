/*
  ตัวเชื่อม VIA 2 เข้ากับ capture_app — โหลดภาพของเคสให้อัตโนมัติ และบันทึก ROI กลับเข้าเซิร์ฟเวอร์

  วางไฟล์นี้ไว้ที่ capture_app/static/via/ แล้วเพิ่มบรรทัดนี้ท้าย <body> ของ VIA index.html
  ต่อจาก <script src="via.js"></script>

      <script src="_via_dfu.js"></script>

  VIA จะเรียก _via_load_submodules() ให้เองหลัง init เสร็จ (ดู via.js บรรทัด ~368)

  เปิดใช้งาน: /via/index.html?rid=P0001
*/

const DFU_RID = new URLSearchParams(location.search).get('rid');

/* บริเวณที่ต้องมาร์ก — ปรับรายการนี้ให้ตรงกับที่ทีมวิจัยตกลงกัน */
const DFU_ATTRIBUTES = {
  region: {
    roi_type: {
      type: 'dropdown',
      description: 'ชนิดของบริเวณที่มาร์ก',
      options: {
        pressure_at_risk: 'บริเวณแรงกดที่เสี่ยง',
        callus: 'หนังหนาด้าน (callus)',
        deformity: 'บริเวณที่ผิดรูป',
        other: 'อื่นๆ'
      },
      default_options: { pressure_at_risk: true }
    },
    note: { type: 'text', description: 'หมายเหตุ', default_value: '' }
  },
  file: {
    foot_side: {
      type: 'radio',
      description: 'ข้างของเท้า',
      options: { L: 'เท้าซ้าย', R: 'เท้าขวา' },
      default_options: {}
    },
    has_risk_area: {
      type: 'radio',
      description: 'พบบริเวณแรงกดที่เสี่ยงหรือไม่',
      options: { yes: 'พบ', no: 'ไม่พบ' },
      default_options: {}
    }
  }
};

/* VIA โหลดภาพแบบ async ภายในตัวมันเอง (Promise ที่ไม่ได้ส่งออกมาให้ caller await ได้ —
   ดูคอมเมนต์ตรงจุดที่เรียกใช้) ฟังก์ชันนี้ poll จนกว่า _via_current_image_loaded จะเป็น true
   ค่อยเรียก fn — ใช้แทนการเรียกฟังก์ชันที่ต้องพึ่ง _via_current_image ทันทีหลัง _via_show_img() */
function dfu_wait_for_image_then(fn, attemptsLeft) {
  if (attemptsLeft === undefined) attemptsLeft = 40; // ~2s ที่ 50ms/ครั้ง
  if (typeof _via_current_image_loaded !== 'undefined' && _via_current_image_loaded && _via_current_image) {
    fn();
    return;
  }
  if (attemptsLeft <= 0) {
    console.warn('[DBG-dfubar] dfu_wait_for_image_then: gave up waiting for the image to load');
    return;
  }
  setTimeout(function () { dfu_wait_for_image_then(fn, attemptsLeft - 1); }, 50);
}

/* ข้างที่ Negative ไม่มี LOPS/PAD ตามนิยามของเกณฑ์ IWGDF อยู่แล้ว — ไม่มีอะไรให้มาร์ก จึงไม่โหลด
   ภาพข้างนั้นเข้า VIA เลย ข้างที่ label ยังเป็น null (ฟอร์มกรอกไม่ครบ) ถือว่า "ต้องมาร์กไว้ก่อน"
   เพื่อความปลอดภัย เผื่อทีหลังกรอกฟอร์มครบแล้วกลายเป็น Positive จะได้ไม่พลาดไม่ได้มาร์กไว้
   ดึงข้อมูลจาก /api/crf/{rid} เดียวกับที่หน้าอื่นใช้ ไม่ต้องเพิ่ม endpoint ใหม่ */
async function dfu_needed_sides() {
  try {
    const res = await fetch('/api/crf/' + DFU_RID);
    if (!res.ok) return ['L', 'R']; // ไม่มีฟอร์ม/ดึงไม่ได้ — ปลอดภัยไว้ก่อน ให้มาร์กได้ทั้งคู่
    const rec = await res.json();
    const der = (rec.data && rec.data.derived) || {};
    return ['L', 'R'].filter(function (side) {
      const label = der[side] && der[side].label;
      return label !== 'Negative';
    });
  } catch (e) {
    return ['L', 'R'];
  }
}

/* ข้างที่มีภาพอยู่แล้วใน project ที่เปิดขึ้นมา (ทั้งจากไฟล์บันทึกเก่า หรือเพิ่งเพิ่มไป) */
function dfu_existing_sides_in_project() {
  const sides = [];
  for (const img_id in _via_img_metadata) {
    const side = _via_img_metadata[img_id].file_attributes && _via_img_metadata[img_id].file_attributes.foot_side;
    if (side && sides.indexOf(side) === -1) sides.push(side);
  }
  return sides;
}

async function _via_load_submodules() {
  if (!DFU_RID) {
    show_message('ไม่ได้ระบุรหัสวิจัย — เปิดหน้านี้จากแบบบันทึกข้อมูล หรือใส่ ?rid=P0001 ท้าย URL', 8000);
    return;
  }

  // [DBG-dfubar] ห่อ try/catch แยกทีละขั้นไว้ชั่วคราวเพื่อไล่หาว่าจุดไหนพังแบบเงียบๆ — ถ้าพัง
  // จะโชว์เป็นข้อความสีเหลืองที่แถบข้อความของ VIA (กลางล่างจอ) ให้เห็นแม้ไม่ได้เปิด DevTools console
  try {
    dfu_simplify_ui();
  } catch (e) {
    console.error('[DBG-dfubar] dfu_simplify_ui failed:', e);
    show_message('[DBG-dfubar] dfu_simplify_ui error: ' + e.message, 15000);
  }
  try {
    dfu_add_toolbar();
    console.log('[DBG-dfubar] dfu_add_toolbar OK, #dfu_bar in DOM =', !!document.getElementById('dfu_bar'));
  } catch (e) {
    console.error('[DBG-dfubar] dfu_add_toolbar failed:', e);
    show_message('[DBG-dfubar] dfu_add_toolbar error: ' + e.message, 15000);
  }

  // มี ROI ที่เคยบันทึกไว้แล้วหรือไม่ + ข้างไหนที่ยังต้องมาร์ก (ตาม label ปัจจุบันของฟอร์ม)
  let saved = null;
  try {
    const res = await fetch('/api/roi/' + DFU_RID);
    if (res.ok) saved = await res.json();
  } catch (e) { /* ไม่มีก็เริ่มใหม่ */ }
  const neededSides = await dfu_needed_sides();

  try {
    if (saved && saved.project) {
      // เปิดของเดิมเสมอ ไม่ว่า label ตอนนี้จะว่าอย่างไร — ไม่ไปลบ/ซ่อนงานที่มาร์กไว้แล้ว
      project_open_parse_json_file(JSON.stringify(saved.project));
      const missing = neededSides.filter(function (s) { return dfu_existing_sides_in_project().indexOf(s) === -1; });
      if (missing.length) {
        dfu_add_case_images(missing);
        update_img_fn_list();
      }
      show_message('เปิด ROI ที่บันทึกไว้ของ ' + DFU_RID, 4000);
    } else if (neededSides.length > 0) {
      project_import_attributes_from_json(JSON.stringify(DFU_ATTRIBUTES));
      dfu_add_case_images(neededSides);
      project_set_name(DFU_RID + '_roi');
      _via_show_img(0);
      update_img_fn_list();
      show_message('โหลดภาพของ ' + DFU_RID + ' แล้ว — มาร์กบริเวณแล้วกดบันทึก', 5000);
    }
    // เคสที่ neededSides ว่างเปล่าและยังไม่เคยบันทึกไว้ (ทั้งสองข้าง Negative) — ไม่มีอะไรให้โหลด
    // ปล่อยให้ VIA แสดงหน้าเปล่าตามปกติของมันไป ไม่ต้องขึ้นข้อความอธิบายในนี้ (บอกที่หน้าเว็บเราแทน)

    toggle_attributes_editor();
    update_attributes_update_panel();
    annotation_editor_show();

    // ซูมเริ่มต้นที่ 3x ให้เอง กันไม่ต้องกด + เอง — index 7 ใน VIA_CANVAS_ZOOM_LEVELS = 3.0
    // (ดู via.js บรรทัด ~96) VIA จะจำระดับซูมนี้ไว้ใช้ต่อตอนสลับภาพซ้าย/ขวาเองอยู่แล้ว
    // ("Preserve zoom level" ใน via.js) ไม่ต้องตั้งซ้ำทุกครั้งที่เปลี่ยนภาพ
    //
    // _via_show_img()/project_open_parse_json_file() โหลดภาพแบบ async ภายใน (ผูก Promise ไว้
    // ข้างในไม่ส่งออกมาให้ await ได้) ถ้าเรียก set_zoom() ทันทีแบบ synchronous เหมือนโค้ดเดิม
    // _via_current_image ยังเป็น undefined อยู่ -> set_zoom() ไป error ตอนอ่าน .naturalWidth
    // (นี่คือ error ที่เจอ) ต้องรอให้ VIA โหลดภาพเสร็จจริงก่อน โดย poll _via_current_image_loaded
    // — ข้ามไปเลยถ้าไม่มีภาพอะไรถูกโหลดเลย (กันรอ poll จนหมดเวลาเปล่าๆ)
    if ((saved && saved.project) || neededSides.length > 0) {
      dfu_wait_for_image_then(function () { set_zoom(7); });
    }
  } catch (e) {
    console.error('[DBG-dfubar] image/attribute load failed:', e);
    show_message('[DBG-dfubar] load error: ' + e.message, 15000);
  }

  console.log('[DBG-dfubar] end of _via_load_submodules, #dfu_bar in DOM =', !!document.getElementById('dfu_bar'));
}

/* ภาพที่ใช้มาร์ก ROI คือรูปความละเอียดเต็ม (_full.png) ไม่ใช่รูป 224x224 ที่ใช้เทรนโมเดล —
   รูปเทรนเล็กเกินกว่าจะมองเห็นรายละเอียดตอนมาร์ก ทั้งสองไฟล์ผ่าน CLAHE แบบเดียวกัน ต่างกันแค่ขนาด
   sides = รายการข้าง ('L'/'R') ที่จะโหลด — โหลดเฉพาะข้างที่ dfu_needed_sides() บอกว่ายังต้องมาร์ก */
function dfu_add_case_images(sides) {
  const base = '/api/file/podo/' + DFU_RID + '/preprocessing/';
  sides.forEach(function (side) {
    const url = base + DFU_RID + '_podo_' + side + '_full.png';
    const img_id = project_file_add_url(url);
    if (img_id && _via_img_metadata[img_id]) {
      _via_img_metadata[img_id].file_attributes['foot_side'] = side;
    }
  });
}

/* VIA เป็นเครื่องมือทั่วไปมีปุ่ม/เมนูเยอะมากสำหรับงาน generic annotation แต่งานเรามีแค่ "มาร์กบริเวณ
   2 ภาพ (ซ้าย/ขวา) แล้วกดบันทึก" — ซ่อนเฉพาะส่วนที่ไม่เกี่ยวด้วย CSS (ไม่แก้ via.js/index.html เอง
   เพื่อไม่ให้กระทบไฟล์ third-party ต้นฉบับ) เหลือแค่: สลับภาพ ซูม เปิด/ปิดแผงแก้แอตทริบิวต์ ลบบริเวณ
   ซึ่งพวกนี้ทำผ่านคีย์ลัดอย่างเดียวไม่สะดวกสำหรับผู้ใช้ทั่วไป ส่วนปุ่ม Save/Load/Settings ของ VIA เอง
   ซ่อนไปเลยเพราะซ้ำซ้อนกับปุ่ม "บันทึก ROI" ของเราและอาจสับสนว่าต้องกดปุ่มไหนกันแน่ */
function dfu_simplify_ui() {
  const style = document.createElement('style');
  style.textContent =
    '.menubar { display: none !important; }' +
    '.toolbar svg[onclick="project_open_select_project_file()"],' +
    '.toolbar svg[onclick="project_save_with_confirm()"],' +
    '.toolbar svg[onclick="settings_panel_toggle()"],' +
    '.toolbar svg[onclick="sel_local_data_file(\'annotations\')"],' +
    '.toolbar svg[onclick="download_all_region_data(\'csv\')"],' +
    '.toolbar svg#toolbar_image_grid_toggle,' +
    '.toolbar svg[onclick="sel_all_regions()"],' +
    '.toolbar svg[onclick="copy_sel_regions()"],' +
    '.toolbar svg[onclick="paste_sel_regions_in_current_image()"],' +
    '.toolbar svg[onclick="paste_to_multiple_images_with_confirm()"],' +
    '.toolbar svg[onclick="del_sel_regions_with_confirm()"]' +
    ' { display: none !important; }';
  document.head.appendChild(style);
}

/* แถบเครื่องมือเล็กๆ มุมขวาบน: รหัสเคส + ปุ่มบันทึก + กลับไปที่ฟอร์ม */
function dfu_add_toolbar() {
  const bar = document.createElement('div');
  bar.id = 'dfu_bar';
  bar.style.cssText =
    'position:fixed;top:0;right:0;z-index:9999;display:flex;align-items:center;gap:10px;' +
    'background:#132430;color:#e8eef1;padding:8px 14px;font-size:13px;' +
    'font-family:sans-serif;border-bottom-left-radius:4px';
  bar.innerHTML =
    '<b style="font-family:monospace;letter-spacing:.05em">' + DFU_RID + '</b>' +
    '<span id="dfu_status" style="color:#a9bec8"></span>' +
    '<button id="dfu_save" style="padding:6px 14px;border:0;border-radius:3px;' +
    'background:#0d6a72;color:#fff;font-weight:600;cursor:pointer">บันทึก ROI</button>' +
    '<button id="dfu_back" style="padding:6px 12px;border:1px solid #47606f;border-radius:3px;' +
    'background:transparent;color:#dce7ec;cursor:pointer">กลับไปที่เคสนี้</button>';
  document.body.appendChild(bar);

  document.getElementById('dfu_save').addEventListener('click', dfu_save_roi);
  document.getElementById('dfu_back').addEventListener('click', function () {
    window.location.href = '/crf-detail.html?pid=' + encodeURIComponent(DFU_RID);
  });
}

/* โครงสร้างเดียวกับที่ VIA ใช้ตอน "Save Project" (via.js: project_save_confirmed) */
function dfu_project_json() {
  return {
    _via_settings: _via_settings,
    _via_img_metadata: _via_img_metadata,
    _via_attributes: _via_attributes,
    _via_data_format_version: '2.0.10',
    _via_image_id_list: _via_image_id_list
  };
}

/* สรุปย่อไว้ให้ฝั่งฟอร์มอ่าน โดยไม่ต้องแกะโปรเจกต์ทั้งก้อน */
function dfu_summary() {
  const out = {};
  for (const img_id in _via_img_metadata) {
    const m = _via_img_metadata[img_id];
    const side = (m.file_attributes && m.file_attributes.foot_side) || '?';
    const regions = m.regions || [];
    out[side] = {
      region_count: regions.length,
      has_risk_area: (m.file_attributes && m.file_attributes.has_risk_area) ||
                     (regions.length ? 'yes' : ''),
      filename: m.filename
    };
  }
  return out;
}

/* หลังบันทึกสำเร็จ ถามว่าจะทำ ROI เคสนี้ต่อ (เช่น มาร์กอีกจุด) หรือกลับไปหน้าหลัก (index.html —
   หน้าที่มีเมนู 01-05 ทั้งหมด) — กันไม่ให้ต้องสลับแท็บเองทุกครั้งที่ทำเคสหนึ่งเสร็จ */
function dfu_show_save_complete_dialog() {
  const old = document.getElementById('dfu_save_dialog_overlay');
  if (old) old.remove();

  const overlay = document.createElement('div');
  overlay.id = 'dfu_save_dialog_overlay';
  overlay.style.cssText =
    'position:fixed;inset:0;background:rgba(19,36,48,.5);z-index:10000;' +
    'display:flex;align-items:center;justify-content:center;font-family:sans-serif';
  overlay.innerHTML =
    '<div style="background:#fff;border-radius:6px;padding:26px 30px;max-width:340px;' +
    'text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.3)">' +
      '<div style="font-size:30px;margin-bottom:6px;color:#1c7a58">✓</div>' +
      '<div style="font-weight:700;font-size:15px;margin-bottom:6px;color:#132430">' +
        'บันทึก ROI ของ ' + DFU_RID + ' แล้ว</div>' +
      '<div style="font-size:12.5px;color:#4a6070;margin-bottom:18px">จะทำต่อ หรือกลับไปเลือกเคสอื่น?</div>' +
      '<div style="display:flex;gap:8px;justify-content:center">' +
        '<button id="dfu_continue_btn" style="padding:9px 16px;border-radius:4px;border:1px solid #cdd8de;' +
        'background:#fff;color:#132430;cursor:pointer;font-size:13.5px">ทำต่อ</button>' +
        '<button id="dfu_gohome_btn" style="padding:9px 16px;border-radius:4px;border:0;' +
        'background:#0d6a72;color:#fff;font-weight:600;cursor:pointer;font-size:13.5px">กลับไปหน้าหลัก</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);
  document.getElementById('dfu_continue_btn').addEventListener('click', function () { overlay.remove(); });
  document.getElementById('dfu_gohome_btn').addEventListener('click', function () {
    window.location.href = '/index.html';
  });
}

async function dfu_save_roi() {
  const status = document.getElementById('dfu_status');
  status.textContent = 'กำลังบันทึก…';
  try {
    const res = await fetch('/api/roi/' + DFU_RID, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rid: DFU_RID,
        project: dfu_project_json(),
        summary: dfu_summary()
      })
    });
    if (!res.ok) throw new Error(res.status);
    status.textContent = 'บันทึกแล้ว';
    setTimeout(function () { status.textContent = ''; }, 4000);
    dfu_show_save_complete_dialog();
  } catch (e) {
    status.textContent = '';
    show_message('บันทึกไม่สำเร็จ (' + e.message + ') — ใช้ Project → Save เพื่อเก็บไฟล์ไว้ก่อน', 8000);
  }
}
