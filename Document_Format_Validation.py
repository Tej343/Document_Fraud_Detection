import streamlit as st
import fitz
import tempfile
import pandas as pd
from collections import Counter
import os

st.set_page_config(page_title="Document Format Validation", layout="wide")
st.title("🔍 Intelligent Document Format Validation")

# --- Session State ---
if "trained_un_combos" not in st.session_state:
    st.session_state.trained_un_combos = Counter()

# --- Utility: Convert int color to hex ---
def int_to_hex(color_int):
    """Convert int color (from PyMuPDF) to hex"""
    r = (color_int >> 16) & 255
    g = (color_int >> 8) & 255
    b = color_int & 255
    return f"#{r:02X}{g:02X}{b:02X}"

# --- Utility: Extract Text Formatting Combos ---
def extract_formatting_combos(pdf_path):
    """Extract text formatting combos from a PDF using PyMuPDF."""
    combos = Counter()
    detailed_chars = []

    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc):
        dict_text = page.get_text("dict")
        for block in dict_text["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    font = span.get("font", "Unknown")
                    size = round(span.get("size", 0), 1)
                    color = span.get("color", 0)
                    color_hex = int_to_hex(color)
                    flags = span.get("flags", "")
                    ascender = span.get("ascender", 0)
                    descender = span.get("descender", 0)
                    bbox = span.get("bbox", [])  # Bounding box

                    un_com = f"{size}_{flags}_{font}_{color_hex}_{ascender}_{descender}"
                    combos[un_com] += 1

                    detailed_chars.append({
                        "text": text,
                        "page": page_num,
                        "un_com": un_com,
                        "color": color_hex,
                        "bbox": bbox,
                    })
    return combos, detailed_chars

# --- Utility: Extract Image Combos ---
def extract_image_combos(pdf_path):
    """Extract image combos from a PDF using PyMuPDF."""
    combos = Counter()

    doc = fitz.open(pdf_path)
    for page in doc:
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            ext = base_image.get("ext", "unk")
            cs = base_image.get("colorspace", "unk")
            bpc = base_image.get("bpc", 0)
            size = len(base_image.get("image", b""))
            un_comb_img = f"IMG_{width}_{height}_{ext}_{cs}_0_0_{bpc}_{size}"
            combos[un_comb_img] += 1
    return combos

# ===========================
#  STEP 1: TRAINING
# ===========================
st.header("📘 Step 1: Train on Genuine PDFs")
train_files = st.file_uploader("Upload genuine documents", type=["pdf"], accept_multiple_files=True)

if st.button("📚 Train Model"):
    if not train_files:
        st.warning("Please upload at least one PDF to train.")
    else:
        st.session_state.trained_un_combos = Counter()
        for file in train_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                text_combos, _ = extract_formatting_combos(tmp.name)
                image_combos = extract_image_combos(tmp.name)
                combined_combos = text_combos + image_combos
                st.session_state.trained_un_combos.update(combined_combos)

        st.success("✅ Model trained!")
        df_train = pd.DataFrame(st.session_state.trained_un_combos.items(), columns=["Combo", "Count"])
        # Optional: Show training combos
        # st.dataframe(df_train.sort_values(by="Count", ascending=False), use_container_width=True)

# ===========================
#  STEP 2: TESTING
# ===========================
st.header("📄 Step 2: Upload Test PDF")
test_file = st.file_uploader("Upload document to test", type=["pdf"], key="test")

if st.button("🚨 Validate Test Document"):
    if not st.session_state.trained_un_combos:
        st.warning("Please train the model first.")
    elif not test_file:
        st.warning("Please upload a test PDF.")
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(test_file.read())
            test_pdf_path = tmp.name
            test_text_combos, detailed_chars = extract_formatting_combos(test_pdf_path)
            test_image_combos = extract_image_combos(test_pdf_path)
            test_combos = test_text_combos + test_image_combos

        trained_set = set(st.session_state.trained_un_combos.keys())
        test_set = set(test_combos.keys())

        unexpected = test_set - trained_set
        missing = trained_set - test_set

        total_used = sum(test_combos.values())
        unexpected_used = sum(test_combos[c] for c in unexpected)
        fraud_score = round((unexpected_used / total_used) * 100, 2) if total_used else 0

        # st.subheader("🎯 Fraud Risk Score")
        # st.metric(label="Fraud Score", value=f"{fraud_score}%", delta=None)

        # Collect suspicious characters
        suspicious_chars = [c for c in detailed_chars if c["un_com"] in unexpected]

        if suspicious_chars:
            # st.subheader("🚩 Suspicious Characters (Unexpected Formatting)")
            st.subheader("🚩 Suspicious Content Found!!")
            sus_df = pd.DataFrame(suspicious_chars)
            st.dataframe(sus_df, use_container_width=True)

            # Annotate PDF with red boxes
            doc = fitz.open(test_pdf_path)
            for char in suspicious_chars:
                page = doc[char["page"]]
                rect = fitz.Rect(char["bbox"])
                page.draw_rect(rect, color=(1, 0, 0), width=1.5)

            annotated_path = test_pdf_path.replace(".pdf", "_annotated.pdf")
            doc.save(annotated_path)

            st.success("🔴 Inconsistencies highlighted in annotated PDF.")

            with open(annotated_path, "rb") as f:
                st.download_button("⬇️ Download Annotated PDF", f, file_name="annotated_test.pdf", mime="application/pdf")
        else:
            st.success("✅ No unexpected formatting found in test document.")

        # Show summary of unexpected/missing combos
        # col1, col2 = st.columns(2)

        # with col1:
        #     st.subheader("❌ Unexpected Combos in Test")
        #     if unexpected:
        #         df_unexp = pd.DataFrame([(c, test_combos[c]) for c in unexpected], columns=["Combo", "Count"])
        #         st.dataframe(df_unexp.sort_values(by="Count", ascending=False), use_container_width=True)
        #     else:
        #         st.info("All test combos were seen in training.")

        # with col2:
        #     st.subheader("⚠️ Missing Expected Combos")
        #     if missing:
        #         df_missing = pd.DataFrame([(c, st.session_state.trained_un_combos[c]) for c in missing], columns=["Combo", "Expected Count"])
        #         st.dataframe(df_missing.sort_values(by="Expected Count", ascending=False), use_container_width=True)
        #     else:
        #         st.info("All trained combos were present in test document.")

st.markdown(
    """
    <div style='font-size:17px; color:#666; font-style:italic;'>
        Ideated, Developed, and Created by Madugula Sai Tej!
    </div>
    """,
    unsafe_allow_html=True,
)
