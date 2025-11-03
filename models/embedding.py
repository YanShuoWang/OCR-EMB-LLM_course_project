import os
import time
import pickle
import re
from tqdm import tqdm
import numpy as np
import faiss
from typing import List, Dict, Any
from volcenginesdkarkruntime import Ark

# Set Doubao API key
# Can be obtained from environment variables or set directly
api_key = os.environ.get("ARK_API_KEY") 

# Initialize Doubao client
client = Ark(api_key=api_key)

# Document directory and index directory
data_dir = 'index'
target_file = 'dataset/math_ocr_results.txt'  # Your target file

class DoubaoEmbeddings:
    """
    Doubao embedding model wrapper class
    """
    def __init__(self, model: str = "doubao-embedding-text-240715", batch_size: int = 4):
        """
        Initialize Doubao embedding model
        
        Args:
            model: Model ID
            batch_size: Batch size, Doubao recommends not exceeding 4
        """
        self.model = model
        self.batch_size = batch_size
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents
        
        Args:
            texts: List of texts
            
        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        
        # Process in batches, Doubao recommends no more than 4 per batch
        for i in tqdm(range(0, len(texts), self.batch_size), desc="Generating embeddings"):
            batch_texts = texts[i:i + self.batch_size]
            
            try:
                # Call Doubao embedding API
                resp = client.embeddings.create(
                    model=self.model,
                    input=batch_texts,
                    encoding_format="float"
                )
                
                # Extract embeddings and sort by input order
                batch_embeddings = []
                for item in sorted(resp.data, key=lambda x: x.index):
                    batch_embeddings.append(item.embedding)
                
                all_embeddings.extend(batch_embeddings)
                
                # Add delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing batch {i//self.batch_size + 1}: {e}")
                # Add zero vectors as placeholders for failed batches
                all_embeddings.extend([[] for _ in batch_texts])
                continue
        
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text
        
        Args:
            text: Query text
            
        Returns:
            Embedding vector
        """
        try:
            resp = client.embeddings.create(
                model=self.model,
                input=[text],
                encoding_format="float"
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"Error generating query embedding: {e}")
            return []

class TextSplitter:
    """
    Text splitter - split knowledge points by empty lines
    """
    def __init__(self, max_chunk_size: int = 1000):
        """
        Initialize text splitter
        
        Args:
            max_chunk_size: Maximum chunk size for handling very long knowledge points
        """
        self.max_chunk_size = max_chunk_size
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into knowledge point chunks by empty lines
        
        Args:
            text: Input text
            
        Returns:
            List of knowledge point chunks
        """
        # Use regex to split by empty lines (one or more newline characters)
        # \n\s*\n means newline followed by zero or more whitespace characters and then newline
        chunks = re.split(r'\n\s*\n', text)
        
        # Filter empty strings and chunks containing only whitespace
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        # Handle very long knowledge point chunks
        processed_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.max_chunk_size:
                processed_chunks.append(chunk)
            else:
                # For overly long knowledge points, split by sentences
                sub_chunks = self._split_long_chunk(chunk)
                processed_chunks.extend(sub_chunks)
        
        print(f"Split into {len(processed_chunks)} knowledge point chunks by empty lines")
        return processed_chunks
    
    def _split_long_chunk(self, text: str) -> List[str]:
        """
        Split overly long knowledge point chunks
        
        Args:
            text: Overly long text
            
        Returns:
            List of split text chunks
        """
        # Split by sentence boundaries
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            if char in ['。', '！', '？', '.', '!', '?', '\n']:
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # Add the last sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # Merge sentences into chunks, ensuring each chunk doesn't exceed max length
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.max_chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

