import argparse, textwrap, sys
from legal_search import Pipeline

def main():
    ag = argparse.ArgumentParser()
    ag.add_argument("-q", "--query", required=True, help="新聞段落或案情敘述")
    args = ag.parse_args()

    pipe = Pipeline(top_k=3)
    try:
        result = pipe.run(args.query)
        print("\n" + textwrap.fill(result, width=80))
    except Exception as e:
        sys.exit(f"⚠️  Error: {e}")

if __name__ == "__main__":
    main()

