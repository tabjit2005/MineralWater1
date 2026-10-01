from __future__ import annotations

from html import escape
from typing import Any, Callable

import pandas as pd
import streamlit as st

from neo4j_service import (
    create_customer,
    create_water,
    delete_customer,
    delete_water,
    get_customers,
    get_dashboard_metrics,
    get_profile,
    get_waters,
    graph_neighborhood,
    list_likes,
    list_similarities,
    ping,
    recommend_waters,
    seed_demo_data,
    set_likes,
    set_similar,
    update_customer,
    update_water,
)

st.set_page_config(
    page_title="Mineral Water Recommender",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
      .hero {
        padding: 1.4rem 1.6rem; border-radius: 22px;
        background: linear-gradient(120deg, #111827 0%, #1f2937 55%, #0f766e 100%);
        color: white; margin-bottom: 1rem;
      }
      .hero h1 {margin:0; font-size:2.15rem;}
      .hero p {opacity:.88; margin:.35rem 0 0 0;}
      .water-card {
        padding: 1rem 1.1rem; border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px; margin-bottom: .75rem;
      }
      .score-pill {
        display:inline-block; padding:.2rem .55rem; border-radius:999px;
        background:#0f766e; color:white; font-size:.8rem; font-weight:700;
      }
      .muted {opacity:.72; font-size:.9rem;}
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
        st.info("ยังไม่มีข้อมูลลูกค้า กรุณาไปหน้า Admin / Setup แล้วสร้างข้อมูลตัวอย่าง หรือเพิ่มลูกค้าที่หน้า Customers")
        st.stop()
    labels = {f"{x['customer_id']} — {x['name']}": x["customer_id"] for x in customers}
    chosen = st.selectbox("เลือกผู้ใช้", list(labels), key=key)
    return labels[chosen]


def next_id(existing: list[str], prefix: str, start: int) -> str:
    numbers = [int(x[len(prefix):]) for x in existing if x.startswith(prefix) and x[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers) + 1 if numbers else start):03d}"


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
) -> None:
    """Table + add / edit / delete tabs for one node label (Customer or Water)."""
    st.write(f"ทั้งหมด {len(rows)} รายการ")
    if rows:
        st.dataframe(pd.DataFrame(rows).rename(columns=column_labels), width="stretch", hide_index=True)

    by_id = {row[id_field]: row for row in rows}
    add_tab, edit_tab, delete_tab = st.tabs(["➕ เพิ่ม", "✏️ แก้ไข", "🗑️ ลบ"])

    with add_tab:
        with st.form(f"add_{id_field}"):
            new_id = st.text_input(f"รหัส{noun} ({id_field})", value=next_id(list(by_id), id_prefix, id_start))
            new_name = st.text_input(f"ชื่อ{noun}")
            submitted = st.form_submit_button("เพิ่ม", type="primary")
        if submitted:
            new_id, new_name = new_id.strip(), new_name.strip()
            if not new_id or not new_name:
                st.error("กรุณากรอกทั้งรหัสและชื่อ")
            elif not create(new_id, new_name):
                st.error(f"รหัส {new_id} ถูกใช้แล้ว กรุณาใช้รหัสอื่น")
            else:
                flash(f"เพิ่ม{noun} {new_id} — {new_name} แล้ว")
                st.rerun()

    if not rows:
        edit_tab.info(f"ยังไม่มี{noun}ให้แก้ไข")
        delete_tab.info(f"ยังไม่มี{noun}ให้ลบ")
        return

    def label(item_id: str) -> str:
        return f"{item_id} — {by_id[item_id]['name']}"

    with edit_tab:
        edit_id = st.selectbox(f"เลือก{noun}ที่จะแก้ไข", list(by_id), format_func=label, key=f"edit_{id_field}")
        with st.form(f"edit_form_{id_field}"):
            st.text_input(f"รหัส{noun} ({id_field})", value=edit_id, disabled=True)
            edited_name = st.text_input(f"ชื่อ{noun}", value=by_id[edit_id]["name"])
            submitted = st.form_submit_button("บันทึกการแก้ไข", type="primary")
        if submitted:
            edited_name = edited_name.strip()
            if not edited_name:
                st.error("ชื่อห้ามว่าง")
            elif not update(edit_id, edited_name):
                st.error(f"ไม่พบ{noun} {edit_id} (อาจถูกลบไปแล้ว)")
            else:
                flash(f"แก้ไข{noun} {edit_id} เป็น {edited_name} แล้ว")
                st.rerun()

    with delete_tab:
        delete_id = st.selectbox(f"เลือก{noun}ที่จะลบ", list(by_id), format_func=label, key=f"delete_{id_field}")
        st.warning(delete_warning(by_id[delete_id]))
        confirmed = st.checkbox(f"ยืนยันการลบ {label(delete_id)}", key=f"confirm_{id_field}_{delete_id}")
        if st.button("ลบ", type="primary", disabled=not confirmed, key=f"delete_button_{id_field}"):
            if delete(delete_id):
                flash(f"ลบ{noun} {label(delete_id)} แล้ว")
            st.rerun()


