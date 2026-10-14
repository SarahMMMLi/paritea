import streamlit as st

from paritea_ui.components import cached_pauli_webs, diagram_picker, report_errors
from paritea_ui.core import diagram_summary
from paritea_ui.drawing import draw_diagram

st.title("Pauli webs")
st.write(
    "**Stabilising webs** describe the stabilisers of the diagram; **detecting regions** are webs that do not reach "
    "the boundary, so every fault that anticommutes with one is detected."
)

with st.sidebar:
    spec = diagram_picker("webs")

with report_errors("Building the diagram and computing its Pauli webs"):
    result = cached_pauli_webs(spec)
diagram = result.diagram

for column, (label, value) in zip(st.columns(6), diagram_summary(diagram).items()):
    column.metric(label, value)

webs_by_kind = {
    f"Stabilising webs ({len(result.stabilisers)})": result.stabilisers,
    f"Detecting regions ({len(result.regions)})": result.regions,
    "Diagram only": [],
}
kind = st.radio("Show", list(webs_by_kind), horizontal=True)
webs = webs_by_kind[kind]

web = None
if webs:
    index = st.number_input("Web", min_value=1, max_value=len(webs), value=1, help="Which web to highlight")
    web = webs[index - 1]
elif kind != "Diagram only":
    st.info("This diagram has none.")

show_phases = st.toggle("Show spider phases", value=diagram.num_nodes() <= 200)
st.pyplot(draw_diagram(diagram, web=web, show_phases=show_phases))

if web is not None:
    with st.expander("Web as edge → Pauli"):
        st.dataframe(
            [
                {"Edge": e, "Endpoints": str(diagram.get_edge_endpoints_by_index(e)), "Pauli": str(p)}
                for e, p in web.items()
            ],
            hide_index=True,
        )
