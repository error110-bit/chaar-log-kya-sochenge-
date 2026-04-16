from selenium import webdriver
from selenium.webdriver.common.by import By
import requests
from bs4 import BeautifulSoup
import time

# -----------------------------
# PART 1: INTERNSHALA SCRAPER
# -----------------------------

def scrape_internshala():
    print("\n🔍 Scraping Internshala...\n")

    base_url = "https://internshala.com"
    url = "https://internshala.com/internships/"

    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    links = soup.find_all("a")

    results = []

    for link in links:
        text = link.get_text(strip=True)
        href = link.get("href")

        if href and "/internship/detail/" in href and len(text) > 5:
            results.append({
                "company": "Unknown",
                "title": text,
                "source": "Internshala",
                "link": base_url + href
            })

    return results[:10]  # limit


# -----------------------------
# PART 2: GOLDMAN SCRAPER
# -----------------------------

def scrape_goldman():
    print("\n🔍 Scraping Goldman Sachs...\n")

    driver = webdriver.Chrome()
    driver.get("https://www.goldmansachs.com/careers/students/")
    time.sleep(8)

    links = driver.find_elements(By.TAG_NAME, "a")

    useful_links = []

    for link in links:
        try:
            text = link.text.strip()
            href = link.get_attribute("href")

            if text and href:
                if any(word in text.lower() for word in ["student", "intern", "program", "apply"]):
                    useful_links.append((text, href))
        except:
            continue

    keywords = ["intern", "program", "analyst", "student"]
    results = []

    for text, link in useful_links[:5]:
        try:
            driver.get(link)
            time.sleep(6)

            elements = driver.find_elements(By.TAG_NAME, "p")

            for el in elements:
                content = el.text.strip()

                if content and any(word in content.lower() for word in keywords):
                    results.append({
                        "company": "Goldman Sachs",
                        "title": content[:100],
                        "source": "Company Website",
                        "link": link
                    })
        except:
            continue

    driver.quit()
    return results


# -----------------------------
# PART 3: CLEAN DATA
# -----------------------------

def clean_data(data):
    unique = []
    seen = set()

    for item in data:
        key = item["title"]

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


# -----------------------------
# MAIN PROGRAM
# -----------------------------

intern_data = scrape_internshala()
goldman_data = scrape_goldman()

all_data = intern_data + goldman_data
cleaned = clean_data(all_data)

# -----------------------------
# FINAL OUTPUT
# -----------------------------

print("\n🚀 OPPORTUNITY RADAR\n")

for item in cleaned:
    print("🏢 Company:", item["company"])
    print("🎯 Title:", item["title"])
    print("📌 Source:", item["source"])
    print("🔗 Link:", item["link"])
    print("⚡ Status: Active Opportunity Detected")
    print("-" * 60)

