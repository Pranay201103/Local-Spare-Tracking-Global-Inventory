import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from sqlalchemy import text

# Initialize Postgres Connection
conn = st.connection("postgresql", type="sql")

# --- HELPERS ---
def get_display_fields(row):
    row_dict = row.to_dict()
    # Fields that shouldn't appear in the expander detail view
    exclude = ['id', 'eq_id', 'eq_type', 'qty', 'spare_type', 'description']
    return {k.replace('_', ' ').title(): v for k, v in row_dict.items() if v and str(v) != 'nan' and k not in exclude}

# --- UI CONFIG ---
st.set_page_config(layout="wide", page_title="Inventory Management")
if 'msg' not in st.session_state: st.session_state.msg = None
page = st.sidebar.radio("Navigation", ["Dashboard", "Manage Inventory", "History", "Spare Tracking"])

# --- DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Equipment Inventory Dashboard")
    all_df = conn.query("SELECT * FROM inventory")
    if not all_df.empty:
        c1, c2 = st.columns(2)
        spare_qty = all_df.groupby('spare_type')['qty'].sum().reset_index()
        fig1 = px.bar(spare_qty, x='spare_type', y='qty', title="Total Qty by Spare Type", color='spare_type', text_auto=True)
        c1.plotly_chart(fig1, use_container_width=True)
        eq_qty = all_df.groupby('eq_type')['qty'].sum().reset_index()
        fig2 = px.pie(eq_qty, names='eq_type', values='qty', title="Qty by Equipment")
        c2.plotly_chart(fig2, use_container_width=True)
    
    st.divider()
    search = st.text_input("🔍 Search Equipment ID:").upper().strip()
    if search:
        df = conn.query(f"SELECT * FROM inventory WHERE eq_id ILIKE '%%{search}%%'")
        if not df.empty:
            for spare in df['spare_type'].unique():
                st.subheader(f"📦 {spare}s")
                for _, row in df[df['spare_type'] == spare].iterrows():
                    header = row['description'] if row['description'] else "Mechanical Spare"
                    with st.expander(f"📍 {header} | Qty: {row['qty']}"):
                        for k, v in get_display_fields(row).items(): st.markdown(f"**{k}:** {v}")
        else: st.warning("No items found.")

