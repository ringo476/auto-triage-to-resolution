import os

import openai
from app.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import async_sessionmaker

engine=create_async_engine(settings.DATABASE_URL,echo=False)
Sessionlocal=async_sessionmaker(autocommit=False,expire_on_commit=False,bind=engine)
client=openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

async def get_db_session():
    async with Sessionlocal() as session:
        try:
            yield session
            await session.commit()        
        except Exception:
            await session.rollback()
            raise

async def search_knowledge_base(query: str, limit: int = 3) -> str:
    response=client.embeddings.create(text=query,model="text-embedding-3-small")
    acquired_resp=response.data[0].embedding
    vector_str=str(acquired_resp)
    sql_query=text(""" 
        SELECT content
        FROM documents
        ORDER BY embedding <=>: vector_str::vector
        LIMIT :limit;        
    """)
    async with Sessionlocal() as session:
        result=await session.execute(sql_query,{"vector_str":vector_str, "limit":limit})
        matched_rows=result.fetchall()
        contexts=[row[0] for row in matched_rows]
        if not contexts:
            return "No relevant information found in the database."
        return "\n\n".join(contexts)
async def seed_dummy_data():
    pass
