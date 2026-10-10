import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:1.5b"


def ask_llm(question):
    data = {
        "model": MODEL,
        "prompt": question,
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        json=data
    )

    if response.status_code != 200:
        raise Exception(f"Erreur Ollama : {response.text}")

    result = response.json()

    return result["response"]


if __name__ == "__main__":
    question = input("Votre question : ")

    answer = ask_llm(question)

    print("\nRéponse du LLM :")
    print(answer)