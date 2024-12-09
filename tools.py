import math 
import httpx

def wikipedia(q):
    return httpx.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query",
        "list": "search",
        "srsearch": q,
        "format": "json"
    }).json()["query"]["search"][0]["snippet"]

def calculate(operation: str) -> float:
    return eval(operation)

# print("Testing 'calculate':")
# print("4 * 7 / 3 =", calculate("4 * 7 / 3"))

# print("\nTesting 'wikipedia':")
# print("Wikipedia result for 'Earth mass':")
# print(wikipedia("Earth mass"))
