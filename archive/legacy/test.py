import requests


BASE_URL = "http://127.0.0.1:5000"


def main():
    health = requests.get(f"{BASE_URL}/health", timeout=15)
    health.raise_for_status()
    print("Health:", health.json())

    params = {
        "keyword": "software",
        "page": 1,
        "page_size": 5,
        "sort_by": "title",
        "sort_order": "asc",
    }
    internships = requests.get(f"{BASE_URL}/internships", params=params, timeout=20)
    internships.raise_for_status()
    payload = internships.json()

    print("\nInternship query meta:")
    print(payload.get("meta", {}))

    print("\nTop records:")
    for idx, item in enumerate(payload.get("data", []), start=1):
        print(f"{idx}. {item.get('title')} | {item.get('company')} | {item.get('apply_link')}")


if __name__ == "__main__":
    main()