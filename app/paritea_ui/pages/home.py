import streamlit as st

st.title("paritea")
st.write(
    "A user interface for [paritea](https://github.com/paritea/paritea), a toolkit for handling faults in "
    "Clifford ZX diagrams."
)

st.subheader("Pages")
st.page_link("paritea_ui/pages/pauli_webs.py", label="Pauli webs", icon=":material/hub:")
st.caption("Generate a diagram, compute its stabilising webs and detecting regions, and view them on the diagram.")
