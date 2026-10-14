"""Entry point of the paritea UI. Run from this directory with: uv run streamlit run streamlit_app.py"""

import streamlit as st

st.set_page_config(page_title="paritea", page_icon=":material/hub:", layout="wide")

pages = [
    st.Page("paritea_ui/pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("paritea_ui/pages/pauli_webs.py", title="Pauli webs", icon=":material/hub:"),
]
st.navigation(pages).run()
