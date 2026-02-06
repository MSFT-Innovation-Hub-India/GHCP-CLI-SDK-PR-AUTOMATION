#!/usr/bin/env python3
"""
Deploy Vector Store Script

This script creates a vector store in Azure OpenAI and uploads all markdown files
from the knowledge/ folder. It updates the .env file with the vector store ID.

Usage:
    python scripts/deploy-vector-store.py

Requirements:
    - Azure CLI authenticated (az login)
    - openai and azure-identity packages installed
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv, set_key

# Configuration
KNOWLEDGE_FOLDER = PROJECT_ROOT / "knowledge"
ENV_FILE = PROJECT_ROOT / "agent" / ".env"
VECTOR_STORE_NAME = "fleet-compliance-knowledge"


def get_azure_openai_client():
    """Create Azure OpenAI client with Azure AD authentication."""
    load_dotenv(ENV_FILE)
    
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT not set in .env file")
    
    # Remove /openai/v1/ suffix if present
    endpoint = endpoint.replace("/openai/v1/", "").replace("/openai/v1", "")
    
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default"
    )
    
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview"
    )


def get_existing_vector_store(client, name: str):
    """Check if a vector store with the given name already exists."""
    vector_stores = client.vector_stores.list()
    for vs in vector_stores.data:
        if vs.name == name:
            return vs
    return None


def create_vector_store(client, name: str):
    """Create a new vector store."""
    print(f"Creating vector store: {name}")
    vs = client.vector_stores.create(name=name)
    print(f"  Created: {vs.id}")
    return vs


def upload_files_to_vector_store(client, vector_store_id: str, folder: Path):
    """Upload all markdown files from the folder to the vector store."""
    md_files = list(folder.glob("*.md"))
    
    if not md_files:
        print(f"No markdown files found in {folder}")
        return
    
    print(f"\nUploading {len(md_files)} files to vector store...")
    
    for md_file in md_files:
        print(f"  Uploading: {md_file.name}")
        
        # Upload file to OpenAI
        with open(md_file, "rb") as f:
            file_obj = client.files.create(file=f, purpose="assistants")
        
        # Attach to vector store
        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_obj.id
        )
        print(f"    ✓ Uploaded: {file_obj.id}")
    
    print("\nWaiting for files to be processed...")
    
    # Poll until all files are processed
    import time
    while True:
        vs = client.vector_stores.retrieve(vector_store_id)
        counts = vs.file_counts
        
        if counts.in_progress == 0:
            print(f"  Completed: {counts.completed}, Failed: {counts.failed}")
            break
        
        print(f"  In progress: {counts.in_progress}, Completed: {counts.completed}")
        time.sleep(2)


def update_env_file(vector_store_id: str):
    """Update the .env file with the vector store ID."""
    print(f"\nUpdating {ENV_FILE} with vector store ID...")
    set_key(str(ENV_FILE), "AZURE_OPENAI_VECTOR_STORE_ID", vector_store_id)
    print(f"  ✓ AZURE_OPENAI_VECTOR_STORE_ID={vector_store_id}")


def main():
    print("=" * 60)
    print("  Azure OpenAI Vector Store Deployment")
    print("=" * 60)
    print()
    
    # Get client
    print("Connecting to Azure OpenAI...")
    client = get_azure_openai_client()
    print("  ✓ Connected")
    
    # Check for existing vector store
    print(f"\nChecking for existing vector store: {VECTOR_STORE_NAME}")
    existing_vs = get_existing_vector_store(client, VECTOR_STORE_NAME)
    
    if existing_vs:
        print(f"  Found existing: {existing_vs.id}")
        print(f"  Status: {existing_vs.status}")
        print(f"  Files: {existing_vs.file_counts.total} total, {existing_vs.file_counts.completed} completed")
        
        response = input("\nDelete and recreate? (y/N): ").strip().lower()
        if response == "y":
            print(f"\nDeleting vector store: {existing_vs.id}")
            client.vector_stores.delete(existing_vs.id)
            print("  ✓ Deleted")
            vector_store = create_vector_store(client, VECTOR_STORE_NAME)
            upload_files_to_vector_store(client, vector_store.id, KNOWLEDGE_FOLDER)
            update_env_file(vector_store.id)
        else:
            print("\nKeeping existing vector store.")
            update_env_file(existing_vs.id)
    else:
        print("  Not found, creating new...")
        vector_store = create_vector_store(client, VECTOR_STORE_NAME)
        upload_files_to_vector_store(client, vector_store.id, KNOWLEDGE_FOLDER)
        update_env_file(vector_store.id)
    
    print("\n" + "=" * 60)
    print("  Deployment Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
