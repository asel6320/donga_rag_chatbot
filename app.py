from urllib.parse import quote

import streamlit as st

import answer as rag


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Smart University Knowledge Hub",
    page_icon="🎓"
)

st.title("🎓 Smart University Knowledge Hub")
st.caption("Answers come only from official university documents.")


# ============================================================
# SIDEBAR
# ============================================================

NOT_SET = "— choose —"

with st.sidebar:

    st.header("Who are you?")

    st.write(
        "Rules differ between groups, "
        "so please choose before asking."
    )

    level = st.selectbox(
        "Program level",
        [
            NOT_SET,
            "undergraduate",
            "graduate"
        ]
    )

    student_type = st.selectbox(
        "Student type",
        [
            NOT_SET,
            "international",
            "domestic"
        ]
    )

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()


group_ready = NOT_SET not in (
    level,
    student_type
)


# ============================================================
# HELPERS
# ============================================================

def pdf_link(src: dict) -> str | None:
    """
    Return a link to the original source.

    Web sources open their URL.
    PDF sources open the cited PDF page.
    """

    # Web source
    if src.get("url"):
        return src["url"]

    # No PDF file available
    if not src.get("file"):
        return None

    page_number = src.get("page_number")

    if page_number:
        return (
            f"/app/static/{quote(src['file'])}"
            f"#page={page_number}"
        )

    return f"/app/static/{quote(src['file'])}"


def show_sources(sources: list[dict]):
    """
    Display the passages used by the RAG answer.
    """

    if not sources:
        return

    st.markdown("**Sources**")

    for s in sources:

        printed = (
            f", printed p.{s['printed_page']}"
            if s.get("printed_page")
            else ""
        )

        page_number = s.get("page_number")

        # Different label for web vs PDF sources
        if s.get("url"):

            label = (
                f"[{s['n']}] "
                f"{s['source']} — "
                f"{s['section']}"
            )

        else:

            label = (
                f"[{s['n']}] "
                f"{s['source']} — "
                f"{s['section']} "
                f"(PDF p.{page_number}{printed})"
            )

        link = pdf_link(s)

        if link:
            st.markdown(f"[{label}]({link})")
        else:
            st.markdown(label)

        # Show retrieved passage
        with st.expander(
            f"Show passage [{s['n']}]"
        ):
            st.text(s.get("snippet", ""))


# ============================================================
# CHAT HISTORY
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

        show_sources(
            message.get("sources", [])
        )


# ============================================================
# USER GROUP CHECK
# ============================================================

if not group_ready:

    st.info(
        "👈 Choose your program level and "
        "student type in the sidebar to start."
    )


# ============================================================
# CHAT INPUT
# ============================================================

question = st.chat_input(
    "Ask about admission, documents, fees, scholarships...",
    disabled=not group_ready
)


# ============================================================
# ANSWER
# ============================================================

if question:

    # Save user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    # Display user message
    with st.chat_message("user"):
        st.markdown(question)

    # Generate answer
    with st.chat_message("assistant"):

        with st.spinner(
            "Searching official university documents..."
        ):

            try:

                res = rag.answer(
                    question,
                    level=level,
                    student_type=student_type
                )

            except Exception as e:

                res = {
                    "answer": (
                        f"⚠️ Error: {e}\n\n"
                        "Please check that GROQ_API_KEY is "
                        "correctly configured in the .env file "
                        "and that the selected Groq model is available."
                    ),
                    "sources": []
                }

        # Display answer
        st.markdown(res["answer"])

        # Display sources
        show_sources(
            res.get("sources", [])
        )

    # Save assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": res["answer"],
            "sources": res.get("sources", [])
        }
    )