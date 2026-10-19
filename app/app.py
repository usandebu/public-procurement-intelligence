import json
import os

import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.vector_search.client import VectorSearchClient

from procurement.formatting import format_deadline, format_euros
from procurement.rag import SEARCH_COLUMNS, answer_question

CATALOG = os.getenv("CATALOG", "procurement")
VS_ENDPOINT = os.getenv("VS_ENDPOINT", "procurement_vs")
GENERATOR = os.getenv("GENERATOR_ENDPOINT", "databricks-gpt-oss-120b")
CATALOG_PATH = f"/Volumes/{CATALOG}/gold/app_data/tender_catalog.json"
INDEX_NAME = f"{CATALOG}.silver.document_chunks_index"
NUM_RESULTS = 5

st.set_page_config(page_title="Asistente de pliegos", page_icon="📄", layout="wide")


@st.cache_resource
def workspace_client() -> WorkspaceClient:
    return WorkspaceClient()


@st.cache_resource
def search_index():
    client = workspace_client()
    vector_client = VectorSearchClient(
        workspace_url=client.config.host,
        service_principal_client_id=os.environ["DATABRICKS_CLIENT_ID"],
        service_principal_client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
        disable_notice=True,
    )
    return vector_client.get_index(endpoint_name=VS_ENDPOINT, index_name=INDEX_NAME)


@st.cache_data(ttl=600)
def load_catalog() -> list[dict]:
    response = workspace_client().files.download(CATALOG_PATH)
    return json.loads(response.contents.read())


def search(question: str, entry_id: str | None, num_results: int) -> list[list]:
    response = search_index().similarity_search(
        query_text=question,
        columns=SEARCH_COLUMNS,
        num_results=num_results,
        query_type="HYBRID",
        filters={"entry_id": entry_id} if entry_id else None,
    )
    return response["result"]["data_array"]


def complete(messages: list[dict]):
    response = workspace_client().api_client.do(
        "POST",
        f"/serving-endpoints/{GENERATOR}/invocations",
        body={"messages": messages, "max_tokens": 1500, "temperature": 0},
    )
    return response["choices"][0]["message"]["content"]


def tender_label(tender: dict) -> str:
    title = (tender.get("tender_title") or "")[:90]
    return f"{tender['folder_id']} - {title}"


st.title("Asistente de pliegos de licitación")
st.caption(
    "Preguntas en lenguaje natural sobre los pliegos (PCAP y PPT) de licitaciones públicas "
    "españolas de servicios informáticos. Las respuestas citan documento y página."
)

try:
    tenders = load_catalog()
except (DatabricksError, OSError, ValueError) as error:
    st.error(f"No se pudo cargar el catálogo de licitaciones: {error}")
    st.stop()

with st.sidebar:
    st.header("Licitación")
    scope = st.radio(
        "Dónde buscar",
        ["Una licitación (recomendado)", "Todas las licitaciones"],
        index=0,
    )
    selected = None
    if scope.startswith("Una"):
        selected = st.selectbox(
            "Elige una licitación", tenders, format_func=tender_label
        )
        st.markdown(f"**Organismo:** {selected['organ_name']}")
        if selected.get("budget"):
            st.markdown(
                f"**Presupuesto (sin IVA):** {format_euros(selected['budget'])}"
            )
        if selected.get("submission_deadline"):
            st.markdown(
                f"**Plazo de presentación:** {format_deadline(selected['submission_deadline'])}"
            )
        if selected.get("detail_url"):
            st.link_button(
                "Abrir en la Plataforma de Contratación", selected["detail_url"]
            )
    else:
        st.warning(
            "Buscar en todas las licitaciones es menos preciso: muchas cláusulas se repiten "
            "entre pliegos y pueden mezclarse."
        )
    st.caption(f"{len(tenders)} licitaciones con documentos indexados.")

question = st.text_input(
    "Tu pregunta",
    placeholder="Por ejemplo: ¿Cuál es el plazo de ejecución y se admite prórroga?",
)

if question:
    entry_id = selected["entry_id"] if selected else None
    with st.spinner("Buscando en los pliegos..."):
        result = answer_question(question, search, complete, entry_id, NUM_RESULTS)

    if result.is_refusal:
        st.info(result.text)
    else:
        st.markdown(result.text)

    if result.cited:
        st.subheader("Fuentes citadas")
        for source in result.cited:
            with st.expander(f"[{source.number}] {source.label}"):
                st.caption(f"{source.tender_title} - {source.organ_name}")
                st.write(source.text)
    st.caption(
        "Las respuestas las genera un modelo de lenguaje a partir de los fragmentos "
        "recuperados. Comprueba siempre la cita en el documento original."
    )
