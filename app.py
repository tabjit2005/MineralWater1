from __future__ import annotations

import base64
import json
import re
import unicodedata
import zlib
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import pandas as pd
import pymupdf
import streamlit as st
from PIL import Image, ImageOps

from neo4j_service import (
    create_customer,
    create_water,
    delete_customer,
    delete_water,
    get_customers,
    get_dashboard_metrics,
    get_profile,
    get_water_images,
    get_waters,
    graph_neighborhood,
    list_likes,
    list_similarities,
    ping,
    recommend_waters,
    seed_demo_data,
    set_likes,
    set_similar,
    set_water_image,
    update_customer,
    update_water,
)

IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]
IMAGE_MAX_SIDE = 480  # stored pictures are shrunk to this so a node property stays small
BRAND_IMAGE_DIR = Path(__file__).parent / "images"  # bundled brand photos, see images/CREDITS.md

# Sidebar menu: internal page key -> Thai label.
PAGES = {
    "Dashboard": "📊 ภาพรวม",
    "Recommendations": "✨ แนะนำน้ำแร่",
    "Customers": "👤 ลูกค้า",
    "Waters": "💧 น้ำแร่",
    "Relationships": "🔗 ความสัมพันธ์",
    "Graph Explorer": "🕸️ กราฟความสัมพันธ์",
    "Admin / Setup": "⚙️ ตั้งค่าข้อมูล",
}

# Hub (landing page): homework 1-3 live in homework/<folder>/, card 4 opens this app.
REPO_URL = "https://github.com/tabjit2005/MineralWater1"
REPO_BRANCH = "main"
HOMEWORK_DIR = Path(__file__).parent / "homework"
HOMEWORK = [
    {
        "folder": "01_club",
        "tag": "01 / CLUB",
        "icon": "👥",
        "title": "ระบบชมรมด้วย Neo4j",
        "text": "ออกแบบกราฟนักศึกษาและชมรม แล้วเขียน Cypher แนะนำชมรมจากเพื่อนของนักศึกษา",
        "name": "งานที่ 1 — ระบบชมรมด้วย Neo4j",
        "about": (
            "เอกสารรวมคำสั่ง Cypher ของระบบชมรมพร้อมภาพผลลัพธ์จาก Neo4j "
            "เริ่มจากสร้างข้อมูลนักศึกษาและชมรม กำหนดความสัมพันธ์ แล้วไล่ทีละขั้นจนได้คำสั่งแนะนำชมรม "
            "ที่เพื่อนของนักศึกษาเป็นสมาชิกมากที่สุด โดยไม่แนะนำชมรมที่เจ้าตัวเป็นสมาชิกอยู่แล้ว"
        ),
        "topics": [
            "สร้าง Student 5 คน และ Club 3 ชมรม ด้วย CREATE",
            "ความสัมพันธ์ FRIEND (นักศึกษา → นักศึกษา) และ MEMBER_OF (นักศึกษา → ชมรม)",
            "ค้นหาด้วย MATCH + WHERE + RETURN",
            "Traversal: S001 → FRIEND → เพื่อน → MEMBER_OF → Club",
            "นับเพื่อนในแต่ละชมรมด้วย count(DISTINCT friend) และตัดชมรมเดิมด้วย WHERE NOT",
            "แนะนำชมรมอันดับ 1 ด้วย ORDER BY และ LIMIT 1",
        ],
    },
    {
        "folder": "02_graph",
        "tag": "02 / GRAPH",
        "icon": "🕸️",
        "title": "น้ำแร่ด้วย Graph",
        "text": "สร้างกราฟผู้ใช้และน้ำแร่ด้วย Python / NetworkX เพื่อสำรวจความชอบและแนะนำน้ำแร่",
        "name": "งานที่ 2 — ระบบแนะนำน้ำแร่ด้วย Graph (NetworkX)",
        "about": (
            "Notebook บน Google Colab ที่สร้างกราฟแบบไม่มีทิศทางของผู้ใช้ 10 คนและน้ำแร่ 7 ยี่ห้อด้วย NetworkX "
            "แล้วใช้การเดินบนกราฟหาผู้ใช้ที่ชอบน้ำแร่เหมือนกัน เพื่อแนะนำยี่ห้อที่ผู้ใช้ยังไม่เคยเลือก "
            "คะแนนของแต่ละยี่ห้อคือจำนวนเส้นทางที่เดินไปถึงยี่ห้อนั้นได้"
        ),
        "topics": [
            "สร้าง Node ผู้ใช้และน้ำแร่ และ Edge ความชอบด้วย nx.Graph()",
            "วาดกราฟด้วย matplotlib แยกสี Node สองประเภท",
            "ใช้ G.neighbors() ตอบคำถามว่าใครชอบน้ำแร่อะไร",
            "หาผู้ใช้ที่ชอบน้ำแร่เหมือนกันด้วยการเดินสองทอด",
            "นับคะแนนคำแนะนำด้วย Counter และสร้างฟังก์ชัน recommend_waters()",
        ],
    },
    {
        "folder": "03_neo4j",
        "tag": "03 / NEO4J",
        "icon": "🗃️",
        "title": "น้ำแร่ด้วย Neo4j",
        "text": "เชื่อม Neo4j Aura จาก Python แล้วแนะนำน้ำแร่ด้วย Cypher จากลูกค้าที่มีรสนิยมคล้ายกัน",
        "name": "งานที่ 3 — ระบบแนะนำน้ำแร่ด้วย Neo4j Aura",
        "about": (
            "Notebook ที่ย้ายโจทย์น้ำแร่จากกราฟในหน่วยความจำไปเก็บใน Neo4j Aura ผ่าน Neo4j Python Driver "
            "สร้าง Customer, Water และความสัมพันธ์ SIMILAR_TO กับ LIKES แล้วเขียน Cypher แนะนำน้ำแร่ "
            "ที่ลูกค้าที่คล้ายกันชอบแต่เจ้าตัวยังไม่ได้ชอบ เป็นต้นแบบของระบบในการ์ดที่ 4"
        ),
        "topics": [
            "เชื่อมต่อ Neo4j Aura และหา home database",
            "สร้าง Unique Constraint ของ customer_id และ water_id",
            "เพิ่มข้อมูลหลายรายการด้วย UNWIND + MERGE",
            "Traversal หลายทอด: Customer → SIMILAR_TO → Customer → LIKES → Water",
            "Aggregation ด้วย count() และแสดงผลเป็นตาราง pandas",
            "ฟังก์ชัน recommend_waters(), find_customer() และ liked_waters()",
        ],
    },
]

