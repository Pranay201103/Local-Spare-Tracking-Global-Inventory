import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from sqlalchemy import text

# --- DATABASE CONNECTION ---
# This looks for [connections.postgresql] in your Streamlit Secrets
conn = st.connection("postgresql", type="sql")

# --- 2. HELPERS ---
def get_display_fields(row):
    row_dict = row.to_dict()
    exclude = ['id', 'eq_id', 'eq_type', 'qty', 'spare_type']
    return {k.replace('_', ' ').title(): v for k, v in row_dict.items() if v and str(v) != 'nan' and k not in exclude}

# --- 3. APP UI ---
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
        # (Your original form logic here...)
        eq_id = st.text_input("Equipment ID:", key="add_id").upper().strip()
        eq_type = st.selectbox("Equipment Type:", ["Pump", "Compressor", "AFC", "Fan"])
        spare_type = st.selectbox("Spare Type:", ["Seal", "Bearing", "Mechanical spares", "Valve"])
        qty = st.number_input("Total Quantity:", min_value=0)
        loc = st.text_input("Storage Location:")
        if st.button("Save Entry"):
            with conn.session as s:
                s.execute(text("INSERT INTO inventory (eq_id, eq_type, spare_type, qty, storage_loc) VALUES (:id, :type, :spare, :qty, :loc)"),
                          {"id": eq_id, "type": eq_type, "spare": spare_type, "qty": qty, "loc": loc})
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
                    new_q = st.number_input(f"New Qty for {r['spare_type']}", value=int(r['qty']), key=f"q_{r['id']}")
                    rsn = st.text_input(f"Reason for {r['spare_type']}", key=f"r_{r['id']}")
                    u_data[r['id']] = (new_q, rsn, r['spare_type'], r['qty'])

                if st.form_submit_button("Save Updates"):
                    with conn.session as s:
                        for id, (q, rsn, sp, old_q) in u_data.items():
                            if int(q) != int(old_q):
                                s.execute(text("UPDATE inventory SET qty = :q WHERE id = :id"), {"q": q, "id": id})
                                s.execute(text("INSERT INTO logs (date, equipment, spare, old_qty, new_qty, reason) VALUES (:d, :eq, :sp, :o, :n, :rsn)"),
                                          {"d": datetime.datetime.now(), "eq": selected_eq, "sp": sp, "o": old_q, "n": q, "rsn": rsn})
                        s.commit()
                    st.rerun()

# --- HISTORY ---
elif page == "History":
    st.title("📜 Transaction Log")
    log_df = conn.query("SELECT * FROM logs ORDER BY date DESC")
    st.dataframe(log_df, use_container_width=True)

# --- SPARE TRACKING ---
elif page == "Spare Tracking":
    st.title("📊 Activity Dashboard")
    log_df = conn.query("SELECT * FROM logs")
    if not log_df.empty:
        sel_eqs = st.multiselect("Filter by Equipment:", log_df['equipment'].unique())
        if sel_eqs: log_df = log_df[log_df['equipment'].isin(sel_eqs)]
        for _, row in log_df.sort_values(by='date', ascending=False).iterrows():
            with st.container(border=True):
                st.write(f"**{row['equipment']}** | {row['date']}")
                st.write(f"Item: {row['spare']} | Change: {row['old_qty']} -> {row['new_qty']}")
