
import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="Public Transit Route Optimization",
    page_icon="🚌",
    layout="wide"
)

st.title("🚌 Public Transit Route Optimization")
st.write("AI-Powered Bus Route Analysis Dashboard")

# Load route profiles
file_path = "outputs/route_profiles.csv"

if os.path.exists(file_path):
    df = pd.read_csv(file_path)

    st.success("Route dataset loaded successfully!")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Bus Routes", len(df))

    with col2:
        st.metric("Total Features", len(df.columns))

    st.subheader("Bus Route Dataset")
    st.dataframe(df, use_container_width=True)

    st.subheader("Route Performance Analysis")

    possible_labels = [
        col for col in df.columns
        if "performance" in col.lower()
        or "label" in col.lower()
    ]

    if possible_labels:
        label_col = possible_labels[0]
        st.bar_chart(df[label_col].value_counts())

else:
    st.error("Route profiles not found. Run python train_pipeline.py first.")
