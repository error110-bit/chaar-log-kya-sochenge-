import requests
from bs4 import BeautifulSoup

base_url = "https://internshala.com"
url = "https://internshala.com/internships/"

headers = {"User-Agent": "Mozilla/5.0"}

res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

links = soup.find_all("a")

internship_links = []

# Step 1: collect internship links
for link in links:
    href = link.get("href")
    text = link.get_text(strip=True)

    if href and "/internship/detail/" in href:
        full_link = base_url + href
        internship_links.append((text, full_link))


# Step 2: visit each internship page
for title, link in internship_links[:5]:  # limit to 5 for now
    print("\n🔗 Opening:", link)

    page = requests.get(link, headers=headers)
    soup2 = BeautifulSoup(page.text, "html.parser")

    # Try extracting company name
    company = soup2.find("a", class_="link_display_like_text")

    # Try extracting stipend
    stipend = soup2.find("span", class_="stipend")

    print("Title:", title)
    print("Company:", company.text.strip() if company else "N/A")
    print("Stipend:", stipend.text.strip() if stipend else "N/A")
    print("Link:", link)
    print("=" * 50)