st.set_page_config(
    page_title="ระบบแนะนำน้ำแร่",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Base colours and fonts live in .streamlit/config.toml; this adds the water-themed details.
st.markdown(
    """
    <style>
      /* Top padding clears Streamlit's fixed header so the hero banner is not clipped */
      .block-container {padding-top: 4rem; padding-bottom: 2rem;}

      /* Hero banner: deep-water gradient, bubbles, and a wave along the bottom edge */
      .hero {
        position: relative; overflow: hidden;
        padding: 1.6rem 1.8rem 2.7rem; border-radius: 24px; margin-bottom: 1.1rem;
        color: white;
        background:
          radial-gradient(circle at 88% 28%, rgba(255,255,255,.20) 0 26px, transparent 27px),
          radial-gradient(circle at 78% 62%, rgba(255,255,255,.14) 0 14px, transparent 15px),
          radial-gradient(circle at 94% 70%, rgba(255,255,255,.12) 0 9px, transparent 10px),
          radial-gradient(circle at 70% 24%, rgba(255,255,255,.10) 0 7px, transparent 8px),
          linear-gradient(120deg, #0b3954 0%, #0e7490 55%, #22b8cf 100%);
        box-shadow: 0 10px 28px rgba(11,57,84,.18);
      }
      .hero::after {
        content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 44px;
        background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 60' preserveAspectRatio='none'%3E%3Cpath d='M0 34 C150 64 300 4 450 34 S750 64 900 34 S1100 4 1200 34 V60 H0Z' fill='%23ffffff' fill-opacity='.22'/%3E%3Cpath d='M0 44 C200 20 400 66 600 44 S1000 20 1200 44 V60 H0Z' fill='%23f3fafc'/%3E%3C/svg%3E") center / 100% 100% no-repeat;
      }
      .hero h1 {margin: 0; padding: 0; font-size: 2.1rem; color: white;}
      .hero p {opacity: .92; margin: .35rem 0 0 0;}
      .hero .hero-sub {opacity: .75; font-size: .85rem; letter-spacing: .04em;}

      /* Sidebar: deep-water gradient with pill-shaped menu items */
      [data-testid="stSidebar"] {background: linear-gradient(180deg, #0b3954 0%, #0e5f7a 100%);}
      .brand {display: flex; align-items: center; gap: .6rem; margin: .2rem 0 .1rem;}
      .brand .drop {
        width: 42px; height: 42px; border-radius: 14px; font-size: 1.4rem;
        display: flex; align-items: center; justify-content: center;
        background: rgba(95,212,230,.20); border: 1px solid rgba(95,212,230,.45);
      }
      .brand b {font-size: 1.15rem; line-height: 1.2; color: #ffffff;}
      .brand span {font-size: .78rem; opacity: .75;}
      .author {
        padding: .7rem .85rem; border-radius: 14px; font-size: .9rem; line-height: 1.5;
        background: rgba(255,255,255,.07); border: 1px solid rgba(95,212,230,.30);
      }
      .author small {display: block; opacity: .7; font-size: .75rem; letter-spacing: .03em;}
      .author b {color: #ffffff;}
      [data-testid="stSidebar"] [role="radiogroup"] {gap: .2rem;}
      [data-testid="stSidebar"] [role="radiogroup"] label {
        width: 100%; padding: .5rem .7rem; border-radius: 12px; transition: background .15s;
      }
      [data-testid="stSidebar"] [role="radiogroup"] label:hover {background: rgba(255,255,255,.08);}
      [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(95,212,230,.20); box-shadow: inset 3px 0 0 #5fd4e6;
      }

      /* Cards */
      [data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #c5e3ee; border-top: 4px solid #22b8cf;
        border-radius: 18px; padding: 1rem 1.2rem; box-shadow: 0 4px 14px rgba(14,116,144,.08);
      }
      [data-testid="stMetricValue"] {color: #0e7490; font-weight: 700;}
      [class*="st-key-card_"], [data-testid="stForm"] {
        background: #ffffff; box-shadow: 0 4px 14px rgba(14,116,144,.07);
      }
      [data-testid="stImage"] img {border-radius: 14px; box-shadow: 0 4px 12px rgba(11,57,84,.12);}

      .score-pill {
        display: inline-block; padding: .2rem .65rem; border-radius: 999px;
        background: linear-gradient(90deg, #0e7490, #22b8cf);
        color: white; font-size: .8rem; font-weight: 700;
      }
      .muted {opacity: .72; font-size: .9rem;}

      /* Hub landing page */
      .hero.hub {text-align: center; padding: 2.2rem 1.8rem 3.4rem;}
      .hero.hub h1 {font-size: 2.5rem; margin-top: .7rem;}
      .hub-badge {
        display: inline-block; padding: .3rem 1rem; border-radius: 999px;
        font-size: .75rem; letter-spacing: .14em;
        background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.40);
      }
      .hub-head {display: flex; align-items: center; justify-content: space-between;}
      .hub-icon {
        width: 46px; height: 46px; border-radius: 14px; font-size: 1.35rem;
        display: flex; align-items: center; justify-content: center;
        background: #e1f1f7; border: 1px solid #c5e3ee;
      }
      .hub-tag {font-size: .75rem; letter-spacing: .1em; color: #4b7f95;}
      /* Fixed minimum heights keep the buttons of all four cards on one line */
      .hub-name {margin: .9rem 0 .2rem !important; padding: 0 !important; font-size: 1.2rem !important; min-height: 3.3rem;}
      .hub-desc {margin: 0; min-height: 6.6rem; color: #33596b;}
      [class*="st-key-card_hub_"] {min-height: 23.5rem;}
      .hub-footer {text-align: center; color: #4b7f95; font-size: .88rem; line-height: 1.8;}
      .hub-footer small {opacity: .8;}
      /* Homework viewer page */
      .hero.work h1 {font-size: 1.9rem; margin-top: .6rem;}
      .work-section {margin: 0 0 .5rem; padding: 0; font-size: 1.1rem;}
      .nb-label {
        margin: .9rem 0 .25rem; font-size: .72rem; letter-spacing: .08em; color: #4b7f95;
      }
      .st-key-card_hub_app {border-color: #22b8cf; box-shadow: 0 6px 20px rgba(14,116,144,.16);}
    </style>
    """,
    unsafe_allow_html=True,
)


def require_connection() -> None:
    try:
        if not ping():
            raise RuntimeError("Neo4j did not return a healthy response")
    except Exception as exc:
        st.error("ยังเชื่อมต่อ Neo4j Aura ไม่สำเร็จ")
        st.code(
            '[neo4j]\nuri = "neo4j+s://12ca74ed.databases.neo4j.io"\n'
            'username = "12ca74ed"\npassword = "YOUR_PASSWORD"\ndatabase = "12ca74ed"',
            language="toml",
        )
        st.caption("ให้นำค่าด้านบนไปใส่ใน .streamlit/secrets.toml (หรือ Streamlit Secrets) และห้าม commit password ลง GitHub")
        st.exception(exc)
        st.stop()


def flash(message: str) -> None:
    """Keep a success message across the st.rerun() that follows a write."""
    st.session_state["flash"] = message


def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def customer_selector(key: str = "customer") -> str:
    customers = get_customers()
    if not customers:
        st.info('ยังไม่มีข้อมูลลูกค้า กรุณาไปที่เมนู "ตั้งค่าข้อมูล" แล้วสร้างข้อมูลตัวอย่าง หรือเพิ่มลูกค้าที่เมนู "ลูกค้า"')
        st.stop()
    labels = {f"{x['customer_id']} — {x['name']}": x["customer_id"] for x in customers}
    chosen = st.selectbox("เลือกผู้ใช้", list(labels), key=key)
    return labels[chosen]


def next_id(existing: list[str], prefix: str, start: int) -> str:
    numbers = [int(x[len(prefix):]) for x in existing if x.startswith(prefix) and x[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers) + 1 if numbers else start):03d}"


