import streamlit as st
import pandas as pd
from sqlalchemy import text

# Connects to PostgreSQL using the secrets you will add in Step 3
conn = st.connection("postgresql", type="sql")

st.title("Inventory Manager")

# Simple Example: Add Item
with st.form("add_item"):
    eq_id = st.text_input("Equipment ID")
    qty = st.number_input("Quantity", 0)
    if st.form_submit_button("Save"):
        with conn.session as s:
            s.execute(text("INSERT INTO inventory (eq_id, qty) VALUES (:id, :q)"), {"id": eq_id, "q": qty})
            s.commit()
        st.success("Added!")

# Display data
st.subheader("Inventory")
df = conn.query("SELECT * FROM inventory;")
st.dataframe(df)