# --- MANAGE INVENTORY ---
elif page == "Manage Inventory":
    st.title("➕ Manage Inventory")
    if st.session_state.msg: st.success(st.session_state.msg); st.session_state.msg = None
    tab1, tab2 = st.tabs(["➕ Add New", "🔄 Update Quantity"])
    
    with tab1:
        eq_id = st.text_input("Equipment ID:", key="add_id").upper().strip()
        eq_type = st.selectbox("Equipment Type:", ["Pump", "Compressor", "AFC", "Fan"])
        options = {"Pump": ["Seal", "Bearing", "Mechanical spares"], "Compressor": ["Valve", "Bearing", "Mechanical spares"], "AFC": ["Belt", "Pulley", "Bearing", "Mechanical spares"]}
        spare_type = st.selectbox("Spare Type:", options.get(eq_type, ["Bearing", "Mechanical spares"]))
        
        subtype = cat = origin = vendor = ref_date = item_detail = bearing_no = description = pulley_type = pulley_desc = seal_oem = valve_oem = None
        
        # Logic preserved from your original code
        if eq_type == "Pump" and spare_type == "Seal":
            subtype = st.selectbox("Sub-type:", ["Cartridge seal", "Seal spare"])
            if subtype == "Seal spare": cat = st.selectbox("Category:", ["Faces", "Packings"]); item_detail = st.text_input(f"Enter {cat} details:")
            seal_oem = st.text_input("Seal OEM:")
            origin = st.selectbox("Origin:", ["OEM", "Locally made", "Locally refurbished"])
        elif eq_type == "Compressor" and spare_type == "Valve":
            subtype = st.selectbox("Valve Type:", ["Suction valve", "Discharge valve"])
            origin = st.selectbox("Condition:", ["New", "Refurbished"])
            if origin == "New": valve_oem = st.text_input("Valve OEM:")
            else: vendor = st.text_input("Vendor Name:"); ref_date = str(st.date_input("Refurbishment Date:"))
        elif spare_type == "Bearing": bearing_no = st.text_input("Bearing Number:"); origin = st.selectbox("Origin:", ["OEM", "Locally made"])
        elif spare_type == "Mechanical spares": description = st.text_input("Description:"); origin = st.selectbox("Origin:", ["OEM", "Locally made"])
        elif eq_type == "AFC" and spare_type == "Pulley": pulley_type = st.selectbox("Pulley Type:", ["Motor pulley", "Fan pulley"]); pulley_desc = st.text_input("Pulley Description:"); origin = st.selectbox("Origin:", ["OEM", "Locally made"])
        
        if origin and origin != "OEM" and spare_type != "Valve": vendor = st.text_input("Vendor Name:"); ref_date = str(st.date_input("Date:"))
        qty = st.number_input("Total Quantity:", min_value=0)
        loc = st.text_input("Storage Location:")

        if st.button("Save Entry"):
            with conn.session as s:
                s.execute(text("""INSERT INTO inventory (eq_id, eq_type, spare_type, subtype, category, item_detail, origin, vendor, ref_date, qty, storage_loc, bearing_no, description, pulley_type, pulley_desc, seal_oem, valve_oem) 
                               VALUES (:id, :et, :st, :sub, :cat, :det, :ori, :ven, :ref, :qty, :loc, :bn, :desc, :pt, :pd, :soem, :voem)"""),
                          {"id": eq_id, "et": eq_type, "st": spare_type, "sub": subtype, "cat": cat, "det": item_detail, "ori": origin, "ven": vendor, "ref": ref_date, "qty": qty, "loc": loc, "bn": bearing_no, "desc": description, "pt": pulley_type, "pd": pulley_desc, "soem": seal_oem, "voem": valve_oem})
                s.commit()
            st.session_state.msg = "Added successfully!"; st.rerun()

    with tab2:
        df = conn.query("SELECT DISTINCT eq_id FROM inventory")
        selected_eq = st.selectbox("Select Equipment ID:", [""] + list(df['eq_id'].unique()))
        if selected_eq:
            eq_df = conn.query(f"SELECT * FROM inventory WHERE eq_id = '{selected_eq}'")
            with st.form("update_form"):
                u_data = {}
                for i, r in eq_df.iterrows():
                    new_q = st.number_input(f"New Qty ({r['spare_type']})", value=int(r['qty']), key=f"q_{r['id']}")
                    rsn = st.text_input(f"Reason ({r['spare_type']})", key=f"r_{r['id']}")
                    u_data[r['id']] = (new_q, rsn, r['spare_type'], r['qty'])

                if st.form_submit_button("Save Updates"):
                    with conn.session as s:
                        for id, (q, rsn, sp, old_q) in u_data.items():
                            if int(q) != int(old_q):
                                s.execute(text("UPDATE inventory SET qty = :q WHERE id = :id"), {"q": q, "id": id})
                                s.execute(text("INSERT INTO logs (date, equipment, spare, old_qty, new_qty, reason) VALUES (NOW(), :eq, :sp, :o, :n, :rsn)"),
                                          {"eq": selected_eq, "sp": f"{sp} | Details updated", "o": old_q, "n": q, "rsn": rsn})
                        s.commit()
                    st.rerun()

# --- HISTORY & TRACKING ---
elif page == "History":
    st.title("📜 Transaction Log")
    log_df = conn.query("SELECT * FROM logs ORDER BY date DESC")
    st.dataframe(log_df, use_container_width=True)

elif page == "Spare Tracking":
    st.title("📊 Activity Dashboard")
    log_df = conn.query("SELECT * FROM logs ORDER BY date DESC")
    for _, row in log_df.head(10).iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            col1.write(f"**{row['equipment']}**\n{row['date']}")
            col2.write(f"Change: {row['old_qty']} ➔ {row['new_qty']} | Reason: {row['reason']}")