def prepare_image(uploaded: Any) -> bytes | None:
    """Shrink an uploaded picture to a small JPEG; None when the file is not a readable image."""
    try:
        picture = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGBA")
        flat = Image.new("RGB", picture.size, "white")  # JPEG has no transparency
        flat.paste(picture, mask=picture.getchannel("A"))
        flat.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
        buffer = BytesIO()
        flat.save(buffer, "JPEG", quality=85)
    except Exception:
        return None
    return buffer.getvalue()


def placeholder_svg(water_id: str, name: str) -> str:
    """Drawn bottle for waters without an uploaded picture; colour is fixed per water_id."""
    hue = zlib.crc32(water_id.encode()) % 360
    text = name if len(name) <= 18 else name[:17] + "…"
    font_size = min(11.0, 116 / max(len(text), 1))  # shrink long names to fit the 76-unit label
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -40 240 320" width="240" height="320">
  <rect y="-40" width="240" height="320" fill="hsl({hue},60%,94%)"/>
  <rect x="103" y="26" width="34" height="18" rx="4" fill="hsl({hue},55%,38%)"/>
  <path d="M106 44h28v20c0 12 24 20 24 44v92c0 9-7 16-16 16H98c-9 0-16-7-16-16v-92c0-24 24-32 24-44z"
        fill="hsl({hue},65%,56%)"/>
  <path d="M94 112c0-10 6-17 12-23v112c-7 0-12-5-12-12z" fill="#ffffff" opacity=".28"/>
  <rect x="82" y="128" width="76" height="46" fill="#ffffff"/>
  <text x="120" y="155" text-anchor="middle" font-family="sans-serif" font-size="{font_size:.1f}" font-weight="700"
        fill="hsl({hue},55%,28%)">{escape(text)}</text>
</svg>"""


@lru_cache(maxsize=None)
def brand_picture(name: str) -> bytes | None:
    """Bundled photo matched by water name: "Nestlé Pure Life" -> images/nestle-pure-life.jpg."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    path = BRAND_IMAGE_DIR / f"{slug}.jpg"
    return path.read_bytes() if slug and path.is_file() else None


def water_picture(water_id: str, name: str, images: dict[str, bytes]) -> bytes | str:
    """What to hand to st.image: uploaded JPEG, else bundled brand photo, else drawn placeholder."""
    return images.get(water_id) or brand_picture(name) or placeholder_svg(water_id, name)


