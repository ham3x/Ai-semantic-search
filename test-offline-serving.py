#!/usr/bin/env python3
import argparse
import sys
import json
import urllib.request
import urllib.error

def test_gateway_models(gateway_url):
    print(f"🔍 Testing model listing from gateway: {gateway_url}/v1/models")
    req = urllib.request.Request(f"{gateway_url}/v1/models")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("id") for m in data.get("data", [])]
            print(f"✅ Success! Available Gateway Models: {models}")
            return models
    except Exception as e:
        print(f"❌ Failed to query /v1/models: {e}")
        return []

def test_chat_completion(gateway_url, model_name="llama-3-8b"):
    print(f"🤖 Testing LLM chat completion for model '{model_name}'...")
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant operating in an offline environment."},
            {"role": "user", "content": "Confirm you are online and working properly."}
        ],
        "temperature": 0.2,
        "max_tokens": 100
    }
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f"{gateway_url}/v1/chat/completions",
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode())
            answer = res["choices"][0]["message"]["content"]
            print(f"✅ Chat Completion Response:\n{answer.strip()}\n")
    except Exception as e:
        print(f"❌ Chat completion failed: {e}")

def test_embedding(gateway_url, model_name="text-embedding-bge-large"):
    print(f"🔤 Testing Text Embedding generation for model '{model_name}'...")
    payload = {
        "model": model_name,
        "input": ["Air-gapped semantic search test sentence."]
    }
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f"{gateway_url}/v1/embeddings",
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode())
            embedding_dim = len(res["data"][0]["embedding"])
            print(f"✅ Success! Embedding generated with dimension vector size: {embedding_dim}")
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Test Air-Gapped AI Gateway Deployment")
    parser.add_argument("--gateway", default="http://localhost:4000", help="LiteLLM Gateway Base URL")
    args = parser.parse_args()

    print("=========================================================")
    print("🧪 Air-Gapped Model Gateway Test Suite")
    print("=========================================================")
    
    models = test_gateway_models(args.gateway)
    if models:
        test_chat_completion(args.gateway, model_name=models[0])
        test_embedding(args.gateway)
    else:
        print("⚠️ Gateway did not return active models. Check Kubernetes pod logs.")

if __name__ == "__main__":
    main()
