import os
import sys


def main():
    if not os.path.exists("document.pdf"):
        print("RAG placeholder: arquivo document.pdf nao encontrado.")
        return 0

    print("RAG placeholder: ingest desativado (sem dependencias externas).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