def water_picture_uri(water_id: str, name: str, images: dict[str, bytes]) -> str:
    """Same picture as a data URI, for st.column_config.ImageColumn."""
    data = images.get(water_id) or brand_picture(name)
    if data:
        return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    return "data:image/svg+xml;base64," + base64.b64encode(placeholder_svg(water_id, name).encode()).decode()


def manage_nodes(
    *,
    noun: str,
    id_field: str,
    rows: list[dict[str, Any]],
    column_labels: dict[str, str],
    id_prefix: str,
    id_start: int,
    create: Callable[[str, str], bool],
    update: Callable[[str, str], bool],
    delete: Callable[[str], bool],
    delete_warning: Callable[[dict[str, Any]], str],
    images: dict[str, bytes] | None = None,
    set_image: Callable[[str, bytes | None], bool] | None = None,
) -> None:
    """Table + add / edit / delete tabs for one node label (Customer or Water).

    Pass `images` and `set_image` to let the label carry an uploaded picture.
    """
    st.write(f"ทั้งหมด {len(rows)} รายการ")
    if rows:
        st.dataframe(pd.DataFrame(rows).rename(columns=column_labels), width="stretch", hide_index=True)

    by_id = {row[id_field]: row for row in rows}
    add_tab, edit_tab, delete_tab = st.tabs(["➕ เพิ่ม", "✏️ แก้ไข", "🗑️ ลบ"])

    # Bumped after each successful save so the form (name, uploader) starts empty again.
    saves_key = f"saves_{id_field}"
    saves = st.session_state.get(saves_key, 0)

    with add_tab:
        with st.form(f"add_{id_field}_{saves}"):
            new_id = st.text_input(f"รหัส{noun} ({id_field})", value=next_id(list(by_id), id_prefix, id_start))
            new_name = st.text_input(f"ชื่อ{noun}")
            upload = st.file_uploader(f"รูป{noun} (ไม่บังคับ)", type=IMAGE_TYPES) if set_image else None
            submitted = st.form_submit_button("เพิ่ม", type="primary")
        if submitted:
            new_id, new_name = new_id.strip(), new_name.strip()
            new_image = prepare_image(upload) if upload else None
            if not new_id or not new_name:
                st.error("กรุณากรอกทั้งรหัสและชื่อ")
            elif upload and new_image is None:
                st.error("ไฟล์ที่อัปโหลดไม่ใช่รูปภาพที่อ่านได้ กรุณาเลือกไฟล์อื่น")
            elif not create(new_id, new_name):
                st.error(f"รหัส {new_id} ถูกใช้แล้ว กรุณาใช้รหัสอื่น")
            else:
                if new_image:
                    set_image(new_id, new_image)
                st.session_state[saves_key] = saves + 1
                flash(f"เพิ่ม{noun} {new_id} — {new_name} แล้ว" + (" พร้อมรูป" if new_image else ""))
                st.rerun()

    if not rows:
        edit_tab.info(f"ยังไม่มี{noun}ให้แก้ไข")
        delete_tab.info(f"ยังไม่มี{noun}ให้ลบ")
        return

    def label(item_id: str) -> str:
        return f"{item_id} — {by_id[item_id]['name']}"

    with edit_tab:
        edit_id = st.selectbox(f"เลือก{noun}ที่จะแก้ไข", list(by_id), format_func=label, key=f"edit_{id_field}")
        has_image = bool(set_image) and edit_id in (images or {})
        if set_image:
            st.image(water_picture(edit_id, by_id[edit_id]["name"], images or {}), width=160)
            st.caption("รูปปัจจุบัน" if has_image else "ยังไม่มีรูปที่อัปโหลด (แสดงรูปเริ่มต้น)")
        upload, remove_image = None, False
        with st.form(f"edit_form_{id_field}_{edit_id}_{saves}"):
            st.text_input(f"รหัส{noun} ({id_field})", value=edit_id, disabled=True)
            edited_name = st.text_input(f"ชื่อ{noun}", value=by_id[edit_id]["name"])
            if set_image:
                upload = st.file_uploader(f"เปลี่ยนรูป{noun} (ไม่บังคับ)", type=IMAGE_TYPES)
                if has_image:
                    remove_image = st.checkbox("ลบรูปปัจจุบัน แล้วกลับไปใช้รูปเริ่มต้น")
            submitted = st.form_submit_button("บันทึกการแก้ไข", type="primary")
        if submitted:
            edited_name = edited_name.strip()
            new_image = prepare_image(upload) if upload else None
            if not edited_name:
                st.error("ชื่อห้ามว่าง")
            elif upload and new_image is None:
                st.error("ไฟล์ที่อัปโหลดไม่ใช่รูปภาพที่อ่านได้ กรุณาเลือกไฟล์อื่น")
            elif not update(edit_id, edited_name):
                st.error(f"ไม่พบ{noun} {edit_id} (อาจถูกลบไปแล้ว)")
            else:
                # A newly uploaded picture wins over the "remove" checkbox.
                if new_image:
                    set_image(edit_id, new_image)
                elif remove_image:
                    set_image(edit_id, None)
                st.session_state[saves_key] = saves + 1
                image_note = " และเปลี่ยนรูป" if new_image else " และลบรูป" if remove_image else ""
                flash(f"แก้ไข{noun} {edit_id} เป็น {edited_name}{image_note} แล้ว")
                st.rerun()

    with delete_tab:
        delete_id = st.selectbox(f"เลือก{noun}ที่จะลบ", list(by_id), format_func=label, key=f"delete_{id_field}")
        st.warning(delete_warning(by_id[delete_id]))
        confirmed = st.checkbox(f"ยืนยันการลบ {label(delete_id)}", key=f"confirm_{id_field}_{delete_id}")
        if st.button("ลบ", type="primary", disabled=not confirmed, key=f"delete_button_{id_field}"):
            if delete(delete_id):
                flash(f"ลบ{noun} {label(delete_id)} แล้ว")
            st.rerun()


