import ollama
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(autocommit=False, expire_on_commit=False, bind=engine)

# Use Ollama's async client for open-source embeddings, pointed at the configured Ollama host
embed_client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)


async def get_db_session():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _get_embedding(text_input: str) -> list[float]:
    """Generates an embedding vector using the configured Ollama embedding model."""
    response = await embed_client.embed(model=settings.OLLAMA_EMBED_MODEL, input=text_input)
    return response["embeddings"][0]


async def search_knowledge_base(query: str, limit: int = 3) -> str:
    """Retrieves relevant documents from pgvector using semantic similarity search."""
    embedding = await _get_embedding(query)
    vector_str = str(embedding)
    sql_query = text(""" 
        SELECT content
        FROM documents
        ORDER BY embedding <=> :vector_str::vector
        LIMIT :limit;        
    """)
    async with SessionLocal() as session:
        result = await session.execute(sql_query, {"vector_str": vector_str, "limit": limit})
        matched_rows = result.fetchall()
        contexts = [row[0] for row in matched_rows]
        if not contexts:
            return "No relevant information found in the database."
        return "\n\n".join(contexts)


async def seed_data(documents: list[str]):
    """
    Takes a list of strings (e.g. past Jira tickets or documentation) and 
    embeds them into the pgvector database so the rag_node can find them.
    """
    async with SessionLocal() as session:
        for doc in documents:
            # 1. Generate the embedding vector using open-source model
            embedding = await _get_embedding(doc)
            vector_str = str(embedding)
            
            # 2. Insert into the documents table
            sql_query = text("""
                INSERT INTO documents (content, embedding)
                VALUES (:content, :embedding::vector)
            """)
            await session.execute(sql_query, {"content": doc, "embedding": vector_str})
            
        await session.commit()
        print(f"Successfully seeded {len(documents)} documents into the knowledge base!")
