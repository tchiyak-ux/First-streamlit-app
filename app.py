import io
import re

import streamlit as st
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="Outil PDF", page_icon="📄", layout="centered")

st.title("📄 Outil PDF : fusion & extraction")
st.caption("Fusionnez plusieurs PDF ou extrayez des pages, puis téléchargez le résultat.")


# ----------------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------------
def parse_page_ranges(text: str, total_pages: int) -> list[int]:
    """
    Convertit une chaîne comme "1-3, 5, 8-10" en liste d'indices (base 0).
    Lève ValueError si la saisie est invalide ou hors limites.
    L'ordre saisi est conservé (ex. "5, 1-2" donne 5, 1, 2).
    """
    text = text.strip()
    if not text:
        raise ValueError("Veuillez saisir au moins une page.")

    pages: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue

        match_range = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        match_single = re.fullmatch(r"\d+", part)

        if match_range:
            start, end = int(match_range.group(1)), int(match_range.group(2))
            if start > end:
                raise ValueError(f"Plage invalide : « {part} » (début > fin).")
            numbers = range(start, end + 1)
        elif match_single:
            numbers = [int(part)]
        else:
            raise ValueError(f"Format invalide : « {part} ». Exemple : 1-3, 5, 8-10")

        for n in numbers:
            if n < 1 or n > total_pages:
                raise ValueError(
                    f"La page {n} n'existe pas (le document a {total_pages} pages)."
                )
            pages.append(n - 1)

    return pages


def writer_to_bytes(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def read_pdf(uploaded_file) -> PdfReader:
    """Lit un PDF uploadé, et gère les fichiers protégés par mot de passe."""
    reader = PdfReader(uploaded_file)
    if reader.is_encrypted:
        # Tentative de déchiffrement avec mot de passe vide
        if reader.decrypt("") == 0:
            raise ValueError(f"« {uploaded_file.name} » est protégé par un mot de passe.")
    return reader


# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------
tab_merge, tab_extract = st.tabs(["🔗 Fusionner", "✂️ Extraire des pages"])

# ============================== FUSION ======================================
with tab_merge:
    st.subheader("Fusionner plusieurs PDF")

    files = st.file_uploader(
        "Sélectionnez au moins 2 fichiers PDF",
        type="pdf",
        accept_multiple_files=True,
        key="merge_uploader",
    )

    if files:
        st.markdown("**Ordre de fusion**")
        st.caption("Modifiez le numéro d'ordre pour réorganiser les fichiers.")

        orders = []
        for i, f in enumerate(files):
            col1, col2 = st.columns([1, 5])
            order = col1.number_input(
                "Ordre",
                min_value=1,
                max_value=len(files),
                value=i + 1,
                key=f"order_{f.name}_{i}",
                label_visibility="collapsed",
            )
            col2.write(f"📄 {f.name}")
            orders.append(order)

        # Tri stable : à numéro égal, l'ordre d'upload est conservé
        sorted_files = [f for _, f in sorted(zip(orders, files), key=lambda x: x[0])]

        if st.button("Fusionner", type="primary", key="merge_btn"):
            if len(files) < 2:
                st.warning("Ajoutez au moins 2 fichiers pour fusionner.")
            else:
                try:
                    writer = PdfWriter()
                    total = 0
                    for f in sorted_files:
                        reader = read_pdf(f)
                        for page in reader.pages:
                            writer.add_page(page)
                        total += len(reader.pages)

                    st.session_state["merged_pdf"] = writer_to_bytes(writer)
                    st.session_state["merged_pages"] = total
                except Exception as e:
                    st.session_state.pop("merged_pdf", None)
                    st.error(f"Erreur lors de la fusion : {e}")

    if "merged_pdf" in st.session_state and files:
        st.success(
            f"Fusion réussie : {st.session_state['merged_pages']} pages au total."
        )
        st.download_button(
            "⬇️ Télécharger le PDF fusionné",
            data=st.session_state["merged_pdf"],
            file_name="fusion.pdf",
            mime="application/pdf",
        )

# ============================== EXTRACTION ==================================
with tab_extract:
    st.subheader("Extraire des pages d'un PDF")

    file = st.file_uploader(
        "Sélectionnez un fichier PDF",
        type="pdf",
        key="extract_uploader",
    )

    if file:
        try:
            reader = read_pdf(file)
            n_pages = len(reader.pages)
            st.info(f"Le document contient **{n_pages}** page(s).")

            ranges = st.text_input(
                "Pages à extraire",
                placeholder="Ex. : 1-3, 5, 8-10",
                help="Séparez les pages ou plages par des virgules. "
                "L'ordre saisi est conservé.",
            )

            if st.button("Extraire", type="primary", key="extract_btn"):
                try:
                    indices = parse_page_ranges(ranges, n_pages)
                    writer = PdfWriter()
                    for idx in indices:
                        writer.add_page(reader.pages[idx])

                    st.session_state["extracted_pdf"] = writer_to_bytes(writer)
                    st.session_state["extracted_count"] = len(indices)
                except ValueError as e:
                    st.session_state.pop("extracted_pdf", None)
                    st.error(str(e))

            if "extracted_pdf" in st.session_state:
                st.success(
                    f"{st.session_state['extracted_count']} page(s) extraite(s)."
                )
                st.download_button(
                    "⬇️ Télécharger le PDF extrait",
                    data=st.session_state["extracted_pdf"],
                    file_name="extrait.pdf",
                    mime="application/pdf",
                )
        except Exception as e:
            st.error(f"Impossible de lire ce PDF : {e}")