def hub_card_header(icon: str, tag: str, title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="hub-head"><div class="hub-icon">{icon}</div><div class="hub-tag">{escape(tag)}</div></div>
        <h3 class="hub-name">{escape(title)}</h3>
        <p class="hub-desc">{escape(text)}</p>
        """,
        unsafe_allow_html=True,
    )


def homework_files(folder: str) -> list[Path]:
    return sorted(p for p in (HOMEWORK_DIR / folder).glob("*") if p.is_file() and not p.name.startswith("."))


def github_url(folder: str) -> str:
    return f"{REPO_URL}/tree/{REPO_BRANCH}/homework/{folder}"


def colab_url(folder: str, notebook: Path) -> str:
    repo = REPO_URL.split("github.com/")[1]
    return f"https://colab.research.google.com/github/{repo}/blob/{REPO_BRANCH}/homework/{folder}/{quote(notebook.name)}"


def notebook_text(value: Any) -> str:
    """Notebook JSON stores text either as one string or as a list of lines."""
    return value if isinstance(value, str) else "".join(value or [])


def output_text(value: Any) -> str:
    """Saved notebook output as plain text, without terminal colour/cursor codes."""
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", notebook_text(value)).rstrip()


def render_notebook(path: Path) -> None:
    """Show a Jupyter notebook: markdown, code, and the outputs saved in the file."""
    cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
    for cell in cells:
        source = notebook_text(cell.get("source"))
        if not source.strip():
            continue
        if cell.get("cell_type") == "markdown":
            st.markdown(source, unsafe_allow_html=True)
            continue
        if cell.get("cell_type") != "code":
            continue
        st.code(source, language="python")
        # pip's progress bars are noise, so outputs of install cells are not shown.
        outputs = [] if re.search(r"^\s*[!%]pip\b", source, re.MULTILINE) else cell.get("outputs", [])
        if outputs:
            st.markdown('<div class="nb-label">ผลลัพธ์</div>', unsafe_allow_html=True)
        for output in outputs:
            kind = output.get("output_type")
            data = output.get("data", {})
            if kind == "stream":
                st.code(output_text(output.get("text")), language=None)
            elif kind == "error":
                st.code(output_text("\n".join(output.get("traceback", []))), language=None)
            elif "image/png" in data:
                st.image(base64.b64decode(notebook_text(data["image/png"])))
            elif "text/plain" in data:
                # Plain text is preferred over text/html, which Colab fills with its own widgets.
                st.code(output_text(data["text/plain"]), language=None)


@st.cache_data(show_spinner="กำลังเปิดเอกสาร...")
def pdf_page_images(path: str, modified: float) -> list[bytes]:
    """Render every PDF page to PNG; `modified` refreshes the cache when the file changes."""
    with pymupdf.open(path) as document:
        return [page.get_pixmap(dpi=130).tobytes("png") for page in document]


def render_pdf(path: Path) -> None:
    pages = pdf_page_images(str(path), path.stat().st_mtime)
    for number, page in enumerate(pages, start=1):
        st.image(page)  # natural size (about 1100 px wide); Streamlit caps it at the frame width
        st.caption(f"หน้า {number} / {len(pages)}")


def render_homework(work: dict[str, Any]) -> None:
    """One homework: name, description, actions, and the work itself inside a scrolling frame."""
    if st.button("← กลับหน้าหลัก"):
        st.session_state["view"] = "hub"
        st.rerun()

    st.markdown(
        f"""
        <div class="hero work">
          <span class="hub-badge">{escape(work["tag"])}</span>
          <h1>{work["icon"]} {escape(work["name"])}</h1>
          <p>{escape(work["text"])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    files = homework_files(work["folder"])
    viewable = [p for p in files if p.suffix.lower() in (".ipynb", ".pdf")]
    about, actions = st.columns([2, 1])
    with about, st.container(border=True, key="card_work_about"):
        st.markdown('<h3 class="work-section">เกี่ยวกับการบ้านนี้</h3>', unsafe_allow_html=True)
        st.write(work["about"])
        st.markdown("**สิ่งที่ทำในงานนี้**\n" + "\n".join(f"- {topic}" for topic in work["topics"]))
    with actions, st.container(border=True, key="card_work_files"):
        st.markdown('<h3 class="work-section">ไฟล์งาน</h3>', unsafe_allow_html=True)
        for path in files:
            st.caption(f"📄 {path.name} · {path.stat().st_size / 1024:,.0f} KB")
        for path in viewable:
            if path.suffix.lower() == ".ipynb":
                st.link_button("เปิดการบ้านใน Colab ↗", colab_url(work["folder"], path), width="stretch")
        for path in files:
            st.download_button(
                f"ดาวน์โหลด {path.suffix.lstrip('.').upper() or 'ไฟล์'} ↓",
                data=path.read_bytes(),
                file_name=path.name,
                width="stretch",
                key=f"download_{work['folder']}_{path.name}",
            )
        st.link_button("ดูไฟล์บน GitHub ↗", github_url(work["folder"]), width="stretch")

    if not viewable:
        st.info("ยังไม่มีไฟล์ .ipynb หรือ .pdf ให้แสดงในโฟลเดอร์ของงานนี้")
        return
    st.markdown('<h3 class="work-section">เนื้อหาการบ้าน</h3>', unsafe_allow_html=True)
    areas = st.tabs([p.name for p in viewable]) if len(viewable) > 1 else [st.container()]
    for index, (area, path) in enumerate(zip(areas, viewable)):
        with area, st.container(height=760, border=True, key=f"card_frame_{index}"):
            if path.suffix.lower() == ".ipynb":
                render_notebook(path)
            else:
                render_pdf(path)


def render_hub() -> None:
    """Landing page: one card per homework folder plus a card that opens the recommender."""
    st.markdown(
        """
        <div class="hero hub">
          <span class="hub-badge">HOMEWORK · RECOMMENDATION HUB</span>
          <h1>รวมการบ้านและระบบแนะนำ</h1>
          <p>ระบบชมรม · กราฟน้ำแร่ · Neo4j<br>เลือกงานที่ต้องการเปิดดูได้จากการ์ดด้านล่าง</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(len(HOMEWORK) + 1)
    for column, work in zip(columns, HOMEWORK):
        files = homework_files(work["folder"])
        notebook = next((p for p in files if p.suffix.lower() == ".ipynb"), None)
        pdf = next((p for p in files if p.suffix.lower() == ".pdf"), None)
        with column, st.container(border=True, key=f"card_hub_{work['folder']}"):
            hub_card_header(work["icon"], work["tag"], work["title"], work["text"])
            if not files:
                st.caption(f"⏳ ยังไม่มีไฟล์งาน — วางไฟล์ไว้ในโฟลเดอร์ `homework/{work['folder']}/`")
                continue
            if st.button("ดูการบ้าน →", type="primary", width="stretch", key=f"open_{work['folder']}"):
                st.session_state["view"] = "homework"
                st.session_state["homework"] = work["folder"]
                st.rerun()
            if notebook:
                st.link_button("เปิดการบ้านใน Colab ↗", colab_url(work["folder"], notebook), width="stretch")
            elif pdf:
                st.download_button(
                    "ดาวน์โหลดเอกสาร PDF ↓",
                    data=pdf.read_bytes(),
                    file_name=pdf.name,
                    mime="application/pdf",
                    width="stretch",
                    key=f"pdf_{work['folder']}",
                )
            else:
                st.link_button("ดูไฟล์บน GitHub ↗", github_url(work["folder"]), width="stretch")

    with columns[-1], st.container(border=True, key="card_hub_app"):
        hub_card_header(
            "💧",
            f"{len(HOMEWORK) + 1:02d} / APPLICATION",
            "ระบบแนะนำน้ำแร่",
            "ทดลองระบบแนะนำ เลือกผู้ใช้ จัดการข้อมูลลูกค้า น้ำแร่ และสำรวจกราฟความสัมพันธ์ภายในแอป",
        )
        if st.button("เข้าสู่ระบบแนะนำ →", type="primary", width="stretch"):
            st.session_state["view"] = "app"
            st.rerun()
        st.link_button("ดูโค้ดโปรเจกต์บน GitHub ↗", REPO_URL, width="stretch")

    st.divider()
    st.markdown(
        """
        <div class="hub-footer">
          กมลวรรณ ทับจิต · รหัสนักศึกษา 664245002<br>
          <small>Mineral Water Recommendation Project</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


# The hub needs no database, so it is shown before the Neo4j connection check.
view = st.session_state.setdefault("view", "hub")
opened_work = next((w for w in HOMEWORK if w["folder"] == st.session_state.get("homework")), None)
if view == "homework" and opened_work:
    render_homework(opened_work)
    st.stop()
if view != "app":
    render_hub()
    st.stop()

require_connection()

with st.sidebar:
    if st.button("← กลับหน้าหลัก", width="stretch"):
        st.session_state["view"] = "hub"
        st.rerun()
    st.markdown(
        """
        <div class="brand">
          <div class="drop">💧</div>
          <div><b>ระบบแนะนำน้ำแร่</b><br><span>Neo4j Aura + Streamlit</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    page = st.radio("เมนู", list(PAGES), format_func=PAGES.get, key="page")
    st.divider()
    st.markdown(
        """
        <div class="author">
          <small>ผู้จัดทำ</small>
          <b>กมลวรรณ ทับจิต</b><br>
          รหัสนักศึกษา 664245002
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="hero">
      <div class="hero-sub">MINERAL WATER RECOMMENDATION SYSTEM</div>
      <h1>💧 ระบบแนะนำน้ำแร่</h1>
      <p>แนะนำน้ำแร่ด้วย Graph Database จากลูกค้าที่มีรสนิยมคล้ายกัน</p>
    </div>
    """,
    unsafe_allow_html=True,
)

show_flash()

if page == "Dashboard":
    st.subheader("ภาพรวมระบบ")
    m = get_dashboard_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👤 ลูกค้า", m.get("customers", 0))
    c2.metric("💧 น้ำแร่", m.get("waters", 0))
    c3.metric("❤️ ความสัมพันธ์ LIKES", m.get("likes", 0))
    c4.metric("🤝 ความสัมพันธ์ SIMILAR_TO", m.get("similarities", 0))

    waters = sorted(get_waters(), key=lambda w: (-w["likes"], w["name"]))
    if waters:
        st.markdown("### ความนิยมของน้ำแร่")
        images = get_water_images()
        table = [{"image": water_picture_uri(w["water_id"], w["name"], images), **w} for w in waters]
        st.dataframe(
            pd.DataFrame(table).rename(
                columns={"image": "รูป", "water_id": "รหัส", "name": "น้ำแร่", "likes": "จำนวนคนชอบ"}
            ),
            column_config={
                "รูป": st.column_config.ImageColumn(width="small"),
                "จำนวนคนชอบ": st.column_config.ProgressColumn(
                    format="%d", min_value=0, max_value=max(1, waters[0]["likes"])
                ),
            },
            width="stretch",
            hide_index=True,
        )

    st.divider()
    customer_id = customer_selector("dash_customer")
    profile = get_profile(customer_id)

    if profile:
        left, mid, right = st.columns([1, 1, 1])
        with left:
            st.markdown(f"### {profile['name']}")
            st.write(f"**รหัส:** {profile['customer_id']}")
            st.write(f"**ชอบน้ำแร่:** {len(profile['liked'])} แบรนด์")
            st.write(f"**ลูกค้าที่คล้ายกัน:** {len(profile['similar'])} คน")
        with mid:
            st.markdown("### น้ำแร่ที่ชอบ")
            if profile["liked"]:
                st.dataframe(pd.DataFrame(profile["liked"]), width="stretch", hide_index=True)
            else:
                st.info("ยังไม่มีน้ำแร่ที่ชอบ")
        with right:
            st.markdown("### ลูกค้าที่คล้ายกัน")
            if profile["similar"]:
                st.dataframe(pd.DataFrame(profile["similar"]), width="stretch", hide_index=True)
            else:
                st.info("ยังไม่มีลูกค้าที่คล้ายกัน")

elif page == "Recommendations":
    st.subheader("✨ น้ำแร่ที่แนะนำ")
    customer_id = customer_selector("rec_customer")
    top_n = st.slider("จำนวนคำแนะนำ", 3, 12, 6)
    rows = recommend_waters(customer_id, top_n)

    st.caption("score = จำนวนลูกค้าที่คล้ายกัน (SIMILAR_TO) ที่ชอบน้ำแร่นั้น โดยตัดน้ำแร่ที่ผู้ใช้ชอบอยู่แล้วออก")
    if not rows:
        st.info("ยังไม่มีคำแนะนำสำหรับผู้ใช้นี้")
    images = get_water_images() if rows else {}
    for i, row in enumerate(rows, start=1):
        names = ", ".join(row.get("similar_names") or [])
        with st.container(border=True, key=f"card_rec_{i}"):
            picture, details = st.columns([1, 6], vertical_alignment="center")
            picture.image(water_picture(row["water_id"], str(row["recommendation"]), images), width=120)
            details.markdown(
                f"""
                <span class="score-pill">#{i} · score {row['score']}</span>
                <h3 style="margin:.55rem 0 .2rem 0">{escape(str(row['recommendation']))}</h3>
                <div class="muted">{escape(str(row['water_id']))}</div>
                <p><b>เหตุผล:</b> ลูกค้าที่คล้ายกัน {row['score']} คนชอบ ({escape(names)})</p>
                """,
                unsafe_allow_html=True,
            )

elif page == "Customers":
    st.subheader("👤 จัดการลูกค้า")
    manage_nodes(
        noun="ลูกค้า",
        id_field="customer_id",
        rows=get_customers(),
        column_labels={"customer_id": "รหัส", "name": "ชื่อ", "likes": "ชอบน้ำแร่ (แบรนด์)", "similar": "ลูกค้าที่คล้ายกัน (คน)"},
        id_prefix="C",
        id_start=1,
        create=create_customer,
        update=update_customer,
        delete=delete_customer,
        delete_warning=lambda row: (
            f"การลบจะลบความสัมพันธ์ของลูกค้าคนนี้ด้วย: LIKES {row['likes']} เส้น "
            f"และ SIMILAR_TO {row['similar']} เส้น (ย้อนกลับไม่ได้)"
        ),
    )

elif page == "Waters":
    st.subheader("💧 จัดการน้ำแร่")
    waters = get_waters()
    images = get_water_images()
    if waters:
        gallery = st.columns(6)
        for i, w in enumerate(waters):
            with gallery[i % 6]:
                st.image(water_picture(w["water_id"], w["name"], images), width=140)
                st.caption(f"{w['water_id']} — {w['name']}")
        st.caption(
            "น้ำแร่ที่ยังไม่ได้อัปโหลดรูปจะใช้รูปประจำแบรนด์ตามชื่อ (ถ้ามีในโฟลเดอร์ images) "
            "ไม่เช่นนั้นจะแสดงรูปขวดที่ระบบวาดให้ อัปโหลดรูปเองได้ที่แท็บ เพิ่ม หรือ แก้ไข ด้านล่าง"
        )
    manage_nodes(
        noun="น้ำแร่",
        id_field="water_id",
        rows=waters,
        images=images,
        set_image=set_water_image,
        column_labels={"water_id": "รหัส", "name": "ชื่อ", "likes": "จำนวนคนชอบ"},
        id_prefix="W",
        id_start=101,
        create=create_water,
        update=update_water,
        delete=delete_water,
        delete_warning=lambda row: (
            f"การลบจะลบความสัมพันธ์ LIKES ที่ชี้มายังน้ำแร่นี้ด้วย {row['likes']} เส้น (ย้อนกลับไม่ได้)"
        ),
    )

elif page == "Relationships":
    st.subheader("🔗 จัดการความสัมพันธ์")
    customer_id = customer_selector("rel_customer")
    profile = get_profile(customer_id)
    if not profile:
        st.error(f"ไม่พบลูกค้า {customer_id} (อาจถูกลบไปแล้ว)")
        st.stop()
    st.caption("เลือกเพิ่มหรือเอาออกในช่องด้านล่าง แล้วกดบันทึก ระบบจะเพิ่ม/ลบความสัมพันธ์ให้ตรงกับที่เลือก")

    likes_tab, similar_tab = st.tabs(["LIKES (ลูกค้า → น้ำแร่)", "SIMILAR_TO (ลูกค้า ↔ ลูกค้า)"])

    with likes_tab:
        water_names = {w["water_id"]: w["name"] for w in get_waters()}
        current = [x["water_id"] for x in profile["liked"]]
        chosen = st.multiselect(
            f"น้ำแร่ที่ {profile['name']} ชอบ",
            list(water_names),
            default=current,
            format_func=lambda x: f"{x} — {water_names[x]}",
            key=f"likes_{customer_id}",
        )
        added, removed = sorted(set(chosen) - set(current)), sorted(set(current) - set(chosen))
        if added or removed:
            st.write(f"จะเพิ่ม {len(added)} เส้น: {', '.join(added) or '-'} · จะลบ {len(removed)} เส้น: {', '.join(removed) or '-'}")
        if st.button("บันทึก LIKES", type="primary", disabled=not (added or removed)):
            set_likes(customer_id, chosen)
            flash(f"บันทึก LIKES ของ {customer_id} แล้ว (เพิ่ม {len(added)} · ลบ {len(removed)})")
            st.rerun()

        st.markdown("#### LIKES ทั้งหมดในระบบ")
        st.dataframe(pd.DataFrame(list_likes()), width="stretch", hide_index=True)

    with similar_tab:
        other_names = {c["customer_id"]: c["name"] for c in get_customers() if c["customer_id"] != customer_id}
        current = [x["customer_id"] for x in profile["similar"]]
        chosen = st.multiselect(
            f"ลูกค้าที่คล้ายกับ {profile['name']}",
            list(other_names),
            default=current,
            format_func=lambda x: f"{x} — {other_names[x]}",
            key=f"similar_{customer_id}",
        )
        st.caption("SIMILAR_TO เป็นความสัมพันธ์สองทิศทาง: ถ้า A คล้าย B แล้ว B ก็คล้าย A ด้วย (เก็บเพียงหนึ่งเส้นต่อคู่)")
        added, removed = sorted(set(chosen) - set(current)), sorted(set(current) - set(chosen))
        if added or removed:
            st.write(f"จะเพิ่ม {len(added)} เส้น: {', '.join(added) or '-'} · จะลบ {len(removed)} เส้น: {', '.join(removed) or '-'}")
        if st.button("บันทึก SIMILAR_TO", type="primary", disabled=not (added or removed)):
            set_similar(customer_id, chosen)
            flash(f"บันทึก SIMILAR_TO ของ {customer_id} แล้ว (เพิ่ม {len(added)} · ลบ {len(removed)})")
            st.rerun()

        st.markdown("#### SIMILAR_TO ทั้งหมดในระบบ")
        st.dataframe(pd.DataFrame(list_similarities()), width="stretch", hide_index=True)

elif page == "Graph Explorer":
    st.subheader("🕸️ กราฟความสัมพันธ์")
    customer_id = customer_selector("graph_customer")
    rows = graph_neighborhood(customer_id)
    if not rows:
        st.info("ผู้ใช้นี้ยังไม่มีความสัมพันธ์ในกราฟ")
    else:
        fill = {"Customer": "#e0f2fe", "Water": "#cdf5ee"}
        dot = ["digraph G {", 'rankdir="LR";', 'node [shape=box, style="rounded,filled", fillcolor="#f8fafc", color="#7cc4d8", fontname="sans-serif"];',
               'edge [color="#4b7f95", fontcolor="#33596b", fontname="sans-serif"];']
        seen_nodes = set()
        for r in rows:
            for nid, label, name in [
                (r["source_id"], r["source_label"], r["source_name"]),
                (r["target_id"], r["target_label"], r["target_name"]),
            ]:
                if nid not in seen_nodes:
                    safe_name = str(name).replace("\\", "/").replace('"', "'")
                    safe_id = str(nid).replace("\\", "/").replace('"', "'")
                    border = ', penwidth=3, color="#0e7490"' if nid == customer_id else ""
                    dot.append(
                        f'"{safe_id}" [label="{safe_name}\\n:{label}", fillcolor="{fill.get(label, "#f8fafc")}"{border}];'
                    )
                    seen_nodes.add(nid)
            source = str(r["source_id"]).replace("\\", "/").replace('"', "'")
            target = str(r["target_id"]).replace("\\", "/").replace('"', "'")
            # SIMILAR_TO is treated as symmetric, so draw it without an arrowhead.
            direction = ", dir=none" if r["relationship"] == "SIMILAR_TO" else ""
            dot.append(f'"{source}" -> "{target}" [label="{r["relationship"]}"{direction}];')
        dot.append("}")
        st.graphviz_chart("\n".join(dot), width="stretch")
        with st.expander("ดูข้อมูล edge ที่ใช้วาดกราฟ"):
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

elif page == "Admin / Setup":
    st.subheader("⚙️ Setup ข้อมูลตัวอย่าง")
    st.warning("ปุ่มนี้ไม่ลบข้อมูลเดิม และใช้ MERGE จึงสามารถกดซ้ำได้ (ชื่อของรหัสตัวอย่าง C001–C010 / W101–W107 จะถูกตั้งกลับเป็นค่าตัวอย่าง)")
    st.markdown(
        """
        **Graph schema**
        - `(:Customer {customer_id, name})-[:SIMILAR_TO]-(:Customer)`
        - `(:Customer)-[:LIKES]->(:Water {water_id, name, image})`
        """
    )
    if st.button("สร้าง Constraint + Demo Data", type="primary", width="stretch"):
        with st.spinner("กำลังสร้างข้อมูล..."):
            seed_demo_data()
        flash("สร้างข้อมูลตัวอย่างเรียบร้อยแล้ว")
        st.rerun()