require_connection()

with st.sidebar:
    st.markdown("## 💧 MineralWater")
    st.caption("Neo4j Aura + Streamlit")
    page = st.radio(
        "เมนู",
        ["Dashboard", "Recommendations", "Customers", "Waters", "Relationships", "Graph Explorer", "Admin / Setup"],
    )
    st.divider()
    st.caption("Bachelor-level Graph Database Project")

st.markdown(
    """
    <div class="hero">
      <h1>💧 Mineral Water Recommendation System</h1>
      <p>ระบบแนะนำน้ำแร่ด้วย Graph Database จากลูกค้าที่มีรสนิยมคล้ายกัน</p>
    </div>
    """,
    unsafe_allow_html=True,
)

show_flash()

if page == "Dashboard":
    st.subheader("ภาพรวมระบบ")
    m = get_dashboard_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", m.get("customers", 0))
    c2.metric("Waters", m.get("waters", 0))
    c3.metric("LIKES relationships", m.get("likes", 0))
    c4.metric("SIMILAR_TO relationships", m.get("similarities", 0))

    waters = sorted(get_waters(), key=lambda w: (-w["likes"], w["name"]))
    if waters:
        st.markdown("### ความนิยมของน้ำแร่")
        st.dataframe(
            pd.DataFrame(waters).rename(columns={"water_id": "รหัส", "name": "น้ำแร่", "likes": "จำนวนคนชอบ"}),
            column_config={
                "จำนวนคนชอบ": st.column_config.ProgressColumn(
                    format="%d", min_value=0, max_value=max(1, waters[0]["likes"])
                )
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
    for i, row in enumerate(rows, start=1):
        names = ", ".join(row.get("similar_names") or [])
        st.markdown(
            f"""
            <div class="water-card">
              <span class="score-pill">#{i} · score {row['score']}</span>
              <h3 style="margin:.55rem 0 .2rem 0">{escape(str(row['recommendation']))}</h3>
              <div class="muted">{escape(str(row['water_id']))}</div>
              <p><b>เหตุผล:</b> ลูกค้าที่คล้ายกัน {row['score']} คนชอบ ({escape(names)})</p>
            </div>
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
    manage_nodes(
        noun="น้ำแร่",
        id_field="water_id",
        rows=get_waters(),
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
    st.subheader("🕸️ Graph Explorer")
    customer_id = customer_selector("graph_customer")
    rows = graph_neighborhood(customer_id)
    if not rows:
        st.info("ผู้ใช้นี้ยังไม่มีความสัมพันธ์ในกราฟ")
    else:
        fill = {"Customer": "#dbeafe", "Water": "#ccfbf1"}
        dot = ["digraph G {", 'rankdir="LR";', 'node [shape=box, style="rounded,filled", fillcolor="#f8fafc"];']
        seen_nodes = set()
        for r in rows:
            for nid, label, name in [
                (r["source_id"], r["source_label"], r["source_name"]),
                (r["target_id"], r["target_label"], r["target_name"]),
            ]:
                if nid not in seen_nodes:
                    safe_name = str(name).replace("\\", "/").replace('"', "'")
                    safe_id = str(nid).replace("\\", "/").replace('"', "'")
                    border = ', penwidth=3, color="#0f766e"' if nid == customer_id else ""
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
        - `(:Customer)-[:LIKES]->(:Water {water_id, name})`
        """
    )
    if st.button("สร้าง Constraint + Demo Data", type="primary", width="stretch"):
        with st.spinner("กำลังสร้างข้อมูล..."):
            seed_demo_data()
        flash("สร้างข้อมูลตัวอย่างเรียบร้อยแล้ว")
        st.rerun()
