from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mistralai import Mistral
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv, find_dotenv
import os
load_dotenv(find_dotenv())

sbert_model = SentenceTransformer('all-MiniLM-L6-v2')

CHROMA_PATH = "chromadb"
# 2. Create Chroma collection
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(name="support_client_docs")

loader = DirectoryLoader(
    path="./knowledge_base",
    glob="**/*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"}
)

documents = loader.load()
print("Loaded docs:", len(documents))

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
        ("####", "h4"),
        ("***", "h5"),
    ]
)

header_docs = []
for doc in documents:
    header_docs.extend(
        header_splitter.split_text(doc.page_content)
    )

print("Header chunks:", len(header_docs))


size_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=50
)

final_docs = size_splitter.split_documents(header_docs)

print("Final chunks:", len(final_docs))


BATCH_SIZE = 32  # or smaller if needed
for i in range(0, len(final_docs), BATCH_SIZE):
    batch_docs = final_docs[i:i + BATCH_SIZE]
    batch_texts = [doc.page_content for doc in batch_docs]

    batch_embeddings = sbert_model.encode(batch_texts, convert_to_numpy=True)

    collection.add(
        documents=batch_texts,
        ids=[f"doc_{i + j}" for j in range(len(batch_docs))],
        embeddings=batch_embeddings.tolist()
    )


print("Data added to ChromaDB collection.")

collection = client.get_collection("support_client_docs")
print("Vector count:", collection.count())
