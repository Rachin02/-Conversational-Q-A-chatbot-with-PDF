import os
import streamlit as st
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI , OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_classic.chains import create_retrieval_chain, create_history_aware_retriever
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

from dotenv import load_dotenv
load_dotenv()


# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]
# os.environ["LANGCHAIN_PROJECT"] = "Conversation with uploaded PDF"        # currently tracing is not working, I will work on it later.
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"



def select_model(have_api):

    llm = None
    if have_api == "YES":
        api_key = st.sidebar.text_input("Enter you API key: ", placeholder="Enter your OpenAI/ Gemini/ Groq API key", type = "password")

        if api_key[:2] =="sk":
            llm = ChatOpenAI(model = "gpt-5-nano", api_key= api_key)

        elif api_key[:2] == "gs":
            llm = ChatGroq(model = "llama-3.1-8b-instant",api_key = api_key)
    
        elif api_key[:2] == "AI":
            llm = ChatGoogleGenerativeAI(model = "gemini-3-flash-preview", api_key = api_key)

    else:
        model_name = st.sidebar.selectbox("Select the model",["gpt-5-nano", "gpt-4o-mini"])
        llm = ChatOpenAI(model = model_name)

    return llm

## ---------------------------------------------------------------------------------------------------------------------------

st.title("Conversational RAG with PDF upload and chat history")
st.write("Upload PDF and chat with their content")

have_api = st.sidebar.selectbox("Do you have your API key? ", options=["NO","YES"] )

model = select_model(have_api)
embedding = OpenAIEmbeddings()

session_id = st.sidebar.text_input("Session ID [Optional]", value = "default")

st.sidebar.markdown(
        """
        <div style="
            background-color: #8dc6ff;
            color: black;
            padding: 7px;
            border-radius: 10px;
            text-align: center;
            font-size: 13px;
            font-weight: 200;
        ">
            Developed by Rachin
        </div>
        """,
        unsafe_allow_html=True
    )
         


if 'store' not in st.session_state:
    st.session_state.store = {}

uploaded_files = st.file_uploader("Choose a PDF file", type = "pdf", accept_multiple_files= True)


if uploaded_files:
    documents = []

    for uploaded_file in uploaded_files:
        tempPdf = "temp.pdf"
        with open(tempPdf, "wb") as file:
            file.write(uploaded_file.getvalue())
            file_name = uploaded_file.name

        loader = PyPDFLoader(tempPdf)
        docs = loader.load()
        documents.extend(docs)


    # st.write(documents)


    # split and create embedding for the documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 5000, chunk_overlap = 500)
    final_docs = text_splitter.split_documents(documents)
    vectorStore = Chroma.from_documents(documents=final_docs, embedding= embedding)
    retriever = vectorStore.as_retriever()


   
    contextualize_q_system_prompt = (
        """
        Given a chat history and the latest user question, which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do not answer the question, just reformulate it if needed and otherwise return it as is.

        """
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("user","{input}")
        ]
    )

    history_aware_retriever = create_history_aware_retriever(model, retriever, contextualize_q_prompt)


    system_prompt = (
        """ 
        You are an assistant for question answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, say that you don't know. Use seven sentences maximum and keep the answer concise.\n\n 
        {context}
        """
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("user","{input}")
        ]
    )

    question_answer_chain = create_stuff_documents_chain(model , prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)


    def get_session_history(session_id:str) -> BaseChatMessageHistory:
        if session_id not in st.session_state.store:
            st.session_state.store[session_id] = ChatMessageHistory()
        return st.session_state.store[session_id]
    
    conversation_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key = "input",
        history_messages_key = "chat_history",
        output_messages_key = "answer"
    )

    user_text = st.text_input("Enter question related to your uploaded pdf")

    if st.button("Ask"):
          session_history = get_session_history(session_id)
          response = conversation_rag_chain.invoke(
                {"input": user_text},
                config = {
                            "configurable":{"session_id": session_id} #constructs a key like abc123 in store
                }
          )

          st.success(f"AI Response: {response['answer']}")
          st.write(":orange[Session state: ]")
          st.write(st.session_state.store)
          st.write(":orange[Chat History: ]")
          st.write(session_history.messages)

   

   
# streamlit run app.py