class FAISSVectorStore:
    """
    FAISS vector store
    """
    def __init__(self, embedding_dim: int = 1024):  # Doubao embedding dimension is typically 1024
        self.embedding_dim = embedding_dim
        self.index = None
        self.texts = []
        self.metadatas = []
    
    def build_index(self, embeddings: List[List[float]], texts: List[str], metadatas: List[Dict] = None):
        """
        Build FAISS index
        
        Args:
            embeddings: List of embedding vectors
            texts: List of texts
            metadatas: List of metadata
        """
        if not embeddings or not texts:
            raise ValueError("Embeddings and texts cannot be empty")
        
        self.texts = texts
        self.metadatas = metadatas if metadatas else [{}] * len(texts)
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create FAISS index (using inner product, as Doubao returns normalized vectors)
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(embeddings_array)
    
    def similarity_search(self, query_embedding: List[float], k: int = 5) -> List[Dict]:
        """
        Similarity search
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of similar results
        """
        if self.index is None:
            raise ValueError("Index not built")
        
        # Convert to numpy array
        query_array = np.array([query_embedding]).astype('float32')
        
        # Search
        scores, indices = self.index.search(query_array, k)
        
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < len(self.texts):
                results.append({
                    'text': self.texts[idx],
                    'metadata': self.metadatas[idx],
                    'score': float(score),
                    'rank': i + 1
                })
        
        return results
    
    def save(self, filepath: str):
        """
        Save index and metadata
        """
        if self.index is None:
            raise ValueError("Index not built")
        
        # Save FAISS index
        faiss.write_index(self.index, f"{filepath}.faiss")
        
        # Save texts and metadata
        with open(f"{filepath}.pkl", 'wb') as f:
            pickle.dump({
                'texts': self.texts,
                'metadatas': self.metadatas,
                'embedding_dim': self.embedding_dim
            }, f)
    
    def load(self, filepath: str):
        """
        Load index and metadata
        """
        # Load FAISS index
        self.index = faiss.read_index(f"{filepath}.faiss")
        
        # Load texts and metadata
        with open(f"{filepath}.pkl", 'rb') as f:
            data = pickle.load(f)
            self.texts = data['texts']
            self.metadatas = data['metadatas']
            self.embedding_dim = data['embedding_dim']

def process_single_file(file_path: str, embedding_model: DoubaoEmbeddings, max_chunk_size: int = 1000):
    """
    Process a single file
    
    Args:
        file_path: File path
        embedding_model: Embedding model
        max_chunk_size: Maximum chunk size
        
    Returns:
        Processed data
    """
    # Read file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"Successfully read file: {file_path}")
        print(f"File length: {len(content)} characters")
    except Exception as e:
        print(f"Failed to read file: {e}")
        return None
    
    # Split text
    splitter = TextSplitter(max_chunk_size=max_chunk_size)
    chunks = splitter.split_text(content)
    
    if not chunks:
        print("No valid text chunks found")
        return None
    
    # Generate embeddings
    embeddings = embedding_model.embed_documents(chunks)
    
    # Filter failed embeddings
    valid_data = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding:  # Only keep successful embeddings
            valid_data.append({
                'text': chunk,
                'embedding': embedding,
                'metadata': {
                    'source': file_path,
                    'chunk_id': i,
                    'chunk_size': len(chunk)
                }
            })
    
    print(f"Successfully generated {len(valid_data)} embeddings")
    return valid_data

def main():
    """
    Main function
    """
    # Initialize embedding model
    embedding_model = DoubaoEmbeddings(batch_size=4)  # Doubao recommends batch size not exceeding 4
    
    # Process target file
    print(f"Starting to process file: {target_file}")
    processed_data = process_single_file(target_file, embedding_model, max_chunk_size=1000)
    
    if not processed_data:
        print("File processing failed")
        return
    
    # Extract texts, embeddings and metadata
    texts = [item['text'] for item in processed_data]
    embeddings = [item['embedding'] for item in processed_data]
    metadatas = [item['metadata'] for item in processed_data]
    
    # Build vector store
    vector_store = FAISSVectorStore(embedding_dim=len(embeddings[0]) if embeddings else 1024)
    vector_store.build_index(embeddings, texts, metadatas)
    
    # Save vector store
    index_path = os.path.join(data_dir, 'math_ocr_index')
    os.makedirs(data_dir, exist_ok=True)
    vector_store.save(index_path)
    print(f"Vector index saved to: {index_path}")
    
    # Test search functionality
    print("\nTesting search functionality...")
    test_query = "interval reproduction"  # Adjust test query based on your document content
    query_embedding = embedding_model.embed_query(test_query)
    
    if query_embedding:
        results = vector_store.similarity_search(query_embedding, k=3)
        print(f"Query: '{test_query}'")
        print("Top 3 most similar results:")
        for result in results:
            print(f"Score: {result['score']:.4f}")
            print(f"Text: {result['text'][:100]}...")
            print("-" * 80)
    else:
        print("Test query failed")

if __name__ == "__main__":
    main()