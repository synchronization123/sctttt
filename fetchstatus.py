import requests
import json

# DefectDojo API details
DEFECTDOJO_BASE_URL = "https://demo.defectdojo.org/api/v2"
DEFECTDOJO_TOKEN = "abc"

# JIRA API details
JIRA_URL = "https://jira.demo.almworks.com/rest/api/2/search"
JIRA_TOKEN = "abc"

# Common headers
DEFECTDOJO_HEADERS = {
    "Authorization": f"Token {DEFECTDOJO_TOKEN}",
    "Content-Type": "application/json"
}

JIRA_HEADERS = {
    "Authorization": f"Bearer {JIRA_TOKEN}",
    "Content-Type": "application/json"
}

def fetch_all_tests():
    """Fetch all tests with 'crm_jira' tag from DefectDojo with pagination."""
    tests = []
    url = f"{DEFECTDOJO_BASE_URL}/tests/?tags=crm_jira&page_size=100"
    
    while url:
        try:
            response = requests.get(url, headers=DEFECTDOJO_HEADERS)
            response.raise_for_status()
            data = response.json()
            tests.extend(data.get("results", []))
            url = data.get("next")  # Fetch next page if available
        except requests.RequestException as e:
            print(f"Error fetching tests: {e}")
            break

    return tests

def fetch_jira_status(issue_keys):
    """Fetch statuses of JIRA issues in batches of 50."""
    jira_statuses = {}

    for i in range(0, len(issue_keys), 50):  # Process in chunks of 50
        chunk = issue_keys[i:i+50]
        jql_query = f"key in ({','.join(chunk)})"
        params = {
            "jql": jql_query,
            "fields": "key,status",
            "maxResults": 50
        }

        try:
            response = requests.get(JIRA_URL, headers=JIRA_HEADERS, params=params)
            response.raise_for_status()
            jira_statuses.update({
                issue["key"]: issue["fields"]["status"]["name"]
                for issue in response.json().get("issues", [])
            })
        except requests.RequestException as e:
            print(f"Error fetching JIRA statuses: {e}")

    return jira_statuses

def update_test(test_id, new_status):
    """Update the 'build_id' field in DefectDojo test with new JIRA status."""
    url = f"{DEFECTDOJO_BASE_URL}/tests/{test_id}/"
    test_data = {
        "build_id": new_status  # Update JIRA status in build_id
    }

    try:
        response = requests.patch(url, headers=DEFECTDOJO_HEADERS, json=test_data)
        response.raise_for_status()
        print(f"✅ Updated test {test_id} with status: {new_status}")
    except requests.RequestException as e:
        print(f"❌ Error updating test {test_id}: {e}")

def main():
    tests = fetch_all_tests()

    if not tests:
        print("No tests found.")
        return

    jira_issues = {}  # {issue_key: [(test_id, defectdojo_status)]}

    for test in tests:
        issue_key = test["title"]
        defectdojo_status = test["build_id"]  # Fetch the existing status in DefectDojo

        # Skip updates for issues already in "Open" or "To Do"
        if defectdojo_status not in ["Closed", "To Do"]:
            if issue_key not in jira_issues:
                jira_issues[issue_key] = []
            jira_issues[issue_key].append((test["id"], defectdojo_status))  # Store multiple test IDs for same key

    if not jira_issues:
        print("No tests require updates.")
        return

    # Fetch JIRA statuses for selected issue keys
    jira_statuses = fetch_jira_status(list(jira_issues.keys()))

    for issue_key, test_list in jira_issues.items():
        if issue_key in jira_statuses:
            new_status = jira_statuses[issue_key]
            for test_id, defectdojo_status in test_list:
                if new_status != defectdojo_status:  # Update only if status has changed
                    update_test(test_id, new_status)
                else:
                    print(f"🔹 No change for test {test_id} (status remains: {new_status})")

if __name__ == "__main__":
    main()
