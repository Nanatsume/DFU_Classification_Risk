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

async function _via_load_submodules() {
  if (!DFU_RID) {
    show_message('ไม่ได้ระบุรหัสวิจัย — เปิดหน้านี้จากแบบบันทึกข้อมูล หรือใส่ ?rid=P0001 ท้าย URL', 8000);
    return;
  }

  dfu_add_toolbar();

  // มี ROI ที่เคยบันทึกไว้แล้วหรือไม่
  let saved = null;
  try {
    const res = await fetch('/api/roi/' + DFU_RID);
    if (res.ok) saved = await res.json();
  } catch (e) { /* ไม่มีก็เริ่มใหม่ */ }

  if (saved && saved.project) {
    project_open_parse_json_file(JSON.stringify(saved.project));
    show_message('เปิด ROI ที่บันทึกไว้ของ ' + DFU_RID, 4000);
  } else {
    project_import_attributes_from_json(JSON.stringify(DFU_ATTRIBUTES));
    dfu_add_case_images();
    project_set_name(DFU_RID + '_roi');
    _via_show_img(0);
    update_img_fn_list();
    show_message('โหลดภาพของ ' + DFU_RID + ' แล้ว — มาร์กบริเวณแล้วกดบันทึก', 5000);
  }

  toggle_attributes_editor();
  update_attributes_update_panel();
  annotation_editor_show();
}

/* ภาพที่ผ่าน preprocessing แล้ว (S1) คือภาพที่ใช้มาร์ก ROI */
function dfu_add_case_images() {
  const base = '/api/file/podo/' + DFU_RID + '/preprocessing/';
  [['L', 'ซ้าย'], ['R', 'ขวา']].forEach(function (pair) {
    const side = pair[0];
    const url = base + DFU_RID + '_podo_' + side + '.png';
    const img_id = project_file_add_url(url);
    if (img_id && _via_img_metadata[img_id]) {
      _via_img_metadata[img_id].file_attributes['foot_side'] = side;
    }
  });
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
    show_message('บันทึก ROI ของ ' + DFU_RID + ' ลงเครื่องแล้ว', 4000);
    setTimeout(function () { status.textContent = ''; }, 4000);
  } catch (e) {
    status.textContent = '';
    show_message('บันทึกไม่สำเร็จ (' + e.message + ') — ใช้ Project → Save เพื่อเก็บไฟล์ไว้ก่อน', 8000);
  }
}
