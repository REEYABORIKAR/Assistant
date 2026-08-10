from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

def chunk_document(extracted_data: list[dict], document_id: str, project_id: str, file_name: str) -> list[dict]:
    """
    Takes extracted data and splits it into chunks using LangChain's RecursiveCharacterTextSplitter.
    Injects required metadata into each chunk.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    
    chunks = []
    chunk_index = 0
    
    for section in extracted_data:
        text = section["text"]
        meta = section["metadata"]
        
        split_texts = text_splitter.split_text(text)
        
        for chunk_text in split_texts:
            chunk = {
                "text": chunk_text,
                "metadata": {
                    "document_id": document_id,
                    "project_id": project_id,
                    "file_name": file_name,
                    "chunk_index": chunk_index,
                }
            }
            # Add source-specific metadata
            if "page_number" in meta:
                chunk["metadata"]["page_number"] = meta["page_number"]
            if "sheet_name" in meta:
                chunk["metadata"]["sheet_name"] = meta["sheet_name"]
            if "row_index" in meta:
                chunk["metadata"]["row_index"] = meta["row_index"]
            if "paragraph_index" in meta:
                chunk["metadata"]["paragraph_index"] = meta["paragraph_index"]
            if "table_index" in meta:
                chunk["metadata"]["table_index"] = meta["table_index"]
                
            chunks.append(chunk)
            chunk_index += 1
            
    return chunks
