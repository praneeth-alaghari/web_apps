import os
from qdrant_client import QdrantClient

# Configuration
LOCAL_QDRANT_URL = "http://localhost:6333"
REMOTE_QDRANT_URL = os.environ.get("REMOTE_QDRANT_URL", "ENTER_YOUR_REMOTE_URL_HERE")
REMOTE_QDRANT_API_KEY = os.environ.get("REMOTE_QDRANT_API_KEY", "")

def migrate_collections():
    print(f"Connecting to local Qdrant at {LOCAL_QDRANT_URL}")
    local_client = QdrantClient(url=LOCAL_QDRANT_URL)
    
    print(f"Connecting to remote Qdrant at {REMOTE_QDRANT_URL}")
    if REMOTE_QDRANT_API_KEY:
        remote_client = QdrantClient(url=REMOTE_QDRANT_URL, api_key=REMOTE_QDRANT_API_KEY)
    else:
        remote_client = QdrantClient(url=REMOTE_QDRANT_URL)
        
    response = local_client.get_collections()
    collections = [collection.name for collection in response.collections]
    
    if not collections:
        print("No collections found in the local Qdrant database.")
        return

    for collection_name in collections:
        print(f"Migrating collection '{collection_name}'...")
        
        # 1. Recreate collection on remote
        collection_info = local_client.get_collection(collection_name)
        
        # NOTE: If your remote collection already exists and you want to overwrite,
        # you might want to call `remote_client.delete_collection(collection_name)` first.
        # Check if the collection already exists on the remote database
        remote_col_response = remote_client.get_collections()
        remote_collections = [c.name for c in remote_col_response.collections]
        
        if collection_name not in remote_collections:
            print(f"  Creating collection '{collection_name}' on remote...")
            # Ideally grab the exact vector parameters, but typically you know your size and distance.
            # Usually: size 1536 (OpenAI), distance Cosine.
            # Let's extract the configuration from the local collection.
            vectors_config = collection_info.config.params.vectors
            remote_client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config
            )
            print(f"  Collection created successfully.")
            
        else:
            print(f"  Collection '{collection_name}' already exists on remote. Appending points...")

        # 2. Iterate local points and push to remote
        # Using pagination with offset and limit to fetch all points.
        offset = None
        limit = 100
        total_migrated = 0
        
        while True:
            scroll_result, next_page_offset = local_client.scroll(
                collection_name=collection_name,
                offset=offset,
                limit=limit,
                with_payload=True,
                with_vectors=True
            )
            
            if not scroll_result:
                break
                
            from qdrant_client.http.models import PointStruct

            points_to_upsert = [
                PointStruct(
                    id=record.id,
                    vector=record.vector,
                    payload=record.payload
                )
                for record in scroll_result
            ]
                
            remote_client.upsert(
                collection_name=collection_name,
                points=points_to_upsert
            )
            
            total_migrated += len(scroll_result)
            print(f"    Migrated {total_migrated} points...")
            
            if next_page_offset is None:
                break
            offset = next_page_offset
            
        print(f"Finished migrating collection '{collection_name}'. Total points: {total_migrated}")

if __name__ == "__main__":
    if REMOTE_QDRANT_URL == "ENTER_YOUR_REMOTE_URL_HERE":
        print("Please configure REMOTE_QDRANT_URL before running this script.")
        exit(1)
        
    migrate_collections()
    print("Migration complete!")
